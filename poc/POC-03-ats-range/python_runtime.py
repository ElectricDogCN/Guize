"""Bind the approved plain-HTTP runtime bytes; this is not a memory-capacity proof."""
from __future__ import annotations
import _hashlib
import _socket
import _ssl
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import platform
import socket
import socketserver
import ssl
import stat
import struct
import sys
from datetime import datetime,timezone

PROFILE_ID='cpython31215-linux-x86_64-plain-http-fixed-image-v1'
BASE_IMAGE='sha256:df18428df8a0f9189c84e7424d214b4c50092af1f9dca5842a00c41c39bda316'

def file_identity(path):
    path=Path(path).resolve(strict=True)
    digest=hashlib.sha256()
    with path.open('rb',buffering=0) as stream,memoryview(bytearray(65536)) as backing:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):raise ValueError('runtime component is not regular')
        if backing.obj.__alloc__()!=65537:raise ValueError('runtime hash slot capacity mismatch')
        while True:
            count=stream.readinto(backing)
            if type(count) is not int or not 0<=count<=len(backing):raise ValueError('runtime component read count')
            if not count:break
            with backing[:count] as block:digest.update(block)
        after=os.fstat(stream.fileno())
    if any(getattr(before,key)!=getattr(after,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
        raise ValueError('runtime component changed while hashing')
    return dict(path=str(path),bytes=before.st_size,sha256=digest.hexdigest(),device=before.st_dev,inode=before.st_ino)

def capture_runtime():
    if sys.platform!='linux' or platform.python_implementation()!='CPython' or os.geteuid()==0:
        raise ValueError('ordinary Linux CPython runtime required')
    if sys.gettrace() is not None or sys.getprofile() is not None:raise ValueError('Python tracing/profiling override')
    for name in ('LD_PRELOAD','LD_AUDIT','OPENSSL_CONF','OPENSSL_MODULES'):
        if os.environ.get(name):raise ValueError('unsupported runtime override: '+name)
    if hashlib.sha256 is not _hashlib.openssl_sha256:raise ValueError('unqualified SHA256 implementation')
    hasher=hashlib.sha256()
    identity=dict(version=sys.version,implementation=platform.python_implementation(),cacheTag=sys.implementation.cache_tag,
        machine=platform.machine(),pointerBytes=struct.calcsize('P'),byteOrder=sys.byteorder,
        openssl=ssl.OPENSSL_VERSION,ioDefaultBufferBytes=io.DEFAULT_BUFFER_SIZE,
        hashBackend=type(hasher).__module__+'.'+type(hasher).__name__,hashName=hasher.name,
        hashBlockBytes=hasher.block_size,hashDigestBytes=hasher.digest_size)
    if (not identity['version'].startswith('3.12.15 ') or identity['machine']!='x86_64'
            or identity['pointerBytes']!=8 or identity['byteOrder']!='little'
            or identity['openssl']!='OpenSSL 3.5.7 9 Jun 2026' or identity['ioDefaultBufferBytes']!=8192
            or identity['hashBackend']!='_hashlib.HASH' or identity['hashName']!='sha256'
            or identity['hashBlockBytes']!=64 or identity['hashDigestBytes']!=32):
        raise ValueError('runtime does not match the fixed source-derived profile')
    maps_path=Path('/proc/self/maps')
    with maps_path.open('rb') as stream:raw=stream.read(1048577)
    if len(raw)>1048576:raise ValueError('runtime mapping metadata quota')
    mappings=[]
    for line in raw.decode().splitlines():
        parts=line.split(maxsplit=5)
        if len(parts)!=6 or not parts[5].startswith('/'):continue
        major,minor=parts[3].split(':')
        mappings.append(dict(path=parts[5],permissions=parts[1],device=os.makedev(int(major,16),int(minor,16)),inode=int(parts[4])))
    files={};native=set()
    for label,module in [('http.client',http.client),('socket',socket),('socketserver',socketserver),
                         ('_socket',_socket),('_hashlib',_hashlib),('_ssl',_ssl)]:
        files[label]=file_identity(module.__file__)
        if label.startswith('_'):native.add(label)
        cached=getattr(module,'__cached__',None)
        if cached is not None and Path(cached).is_file():files[label+'.pyc']=file_identity(cached)
    files['interpreter']=file_identity(sys.executable);native.add('interpreter')
    for name in ('libpython3.12.so.1.0','libcrypto.so.3','libc.so.6'):
        candidates={row['path'] for row in mappings if Path(row['path']).name==name and 'x' in row['permissions']}
        if len(candidates)!=1:raise ValueError('one mapped runtime dependency required: '+name)
        files[name]=file_identity(candidates.pop());native.add(name)
    for label in native:
        file=files[label]
        exact=[row for row in mappings if row['path']==file['path'] and 'x' in row['permissions']
               and (row['device'],row['inode'])==(file['device'],file['inode'])]
        if not exact:raise ValueError('runtime file is not the actual mapped executable inode: '+label)
        if any(row['path']==file['path']+' (deleted)' for row in mappings):raise ValueError('deleted runtime mapping: '+label)
    return dict(identity=identity,files=files,mapsRaw=raw.decode(),mapsSha256=hashlib.sha256(raw).hexdigest(),
                actualMappedNativeComponents=sorted(native),uid=os.getuid(),pid=os.getpid(),
                processStartTicks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))

def pinned_profile(observed):
    return dict(schemaVersion=1,profileId=PROFILE_ID,baseImage=BASE_IMAGE,identity=observed['identity'],
        files={name:{key:row[key] for key in ('path','bytes','sha256')} for name,row in observed['files'].items()})

def verify_runtime(profile):
    if (set(profile)!={'schemaVersion','profileId','baseImage','identity','files'}
            or profile['schemaVersion']!=1 or profile['profileId']!=PROFILE_ID or profile['baseImage']!=BASE_IMAGE):
        raise ValueError('unknown runtime binding profile')
    actual=capture_runtime()
    if pinned_profile(actual)!=profile:raise ValueError('actual runtime bytes differ from the fixed profile')
    return dict(kind='ACTUAL_COMPONENT_BYTE_BINDING_NOT_AGGREGATE_MEMORY',profileId=PROFILE_ID,
        baseImageReference=BASE_IMAGE,identity=actual['identity'],files=actual['files'],
        actualMappedNativeComponents=actual['actualMappedNativeComponents'],mapsSha256=actual['mapsSha256'],
        mapsRaw=actual['mapsRaw'],uid=actual['uid'],pid=actual['pid'],componentBytesBound=True,
        processStartTicks=actual['processStartTicks'],observedAt=datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z'),
        aggregateCapacityProofComplete=False,sourceQualified=False,formalPocAccepted=False)

def verify_runtime_file(path):
    path=Path(path)
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536:raise ValueError('runtime profile byte quota')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate runtime profile member')
            result[key]=value
        return result
    result=verify_runtime(json.loads(raw,object_pairs_hook=unique))
    result['profileSha256']=hashlib.sha256(raw).hexdigest()
    return result

def write_binding(path,result):
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

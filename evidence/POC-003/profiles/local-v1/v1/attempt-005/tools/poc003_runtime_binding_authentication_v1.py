"""Authenticate retained runtime observations only; never execute runtime probes."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os

EXPECTED_NATIVE=sorted(('_ctypes','_hashlib','_socket','_ssl','interpreter','libc.so.6','libcrypto.so.3','libffi.so.8','libpython3.12.so.1.0'))
def need(ok,msg):
 if not ok:raise ValueError(msg)
def utc(value):return datetime.fromisoformat(value.replace('Z','+00:00'))
def validate_binding(raw,profile_raw,*,expected_pid,expected_birth,started_at,finished_at,pointer=None):
 need(isinstance(raw,bytes) and 0<len(raw)<=1048576,'bounded retained runtime binding required')
 report=json.loads(raw);profile=json.loads(profile_raw)
 if pointer is not None:
  need(pointer['sha256']==hashlib.sha256(raw).hexdigest(),'runtime binding pointer hash mismatch')
  need(pointer['pid']==expected_pid and pointer['processStartTicks']==expected_birth,'runtime pointer process birth mismatch')
 need(report['kind']=='ACTUAL_COMPONENT_BYTE_BINDING_NOT_AGGREGATE_MEMORY' and report['componentBytesBound'] is True,'actual component binding required')
 need(report['profileSha256']==hashlib.sha256(profile_raw).hexdigest(),'fixed runtime profile hash mismatch')
 need((report['pid'],report['processStartTicks'],report['uid'])==(expected_pid,expected_birth,1000),'runtime process birth mismatch')
 need(utc(started_at)<=utc(report['observedAt'])<=utc(finished_at),'runtime binding outside actual run window')
 projected=dict(schemaVersion=2,profileId=report['profileId'],baseImage=report['baseImageReference'],identity=report['identity'],crypto=report['crypto'],files={name:{key:row[key] for key in ('path','bytes','sha256')} for name,row in report['files'].items()})
 need(projected==profile,'observed runtime/crypto route differs from immutable fixed profile')
 need(report['actualMappedNativeComponents']==EXPECTED_NATIVE,'all nine mapped native components required')
 maps=report['mapsRaw'];need(hashlib.sha256(maps.encode()).hexdigest()==report['mapsSha256'],'actual mappings hash mismatch')
 mappings=[]
 for line in maps.splitlines():
  fields=line.split(maxsplit=5)
  if len(fields)==6:
   major,minor=fields[3].split(':');mappings.append(dict(path=fields[5],permissions=fields[1],device=os.makedev(int(major,16),int(minor,16)),inode=int(fields[4])))
 for label in EXPECTED_NATIVE:
  file=report['files'][label]
  need(type(file['device']) is int and type(file['inode']) is int and file['inode']>0,'actual mapped inode required')
  need(any(row['path']==file['path'] and 'x' in row['permissions'] and (row['device'],row['inode'])==(file['device'],file['inode']) for row in mappings),'actual mapped runtime inode differs '+label)
  need(not any(row['path']==file['path']+' (deleted)' for row in mappings),'deleted runtime mapping ineligible')
 return dict(profileSha256=report['profileSha256'],bindingSha256=hashlib.sha256(raw).hexdigest(),pid=report['pid'],processStartTicks=report['processStartTicks'],observedAt=report['observedAt'],mappedNativeComponents=EXPECTED_NATIVE,identityAndCryptoRouteMatch=True)

def authenticate_runtime_bindings(data,collection,closed,before,profile_raw,started_at,finished_at):
 data=Path(data);W=data/'work';C=data/'original-matrix'
 stat_text=before['rawObservations']['stat']['text'];need(int(stat_text.split(' ',1)[0])==1,'before process must be PID1')
 birth=int(stat_text.rsplit(')',1)[1].split()[19]);need(birth>0,'actual before process birth required')
 observations={};paths=[]
 for role,path,pointer in [('prepare',W/'python-runtime-binding.prepare.json',None),('controller',W/'python-runtime-binding.controller.json',closed['pythonRuntimeBinding']),('collector',C/'python-runtime-binding.collector.json',collection['pythonRuntimeBinding'])]:
  if pointer is not None:need(pointer['ref']==path.name,'runtime binding reference differs from actual producer')
  need(path.is_file() and not path.is_symlink(),'retained regular runtime binding required')
  observations[role]=validate_binding(path.read_bytes(),profile_raw,expected_pid=1,expected_birth=birth,started_at=started_at,finished_at=finished_at,pointer=pointer);paths.append(path)
 return dict(processBirth=birth,observations=observations,scope='Actual fixed interpreter/module/native maps and crypto-route binding; no extra HASH introspection or independent aggregate-capacity claim'),paths

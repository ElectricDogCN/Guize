"""Public native initialization metadata, before any media input is opened."""
import ctypes
import hashlib
import os
from pathlib import Path
import re

OVERRIDE_ENV=('LD_PRELOAD','LD_AUDIT','LD_LIBRARY_PATH','LD_HWCAP_MASK','GLIBC_TUNABLES',
              'OPENSSL_CONF','OPENSSL_CONF_INCLUDE','OPENSSL_MODULES','OPENSSL_ENGINES','OPENSSL_ia32cap')


def validate_environment():
    for name in OVERRIDE_ENV:
        if os.environ.get(name):raise ValueError('unsupported runtime override: '+name)


class _Dispatch(ctypes.Structure):
    _fields_=[('function_id',ctypes.c_int),('function',ctypes.c_void_p)]


class _Algorithm(ctypes.Structure):
    _fields_=[('names',ctypes.c_char_p),('properties',ctypes.c_char_p),
              ('implementation',ctypes.POINTER(_Dispatch)),('description',ctypes.c_char_p)]


class _DlInfo(ctypes.Structure):
    _fields_=[('name',ctypes.c_char_p),('base',ctypes.c_void_p),
              ('symbol',ctypes.c_char_p),('symbol_address',ctypes.c_void_p)]


def configuration(path):
    path=Path(path).resolve(strict=True)
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536:raise ValueError('crypto configuration byte quota')
    if any(re.match(rb'\s*\.include(?:\s|=)',line) for line in raw.splitlines()):
        raise ValueError('unqualified crypto configuration include')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),activeIncludeCount=0)


def capture(files):
    """Query a global-context method and public dispatch, never a HASH layout."""
    validate_environment()
    if (ctypes.sizeof(_Dispatch)!=16 or ctypes.sizeof(_Algorithm)!=32 or ctypes.sizeof(_DlInfo)!=32):
        raise ValueError('unqualified public native metadata ABI')
    lib=ctypes.CDLL(files['libcrypto.so.3']['path']);libc=ctypes.CDLL(files['libc.so.6']['path'])
    libc.dladdr.argtypes=[ctypes.c_void_p,ctypes.POINTER(_DlInfo)];libc.dladdr.restype=ctypes.c_int
    def location(address,label):
        info=_DlInfo()
        if not address or not libc.dladdr(address,ctypes.byref(info)) or not info.name or not info.base:
            raise ValueError('native function mapping unavailable')
        path=str(Path(info.name.decode('ascii')).resolve(strict=True))
        if path!=files[label]['path']:raise ValueError('native function belongs to another runtime file')
        return dict(libraryPath=path,offsetHex=hex(address-info.base))
    lib.OPENSSL_info.argtypes=[ctypes.c_int];lib.OPENSSL_info.restype=ctypes.c_char_p
    info={key:lib.OPENSSL_info(number).decode('ascii') for key,number in
          [('configDir',1001),('engineDir',1002),('moduleDir',1003)]}
    config=configuration(Path(info['configDir'])/'openssl.cnf')
    lib.EVP_MD_fetch.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p];lib.EVP_MD_fetch.restype=ctypes.c_void_p
    lib.EVP_MD_get_type.argtypes=[ctypes.c_void_p];lib.EVP_MD_get_type.restype=ctypes.c_int
    lib.EVP_MD_get0_provider.argtypes=[ctypes.c_void_p];lib.EVP_MD_get0_provider.restype=ctypes.c_void_p
    lib.OSSL_PROVIDER_get0_name.argtypes=[ctypes.c_void_p];lib.OSSL_PROVIDER_get0_name.restype=ctypes.c_char_p
    lib.EVP_default_properties_is_fips_enabled.argtypes=[ctypes.c_void_p];lib.EVP_default_properties_is_fips_enabled.restype=ctypes.c_int
    lib.ENGINE_get_digest_engine.argtypes=[ctypes.c_int];lib.ENGINE_get_digest_engine.restype=ctypes.c_void_p
    lib.ENGINE_finish.argtypes=[ctypes.c_void_p];lib.ENGINE_finish.restype=ctypes.c_int
    lib.EVP_MD_free.argtypes=[ctypes.c_void_p];lib.EVP_MD_free.restype=None
    lib.OSSL_PROVIDER_query_operation.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
    lib.OSSL_PROVIDER_query_operation.restype=ctypes.POINTER(_Algorithm)
    lib.OSSL_PROVIDER_unquery_operation.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(_Algorithm)]
    lib.OSSL_PROVIDER_unquery_operation.restype=None
    md=lib.EVP_MD_fetch(None,b'SHA256',None)
    if not md:raise ValueError('global SHA256 method unavailable')
    try:
        nid=lib.EVP_MD_get_type(md);provider=lib.EVP_MD_get0_provider(md)
        if not provider:raise ValueError('provider-backed SHA256 required')
        provider_name=lib.OSSL_PROVIDER_get0_name(provider).decode('ascii')
        fips=lib.EVP_default_properties_is_fips_enabled(None)
        engine=lib.ENGINE_get_digest_engine(nid)
        try:engine_present=bool(engine)
        finally:
            if engine:lib.ENGINE_finish(engine)
        if nid!=672 or provider_name!='default' or fips!=0 or engine_present:
            raise ValueError('unqualified global SHA256 provider or ENGINE route')
        no_cache=ctypes.c_int()
        algorithms=lib.OSSL_PROVIDER_query_operation(provider,1,ctypes.byref(no_cache))
        if not algorithms:raise ValueError('public digest dispatch unavailable')
        try:
            matches=[]
            for i in range(256):
                row=algorithms[i]
                if row.names is None:break
                if 'SHA256' in row.names.decode('ascii').split(':'):matches.append(row)
            else:raise ValueError('provider algorithm metadata quota')
            if len(matches)!=1 or no_cache.value!=0:raise ValueError('stable unique SHA256 dispatch required')
            row=matches[0];functions={}
            for i in range(32):
                entry=row.implementation[i]
                if entry.function_id==0:break
                key=str(entry.function_id)
                if key in functions:raise ValueError('duplicate public digest function')
                functions[key]=location(entry.function,'libcrypto.so.3')
            else:raise ValueError('provider dispatch metadata quota')
            algorithm=dict(name='SHA256',nid=nid,provider=provider_name,fipsDefaultEnabled=fips,
                defaultDigestEnginePresent=engine_present,names=row.names.decode('ascii'),
                properties=row.properties.decode('ascii'),noCache=no_cache.value,functions=functions)
        finally:lib.OSSL_PROVIDER_unquery_operation(provider,1,algorithms)
    finally:lib.EVP_MD_free(md)
    libc.gnu_get_libc_version.argtypes=[];libc.gnu_get_libc_version.restype=ctypes.c_char_p
    memcpy=location(ctypes.cast(libc.memcpy,ctypes.c_void_p).value,'libc.so.6')
    memcpy['libcVersion']=libc.gnu_get_libc_version().decode('ascii')
    return dict(opensslInfo=info,configuration=config,algorithm=algorithm,resolvedMemcpy=memcpy,
        semantics='Public global-context metadata plus fixed initialization/source binding; no existing HASH object introspection')

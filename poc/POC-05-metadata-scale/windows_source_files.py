"""No-reparse, identity-bound controlled leaf changes and private credential reads."""
from __future__ import annotations

import ctypes as c
import hashlib
import os
import re
import stat
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace

from metadata_scan import ScanError
from native_scan_protocol import utc
from windows_native import FileTime, U32, I32, U64, I64, PTR, api, close_handle, owner_sid


class WindowsFileError(ScanError):
    pass


class FileInformation(c.Structure):
    _fields_=[('attributes',U32),('creation',FileTime),('access',FileTime),('write',FileTime),
        ('volume',U32),('sizeHigh',U32),('sizeLow',U32),('links',U32),('indexHigh',U32),('indexLow',U32)]


_bound=None
def files_api():
    global _bound
    if os.name!='nt':
        raise WindowsFileError('WINDOWS_FILESYSTEM_REQUIRED')
    if _bound is None:
        kernel=c.WinDLL('kernel32',use_last_error=True)
        security=c.WinDLL('advapi32',use_last_error=True)
        specs={
            'CreateFileW':(kernel,PTR,[c.c_wchar_p,U32,U32,PTR,U32,U32,PTR]),
            'GetFileInformationByHandle':(kernel,I32,[PTR,c.POINTER(FileInformation)]),
            'GetFinalPathNameByHandleW':(kernel,U32,[PTR,c.c_wchar_p,U32,U32]),
            'ReadFile':(kernel,I32,[PTR,PTR,U32,c.POINTER(U32),PTR]),
            'WriteFile':(kernel,I32,[PTR,PTR,U32,c.POINTER(U32),PTR]),
            'SetFilePointerEx':(kernel,I32,[PTR,I64,c.POINTER(I64),U32]),
            'SetEndOfFile':(kernel,I32,[PTR]),
            'FlushFileBuffers':(kernel,I32,[PTR]),
            'SetFileTime':(kernel,I32,[PTR,PTR,PTR,c.POINTER(FileTime)]),
            'SetFileInformationByHandle':(kernel,I32,[PTR,I32,PTR,U32]),
            'GetSecurityInfo':(security,U32,[PTR,I32,U32,c.POINTER(PTR),PTR,c.POINTER(PTR),PTR,c.POINTER(PTR)]),
            'GetAclInformation':(security,I32,[PTR,PTR,U32,U32]),
            'GetAce':(security,I32,[PTR,U32,c.POINTER(PTR)]),
        }
        bound={}
        for name,(library,result,args) in specs.items():
            fn=getattr(library,name);fn.restype=result;fn.argtypes=args;bound[name]=fn
        _bound=bound
    return _bound


def require(value,code):
    if not value:
        raise WindowsFileError(code)


def normalized(path):
    value=str(path)
    if value.startswith('\\\\?\\'):
        value=value[4:]
    return os.path.normcase(os.path.normpath(value))


def extended(path):
    require(path.is_absolute() and re.fullmatch('[A-Za-z]:',path.drive) is not None,'LOCAL_DRIVE_PATH_REQUIRED')
    return '\\\\?\\'+str(path)


def check_handle(handle,path,*,directory):
    info=FileInformation()
    require(files_api()['GetFileInformationByHandle'](handle,c.byref(info)),'NATIVE_FILE_IDENTITY_REQUIRED')
    require(not info.attributes&0x400 and bool(info.attributes&0x10)==directory,'REPARSE_OR_WRONG_FILE_TYPE_REJECTED')
    buffer=c.create_unicode_buffer(32768)
    length=files_api()['GetFinalPathNameByHandleW'](handle,buffer,32768,0)
    require(0<length<32768 and normalized(buffer.value)==normalized(path),'NATIVE_FILE_SCOPE_MISMATCH')
    return SimpleNamespace(st_mode=stat.S_IFDIR if directory else stat.S_IFREG,
        st_ino=info.indexLow|info.indexHigh<<32,st_size=info.sizeLow|info.sizeHigh<<32,
        st_mtime_ns=(info.write.integer()-116444736000000000)*100,volume=info.volume,links=info.links)


def sid_text(sid):
    text=c.c_wchar_p()
    require(api()['ConvertSidToStringSidW'](sid,c.byref(text)),'NATIVE_FILE_OWNER_REQUIRED')
    try:
        return text.value
    finally:
        api()['LocalFree'](c.cast(text,PTR))


def private_acl(handle):
    owner,dacl,descriptor=PTR(),PTR(),PTR()
    require(files_api()['GetSecurityInfo'](handle,1,5,c.byref(owner),None,c.byref(dacl),None,c.byref(descriptor))==0,
        'PRIVATE_FILE_SECURITY_DESCRIPTOR_REQUIRED')
    try:
        current=owner_sid(PTR(-1))
        require(sid_text(owner)==current and bool(dacl),'PRIVATE_OWNED_CREDENTIAL_FILE_REQUIRED')
        size=(U32*3)()
        require(files_api()['GetAclInformation'](dacl,c.byref(size),c.sizeof(size),2),'PRIVATE_FILE_ACL_REQUIRED')
        require(1<=size[0]<=32,'BOUNDED_PRIVATE_FILE_ACL_REQUIRED')
        allowed={current,'S-1-5-18','S-1-5-32-544'}
        for number in range(size[0]):
            ace=PTR()
            require(files_api()['GetAce'](dacl,number,c.byref(ace)),'PRIVATE_FILE_ACE_REQUIRED')
            header=c.string_at(ace,4)
            require(header[0]==0 and int.from_bytes(header[2:4],'little')>=12,'EXPLICIT_PRIVATE_ALLOW_ACL_REQUIRED')
            require(sid_text(PTR(ace.value+8)) in allowed,'CREDENTIAL_FILE_EXPOSED_TO_OTHER_PRINCIPAL')
    finally:
        api()['LocalFree'](descriptor)


class Leaf:
    """Parent handles deny rename/delete; leaf handle also denies other writers."""
    def __init__(self,root,locator):
        self.root=Path(root).absolute();self.target=self.root
        self.parents=[];self.handle=None
        parts=locator.split('/')
        require(parts and all(part and part not in ('.','..') and not any(ord(ch)<32 or ch in ':\\' for ch in part)
            and not part.endswith(('.',' ')) and not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',part,re.I) for part in parts),
            'UNAMBIGUOUS_WINDOWS_LEAF_REQUIRED')
        require(self.root.resolve()==self.root,'NATIVE_FILE_ROOT_ALIAS_REJECTED')
        try:
            for path in [self.root,*[self.root.joinpath(*parts[:number]) for number in range(1,len(parts))]]:
                handle=files_api()['CreateFileW'](extended(path),0x80000000,3,None,3,0x02200000,None)
                require(handle not in (None,c.c_void_p(-1).value),'NATIVE_DIRECTORY_HANDLE_REQUIRED')
                self.parents.append(handle)
                check_handle(handle,path,directory=True)
            self.target=self.root.joinpath(*parts)
        except BaseException:
            self.close()
            raise

    def open(self,*,create=False,write=False,delete=False,mutation_receipt=None):
        require(self.handle is None,'ONE_CONTROLLED_LEAF_HANDLE_REQUIRED')
        require(not create or isinstance(mutation_receipt,dict),'CREATE_DIRTY_RECEIPT_REQUIRED')
        access=0x80000000 | (0x40000000 if write else 0) | (0x10000 if delete else 0)
        handle=files_api()['CreateFileW'](extended(self.target),access,1,None,1 if create else 3,0x00200000,None)
        require(handle not in (None,c.c_void_p(-1).value),'EXCLUSIVE_CONTROLLED_LEAF_HANDLE_REQUIRED')
        self.handle=handle
        if create:
            # CREATE_NEW already changed the filesystem. A later identity query
            # can fail; that failure must not turn the created file into "clean".
            mutation_receipt['filesystemMutated']=True
        state=check_handle(handle,self.target,directory=False)
        require(state.links==1,'SINGLE_LINK_CONTROLLED_FILE_REQUIRED')
        return state

    def read(self,limit=65536):
        state=check_handle(self.handle,self.target,directory=False)
        require(state.st_size<=limit,'BOUNDED_CONTROLLED_FILE_REQUIRED')
        require(files_api()['SetFilePointerEx'](self.handle,0,None,0),'CONTROLLED_FILE_SEEK_FAILED')
        buffer=c.create_string_buffer(limit+1);count=U32()
        require(files_api()['ReadFile'](self.handle,buffer,limit+1,c.byref(count),None),'CONTROLLED_FILE_READ_FAILED')
        require(count.value==state.st_size and count.value<=limit,'ACTUAL_CONTROLLED_FILE_BYTES_REQUIRED')
        return state,buffer.raw[:count.value]

    def apply(self,intent,remote_before,read_payload,receipt):
        operation=intent['operation']
        if operation!='create':
            self.open(write=operation=='update',delete=operation=='delete')
            state,raw=self.read()
            require(intent['beforeSha256']=='sha256:'+hashlib.sha256(raw).hexdigest()
                and remote_before['kind']=='file' and remote_before['fileSizeBytes']==len(raw)
                and utc(remote_before['modifiedAt']).timestamp()==state.st_mtime_ns/1e9,
                'APPROVED_ACTUAL_BEFORE_PAYLOAD_REQUIRED')
            receipt.update(beforeActualSha256='sha256:'+hashlib.sha256(raw).hexdigest(),beforeInode=state.st_ino,beforeVolume=state.volume)
        if operation=='delete':
            require(intent['afterVersion']=='absent','CONTROLLED_DELETE_IDENTITY_MISMATCH')
            delete=c.c_ubyte(1)
            require(files_api()['SetFileInformationByHandle'](self.handle,4,c.byref(delete),c.sizeof(delete)),
                'CONTROLLED_HANDLE_DELETE_FAILED')
            receipt['filesystemMutated']=True
            self.close_leaf()
            return
        require(intent['afterVersion']!='absent' and intent['afterVersion']!=intent['beforeVersion'],'CONTROLLED_NEW_VERSION_REQUIRED')
        payload=read_payload()
        require(isinstance(payload,bytes) and len(payload)<=65536 and intent['payloadSha256']=='sha256:'+hashlib.sha256(payload).hexdigest(),
            'APPROVED_CONTROLLED_PAYLOAD_REQUIRED')
        if operation=='create':
            self.open(create=True,write=True,mutation_receipt=receipt)
        require(files_api()['SetFilePointerEx'](self.handle,0,None,0),'CONTROLLED_FILE_SEEK_FAILED')
        require(files_api()['SetEndOfFile'](self.handle),'CONTROLLED_FILE_TRUNCATE_FAILED')
        receipt['filesystemMutated']=True
        count=U32();buffer=c.create_string_buffer(payload)
        require(files_api()['WriteFile'](self.handle,buffer,len(payload),c.byref(count),None) and count.value==len(payload),
            'ACTUAL_CONTROLLED_FILE_WRITE_REQUIRED')
        require(files_api()['FlushFileBuffers'](self.handle),'CONTROLLED_FILE_FLUSH_FAILED')
        stamp=utc(intent['modifiedAt'])
        delta=stamp-datetime(1601,1,1,tzinfo=timezone.utc)
        value=(delta.days*86400+delta.seconds)*10000000+delta.microseconds*10
        require(0<=value<2**64,'NATIVE_FILE_TIME_RANGE_REQUIRED')
        at=FileTime(value&0xffffffff,value>>32)
        require(files_api()['SetFileTime'](self.handle,None,None,c.byref(at)),'CONTROLLED_FILE_TIME_FAILED')
        state,actual=self.read()
        receipt.update(afterInode=state.st_ino,afterVolume=state.volume,
            afterActualSha256='sha256:'+hashlib.sha256(actual).hexdigest())
        require(receipt['afterActualSha256']==intent['payloadSha256'],'ACTUAL_CONTROLLED_WRITE_MISMATCH')
        self.close_leaf()

    def close_leaf(self):
        if self.handle:
            close_handle(self.handle);self.handle=None

    def close(self):
        self.close_leaf()
        for handle in reversed(self.parents):
            close_handle(handle)
        self.parents=[]


def read_private(path,*,limit=16384):
    path=Path(path).absolute()
    leaf=Leaf(path.parent,path.name)
    try:
        leaf.open()
        private_acl(leaf.handle)
        return leaf.read(limit)[1]
    finally:
        leaf.close()

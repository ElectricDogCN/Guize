"""Actual disposable Windows handles/ACLs; no OpenList or scale acceptance."""
import hashlib
import os
import subprocess
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

import windows_native as native
from windows_source_files import Leaf,WindowsFileError,files_api,read_private


class WindowsSourceFileTests(unittest.TestCase):
    def supported(self):
        if os.name=='nt':
            return True
        with self.assertRaisesRegex(WindowsFileError,'WINDOWS_FILESYSTEM_REQUIRED'):
            files_api()
        return False

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def leaf(self,path):
        result=Leaf(self.root,path)
        self.addCleanup(result.close)
        return result

    @staticmethod
    def sha(raw):
        return 'sha256:'+hashlib.sha256(raw).hexdigest()

    @staticmethod
    def remote(path):
        state=path.stat()
        return dict(kind='file',fileSizeBytes=state.st_size,
            modifiedAt=datetime.fromtimestamp(state.st_mtime,timezone.utc).isoformat())

    def test_actual_handle_create_update_delete_preserves_identity_and_exact_microsecond_time(self):
        if not self.supported(): return
        path=self.root/'实际 文件.bin'
        create=dict(operation='create',beforeVersion='absent',afterVersion='v1',
            payloadSha256=self.sha(b'first'),modifiedAt='2026-01-01T00:00:02.123456Z')
        receipt={'filesystemMutated':False}
        leaf=self.leaf(path.name)
        leaf.apply(create,None,lambda:b'first',receipt)
        self.assertTrue(receipt['filesystemMutated'])
        self.assertEqual(path.read_bytes(),b'first')
        # Integer FILETIME, not float timestamp multiplication, preserves 1us.
        self.assertEqual(path.stat().st_mtime_ns,1767225602123456000)
        update=dict(operation='update',beforeVersion='v1',afterVersion='v2',beforeSha256=self.sha(b'first'),
            payloadSha256=self.sha(b'changed'),modifiedAt='2026-01-01T00:00:03Z')
        receipt={'filesystemMutated':False}
        leaf.apply(update,self.remote(path),lambda:b'changed',receipt)
        self.assertEqual(receipt['beforeInode'],receipt['afterInode'])
        self.assertEqual(receipt['beforeVolume'],receipt['afterVolume'])
        self.assertEqual(path.read_bytes(),b'changed')
        receipt={'filesystemMutated':False}
        leaf.apply(dict(operation='delete',beforeVersion='v2',afterVersion='absent',beforeSha256=self.sha(b'changed')),
            self.remote(path),lambda:self.fail('delete read an unapproved payload'),receipt)
        self.assertTrue(receipt['filesystemMutated'])
        self.assertFalse(path.exists())

    def test_wrong_before_or_new_payload_never_changes_existing_bytes(self):
        if not self.supported(): return
        path=self.root/'existing.bin';path.write_bytes(b'before')
        intent=dict(operation='update',beforeVersion='v1',afterVersion='v2',beforeSha256='sha256:'+'0'*64,
            payloadSha256=self.sha(b'after'),modifiedAt='2026-01-01T00:00:02Z')
        for before in ('sha256:'+'0'*64,self.sha(b'before')):
            leaf=self.leaf(path.name);intent['beforeSha256']=before
            receipt={'filesystemMutated':False}
            with self.assertRaisesRegex(WindowsFileError,'PAYLOAD_REQUIRED'):
                leaf.apply(intent,self.remote(path),lambda:b'wrong',receipt)
            leaf.close()
            self.assertFalse(receipt['filesystemMutated'])
            self.assertEqual(path.read_bytes(),b'before')

    def test_actual_parent_rename_and_competing_writer_are_denied_until_close(self):
        if not self.supported(): return
        folder=self.root/'parent';folder.mkdir();path=folder/'leaf';path.write_bytes(b'original')
        leaf=self.leaf('parent/leaf');leaf.open(write=True)
        with self.assertRaises(OSError): folder.rename(self.root/'moved')
        with self.assertRaises(OSError): path.write_bytes(b'competing')
        with self.assertRaises(OSError): path.unlink()
        self.assertEqual(leaf.read()[1],b'original')
        leaf.close()
        folder.rename(self.root/'moved')
        self.assertEqual((self.root/'moved/leaf').read_bytes(),b'original')

    def test_actual_hardlink_and_junction_cannot_redirect_controlled_changes(self):
        if not self.supported(): return
        outside=self.root/'outside';outside.mkdir();path=outside/'real';path.write_bytes(b'unchanged')
        os.link(path,self.root/'alias')
        leaf=self.leaf('alias')
        with self.assertRaisesRegex(WindowsFileError,'SINGLE_LINK'): leaf.open(write=True)
        leaf.close()
        junction=self.root/'junction'
        command=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(junction),str(outside)],
            capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(command.returncode,0,command.stderr)
        try:
            with self.assertRaisesRegex(WindowsFileError,'REPARSE_OR_WRONG_FILE_TYPE'):
                Leaf(self.root,'junction/real')
        finally:
            os.rmdir(junction)
        self.assertEqual(path.read_bytes(),b'unchanged')

    def test_windows_aliases_are_rejected_before_any_creation(self):
        if not self.supported(): return
        for locator in ('../outside','C:/outside','leaf:stream','folder\\leaf','CON','nul.txt','COM1.bin','trailing.','trailing ','/leaf'):
            with self.subTest(locator=locator),self.assertRaisesRegex(WindowsFileError,'UNAMBIGUOUS_WINDOWS_LEAF'):
                Leaf(self.root,locator)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_actual_private_acl_and_bounded_read_reject_another_principal(self):
        if not self.supported(): return
        path=self.root/'dummy-credential';path.write_bytes(b'unit-only-not-a-secret')
        sid=native.owner_sid(native.PTR(-1))
        for options in (['/inheritance:r'],['/grant:r','*'+sid+':F']):
            completed=subprocess.run(['icacls.exe',str(path),*options],capture_output=True,timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(read_private(path),b'unit-only-not-a-secret')
        with self.assertRaisesRegex(WindowsFileError,'BOUNDED_CONTROLLED_FILE_REQUIRED'): read_private(path,limit=4)
        completed=subprocess.run(['icacls.exe',str(path),'/grant','*S-1-1-0:R'],capture_output=True,timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(completed.returncode,0,completed.stderr)
        with self.assertRaisesRegex(WindowsFileError,'EXPOSED_TO_OTHER_PRINCIPAL'): read_private(path)


if __name__=='__main__': unittest.main()

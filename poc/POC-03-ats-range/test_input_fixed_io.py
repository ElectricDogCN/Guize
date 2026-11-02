"""Real-file input validation with one fixed backing; no ATS or media run."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import weakref

from input_profile import _actual_digest


class Payload(bytearray):pass


class InputFixedIOTests(unittest.TestCase):
    def run_case(self,data,*,short=None,error=False,bad=None,overallocated=False):
        allocations=[];references=[];descriptors=[];readings=[];streams=[]
        original_fdopen=os.fdopen
        def backing(size):
            block=Payload(size+(65536 if overallocated else 0))
            if overallocated:del block[size:]
            allocations.append((size,len(block),block.__alloc__()))
            references.append(weakref.ref(block));return block
        class Reader:
            def __init__(self,stream):self.stream=stream;streams.append(stream)
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def readinto(self,target):
                readings.append((id(target.obj),len(target)))
                if error and len(readings)>1:raise OSError('actual reader injection')
                if bad is not None:return bad(len(target))
                with target[:min(len(target),short or len(target))] as part:
                    return self.stream.readinto(part)
        def opened(fd,mode,*,buffering,closefd):
            self.assertEqual((mode,buffering,closefd),('rb',0,False))
            descriptors.append(fd);return Reader(original_fdopen(fd,mode,buffering=buffering,closefd=closefd))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.bin';path.write_bytes(data)
            try:
                with patch('input_profile.os.fdopen',new=opened),patch('input_profile.bytearray',new=backing,create=True),patch('input_profile.os.read',side_effect=AssertionError('returned-byte reads are forbidden')):
                    actual=_actual_digest(path,len(data))
            finally:
                self.assertEqual([row[0] for row in allocations],[1048576])
                self.assertTrue(all(ref() is None for ref in references))
                self.assertTrue(all(stream.closed for stream in streams))
                self.assertEqual(len(descriptors),1)
                with self.assertRaises(OSError):os.fstat(descriptors[0])
                if overallocated:self.assertEqual(readings,[])
        self.assertEqual(actual,hashlib.sha256(data).hexdigest())
        self.assertEqual(allocations,[(1048576,1048576,1048577)])
        self.assertEqual(len({row[0] for row in readings}),1)
        self.assertEqual(readings[-1][1],1)
        return readings

    def test_empty_short_tail_and_multiblock_inputs_use_one_released_raw_slot(self):
        for data in [b'',b'abcdefghijklmnopq',b'x'*1048576+b'abcdefghijklmnopq']:
            with self.subTest(size=len(data)):self.run_case(data)

    def test_partial_file_reads_reuse_the_same_slot_and_keep_the_eof_probe(self):
        readings=self.run_case(b'abcdefghijklmnopq',short=3)
        self.assertEqual(len(readings),7)

    def test_read_failure_preserves_error_and_releases_slot_stream_and_descriptor(self):
        with self.assertRaisesRegex(OSError,'actual reader injection'):
            self.run_case(b'abcdefghijklmnopq',short=3,error=True)

    def test_invalid_counts_and_premature_eof_are_rejected(self):
        for bad in [lambda n:None,lambda n:True,lambda n:-1,lambda n:n+1]:
            with self.subTest(bad=bad),self.assertRaisesRegex(OSError,'invalid raw input read count'):
                self.run_case(b'abcdefgh',bad=bad)
        with self.assertRaisesRegex(ValueError,'shortened'):
            self.run_case(b'abcdefgh',bad=lambda n:0)

    def test_same_length_excess_backing_is_rejected_before_any_read(self):
        with self.assertRaisesRegex(OSError,'unqualified fixed input backing'):
            self.run_case(b'abcdefgh',overallocated=True)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InputFixedIOTests))
    if result.testsRun!=5 or result.skipped:raise SystemExit('Expected five actual fixed-input tests with no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

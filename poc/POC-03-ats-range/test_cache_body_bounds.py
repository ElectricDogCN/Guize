"""Offline export-file regressions; no ATS or source HTTP workload."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import hashlib
from cache_probe import export_body_observation


class CacheBodyBoundsTests(unittest.TestCase):
    def test_exact_and_partial_exports_preserve_every_returned_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory)/'slice.body'
            source = Path(directory)/'input.bin'
            source.write_bytes(b'abcdefgh')
            destination = Path(directory)/'copy.bin'
            for data in (b'abcdefgh', b'abc', b''):
                with self.subTest(size=len(data)):
                    body.write_bytes(data)
                    result = export_body_observation(body, destination, source, 0, 8)
                    self.assertEqual(destination.read_bytes(), data)
                    self.assertEqual(result, dict(actualBytes=len(data), actualSha256=hashlib.sha256(data).hexdigest(),
                                                  exactInputSliceEqual=len(data) == 8))

    def test_oversized_export_is_rejected_before_opening_its_body(self):
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory)/'slice.body'
            body.write_bytes(b'abcdefghi')
            with mock.patch.object(Path, 'open', side_effect=AssertionError('oversized body opened')):
                with self.assertRaisesRegex(ValueError, 'selected Slice'):
                    export_body_observation(body, Path(directory)/'copy.bin', Path(directory)/'input.bin', 0, 8)

    def test_growth_between_size_check_and_open_is_rejected_without_trimming(self):
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory)/'slice.body'
            body.write_bytes(b'abcdefgh')
            source = Path(directory)/'input.bin'
            source.write_bytes(b'abcdefgh')
            original_open = Path.open

            def growing_open(path, *args, **kwargs):
                if path == body and args[0] == 'rb':
                    with original_open(path, 'ab') as stream:
                        stream.write(b'i')
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, 'open', growing_open):
                with self.assertRaisesRegex(ValueError, 'changed|selected Slice'):
                    export_body_observation(body, Path(directory)/'copy.bin', source, 0, 8)
            self.assertEqual(body.read_bytes(), b'abcdefghi')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CacheBodyBoundsTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 3 or result.skipped:
        raise SystemExit('Expected three actual offline tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

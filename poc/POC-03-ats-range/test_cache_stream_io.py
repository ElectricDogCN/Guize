"""Actual cache files, short raw I/O and fixed backing lifetimes; no ATS workload."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import weakref

from cache_probe import assemble_export_bodies, export_body_observation


class Slot(bytearray):
    pass


class CacheStreamTests(unittest.TestCase):
    def test_multiblock_copy_comparison_and_partial_writes_use_two_fixed_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            body, source, output = (Path(directory)/n for n in ('body', 'source', 'output'))
            data = bytes(range(256)) * 513 + b'tail'
            body.write_bytes(data)
            source.write_bytes(b'offset' + data + b'other bytes')
            original_open = Path.open
            readers = {'body': set(), 'source': set()}
            modes = []
            class Raw:
                def __init__(self, path, stream): self.path, self.stream = path, stream
                def __enter__(self): return self
                def __exit__(self, *args): self.close()
                def close(self): self.stream.close()
                def seek(self, offset): return self.stream.seek(offset)
                def readinto(self, target):
                    readers[self.path.name].add(id(target.obj))
                    self_test.assertEqual((len(target.obj), target.obj.__alloc__()), (65536, 65537))
                    with target[:min(len(target), 997 if self.path == body else 211)] as part:
                        return self.stream.readinto(part)
                def write(self, block):
                    with block[:min(len(block), 307)] as part:
                        return self.stream.write(part)
            def opening(path, *args, **kwargs):
                modes.append(kwargs.get('buffering'))
                return Raw(path, original_open(path, *args, **kwargs))
            self_test = self
            with patch.object(Path, 'open', new=opening):
                result = export_body_observation(body, output, source, 6, len(data))
            self.assertEqual(output.read_bytes(), data)
            self.assertEqual(result, dict(actualBytes=len(data), actualSha256=hashlib.sha256(data).hexdigest(), exactInputSliceEqual=True))
            self.assertEqual(modes, [0, 0, 0])
            self.assertEqual([len(readers[n]) for n in ('body', 'source')], [1, 1])
            self.assertTrue(readers['body'].isdisjoint(readers['source']))

    def test_short_reference_cannot_be_accepted_as_complete_slice(self):
        with tempfile.TemporaryDirectory() as directory:
            body, source, output = (Path(directory)/n for n in ('body', 'source', 'output'))
            body.write_bytes(b'abcdefgh'); source.write_bytes(b'abc')
            result = export_body_observation(body, output, source, 0, 8)
            self.assertEqual(output.read_bytes(), b'abcdefgh')
            self.assertEqual(result['actualSha256'], hashlib.sha256(b'abcdefgh').hexdigest())
            self.assertFalse(result['exactInputSliceEqual'])

    def test_later_block_mismatch_does_not_trim_export_or_claim_equality(self):
        with tempfile.TemporaryDirectory() as directory:
            body, source, output = (Path(directory)/n for n in ('body', 'source', 'output'))
            data = b'a' * 65536 + b'actual'
            body.write_bytes(data); source.write_bytes(b'a' * 65536 + b'wrong!')
            result = export_body_observation(body, output, source, 0, len(data))
            self.assertEqual(output.read_bytes(), data)
            self.assertEqual(result['actualBytes'], len(data))
            self.assertFalse(result['exactInputSliceEqual'])

    def test_zero_progress_write_is_failure_and_does_not_open_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            body, source, output = (Path(directory)/n for n in ('body', 'source', 'output'))
            body.write_bytes(b'abcdefgh')
            original_open = Path.open
            closed = []
            class Output:
                def __enter__(self): return self
                def __exit__(self, *args): closed.append(True)
                def write(self, block): return 0
            def opening(path, *args, **kwargs):
                if path == source: raise AssertionError('reference opened after failed write')
                return Output() if path == output else original_open(path, *args, **kwargs)
            with patch.object(Path, 'open', new=opening):
                with self.assertRaisesRegex(OSError, 'progress'):
                    export_body_observation(body, output, source, 0, 8)
            self.assertEqual(closed, [True])

    def test_retained_overallocation_is_rejected_before_media_read(self):
        with tempfile.TemporaryDirectory() as directory:
            body, source, output = (Path(directory)/n for n in ('body', 'source', 'output'))
            body.write_bytes(b'abcdefgh')
            original_open = Path.open
            def overallocated(size):
                slot = bytearray(size * 2)
                del slot[size:]
                self.assertEqual(len(slot), size)
                self.assertGreater(slot.__alloc__(), size + 1)
                return slot
            class Unreadable:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def readinto(self, target): raise AssertionError('media read before capacity rejection')
            def opening(path, *args, **kwargs):
                return Unreadable() if path == body else original_open(path, *args, **kwargs)
            with patch('cache_probe.bytearray', new=overallocated, create=True), patch.object(Path, 'open', new=opening):
                with self.assertRaisesRegex(OSError, 'backing capacity'):
                    export_body_observation(body, output, source, 0, 8)

    def test_assembly_uses_one_slot_across_parts_and_releases_it(self):
        references = []
        def allocate(size):
            slot = Slot(size); references.append(weakref.ref(slot)); return slot
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/str(n) for n in range(3)]
            values = [b'a' * 65537, b'bc', b'']
            for path, data in zip(paths, values): path.write_bytes(data)
            output = Path(directory)/'assembled'
            original_open = Path.open
            modes = []
            class Output:
                def __init__(self, stream): self.stream = stream
                def __enter__(self): return self
                def __exit__(self, *args): self.stream.close()
                def write(self, block):
                    with block[:min(len(block), 337)] as part: return self.stream.write(part)
            def opening(path, *args, **kwargs):
                modes.append(kwargs.get('buffering'))
                stream = original_open(path, *args, **kwargs)
                return Output(stream) if path == output else stream
            with patch('cache_probe.bytearray', new=allocate, create=True), patch.object(Path, 'open', new=opening):
                count, digest = assemble_export_bodies(paths, output)
            expected = b''.join(values)
            self.assertEqual((count, digest), (len(expected), hashlib.sha256(expected).hexdigest()))
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(modes, [0, 0, 0, 0])
            self.assertEqual(len(references), 1)
            self.assertIsNone(references[0]())


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CacheStreamTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 6 or result.skipped:
        raise SystemExit('Expected six actual cache streaming tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

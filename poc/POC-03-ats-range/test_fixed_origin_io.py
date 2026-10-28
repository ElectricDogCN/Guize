"""Fixed raw-file buffers with synthetic content; no ATS/media experiment."""
import hashlib
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from lab import Origin, context, digest, sign
from test_request_concurrency import handler


class Payload(bytearray):
    pass


class FixedOriginIOTests(unittest.TestCase):
    def setUp(self):
        self.allocations = []
        self.references = []

    def backing(self, size):
        block = Payload(size)
        self.allocations.append(size)
        self.references.append(weakref.ref(block))
        return block

    def live(self):
        return sum(ref() is not None for ref in self.references)

    def test_digest_empty_short_and_multiblock_files_have_exact_hash_with_one_backing(self):
        original = Path.open
        for data in (b'', b'abcdefghijklmnopq', b'x'*1048576+b'abcdefghijklmnopq'):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as directory:
                source = Path(directory)/'source.bin'
                source.write_bytes(data)
                self.allocations.clear()
                opened = []
                def raw_open(path, mode, *, buffering):
                    self.assertEqual(mode, 'rb')
                    self.assertEqual(buffering, 0)
                    stream = original(path, mode, buffering=buffering)
                    opened.append(stream)
                    return stream
                with patch.object(Path, 'open', new=raw_open), patch('lab.bytearray', new=self.backing, create=True):
                    actual = digest(source)
                self.assertEqual(actual, hashlib.sha256(data).hexdigest())
                self.assertEqual(self.allocations, [1048576])
                self.assertEqual(self.live(), 0)
                self.assertTrue(all(stream.closed for stream in opened))

    def digest_reader(self, fail=False):
        data = b'abcdefghijklmnopq'
        offset = 0
        identities = []
        state = {'closed':False}
        test = self
        class Input:
            def __enter__(self): return self
            def __exit__(self, *args): state['closed'] = True
            def readinto(self, target):
                nonlocal offset
                identities.append(id(target.obj))
                if fail and offset:
                    raise OSError('synthetic raw read failure')
                count = min(3, len(data)-offset)
                target[:count] = data[offset:offset+count]
                offset += count
                return count
        def opened(path, mode, *, buffering):
            test.assertEqual((mode, buffering), ('rb', 0))
            return Input()
        with patch.object(Path, 'open', new=opened), patch('lab.bytearray', new=self.backing, create=True):
            if fail:
                with self.assertRaisesRegex(OSError, 'synthetic raw read failure'):
                    digest('synthetic-input')
            else:
                self.assertEqual(digest('synthetic-input'), hashlib.sha256(data).hexdigest())
        self.assertTrue(state['closed'])
        self.assertEqual(len(set(identities)), 1)
        self.assertEqual(self.allocations, [1048576])
        self.assertEqual(self.live(), 0)

    def test_digest_short_reads_reuse_the_same_backing_until_eof(self):
        self.digest_reader()

    def test_digest_failure_closes_input_releases_backing_and_preserves_error(self):
        self.digest_reader(fail=True)

    def test_same_length_retained_excess_capacity_is_rejected_before_reading(self):
        observed = {'closed':False,'reads':0}
        test = self
        class Input:
            def __enter__(self): return self
            def __exit__(self, *args): observed['closed'] = True
            def readinto(self, target):
                observed['reads'] += 1
                raise AssertionError('unqualified retained capacity reached source read')
        def oversized(size):
            result = Payload(size+8)
            del result[size:]
            test.assertEqual(len(result), size)
            test.assertGreater(result.__alloc__(), size+1)
            self.references.append(weakref.ref(result))
            return result
        with patch.object(Path, 'open', new=lambda *args, **kwargs:Input()), patch('lab.bytearray', new=oversized, create=True):
            with self.assertRaisesRegex(OSError, 'unqualified fixed hash backing capacity'):
                digest('synthetic-input')
        self.assertTrue(observed['closed'])
        self.assertEqual(observed['reads'], 0)
        self.assertEqual(self.live(), 0)

    def test_origin_short_reads_preserve_all_content_using_one_raw_backing(self):
        data = b'abcdefghijklmnopqrs'
        state = SimpleNamespace(lock=threading.RLock(), origin_rows={}, active_origin={}, origin_active_peak=0,
            fault=None, cfg=dict(maximumOriginRequests=8, aclVersion='synthetic-acl', secret='synthetic-only', chunkBytes=8,
                inputs={'base':dict(sizeBytes=len(data), etag='"synthetic"', path='synthetic-input', sha256='synthetic')}))
        rid = 'e'*32
        path = '/ctx/'+context('synthetic-acl', 'lab-user-a')+'/base/object.bin'
        headers = {'X-Lab-Request-ID':rid, 'X-Lab-Origin-Expiry':'1000',
                   'X-Lab-Origin-Signature':sign('synthetic-only', path, rid, 1000)}
        offset = 0
        identities = []
        observed = {'closed':False}
        class Input:
            def __enter__(self): return self
            def __exit__(self, *args): observed['closed'] = True
            def seek(self, start):
                nonlocal offset
                offset = start
            def readinto(self, target):
                nonlocal offset
                identities.append(id(target.obj))
                count = min(3, len(target), len(data)-offset)
                target[:count] = data[offset:offset+count]
                offset += count
                return count
        def log(kind, row):
            if kind == 'origin-access':
                self.assertTrue(observed['closed'])
                self.assertEqual(self.live(), 0)
                self.assertEqual(state.active_origin[rid], 0)
        state.log = log
        item = handler(Origin, state, headers, path)
        written = []
        item.wfile = SimpleNamespace(write=lambda view: written.append(bytes(view)), flush=lambda:None)
        def opened(path, mode, *, buffering):
            self.assertEqual((mode, buffering), ('rb', 0))
            return Input()
        with patch.object(Path, 'open', new=opened), patch('lab.bytearray', new=self.backing, create=True), patch('lab.time.time', return_value=999):
            item.handle_media(False)
        self.assertEqual(b''.join(written), data)
        row = state.origin_rows[rid][0]
        self.assertEqual((row['objectReadCount'],row['objectReadBytes']), (7,len(data)))
        self.assertIsNone(row['transportError'])
        self.assertEqual(row['sourceBackingCapacityBytes'], 9)
        self.assertEqual(row['sourceReadMode'], 'raw-readinto')
        self.assertEqual(len(set(identities)), 1)
        self.assertEqual(self.allocations, [8])
        self.assertEqual(self.live(), 0)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixedOriginIOTests))
    if result.testsRun != 5 or result.skipped:
        raise SystemExit('Expected five actual fixed-buffer tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

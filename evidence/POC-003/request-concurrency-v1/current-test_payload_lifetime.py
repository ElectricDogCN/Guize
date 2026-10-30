"""Actual Python reference lifetimes with synthetic bodies; no ATS/media run."""
import hashlib
import http.client
from pathlib import Path
import threading
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from grants import Grant
from lab import Gateway, Origin, context, sign
from cache_probe import export_body_observation
from collect import Collector


class Payload(bytearray):
    pass


class PayloadLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.references = []
        self.logs = []

    def payload(self):
        block = Payload(b'abcdefgh')
        self.references.append(weakref.ref(block))
        return block

    def live(self):
        return sum(reference() is not None for reference in self.references)

    def handler(self, cls, state, headers, path, fail_write=False):
        handler = object.__new__(cls)
        handler.server = SimpleNamespace(state=state)
        handler.headers = headers
        handler.path = path
        handler.send_response = lambda *args: None
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        def write(block):
            if fail_write:
                raise OSError('synthetic write failure')
            return len(block)
        handler.wfile = SimpleNamespace(write=write, flush=lambda: None)
        handler.connection = SimpleNamespace(shutdown=lambda *args: None)
        return handler

    def origin(self, fault=None, fail_write=False):
        cfg = dict(maximumOriginRequests=8, aclVersion='synthetic-acl', secret='synthetic-only',
            inputs={'base': dict(sizeBytes=8, etag='"synthetic"', sha256='synthetic', path='synthetic-input')},
            faultAfterBytes=8, chunkBytes=8)
        state = SimpleNamespace(cfg=cfg, lock=threading.RLock(), origin_rows={}, active_origin={}, origin_active_peak=0, fault=fault)
        rid = 'a' * 32
        path = '/ctx/' + context(cfg['aclVersion'], 'lab-user-a') + '/base/object.bin'
        headers = {'X-Lab-Request-ID': rid, 'X-Lab-Origin-Expiry': '1000',
                   'X-Lab-Origin-Signature': sign(cfg['secret'], path, rid, 1000)}
        stream = SimpleNamespace(seek=lambda *args: None, read=lambda *args: self.payload(), closed=False)
        def exit_stream(*args):
            stream.closed = True
        class Input:
            def __enter__(self): return stream
            def __exit__(self, *args): exit_stream()
        def log(kind, row):
            self.logs.append((kind, dict(row)))
            if kind == 'origin-access':
                self.assertTrue(stream.closed)
                self.assertEqual(state.active_origin[rid], 0)
                self.assertEqual(self.live(), 0, 'terminal log retained a media payload')
        state.log = log
        def sleep(seconds):
            if seconds == 2:
                self.assertEqual(state.active_origin[rid], 1)
                self.assertEqual(self.live(), 0, 'truncation hold retained the final block')
        handler = self.handler(Origin, state, headers, path, fail_write)
        with patch.object(Path, 'open', return_value=Input()), patch('lab.time.time', return_value=999), patch('lab.time.sleep', side_effect=sleep):
            handler.handle_media(False)
        return state.origin_rows[rid][0]

    def gateway(self, mode):
        cfg = dict(users={'lab-user-a': 'synthetic-only'}, aclVersion='synthetic-acl', atsPort=1, secret='synthetic-only',
            inputs={'base': dict(sizeBytes=16, etag='"synthetic"')}, chunkBytes=8)
        state = SimpleNamespace(cfg=cfg, version='base', lock=threading.RLock(), gateway_active=0, gateway_active_peak=0, gateway_rows={},
            grants={'lab-user-a': Grant('synthetic-grant', 'lab-user-a', '2000-01-01T00:00:00Z', '2100-01-01T00:00:00Z')})
        calls = 0
        def read(size):
            nonlocal calls
            self.assertEqual(self.live(), 0, 'next read overlapped the previous returned block')
            calls += 1
            if mode == 'incomplete':
                raise http.client.IncompleteRead(self.payload(), 8)
            if calls > 2:
                response.length = 0
                return b''
            return self.payload()
        response = SimpleNamespace(status=200, length=16, read1=read, getheader=lambda *args: None, closed=False)
        connection = SimpleNamespace(request=lambda *args, **kwargs: None, getresponse=lambda: response, closed=False)
        response.close = lambda: setattr(response, 'closed', True)
        connection.close = lambda: setattr(connection, 'closed', True)
        def log(kind, row):
            self.logs.append((kind, dict(row)))
            self.assertTrue(response.closed and connection.closed)
            self.assertEqual(state.gateway_active, 0)
            self.assertEqual(self.live(), 0, 'terminal log retained a returned or partial media block')
        state.log = log
        handler = self.handler(Gateway, state, {'X-Lab-Request-ID': 'b' * 32, 'X-Lab-Case': 'stream',
            'Authorization': 'Bearer synthetic-only'}, '/media/object.bin', mode == 'write-failure')
        with patch('lab.http.client.HTTPConnection', return_value=connection):
            handler.media(False)
        return state.gateway_rows['b' * 32][0]

    def test_origin_success_releases_payload_before_terminal_log(self):
        row = self.origin()
        self.assertEqual(row['objectReadBytes'], 8)

    def test_origin_truncation_preserves_digest_without_retaining_payload(self):
        row = self.origin('truncate')
        self.assertEqual(row['prefixSha256'], hashlib.sha256(b'abcdefgh').hexdigest())
        self.assertEqual(row['prefixFlushedBytes'], 8)

    def test_origin_write_failure_releases_payload_before_terminal_log(self):
        self.assertEqual(self.origin(fail_write=True)['transportError'], 'OSError')

    def test_gateway_normal_blocks_do_not_overlap_and_first_body_clock_remains(self):
        row = self.gateway('normal')
        self.assertEqual(row['responseByteCount'], 16)
        self.assertTrue(row['transportCompleted'])
        self.assertIn('firstBodyChunkAt', row)

    def test_gateway_incomplete_partial_releases_payload_and_retains_failure(self):
        row = self.gateway('incomplete')
        self.assertEqual(row['responseByteCount'], 8)
        self.assertFalse(row['transportCompleted'])
        self.assertEqual(row['transportError'], 'IncompleteRead')

    def test_gateway_write_failure_releases_payload_and_retains_failure(self):
        row = self.gateway('write-failure')
        self.assertFalse(row['transportCompleted'])
        self.assertEqual(row['transportError'], 'OSError')


class ExportBodyLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.references = []

    def payload(self, raw):
        body = Payload(raw)
        self.references.append(weakref.ref(body))
        return body

    def live(self):
        return sum(reference() is not None for reference in self.references)

    def test_adjacent_exports_keep_metadata_and_release_both_bodies(self):
        written = []
        def write(data):
            written.append(bytes(data))
        def read(size):
            self.assertEqual(self.live(), 1)
            return self.payload(b'abcdefgh')
        source = SimpleNamespace(seek=lambda offset: self.assertEqual(offset, 16), read=read)
        class Input:
            def __enter__(self): return source
            def __exit__(self, *args): pass
        results = []
        for raw in (b'abcdefgh', b'abc'):
            with patch('cache_probe.read_export_body', new=lambda *args: self.payload(raw)), patch.object(Path, 'open', return_value=Input()):
                results.append(export_body_observation(Path('synthetic-export'), SimpleNamespace(write_bytes=write),
                                                      'synthetic-input', 16, 8))
            self.assertEqual(self.live(), 0, 'a key body survived into the next key/reassembly')
        self.assertEqual(written, [b'abcdefgh', b'abc'])
        self.assertEqual(results[0], dict(actualBytes=8, actualSha256=hashlib.sha256(b'abcdefgh').hexdigest(), exactInputSliceEqual=True))
        self.assertEqual(results[1], dict(actualBytes=3, actualSha256=hashlib.sha256(b'abc').hexdigest(), exactInputSliceEqual=False))

    def test_input_read_failure_releases_actual_and_preserves_failure(self):
        def fail(*args): raise OSError('synthetic input failure')
        source = SimpleNamespace(seek=lambda *args: None, read=fail)
        class Input:
            def __enter__(self): return source
            def __exit__(self, *args): pass
        with patch('cache_probe.read_export_body', new=lambda *args: self.payload(b'abcdefgh')), patch.object(Path, 'open', return_value=Input()):
            with self.assertRaisesRegex(OSError, 'synthetic input failure'):
                export_body_observation(Path('synthetic-export'), SimpleNamespace(write_bytes=lambda data: None),
                                        'synthetic-input', 0, 8)
        self.assertEqual(self.live(), 0)

    def test_export_write_failure_releases_actual_without_reading_input(self):
        def fail(*args): raise OSError('synthetic output failure')
        def forbidden_open(*args): raise AssertionError('input opened after failed export write')
        with patch('cache_probe.read_export_body', new=lambda *args: self.payload(b'abcdefgh')), patch.object(Path, 'open', new=forbidden_open):
            with self.assertRaisesRegex(OSError, 'synthetic output failure'):
                export_body_observation(Path('synthetic-export'), SimpleNamespace(write_bytes=fail), 'synthetic-input', 0, 8)
        self.assertEqual(self.live(), 0)


class CollectorLifetimeTests(unittest.TestCase):
    def request(self, incomplete=False):
        references = []
        def live(): return sum(ref() is not None for ref in references)
        def payload(raw):
            block = Payload(raw)
            references.append(weakref.ref(block))
            return block
        calls = 0
        def read(size):
            nonlocal calls
            self.assertEqual(live(), 0, 'collector next read overlaps the previous block')
            calls += 1
            if incomplete:
                raise http.client.IncompleteRead(payload(b'abcd'), 4)
            if calls == 1: return payload(b'a')
            if calls == 2: return payload(b'bcdefgh')
            return b''
        response = SimpleNamespace(code=200, headers={'Content-Length': '8'}, read=read, close=lambda: None)
        class Input:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def seek(self, offset): pass
            def read(self, size):
                self_test.assertEqual(live(), 0, 'comparison read retains a response or prior comparison block')
                return payload(b'abcdefgh')
        self_test = self
        original_open = Path.open
        def opened(path, *args, **kwargs):
            if str(path) == 'synthetic-input': return Input()
            return original_open(path, *args, **kwargs)
        def control(*args, **kwargs):
            self.assertEqual(live(), 0, 'collector control polling retains a media block')
            return dict(originRequestCount=0, objectReadCount=0, objectReadBytes=0, activeOriginRequests=0)
        def metadata(path, row):
            self.assertEqual(live(), 0, 'collector final metadata retains comparison media')
        with tempfile.TemporaryDirectory() as directory:
            collector = object.__new__(Collector)
            collector.out = Path(directory)
            (collector.out/'bodies').mkdir()
            collector.cfg = dict(maximumCollectionSeconds=30, users={'lab-user-a': 'synthetic-only'}, aclVersion='synthetic-acl',
                inputs={'base': dict(path='synthetic-input', sizeBytes=8, etag='"synthetic"',
                                    sha256=hashlib.sha256(b'abcdefgh').hexdigest())})
            import time
            collector.monotonic = time.monotonic()
            collector.entry = 'http://synthetic.invalid'
            collector.lock = threading.RLock()
            collector.control = control
            collector.rows = []
            collector.total_bytes = 0
            collector.request_active = 0
            collector.request_peak = 0
            with patch('collect.urllib.request.build_opener', return_value=SimpleNamespace(open=lambda *args, **kwargs: response)), patch.object(Path, 'open', new=opened), patch('collect.write_json', new=metadata):
                row = collector.request('stream')
            self.assertEqual(live(), 0)
            return row

    def test_response_and_comparison_blocks_end_before_control_and_metadata(self):
        row = self.request()
        self.assertEqual(row['bodyBytes'], 8)
        self.assertTrue(row['transportCompleted'])
        self.assertTrue(row['sourceIntervalComparison']['actualBytesEqual'])
        self.assertIsNotNone(row['firstBodyByteAt'])

    def test_incomplete_response_ends_before_control_and_remains_failed(self):
        row = self.request(incomplete=True)
        self.assertEqual(row['bodyBytes'], 4)
        self.assertFalse(row['transportCompleted'])
        self.assertEqual(row['transportError'], 'IncompleteRead')
        self.assertNotIn('sourceIntervalComparison', row)


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (PayloadLifetimeTests, ExportBodyLifetimeTests, CollectorLifetimeTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 11 or result.skipped:
        raise SystemExit('Expected eleven actual lifetime tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

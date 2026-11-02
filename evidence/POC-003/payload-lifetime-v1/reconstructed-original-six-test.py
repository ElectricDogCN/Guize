"""Actual Python reference lifetimes with synthetic bodies; no ATS/media run."""
import hashlib
import http.client
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from grants import Grant
from lab import Gateway, Origin, context, sign


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
        state = SimpleNamespace(cfg=cfg, lock=threading.RLock(), origin_rows={}, active_origin={}, fault=fault)
        rid = 'a' * 32
        path = '/ctx/' + context(cfg['aclVersion'], 'lab-user-a') + '/base/object.bin'
        headers = {'X-Lab-Request-ID': rid, 'X-Lab-Origin-Expiry': '1000',
                   'X-Lab-Origin-Signature': sign(cfg['secret'], path, rid, 1000)}
        stream = SimpleNamespace(seek=lambda *args: None, read=lambda *args: self.payload(), closed=False)
        def exit_stream(*args):
            stream.closed = True
        opened = SimpleNamespace(__enter__=lambda: stream)
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
        state = SimpleNamespace(cfg=cfg, version='base', lock=threading.RLock(), gateway_active=0, gateway_rows={},
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


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PayloadLifetimeTests))
    if result.testsRun != 6 or result.skipped:
        raise SystemExit('Expected six actual lifetime tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

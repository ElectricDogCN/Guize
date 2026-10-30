"""Synchronous overlap regressions with synthetic handlers, no ATS/media run."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from collect import Collector
from grants import Grant
from lab import Gateway, Origin, State, context, sign


def handler(cls, state, headers, path):
    result = object.__new__(cls)
    result.server = SimpleNamespace(state=state)
    result.headers = headers
    result.path = path
    result.send_response = lambda *args: None
    result.send_header = lambda *args: None
    result.end_headers = lambda: None
    result.wfile = SimpleNamespace(write=lambda data: len(data), flush=lambda: None)
    return result


class RequestConcurrencyTests(unittest.TestCase):
    def state(self):
        return SimpleNamespace(lock=threading.RLock(), origin_rows={}, active_origin={}, origin_active_peak=0,
            gateway_active=0, gateway_active_peak=0, gateway_rows={}, log=lambda *args: None)

    def test_origin_peak_survives_two_completed_actual_handler_intervals(self):
        state = self.state()
        state.fault = None
        state.cfg = dict(maximumOriginRequests=8, aclVersion='synthetic-acl', secret='synthetic-only', chunkBytes=8,
            inputs={'base': dict(sizeBytes=8, etag='"synthetic"', path='synthetic-input', sha256='synthetic')})
        overlap = threading.Barrier(2)
        class Input:
            def __enter__(self):
                overlap.wait(timeout=3)
                return self
            def __exit__(self, *args): pass
            def seek(self, offset): pass
            def read(self, count): return b'abcdefgh'
        path = '/ctx/'+context('synthetic-acl', 'lab-user-a')+'/base/object.bin'
        handlers = []
        for rid in ('a'*32, 'b'*32):
            headers = {'X-Lab-Request-ID':rid, 'X-Lab-Origin-Expiry':'1000',
                       'X-Lab-Origin-Signature':sign('synthetic-only', path, rid, 1000)}
            handlers.append(handler(Origin, state, headers, path))
        with patch.object(Path, 'open', new=lambda *args, **kwargs: Input()), patch('lab.time.time', return_value=999):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(item.handle_media, False) for item in handlers]
                for future in futures: future.result(timeout=5)
        observed = State.media_concurrency(state)
        self.assertEqual((observed['activeOrigin'], observed['peakOrigin']), (0, 2))
        self.assertEqual(len(state.origin_rows), 2)
        self.assertTrue(all(rows[0]['objectReadBytes']==8 for rows in state.origin_rows.values()))

    def test_gateway_peak_survives_two_completed_actual_handler_intervals(self):
        state = self.state()
        state.version = 'base'
        state.cfg = dict(users={'lab-user-a':'synthetic-only'}, aclVersion='synthetic-acl', secret='synthetic-only',
                         atsPort=1, chunkBytes=8, inputs={'base':dict(sizeBytes=8, etag='"synthetic"')})
        state.grants = {'lab-user-a':Grant('synthetic-grant','lab-user-a','2000-01-01T00:00:00Z','2100-01-01T00:00:00Z')}
        overlap = threading.Barrier(2)
        def request(*args, **kwargs): overlap.wait(timeout=3)
        def connection(*args, **kwargs):
            response = SimpleNamespace(status=200, length=0, getheader=lambda *args:None,
                                       read1=lambda size:b'', close=lambda:None)
            return SimpleNamespace(request=request, getresponse=lambda:response, close=lambda:None)
        handlers = [handler(Gateway, state, {'X-Lab-Request-ID':rid, 'X-Lab-Case':'stream',
                    'Authorization':'Bearer synthetic-only'}, '/media/object.bin') for rid in ('c'*32,'d'*32)]
        with patch('lab.http.client.HTTPConnection', new=connection):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(item.media, False) for item in handlers]
                for future in futures: future.result(timeout=5)
        observed = State.media_concurrency(state)
        self.assertEqual((observed['activeGateway'], observed['peakGateway']), (0, 2))
        self.assertTrue(all(rows[0]['atsRequestSent'] for rows in state.gateway_rows.values()))

    def collector(self, failing):
        with tempfile.TemporaryDirectory() as directory:
            collector = object.__new__(Collector)
            collector.lock = threading.Lock()
            collector.request_active = collector.request_peak = 0
            collector.out = Path(directory)
            collector.receipt = {'status':'SYNTHETIC_COMPONENT_ONLY'}
            overlap = threading.Barrier(4)
            def work(case, *args):
                overlap.wait(timeout=3)
                if case == 'fail': raise LookupError('synthetic request failure')
                return {'case':case}
            collector._request = work
            cases = ['stream']*3 + ['fail' if failing else 'stream']
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(collector.request, case) for case in cases]
                for case, future in zip(cases, futures):
                    if case == 'fail':
                        with self.assertRaisesRegex(LookupError, 'synthetic request failure'): future.result(timeout=5)
                    else: self.assertEqual(future.result(timeout=5), {'case':'stream'})
            collector.save()
            saved = json.loads((collector.out/'collection.json').read_text())
            self.assertEqual(saved['status'], 'SYNTHETIC_COMPONENT_ONLY')
            stats = saved['requestConcurrency']
            self.assertEqual((stats['active'], stats['peak']), (0, 4))
            self.assertIn('not a closed full-run claim', stats['scope'])

    def test_collector_save_retains_transient_four_request_overlap(self):
        self.collector(False)

    def test_collector_exception_ends_interval_without_erasing_peak_or_failure(self):
        self.collector(True)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RequestConcurrencyTests))
    if result.testsRun != 4 or result.skipped:
        raise SystemExit('Expected four actual concurrency tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

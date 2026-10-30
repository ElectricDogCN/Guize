"""Owned loopback HTTP worker closure and Collector admission regressions; no ATS."""
from concurrent.futures import ThreadPoolExecutor
import http.server
import json
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
import unittest

from collect import Collector
from lab import Server, State


class RequestWindowTests(unittest.TestCase):
    def server(self, cls=Server):
        entered=threading.Event();finished=threading.Event()
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                entered.set()
                try:self.connection.recv(1)
                except OSError:pass  # Expected cancellation of this owned socket.
                finally:finished.set()
        server=cls(('127.0.0.1',0),Handler,SimpleNamespace())
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01})
        thread.start()
        client=socket.create_connection(server.server_address,timeout=2)
        client.sendall(b'GET / HTTP/1.0\r\n\r\n')
        return server,thread,client,entered,finished

    def test_close_waits_for_actual_worker_teardown_and_balances_admission(self):
        server,thread,client,entered,finished=self.server()
        try:
            self.assertTrue(entered.wait(2))
            server.shutdown();server.server_close()
            self.assertFalse(finished.is_set())
            row=server.close_request_window()
            self.assertTrue(finished.is_set())
            self.assertEqual((row['admitted'],row['finished'],row['active'],row['peak']),(1,1,0,1))
            self.assertTrue(row['closed'])
        finally:
            client.close();server.shutdown();server.server_close();thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_worker_delayed_before_first_instruction_is_reserved_until_finished(self):
        scheduled=threading.Event();release=threading.Event()
        class Delayed(Server):
            def process_request_thread(self,request,address):
                scheduled.set();release.wait(3)
                super().process_request_thread(request,address)
            def handle_error(self,*args): pass
        server,thread,client,_,_=self.server(Delayed)
        try:
            self.assertTrue(scheduled.wait(2))
            server.shutdown();server.server_close()
            with self.assertRaisesRegex(TimeoutError,'not closed'):server.close_request_window(timeout=.03)
            self.assertEqual((server.requests_admitted,server.requests_finished,len(server.owned_requests)),(1,0,1))
            release.set();row=server.close_request_window(timeout=2)
            self.assertEqual((row['admitted'],row['finished'],row['active']),(1,1,0))
        finally:
            release.set();client.close();server.shutdown();server.server_close();thread.join(2)

    def test_worker_and_controller_native_close_sequences_share_one_owner(self):
        controller_entered=threading.Event();release=threading.Event()
        worker_attempted=threading.Event();worker_native_entered=threading.Event()
        outcomes=[];errors=[]
        class TrackedSocket(socket.socket):
            def shutdown(self,how):
                if threading.current_thread().name=='window-close-controller':
                    controller_entered.set();release.wait(3)
                else:worker_native_entered.set()
                return super().shutdown(how)
        class TrackedServer(Server):
            def get_request(self):
                accepted,address=super().get_request()
                return TrackedSocket(fileno=accepted.detach()),address
            def shutdown_request(self,request):
                worker_attempted.set()
                return super().shutdown_request(request)
            def handle_error(self,*args):pass
        server,thread,client,entered,finished=self.server(TrackedServer)
        def close():
            try:outcomes.append(server.close_request_window())
            except BaseException as error:errors.append(error)
        closer=threading.Thread(target=close,name='window-close-controller')
        try:
            self.assertTrue(entered.wait(2))
            server.shutdown();server.server_close();closer.start()
            self.assertTrue(controller_entered.wait(2))
            client.sendall(b'x')
            self.assertTrue(finished.wait(2));self.assertTrue(worker_attempted.wait(2))
            self.assertFalse(worker_native_entered.wait(.05),'worker entered native close while controller owned it')
            release.set();closer.join(2)
            self.assertFalse(closer.is_alive());self.assertEqual(errors,[])
            self.assertEqual((outcomes[0]['admitted'],outcomes[0]['finished'],outcomes[0]['active']),(1,1,0))
        finally:
            release.set();client.close()
            if closer.ident is not None:closer.join(2)
            server.shutdown();server.server_close();thread.join(2)

    def collector(self,directory):
        collector=object.__new__(Collector)
        collector.lock=threading.Lock();collector.out=Path(directory)
        collector.request_active=collector.request_peak=0
        collector.request_admission_closed=False;collector.request_window_closed_at=None
        collector.receipt={'status':'SYNTHETIC_COMPONENT_ONLY'}
        return collector

    def test_collector_seal_keeps_peak_and_rejects_late_request(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=self.collector(directory)
            overlap=threading.Barrier(3)
            def work(*args):overlap.wait(2);return {'synthetic':True}
            collector._request=work
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures=[pool.submit(collector.request,'synthetic') for _ in range(3)]
                self.assertTrue(all(f.result(3)=={'synthetic':True} for f in futures))
            closed=collector.close_request_window();collector.save()
            stats=json.loads((Path(directory)/'collection.json').read_text())['requestConcurrency']
            self.assertEqual((stats['active'],stats['peak']),(0,3))
            self.assertTrue(stats['admissionClosed']);self.assertEqual(stats['closedAt'],closed['closedAt'])
            with self.assertRaisesRegex(ValueError,'admission is closed'):collector.request('late')
            self.assertEqual(collector.request_peak,3)

    def test_active_collector_interval_prevents_false_seal_after_admission_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=self.collector(directory);entered=threading.Event();release=threading.Event()
            def work(*args):entered.set();release.wait(3);raise LookupError('synthetic original error')
            collector._request=work
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(collector.request,'synthetic')
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(ValueError,'remain active'):collector.close_request_window()
                collector.save();stats=json.loads((Path(directory)/'collection.json').read_text())['requestConcurrency']
                self.assertEqual(stats['active'],1);self.assertIsNone(stats['closedAt'])
                with self.assertRaisesRegex(ValueError,'admission is closed'):collector.request('late')
                release.set()
                with self.assertRaisesRegex(LookupError,'original error'):future.result(3)
            self.assertEqual(collector.close_request_window()['peak'],1)

    def test_controller_seal_requires_stopped_workers_zero_media_and_preserves_peaks(self):
        with tempfile.TemporaryDirectory() as directory:
            state=object.__new__(State)
            state.run=Path(directory);state.lock=threading.RLock()
            state.media_window_started_at='synthetic-start'
            state.ats=state.ats_epoch=None
            state.active_origin={'old':0};state.gateway_active=1
            state.origin_active_peak=4;state.gateway_active_peak=3
            windows=[{'closed':True,'admitted':2,'finished':2,'active':0}]
            with self.assertRaisesRegex(ValueError,'not closed'):state.close_media_window(windows)
            self.assertFalse((Path(directory)/'media-request-window-closed.json').exists())
            state.gateway_active=0
            with self.assertRaisesRegex(ValueError,'not closed'):state.close_media_window([{'closed':False}])
            row=state.close_media_window(windows)
            self.assertEqual((row['requestConcurrency']['peakOrigin'],row['requestConcurrency']['peakGateway']),(4,3))
            self.assertTrue(row['closed']);self.assertFalse(row['aggregateCapacityProofComplete'])
            with self.assertRaises(FileExistsError):state.close_media_window(windows)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RequestWindowTests))
    if result.testsRun!=6 or result.skipped:raise SystemExit('Expected six actual request window tests with no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

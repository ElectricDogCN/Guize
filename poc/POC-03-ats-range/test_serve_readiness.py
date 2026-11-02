"""Readiness callback ordering and real owned HTTP teardown; no ATS or media."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import lab


class ReadinessTests(unittest.TestCase):
    def state(self,directory):
        state=SimpleNamespace(run=Path(directory),cfg=dict(originPort=0,entryPort=0,atsPort=0,maximumRunSeconds=0),
            epoch_owner=None,ats=None,started=time.monotonic(),events=[],windows=None)
        def command(*args):state.events.append('verify-config')
        def start():
            state.events.append('ats-start');state.ats=SimpleNamespace(pid=123456)
        def stop():state.events.append('ats-stop');state.ats=None
        def close(windows):state.events.append('closed');state.windows=windows
        state.ats_command=command;state.start_ats=start;state.stop_ats=stop
        state.close_media_window=close;state.log=lambda *args:None
        return state

    def run_with_state(self,state,callback=None,server=lab.Server,stop_event=None):
        servers=[]
        def create(*args):
            actual=server(*args);servers.append(actual);return actual
        with patch.object(lab,'State',return_value=state),patch.object(lab,'Server',side_effect=create):
            options={} if stop_event is None else {'stop_event':stop_event}
            lab.serve(state.run,ready_callback=callback,**options)
        return servers

    def test_callback_runs_once_after_live_owned_listeners_and_marker_without_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            state=self.state(directory);seen=[];servers=[]
            original_server=lab.Server
            def create(*args):
                actual=original_server(*args);servers.append(actual);return actual
            def ready(actual):
                self.assertIs(actual,state);self.assertEqual(state.events,['verify-config','ats-start'])
                marker=json.loads((state.run/'listeners-started.json').read_text())
                self.assertEqual(marker['atsPid'],123456)
                self.assertEqual(len(servers),2)
                self.assertTrue(all(server.fileno()>=0 for server in servers))
                self.assertIsNone(sys.getprofile());self.assertIsNone(sys.gettrace())
                self.assertIsNone(threading.getprofile());self.assertIsNone(threading.gettrace())
                for server in servers:
                    with socket.create_connection(server.server_address,timeout=2):pass
                seen.append(actual)
            with patch.object(lab,'State',return_value=state),patch.object(lab,'Server',side_effect=create):
                lab.serve(state.run,ready_callback=ready)
            self.assertEqual(seen,[state]);self.assertEqual(state.events[-2:],['ats-stop','closed'])
            self.assertTrue(all(row['closed'] and row['active']==0 and row['admitted']==row['finished'] for row in state.windows))
            self.assertTrue(all(server.fileno()==-1 for server in servers))

    def test_callback_failure_propagates_after_actual_http_and_target_teardown(self):
        with tempfile.TemporaryDirectory() as directory:
            state=self.state(directory)
            def ready(actual):raise LookupError('supervisor failed')
            with self.assertRaisesRegex(LookupError,'supervisor failed'):self.run_with_state(state,ready)
            self.assertEqual(state.events[-2:],['ats-stop','closed'])
            self.assertEqual(len(state.windows),2)
            self.assertTrue(all(row['closed'] for row in state.windows))

    def test_gateway_bind_failure_does_not_call_callback_and_closes_origin(self):
        with tempfile.TemporaryDirectory() as directory,socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0));occupied.listen()
            state=self.state(directory);state.cfg['entryPort']=occupied.getsockname()[1];seen=[]
            with self.assertRaises(OSError):self.run_with_state(state,seen.append)
            self.assertEqual(seen,[]);self.assertEqual(state.events[-2:],['ats-stop','closed'])
            self.assertEqual(len(state.windows),1);self.assertTrue(state.windows[0]['closed'])
            self.assertFalse((state.run/'listeners-started.json').exists())

    def test_default_entry_needs_no_callback_and_keeps_owned_teardown(self):
        with tempfile.TemporaryDirectory() as directory:
            state=self.state(directory);self.run_with_state(state)
            self.assertTrue((state.run/'listeners-started.json').exists())
            self.assertEqual(state.events,['verify-config','ats-start','ats-stop','closed'])

    def test_cooperative_stop_consumes_inflight_response_before_teardown(self):
        # A bounded real socket exchange models a main-thread owner RPC. This
        # exercises stop ordering, not ATS execution or native owner acceptance.
        with tempfile.TemporaryDirectory() as directory:
            client,peer=socket.socketpair()
            with client,peer:
                client.settimeout(3);peer.settimeout(3)
                state=self.state(directory);state.cfg['maximumRunSeconds']=10
                state.lock=threading.Lock();stop=threading.Event()
                errors=[];requests=[];responses=[];worker=None
                def respond():
                    try:
                        request=b''
                        while len(request)<4:
                            chunk=peer.recv(4-len(request))
                            if not chunk:raise AssertionError('request channel closed early')
                            request+=chunk
                        requests.append(request)
                        stop.set()
                        self.assertNotIn('ats-stop',state.events)
                        peer.sendall(b'1')
                    except BaseException as error:errors.append(error)
                def poll():
                    client.sendall(b'poll')
                    response=client.recv(1);self.assertEqual(response,b'1')
                    responses.append(response);state.events.append('rpc-response-consumed')
                    return None
                def ready(actual):
                    nonlocal worker
                    actual.ats.poll=poll
                    worker=threading.Thread(target=respond);worker.start()
                try:self.run_with_state(state,ready,stop_event=stop)
                finally:
                    if worker is not None:worker.join(timeout=4)
                self.assertIsNotNone(worker);self.assertFalse(worker.is_alive())
                self.assertEqual(errors,[]);self.assertEqual(requests,[b'poll'])
                self.assertEqual(responses,[b'1'])
                self.assertLess(state.events.index('rpc-response-consumed'),state.events.index('ats-stop'))
                self.assertTrue(all(row['closed'] for row in state.windows))

    def test_stop_requested_before_poll_still_closes_owned_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            state=self.state(directory);state.cfg['maximumRunSeconds']=10
            stop=threading.Event()
            def ready(actual):
                def unexpected_poll():raise AssertionError('stop must be checked before the next RPC')
                actual.ats.poll=unexpected_poll;stop.set()
            self.run_with_state(state,ready,stop_event=stop)
            self.assertEqual(state.events[-2:],['ats-stop','closed'])
            self.assertTrue(all(row['closed'] for row in state.windows))

    def test_bad_callback_is_rejected_before_state_or_resource_creation(self):
        with patch.object(lab,'State') as constructor:
            with self.assertRaisesRegex(TypeError,'must be callable'):lab.serve('/unused',ready_callback=object())
            constructor.assert_not_called()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReadinessTests))
    if result.testsRun!=7 or result.skipped:raise SystemExit('Expected seven actual readiness tests with no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

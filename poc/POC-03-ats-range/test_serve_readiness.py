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

    def run_with_state(self,state,callback=None,server=lab.Server):
        servers=[]
        def create(*args):
            actual=server(*args);servers.append(actual);return actual
        with patch.object(lab,'State',return_value=state),patch.object(lab,'Server',side_effect=create):
            lab.serve(state.run,ready_callback=callback)
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

    def test_bad_callback_is_rejected_before_state_or_resource_creation(self):
        with patch.object(lab,'State') as constructor:
            with self.assertRaisesRegex(TypeError,'must be callable'):lab.serve('/unused',ready_callback=object())
            constructor.assert_not_called()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReadinessTests))
    if result.testsRun!=5 or result.skipped:raise SystemExit('Expected five actual readiness tests with no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

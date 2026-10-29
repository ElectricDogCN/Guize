"""Actual disposable Windows images/counters, never an approved metadata experiment."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

import windows_native as native


class WindowsNativeTests(unittest.TestCase):
    def supported(self):
        if os.name == 'nt':
            return True
        with self.assertRaisesRegex(native.WindowsNativeError, 'WINDOWS_NATIVE_REQUIRED'):
            native.api()
        return False

    def close(self, child):
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)
        for stream in (child.stdin, child.stdout):
            if stream:
                stream.close()
        child.close_handles()

    def test_actual_owner_command_line_and_bracketed_qpc_are_native(self):
        if not self.supported():
            return
        record = native.identity(os.getpid())
        self.assertEqual(record['nativeProcessId'], os.getpid())
        self.assertEqual(Path(record['executable']), Path(sys.executable).resolve())
        self.assertEqual(record['executableSha256'], hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())
        self.assertEqual(native.argv_for(record['nativeCommandLine']), native.actual_argv())
        self.assertEqual(record['nativeCommandLineSha256'], hashlib.sha256(record['nativeCommandLine'].encode('utf-16le')).hexdigest())
        samples = [native.clock_sample() for _ in range(32)]
        for sample in samples:
            self.assertEqual(sample['beforeNs'], sample['beforeQpc']*1000000000//sample['qpcFrequency'])
            self.assertEqual(sample['afterNs'], sample['afterQpc']*1000000000//sample['qpcFrequency'])
            self.assertLessEqual(sample['beforeQpc'], sample['afterQpc'])
            self.assertEqual(sample['wallNs'], (sample['utcFileTime100ns']-116444736000000000)*100)

    def test_actual_final_image_cannot_execute_until_its_initial_thread_is_resumed(self):
        if not self.supported():
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root/'actual image entry.bin'
            code = 'import pathlib,sys,json;pathlib.Path(sys.argv[1]).write_bytes(b"actual-entry");print(json.dumps(sys.argv[2:]),flush=True)'
            argv = [sys.executable, '-B', '-c', code, str(marker), '带空格 Unicode', 'a"b', 'trailing\\']
            with (root/'stderr').open('xb') as error:
                child = native.SuspendedProcess(argv, cwd=root, stderr=error)
                try:
                    before = native.identity(child.pid)
                    self.assertFalse(marker.exists())
                    self.assertEqual(native.argv_for(before['nativeCommandLine']), argv)
                    with self.assertRaises(subprocess.TimeoutExpired):
                        child.wait(timeout=.03)
                    result = child.resume()
                    self.assertEqual(result['previousSuspendCount'], 1)
                    self.assertEqual(child.wait(timeout=10), 0)
                    self.assertEqual(marker.read_bytes(), b'actual-entry')
                    self.assertEqual(json.loads(child.stdout.read()), argv[5:])
                    with self.assertRaisesRegex(native.WindowsNativeError, 'EXACT_UNRESUMED_PROCESS_REQUIRED'):
                        child.resume()
                finally:
                    self.close(child)

    def test_actual_separate_collector_retains_native_peak_and_rejects_wrong_identity(self):
        if not self.supported():
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = "import sys\nprint('ready',flush=True)\nfor line in sys.stdin:\n if line.strip()=='exit': break\n data=bytearray(20*1024*1024)\n for n in range(0,len(data),4096): data[n]=1\n print('grown',flush=True)"
            with (root/'stderr').open('xb') as error:
                child = native.SuspendedProcess([sys.executable, '-B', '-c', code], cwd=root, stderr=error)
                try:
                    child.resume()
                    self.assertEqual(child.stdout.readline(), b'ready\r\n')
                    identity = native.identity(child.pid)
                    expected = root/'identity.json'
                    raw = (json.dumps(identity)+'\n').encode()
                    expected.write_bytes(raw)
                    prefix = [sys.executable, '-B', str(Path(native.__file__).resolve()), '--expected', str(expected),
                              '--expected-sha256', 'sha256:'+hashlib.sha256(raw).hexdigest()]
                    samples = []
                    for number in (0, 1):
                        if number:
                            child.stdin.write(b'grow\n');child.stdin.flush()
                            self.assertEqual(child.stdout.readline(), b'grown\r\n')
                        output = root/('counter-'+str(number))
                        argv = prefix+['--pid', str(child.pid), '--output', str(output)]
                        completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
                        self.assertEqual(completed.returncode, 0, completed.stderr)
                        receipt = json.loads(completed.stdout)
                        counter = json.loads(output.read_bytes())
                        self.assertEqual(counter['ProcessId'], child.pid)
                        self.assertEqual(receipt['identity'], identity)
                        self.assertNotIn(receipt['collectorProcessId'], (child.pid, os.getpid()))
                        self.assertEqual(receipt['commandArgs'], argv)
                        self.assertEqual(receipt['counters']['peakResidentBytes'], counter['PeakWorkingSetSize'])
                        self.assertEqual(receipt['sha256'], 'sha256:'+hashlib.sha256(output.read_bytes()).hexdigest())
                        self.assertLessEqual(counter['WorkingSetSize'], counter['PeakWorkingSetSize'])
                        samples.append(counter)
                    self.assertGreater(samples[1]['PeakWorkingSetSize'], samples[0]['PeakWorkingSetSize'])
                    wrong = copy.deepcopy(identity);wrong['creationTime100ns'] += 1
                    with self.assertRaisesRegex(native.WindowsNativeError, 'NATIVE_PROCESS_BINDING_MISMATCH'):
                        native.collect(child.pid, root/'not-created', expected=wrong)
                    self.assertFalse((root/'not-created').exists())
                    with self.assertRaisesRegex(native.WindowsNativeError, 'INDEPENDENT_COLLECTOR_REQUIRED'):
                        native.collect(os.getpid(), root/'not-created', expected={})
                    child.stdin.write(b'exit\n');child.stdin.flush()
                    self.assertEqual(child.wait(timeout=5), 0)
                finally:
                    self.close(child)

    def test_actual_parent_exit_closes_job_and_kills_owned_resumed_image(self):
        if not self.supported():
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = "import os,sys,json,windows_native as n\nfrom pathlib import Path\ne=Path(sys.argv[1]).open('xb')\np=n.SuspendedProcess([sys.executable,'-B','-c',\"import time;print('ready',flush=True);time.sleep(60)\"],cwd=Path(sys.argv[1]).parent,stderr=e)\np.resume()\np.stdout.readline()\nprint(json.dumps(n.identity(p.pid)),flush=True)\nsys.stdin.readline()\nos._exit(0)\n"
            parent = subprocess.Popen([sys.executable, '-B', '-c', code, str(root/'child-stderr')],
                cwd=Path(native.__file__).parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            expected = None
            try:
                line = parent.stdout.readline()
                self.assertTrue(line, parent.stderr.read() if parent.poll() is not None else 'parent did not produce identity')
                expected = json.loads(line)
                self.assertEqual(native.identity(expected['nativeProcessId']), expected)
                parent.stdin.write(b'exit\n');parent.stdin.flush()
                self.assertEqual(parent.wait(timeout=10), 0)
                deadline = time.perf_counter()+5
                while time.perf_counter()<deadline:
                    try:
                        native.identity(expected['nativeProcessId'])
                    except native.WindowsNativeError:
                        break
                    time.sleep(.02)
                else:
                    self.fail('owned child survived parent job closure')
            finally:
                if parent.poll() is None:
                    parent.terminate();parent.wait(timeout=5)
                for stream in (parent.stdin,parent.stdout,parent.stderr):
                    stream.close()

    def test_actual_parent_exit_at_native_creation_return_kills_still_suspended_image(self):
        if not self.supported():
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root/'must-not-run'
            code = '''import ctypes,os,sys,json,windows_native as n
from pathlib import Path
actual=n.api()['CreateProcessW']
def exit_after_native_creation(*args):
 result=actual(*args)
 if not result: return result
 info=ctypes.cast(args[-1],ctypes.POINTER(n.ProcessInformation)).contents
 print(json.dumps(n.identity(info.dwProcessId)),flush=True)
 sys.stdin.readline()
 os._exit(0)
n.api()['CreateProcessW']=exit_after_native_creation
with Path(sys.argv[1]).open('xb') as error:
 n.SuspendedProcess([sys.executable,'-B','-c','from pathlib import Path;import sys;Path(sys.argv[1]).write_text("ran")',sys.argv[2]],cwd=Path(sys.argv[1]).parent,stderr=error)
'''
            parent = subprocess.Popen([sys.executable, '-B', '-c', code, str(root/'stderr'), str(marker)],
                cwd=Path(native.__file__).parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            handle = None
            try:
                line = parent.stdout.readline()
                self.assertTrue(line, parent.stderr.read() if parent.poll() is not None else 'no creation identity')
                expected = json.loads(line)
                self.assertEqual(native.identity(expected['nativeProcessId']), expected)
                handle = native.api()['OpenProcess'](0x100000 | 0x1000 | 1, False, expected['nativeProcessId'])
                self.assertTrue(handle)
                self.assertEqual(native.process_creation(handle), expected['creationTime100ns'])
                self.assertFalse(marker.exists())
                parent.stdin.write(b'exit\n');parent.stdin.flush()
                self.assertEqual(parent.wait(timeout=10), 0)
                self.assertEqual(native.api()['WaitForSingleObject'](handle, 5000), 0,
                    'suspended image survived parent exit at native creation return')
                exit_code = native.U32()
                self.assertTrue(native.api()['GetExitCodeProcess'](handle, native.c.byref(exit_code)))
                self.assertNotEqual(exit_code.value, 259)  # STILL_ACTIVE
                self.assertFalse(marker.exists())
            finally:
                if parent.poll() is None:
                    parent.terminate();parent.wait(timeout=5)
                if handle:
                    if native.api()['WaitForSingleObject'](handle, 0) == 258:
                        self.assertTrue(native.api()['TerminateProcess'](handle, 1))
                        self.assertEqual(native.api()['WaitForSingleObject'](handle, 5000), 0)
                    native.close_handle(handle)
                for stream in (parent.stdin, parent.stdout, parent.stderr):
                    stream.close()

    def test_actual_child_entry_can_precede_parent_post_resume_sample(self):
        if not self.supported():
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = "import windows_native as n,json;print(json.dumps(n.clock_sample()),flush=True)"
            with (root/'stderr').open('xb') as error:
                child = native.SuspendedProcess([sys.executable, '-B', '-c', code],
                    cwd=Path(native.__file__).parent, stderr=error)
                try:
                    actual = native.api()['ResumeThread']
                    entry = []
                    def observe_entry_before_parent_returns(thread):
                        result = actual(thread)
                        # Real scheduling interleaving: observe the child's actual
                        # QPC/UTC sample before taking the parent's post-call one.
                        entry.append(json.loads(child.stdout.readline()))
                        return result
                    with mock.patch.dict(native.api(), {'ResumeThread': observe_entry_before_parent_returns}):
                        receipt = child.resume()
                    self.assertEqual(receipt['previousSuspendCount'], 1)
                    self.assertLessEqual(receipt['resumeCallBefore']['beforeNs'], entry[0]['beforeNs'])
                    self.assertLess(entry[0]['afterNs'], receipt['resumeCallAfter']['beforeNs'])
                    self.assertEqual(child.wait(timeout=5), 0)
                finally:
                    self.close(child)


if __name__ == '__main__':
    unittest.main()

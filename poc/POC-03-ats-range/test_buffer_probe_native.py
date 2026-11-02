"""Real Linux pidfd/log-boundary tests using a simulated diagnostic child, not ATS."""
import os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from buffer_probe import capture_dump
from test_buffer_probe import fixture


class OwnedProcessDiagnosticTests(unittest.TestCase):
    def test_waits_for_new_complete_dump_after_actual_signal(self):
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            self.fail('Linux pidfd required for native regression')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Simulated child's previous table must never satisfy a new capture.
            (root / 'stderr').write_bytes(fixture())
            ready = root / 'ready'
            script = ("import os,signal,time\n"
                      "def emit(*args):\n time.sleep(.15)\n os.write(2," + repr(fixture()[:-len(b'-----------------------------------------------------------------------------------------\n')]) + ")\n time.sleep(.15)\n os.write(2,b'-----------------------------------------------------------------------------------------\\n')\n"
                      "signal.signal(signal.SIGUSR1,emit)\n"
                      "open(" + repr(str(ready)) + ",'x').close()\n"
                      "while True: time.sleep(.05)\n")
            env = dict(os.environ, PROXY_DPRINTF_LEVEL='0')
            env.pop('LD_PRELOAD', None); env.pop('LD_AUDIT', None)
            with (root / 'stderr').open('ab', buffering=0) as err:
                child = subprocess.Popen([sys.executable, '-B', '-c', script], stderr=err,
                                         stdout=subprocess.DEVNULL, env=env)
                try:
                    deadline = time.monotonic() + 3
                    while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(ready.exists(), 'simulated child did not start')
                    start = time.monotonic()
                    result = capture_dump(child, err, root / 'observation')
                    self.assertGreaterEqual(time.monotonic() - start, .28)
                    self.assertEqual(result['stderrOffset'], len(fixture()))
                    self.assertEqual(result['process']['pid'], child.pid)
                    self.assertEqual((root / 'observation/stderr-interval.raw').read_bytes(), fixture())
                    self.assertFalse(result['fullMediaBufferBoundProven'])
                finally:
                    if child.poll() is None:
                        child.terminate()
                    child.wait(timeout=3)

    def test_exited_child_is_refused_before_signalling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / 'stderr').open('ab') as err:
                child = subprocess.Popen([sys.executable, '-B', '-c', 'pass'], stderr=err)
                child.wait(timeout=3)
                with self.assertRaisesRegex(ValueError, 'exited'):
                    capture_dump(child, err, root / 'observation')


if __name__ == '__main__':
    unittest.main()

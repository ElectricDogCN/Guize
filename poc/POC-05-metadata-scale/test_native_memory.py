import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from native_memory import CounterError, collect, native_identity, parse_status, start_ticks


class NativeCounterTests(unittest.TestCase):
    def test_status_values_derive_exact_retained_native_format(self):
        raw = b"Name:\tpython\nPid:\t42\nVmHWM:\t8192 kB\nVmRSS:\t4096 kB\n"
        self.assertEqual(parse_status(raw, 42), dict(nativeProcessId=42, peakResidentBytes=8388608,
                                                   residentBytes=4194304))
        for invalid in (raw + b"Pid:\t42\n", raw.replace(b"kB", b"MB"), raw.replace(b"8192", b"2048"),
                        raw.replace(b"Pid:\t42", b"Pid:\t43"), raw.replace(b"VmRSS:\t4096 kB\n", b""),
                        raw.replace(b"8192", b"-1"), b"x" * 65537):
            with self.subTest(raw=invalid[:64]), self.assertRaises(CounterError):
                parse_status(invalid, 42)

    def test_start_ticks_parse_handles_spaces_and_parentheses_in_kernel_comm(self):
        raw = b"42 (strange ) process name) S " + b"0 " * 18 + b"12345 0 0\n"
        self.assertEqual(start_ticks(raw, 42), 12345)
        for invalid in (raw.replace(b"12345", b"0"), raw.replace(b"12345", b"-1"), b"42 (x) S", raw):
            with self.subTest(raw=invalid[:64]), self.assertRaises(CounterError):
                start_ticks(invalid, 43 if invalid == raw else 42)

    def test_self_sampling_and_invalid_or_unsupported_target_fail_explicitly(self):
        with self.assertRaisesRegex(CounterError, "INDEPENDENT_COLLECTOR_REQUIRED"):
            collect(os.getpid(), "unused-output", expected={})
        if sys.platform.startswith("linux"):
            for pid in (0, -1, True, 2**32):
                with self.subTest(pid=pid), self.assertRaisesRegex(CounterError, "INVALID_NATIVE_PROCESS_ID"):
                    native_identity(pid)
        else:
            with self.assertRaisesRegex(CounterError, "LINUX_PROC_REQUIRED"):
                native_identity(1)

    def test_independent_cli_captures_actual_linux_peak_or_rejects_unsupported_platform(self):
        collector = Path(__file__).with_name("native_memory.py")
        if not sys.platform.startswith("linux"):
            command = [sys.executable, "-B", str(collector), "--start-ticks", "1", "--boot-id", "unsupported",
                       "--exe", sys.executable, "--exe-sha256", "0" * 64, "--cmdline-sha256", "0" * 64,
                       "--pid", "1", "--output", "unused-output"]
            result = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"LINUX_PROC_REQUIRED", result.stderr)
            self.assertEqual(result.stdout, b"")
            return
        self._actual_linux_capture(collector)

    def _actual_linux_capture(self, collector):
        child_code = ("import sys\nprint('ready',flush=True)\n"
                      "for command in sys.stdin:\n"
                      " if command.strip()=='exit': break\n"
                      " data=bytearray(8*1024*1024)\n"
                      " for n in range(0,len(data),4096): data[n]=1\n"
                      " print('grown',flush=True)\n")
        with tempfile.TemporaryDirectory() as temporary:
            child = subprocess.Popen([sys.executable, "-B", "-c", child_code], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                identity = native_identity(child.pid)
                prefix = [sys.executable, "-B", str(collector), "--start-ticks", str(identity["startTicks"]),
                          "--boot-id", identity["bootId"], "--exe", identity["executable"],
                          "--exe-sha256", identity["executableSha256"],
                          "--cmdline-sha256", identity["cmdlineSha256"]]
                receipts = []
                for number in (0, 1):
                    if number:
                        child.stdin.write("grow\n")
                        child.stdin.flush()
                        self.assertEqual(child.stdout.readline().strip(), "grown")
                    output = Path(temporary) / ("counter-" + str(number) + ".raw")
                    argv = prefix + ["--pid", str(child.pid), "--output", str(output)]
                    result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    receipt = json.loads(result.stdout)
                    raw = output.read_bytes()
                    self.assertEqual(receipt["identity"], identity)
                    self.assertNotIn(receipt["collectorProcessId"], (os.getpid(), child.pid))
                    self.assertEqual(receipt["counters"], parse_status(raw, child.pid))
                    self.assertEqual(receipt["sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
                    self.assertEqual(receipt["byteCount"], len(raw))
                    self.assertEqual(receipt["commandArgs"], argv)
                    receipts.append(receipt)
                self.assertGreater(receipts[1]["observedAt"], receipts[0]["observedAt"])
                self.assertGreaterEqual(receipts[1]["counters"]["peakResidentBytes"],
                                        receipts[0]["counters"]["peakResidentBytes"] + 4*1024*1024)
                existing = Path(temporary) / "counter-0.raw"
                saved = existing.read_bytes()
                result = subprocess.run(prefix + ["--pid", str(child.pid), "--output", str(existing)],
                                        capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(existing.read_bytes(), saved)
                wrong = {**identity, "startTicks": identity["startTicks"] + 1}
                with self.assertRaisesRegex(CounterError, "NATIVE_PROCESS_BINDING_MISMATCH"):
                    collect(child.pid, Path(temporary) / "wrong.raw", expected=wrong)
                self.assertFalse((Path(temporary) / "wrong.raw").exists())
            finally:
                if child.poll() is None:
                    child.stdin.write("exit\n")
                    child.stdin.flush()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)
                for pipe in (child.stdin, child.stdout, child.stderr):
                    pipe.close()
            self.assertEqual(child.returncode, 0)
            self.assertFalse(Path("/proc", str(child.pid)).exists())


if __name__ == "__main__":
    unittest.main()

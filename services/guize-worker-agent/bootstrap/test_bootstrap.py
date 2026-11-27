"""Exercise the Worker entry point with the actual frozen GZ-008 package."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


class WorkerBootstrapTest(unittest.TestCase):
    def test_package_conformance_and_digest_rejection(self):
        builder = REPOSITORY / "specs/contracts/runtime/build_worker_sdk.py"
        with TemporaryDirectory(prefix="guize-worker-bootstrap-test-") as temporary:
            directory = Path(temporary)
            sdk = directory / "sdk.zip"
            subprocess.run([sys.executable, "-B", str(builder), str(sdk)], cwd=directory,
                           check=True, capture_output=True, timeout=15)
            command = [sys.executable, "-B", str(HERE / "bootstrap.py"), "--sdk"]
            accepted = subprocess.run([*command, str(sdk)], cwd=directory, check=True,
                                      capture_output=True, text=True, timeout=40)
            result = json.loads(accepted.stdout)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["protocolVersion"], "worker-v1")
            self.assertEqual(result["verifiedCases"], 40)

            altered = directory / "altered.zip"
            payload = sdk.read_bytes()
            altered.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
            rejected = subprocess.run([*command, str(altered)], cwd=directory,
                                      capture_output=True, text=True, timeout=10)
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(rejected.stdout, "")
            self.assertIn("SDK SHA-256 does not match", rejected.stderr)


if __name__ == "__main__":
    unittest.main()

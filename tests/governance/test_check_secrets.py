import os
import subprocess
import sys
import tempfile
import unittest

class TestCheckSecrets(unittest.TestCase):
    def _run(self, repo_root):
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "check-secrets.py"), "--repo-root", repo_root]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_no_secrets_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0)

    def test_aws_key_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            with open(os.path.join(tmpdir, "config.py"), "w") as f:
                f.write("AWS_KEY = 'AKIAEXAMPLEKEY1234567890'\n")
            subprocess.run(["git", "add", "config.py"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "add config"], cwd=tmpdir, capture_output=True)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)

if __name__ == "__main__":
    unittest.main()

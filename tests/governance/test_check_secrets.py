import os
import subprocess
import sys
import tempfile
import unittest


SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "check-secrets.py"))


class TestCheckSecrets(unittest.TestCase):
    def _run(self, repo_root):
        return subprocess.run(
            [sys.executable, SCRIPT, "--repo-root", repo_root],
            capture_output=True,
            text=True,
        )

    def _init_repo(self, directory):
        subprocess.run(["git", "init"], cwd=directory, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=directory, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=directory, check=True)

    def test_no_secrets_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_repo(tmpdir)
            with open(os.path.join(tmpdir, "README.md"), "w", encoding="utf-8") as handle:
                handle.write("safe\n")
            subprocess.run(["git", "add", "README.md"], cwd=tmpdir, check=True)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_aws_key_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_repo(tmpdir)
            secret = "AK" + "IA" + "EXAMPLEKEY123456"
            with open(os.path.join(tmpdir, "config.py"), "w", encoding="utf-8") as handle:
                handle.write(f"AWS_KEY = '{secret}'\n")
            subprocess.run(["git", "add", "config.py"], cwd=tmpdir, check=True)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)

    def test_secret_inside_tests_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._init_repo(tmpdir)
            os.makedirs(os.path.join(tmpdir, "tests"), exist_ok=True)
            secret = "gh" + "p_" + ("A" * 36)
            with open(os.path.join(tmpdir, "tests", "fixture.py"), "w", encoding="utf-8") as handle:
                handle.write(f"TOKEN = '{secret}'\n")
            subprocess.run(["git", "add", "tests/fixture.py"], cwd=tmpdir, check=True)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)

    def test_non_git_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("git grep failed", result.stdout)


if __name__ == "__main__":
    unittest.main()

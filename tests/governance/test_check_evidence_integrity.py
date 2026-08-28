import os
import subprocess
import sys
import tempfile
import unittest

class TestCheckEvidenceIntegrity(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001", report_path=None):
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "check-evidence-integrity.py"), "--task", task_id]
        if report_path:
            cmd.extend(["--report", report_path])
        return subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)

    def test_nonexistent_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(tmpdir, report_path="nonexistent.md")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Report file not found", result.stdout)

    def test_report_with_nonexistent_commits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "evidence", "GZ-001"), exist_ok=True)
            report_path = os.path.join(tmpdir, "evidence", "GZ-001", "final-report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("verifiedHead: 0000000000000000000000000000000000000000\n\n## Commits\n\n3276a1e fake commit\n")
            result = self._run(tmpdir, report_path=report_path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not exist", result.stdout)

    def test_valid_commit_in_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)
            with open(os.path.join(tmpdir, "a.txt"), "w") as f:
                f.write("hello")
            subprocess.run(["git", "add", "a.txt"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=tmpdir)
            head_sha = result.stdout.strip()
            os.makedirs(os.path.join(tmpdir, "evidence", "GZ-001"), exist_ok=True)
            report_path = os.path.join(tmpdir, "evidence", "GZ-001", "final-report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"verifiedHead: {head_sha}\n\n## Commits\n\n{head_sha[:7]} Initial commit\n")
            result = self._run(tmpdir, report_path=report_path)
            self.assertEqual(result.returncode, 0)

    def test_unreachable_commit_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)
            with open(os.path.join(tmpdir, "a.txt"), "w") as f:
                f.write("base")
            subprocess.run(["git", "add", "a.txt"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "sibling"], cwd=tmpdir, capture_output=True)
            with open(os.path.join(tmpdir, "sibling.txt"), "w") as f:
                f.write("sibling")
            subprocess.run(["git", "add", "sibling.txt"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "sibling"], cwd=tmpdir, capture_output=True)
            sibling_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmpdir, capture_output=True, text=True
            ).stdout.strip()
            subprocess.run(["git", "checkout", "--orphan", "current"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "rm", "-rf", "."], cwd=tmpdir, capture_output=True)
            with open(os.path.join(tmpdir, "current.txt"), "w") as f:
                f.write("current")
            subprocess.run(["git", "add", "current.txt"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "current"], cwd=tmpdir, capture_output=True)
            os.makedirs(os.path.join(tmpdir, "evidence", "GZ-001"), exist_ok=True)
            report_path = os.path.join(tmpdir, "evidence", "GZ-001", "final-report.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"## Commits\n\n{sibling_sha} sibling commit\n")
            result = self._run(tmpdir, report_path=report_path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("not reachable from HEAD", result.stdout)

if __name__ == "__main__":
    unittest.main()

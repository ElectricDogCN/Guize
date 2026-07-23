import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, write_evidence_file, write_task_spec


class TestCheckEvidence(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-evidence.py"),
            "--task",
            task_id,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_missing_evidence_files_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            write_evidence_file(tmpdir, "GZ-001", "README.md", "GZ-001\n")
            write_evidence_file(tmpdir, "GZ-001", "scope.md", "GZ-001\n")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)

    def test_empty_evidence_files_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            required = [
                "README.md",
                "scope.md",
                "changed-files.md",
                "commands.md",
                "test-results.md",
                "assumptions.md",
                "risks.md",
                "rollback.md",
                "follow-ups.md",
            ]
            for name in required:
                write_evidence_file(tmpdir, "GZ-001", name, "")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

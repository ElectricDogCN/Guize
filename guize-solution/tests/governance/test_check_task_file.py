import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, ensure_evidence_dir, write_task_spec


class TestCheckTaskFile(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-task-file.py"),
            "--task",
            task_id,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_valid_task_file_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_missing_task_id_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, id=None)
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)

    def test_invalid_branch_name_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, workBranch="feature/invalid-branch")
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

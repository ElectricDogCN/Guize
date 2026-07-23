import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, init_git_repo, stage_file, write_task_spec


class TestCheckTaskScope(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001", base="main"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-task-scope.py"),
            "--task",
            task_id,
            "--base",
            base,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_in_scope_changes_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_git_repo(tmpdir, "main")
            write_task_spec(tmpdir, allowed_scope="- `scripts/*.py`\n- `tests/**`")
            stage_file(tmpdir, "scripts/test.py", "print('hello')\n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_out_of_scope_changes_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_git_repo(tmpdir, "main")
            write_task_spec(tmpdir, allowed_scope="- `scripts/*.py`\n- `tests/**`")
            stage_file(tmpdir, "README.md", "# hello\n")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

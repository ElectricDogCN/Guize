import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR


class TestCheckPRTaskLink(unittest.TestCase):
    def _run(self, extra_args):
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "check-pr-task-link.py")]
        cmd.extend(extra_args)
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_pr_missing_task_id_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(["--branch", "feature/no-task-id", "--repo-root", tmpdir])
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

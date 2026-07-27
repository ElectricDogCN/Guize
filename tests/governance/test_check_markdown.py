import os
import subprocess
import sys
import tempfile
import unittest

class TestCheckMarkdown(unittest.TestCase):
    def _run(self, repo_root):
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "check-markdown.py")]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)

    def test_no_links_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.md"), "w") as f:
                f.write("# Hello\n\nThis is a test.\n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0)

    def test_trailing_whitespace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.md"), "w") as f:
                f.write("# Hello   \n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)

if __name__ == "__main__":
    unittest.main()

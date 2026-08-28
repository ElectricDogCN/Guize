import os
import subprocess
import sys
import tempfile
import unittest


SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "check-markdown.py"))


class TestCheckMarkdown(unittest.TestCase):
    def _run(self, repo_root):
        return subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=repo_root)

    def test_no_links_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.md"), "w", encoding="utf-8") as handle:
                handle.write("# Hello\n\nThis is a test.\n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0)

    def test_trailing_whitespace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.md"), "w", encoding="utf-8") as handle:
                handle.write("# Hello   \n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)

    def test_broken_internal_link_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.md"), "w", encoding="utf-8") as handle:
                handle.write("[missing](missing.md)\n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)

    def test_existing_internal_link_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "target.md"), "w", encoding="utf-8") as handle:
                handle.write("# Target\n")
            with open(os.path.join(tmpdir, "test.md"), "w", encoding="utf-8") as handle:
                handle.write("[target](target.md#section)\n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0)

    def test_github_markdown_is_not_excluded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            github_dir = os.path.join(tmpdir, ".github")
            os.makedirs(github_dir)
            with open(os.path.join(github_dir, "pull_request_template.md"), "w", encoding="utf-8") as handle:
                handle.write("broken trailing whitespace   \n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 1)
            self.assertIn(".github", result.stdout)

    def test_git_metadata_markdown_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = os.path.join(tmpdir, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "internal.md"), "w", encoding="utf-8") as handle:
                handle.write("ignored trailing whitespace   \n")
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

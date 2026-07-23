import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, init_git_repo, stage_file


class TestCheckSpecSync(unittest.TestCase):
    def _run(self, repo_root, base="main"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-spec-sync.py"),
            "--base",
            base,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_never_rules_without_changelog_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_git_repo(tmpdir, "main")
            stage_file(tmpdir, "rules/never-rules.md", "# Never Rules\n")
            stage_file(tmpdir, "rules/never-rules-changelog.md", "# Changelog\n")
            subprocess.run(
                ["git", "commit", "-m", "Add rules"],
                cwd=tmpdir,
                check=True,
                capture_output=True,
            )
            stage_file(tmpdir, "rules/never-rules.md", "# Never Rules\nUpdated\n")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

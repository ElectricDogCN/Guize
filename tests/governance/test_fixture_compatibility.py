"""Regression tests for fixtures compatibility with Python 3.11."""

import os
import sys
import tempfile
import unittest


class TestFixtureCompatibility(unittest.TestCase):
    """Test that fixtures module is compatible with Python 3.11."""

    def test_python_version_compatibility(self):
        """Verify running on Python 3.11+."""
        self.assertGreaterEqual(sys.version_info[:2], (3, 11),
            f"Requires Python 3.11+, got {sys.version_info[:2]}")

    def test_fixtures_importable(self):
        """fixtures.py must be importable on Python 3.11."""
        from tests.governance import fixtures
        self.assertIsNotNone(fixtures)
        self.assertTrue(hasattr(fixtures, 'write_task_spec'))

    def test_write_task_spec_creates_valid_file(self):
        """write_task_spec() must create a valid task spec file."""
        from tests.governance import fixtures

        with tempfile.TemporaryDirectory() as tmpdir:
            path = fixtures.write_task_spec(tmpdir, task_id="TEST-001")
            self.assertTrue(os.path.exists(path))
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn('---', content)
            self.assertIn('id: TEST-001', content)
            self.assertIn('title: Test Task', content)

    def test_front_matter_has_correct_newlines(self):
        """Front matter must have correct newline separation."""
        from tests.governance import fixtures

        with tempfile.TemporaryDirectory() as tmpdir:
            path = fixtures.write_task_spec(tmpdir, task_id="TEST-002",
                                           title="Test Title", type="bug")
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.split('\n')
            self.assertEqual(lines[0], '---')
            self.assertIn('id: TEST-002', lines[1])
            self.assertIn('title: Test Title', lines)
            self.assertIn('type: bug', lines)
            self.assertIn('---', lines)

    def test_pytest_can_collect_all_governance_tests(self):
        """Verify pytest can collect all governance tests without errors."""
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', '--collect-only', '-q', 'tests/governance/'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        self.assertEqual(result.returncode, 0,
            f"Test collection failed:\n{result.stderr}")
        self.assertIn("tests collected", result.stdout)


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DISPATCHER = os.path.join(REPO_ROOT, "scripts", "run-task-scope-gate.py")


class TestTaskScopeDispatcher(unittest.TestCase):
    def write_task(self, root, status):
        path = os.path.join(root, "specs", "tasks", "GZ-101.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                + yaml.safe_dump(
                    {"schemaVersion": 2, "id": "GZ-101", "status": status},
                    sort_keys=False,
                )
                + "---\n# Task\n"
            )

    def write_fake_checker(self, root):
        path = os.path.join(root, "fake-scope.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
        return path

    def run_dispatcher(self, root, status):
        self.write_task(root, status)
        checker = self.write_fake_checker(root)
        return subprocess.run(
            [
                sys.executable,
                DISPATCHER,
                "--repo-root",
                root,
                "--task",
                "GZ-101",
                "--base",
                "origin/main",
                "--scope-script",
                checker,
            ],
            capture_output=True,
            text=True,
        )

    def test_active_task_runs_ordinary_scope_checker(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_dispatcher(root, "in_progress")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"--task", "GZ-101"', result.stdout)
            self.assertIn('"--base", "origin/main"', result.stdout)

    def test_completed_task_is_owned_by_history_scope(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_dispatcher(root, "completed")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Program History", result.stdout)
            self.assertNotIn('"--task"', result.stdout)

    def test_unknown_status_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_dispatcher(root, "approved")
            self.assertEqual(result.returncode, 2)
            self.assertIn("Unsupported Task status", result.stdout)

    def test_missing_task_spec_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            checker = self.write_fake_checker(root)
            result = subprocess.run(
                [
                    sys.executable,
                    DISPATCHER,
                    "--repo-root",
                    root,
                    "--task",
                    "GZ-101",
                    "--base",
                    "origin/main",
                    "--scope-script",
                    checker,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Task Spec not found", result.stdout)


if __name__ == "__main__":
    unittest.main()

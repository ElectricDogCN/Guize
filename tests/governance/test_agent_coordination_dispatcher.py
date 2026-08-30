import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DISPATCHER = os.path.join(REPO_ROOT, "scripts", "run-agent-coordination-gate.py")


class TestAgentCoordinationDispatcher(unittest.TestCase):
    def write_task(self, root, status, task_id="GZ-101"):
        path = os.path.join(root, "specs", "tasks", f"{task_id}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                + yaml.safe_dump(
                    {"schemaVersion": 2, "id": task_id, "status": status},
                    sort_keys=False,
                )
                + "---\n# Task\n"
            )

    def write_program_plan(self, root, task_id="GZ-201", status="completed"):
        path = os.path.join(root, "specs", "coordination", "program-plan.yaml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(
                {"tasks": [{"taskId": task_id, "status": status}]},
                handle,
                sort_keys=False,
            )

    def write_fake_checker(self, root):
        path = os.path.join(root, "fake-checker.py")
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
                "--base-ref",
                "origin/main",
                "--head-ref",
                "HEAD",
                "--branch-name",
                "chore/GZ-101-test",
                "--coordination-script",
                checker,
            ],
            capture_output=True,
            text=True,
        )

    def test_active_task_uses_task_specific_coordination(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_dispatcher(root, "in_progress")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"--task", "GZ-101"', result.stdout)
            self.assertIn('"--base-ref", "origin/main"', result.stdout)
            self.assertIn('"--head-ref", "HEAD"', result.stdout)
            self.assertIn('"--branch-name", "chore/GZ-101-test"', result.stdout)

    def test_completed_task_uses_global_registry_mode(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_dispatcher(root, "completed")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Completion PR", result.stdout)
            self.assertNotIn('"--task"', result.stdout)
            self.assertIn('"--repo-root"', result.stdout)

    def test_unsupported_status_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_dispatcher(root, "approved")
            self.assertEqual(result.returncode, 2)
            self.assertIn("Unsupported Task status", result.stdout)

    def test_completed_program_task_rejects_approved_task_spec(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_program_plan(root, "GZ-201", "completed")
            self.write_task(root, "approved", "GZ-201")
            checker = self.write_fake_checker(root)
            result = subprocess.run(
                [
                    sys.executable,
                    DISPATCHER,
                    "--repo-root",
                    root,
                    "--coordination-script",
                    checker,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("status must be exactly completed", result.stdout)

    def test_completed_program_task_accepts_completed_task_spec(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_program_plan(root, "GZ-201", "completed")
            self.write_task(root, "completed", "GZ-201")
            checker = self.write_fake_checker(root)
            result = subprocess.run(
                [
                    sys.executable,
                    DISPATCHER,
                    "--repo-root",
                    root,
                    "--coordination-script",
                    checker,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legacy_foundation_approved_status_is_not_scanned_as_program_completion(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "specs", "coordination", "program-plan.yaml")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                yaml.safe_dump(
                    {
                        "foundationTasks": [
                            {"taskId": "GZ-001", "status": "completed"}
                        ],
                        "tasks": [],
                    },
                    handle,
                    sort_keys=False,
                )
            self.write_task(root, "approved", "GZ-001")
            checker = self.write_fake_checker(root)
            result = subprocess.run(
                [
                    sys.executable,
                    DISPATCHER,
                    "--repo-root",
                    root,
                    "--coordination-script",
                    checker,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
                    "--coordination-script",
                    checker,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Task Spec not found", result.stdout)


if __name__ == "__main__":
    unittest.main()

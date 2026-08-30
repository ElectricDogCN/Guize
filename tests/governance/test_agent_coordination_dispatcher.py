import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DISPATCHER = os.path.join(REPO_ROOT, "scripts", "run-agent-coordination-gate.py")


class TestAgentCoordinationDispatcher(unittest.TestCase):
    def program_task(self, task_id="GZ-201", status="completed"):
        return {
            "taskId": task_id,
            "title": "Completed Task",
            "status": status,
            "workPackage": "WP-TEST",
            "riskLevel": "medium",
            "coordinationGroup": "test-group",
            "wave": "W1",
            "integrationOrder": 1,
            "dependsOn": [],
            "requirementIds": ["REQ-V1-0001"],
            "moduleIds": ["MOD-TEST"],
            "producesContracts": [],
            "consumesContracts": [],
            "issue": 201,
            "exitGate": "All completion conditions are independently verified.",
        }

    def write_task(self, root, status, task_id="GZ-101", overrides=None):
        plan_task = self.program_task(task_id, status)
        document = {
            "schemaVersion": 2,
            "id": task_id,
            "titleZh": plan_task["title"],
            "status": status,
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": task_id,
            "coordinationMode": "registry",
            "workPackage": plan_task["workPackage"],
            "riskLevel": plan_task["riskLevel"],
            "coordinationGroup": plan_task["coordinationGroup"],
            "wave": plan_task["wave"],
            "integrationOrder": plan_task["integrationOrder"],
            "dependsOn": plan_task["dependsOn"],
            "requirementIds": plan_task["requirementIds"],
            "moduleIds": plan_task["moduleIds"],
            "producesContracts": plan_task["producesContracts"],
            "consumesContracts": plan_task["consumesContracts"],
            "issue": plan_task["issue"],
            "exitGate": plan_task["exitGate"],
        }
        if overrides:
            document.update(overrides)
        path = os.path.join(root, "specs", "tasks", f"{task_id}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                + yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
                + "---\n# Task\n"
            )

    def write_legacy_task(self, root, status, task_id):
        path = os.path.join(root, "specs", "tasks", f"{task_id}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                + yaml.safe_dump(
                    {"id": task_id, "status": status},
                    sort_keys=False,
                    allow_unicode=True,
                )
                + "---\n# Legacy Task\n"
            )

    def write_program_plan(self, root, task_id="GZ-201", status="completed"):
        path = os.path.join(root, "specs", "coordination", "program-plan.yaml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(
                {"tasks": [self.program_task(task_id, status)]},
                handle,
                sort_keys=False,
            )

    def write_foundation_plan(self, root, task_id="GZ-001"):
        path = os.path.join(root, "specs", "coordination", "program-plan.yaml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(
                {
                    "foundationTasks": [
                        {"taskId": task_id, "status": "completed"}
                    ],
                    "tasks": [],
                },
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

    def run_global(self, root):
        checker = self.write_fake_checker(root)
        return subprocess.run(
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
            self.write_program_plan(root)
            self.write_task(root, "approved", "GZ-201")
            result = self.run_global(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("status must be exactly completed", result.stdout)

    def test_completed_program_task_accepts_matching_completed_task_spec(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_program_plan(root)
            self.write_task(root, "completed", "GZ-201")
            result = self.run_global(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completed_program_task_rejects_wave_drift(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_program_plan(root)
            self.write_task(root, "completed", "GZ-201", {"wave": "W99"})
            result = self.run_global(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Task Spec wave does not match Program Plan wave", result.stdout)

    def test_completed_program_task_rejects_dependency_drift(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_program_plan(root)
            self.write_task(
                root,
                "completed",
                "GZ-201",
                {"dependsOn": ["GZ-999"]},
            )
            result = self.run_global(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Task Spec dependsOn does not match Program Plan", result.stdout)

    def test_completed_program_task_rejects_exit_gate_drift(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_program_plan(root)
            self.write_task(
                root,
                "completed",
                "GZ-201",
                {"exitGate": "Weaker completion gate."},
            )
            result = self.run_global(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Task Spec exitGate does not match Program Plan exitGate", result.stdout)

    def test_legacy_foundation_approved_status_is_allowed(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_foundation_plan(root, "GZ-001")
            self.write_legacy_task(root, "approved", "GZ-001")
            result = self.run_global(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema_v2_foundation_approved_status_fails(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_foundation_plan(root, "GZ-014")
            self.write_task(root, "approved", "GZ-014")
            result = self.run_global(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("status must remain completed", result.stdout)

    def test_schema_v2_foundation_completed_status_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_foundation_plan(root, "GZ-014")
            self.write_task(root, "completed", "GZ-014")
            result = self.run_global(root)
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

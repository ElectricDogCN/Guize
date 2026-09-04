import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TASK_CHECKER = os.path.join(REPO_ROOT, "scripts", "check-task-file.py")
COORDINATION = os.path.join(REPO_ROOT, "scripts", "run-agent-coordination-gate.py")
SCOPE = os.path.join(REPO_ROOT, "scripts", "run-task-scope-gate.py")


class TestProgramRegistrationDispatch(unittest.TestCase):
    def write(self, root, relative, content):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def registration_front(self):
        return {
            "schemaVersion": 2,
            "id": "OPS-006",
            "title": "Add Program Task Registration lifecycle",
            "titleZh": "建立 Program Task Registration 生命周期",
            "type": "chore",
            "status": "planned",
            "baseBranch": "main",
            "baseSha": "a" * 40,
            "workBranch": "chore/OPS-006-task-registration",
            "branchPattern": "chore/OPS-006-*",
            "evidencePath": "evidence/OPS-006",
            "issue": 52,
            "workPackage": "WP-M0-GOV-06",
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": "OPS-006",
            "wave": "W1",
            "requirementIds": "REQ-V1-0010",
            "moduleIds": "MOD-GOV",
            "producesContracts": "PROGRAM-TASK-REGISTRATION-V1",
            "consumesContracts": "NONE",
            "acceptanceIds": "NONE",
            "pocIds": "NONE",
            "exitGate": "Registration is independently verified before Reservation.",
            "taskOwner": "ElectricDogCN",
            "coordinator": "program-coordinator-agent",
            "implementer": "governance-lifecycle-agent",
            "reviewer": "independent-governance-review-agent",
            "integrator": "integration-agent",
            "agentRole": "coordinator",
            "riskLevel": "high",
            "coordinationMode": "registration",
            "coordinationGroup": "program-task-registration",
            "dependsOn": "GZ-014",
            "handoffPath": "evidence/OPS-006/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": 3,
        }

    def write_task(self, root, front=None):
        front = front or self.registration_front()
        body = """
# OPS-006

## 允许范围

- `scripts/**`

## 禁止范围

- `backend/**`

## 依赖与集成顺序

- GZ-014 completed.

## 独占写范围

- `scripts/**`

## 共享修改范围

- 无。

## 协作与交接

- Coordinator performs metadata-only Registration.

## 验收标准

- [ ] Registration passes.

## 必须执行的测试

```bash
python scripts/check-program-task-registration.py
```
"""
        self.write(root, "evidence/OPS-006/handoff.md", "# Handoff\n")
        return self.write(
            root,
            "specs/tasks/OPS-006.md",
            "---\n"
            + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
            + "---\n"
            + body,
        )

    def fake_script(self, root, name):
        return self.write(
            root,
            name,
            "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
        )

    def write_plan(self, root):
        self.write(
            root,
            "specs/coordination/program-plan.yaml",
            yaml.safe_dump(
                {"foundationTasks": [], "tasks": []}, sort_keys=False
            ),
        )

    def run_task_checker(self, root):
        return subprocess.run(
            [
                sys.executable,
                TASK_CHECKER,
                "--repo-root",
                root,
                "--task",
                "OPS-006",
            ],
            capture_output=True,
            text=True,
        )

    def test_task_file_accepts_registration_without_lease(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_task(root)
            result = self.run_task_checker(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_file_rejects_registration_lease(self):
        with tempfile.TemporaryDirectory() as root:
            front = self.registration_front()
            front["leaseExpiresAt"] = "2026-10-01T00:00:00Z"
            self.write_task(root, front)
            result = self.run_task_checker(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not contain leaseExpiresAt", result.stdout)

    def test_task_file_rejects_medium_registration(self):
        with tempfile.TemporaryDirectory() as root:
            front = self.registration_front()
            front["riskLevel"] = "medium"
            self.write_task(root, front)
            result = self.run_task_checker(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("high or critical", result.stdout)

    def test_task_file_rejects_registry_planned_alias(self):
        with tempfile.TemporaryDirectory() as root:
            front = self.registration_front()
            front["coordinationMode"] = "registry"
            front["leaseExpiresAt"] = "2026-10-01T00:00:00Z"
            self.write_task(root, front)
            result = self.run_task_checker(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Registry task has invalid status", result.stdout)

    def test_coordination_routes_planned_to_shared_validator(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_task(root)
            self.write_plan(root)
            fake = self.fake_script(root, "fake-registration.py")
            ordinary = self.fake_script(root, "fake-coordination.py")
            result = subprocess.run(
                [
                    sys.executable,
                    COORDINATION,
                    "--repo-root",
                    root,
                    "--task",
                    "OPS-006",
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "HEAD",
                    "--branch-name",
                    "chore/OPS-006-task-registration",
                    "--registration-script",
                    fake,
                    "--coordination-script",
                    ordinary,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"--base-ref", "main"', result.stdout)
            self.assertIn('"--task", "OPS-006"', result.stdout)
            self.assertNotIn("fake-coordination.py", result.stdout)

    def test_coordination_rejects_planned_registry_mode(self):
        with tempfile.TemporaryDirectory() as root:
            front = self.registration_front()
            front["coordinationMode"] = "registry"
            self.write_task(root, front)
            self.write_plan(root)
            fake = self.fake_script(root, "fake.py")
            result = subprocess.run(
                [
                    sys.executable,
                    COORDINATION,
                    "--repo-root",
                    root,
                    "--task",
                    "OPS-006",
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "HEAD",
                    "--registration-script",
                    fake,
                    "--coordination-script",
                    fake,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("coordinationMode registration", result.stdout)

    def test_scope_routes_planned_to_shared_validator(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_task(root)
            fake = self.fake_script(root, "fake-registration.py")
            ordinary = self.fake_script(root, "fake-scope.py")
            result = subprocess.run(
                [
                    sys.executable,
                    SCOPE,
                    "--repo-root",
                    root,
                    "--task",
                    "OPS-006",
                    "--base",
                    "main",
                    "--head-ref",
                    "HEAD",
                    "--branch-name",
                    "chore/OPS-006-task-registration",
                    "--registration-script",
                    fake,
                    "--scope-script",
                    ordinary,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"--base-ref", "main"', result.stdout)
            self.assertIn('"--task", "OPS-006"', result.stdout)
            self.assertNotIn("fake-scope.py", result.stdout)

    def test_scope_rejects_planned_registry_mode(self):
        with tempfile.TemporaryDirectory() as root:
            front = self.registration_front()
            front["coordinationMode"] = "registry"
            self.write_task(root, front)
            fake = self.fake_script(root, "fake.py")
            result = subprocess.run(
                [
                    sys.executable,
                    SCOPE,
                    "--repo-root",
                    root,
                    "--task",
                    "OPS-006",
                    "--base",
                    "main",
                    "--registration-script",
                    fake,
                    "--scope-script",
                    fake,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("coordinationMode registration", result.stdout)


if __name__ == "__main__":
    unittest.main()

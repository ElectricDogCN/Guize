import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRANSITION_SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-transitions.py")
AGENT_DISPATCHER = os.path.join(REPO_ROOT, "scripts", "run-agent-coordination-gate.py")
SCOPE_DISPATCHER = os.path.join(REPO_ROOT, "scripts", "run-task-scope-gate.py")
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
SPEC = importlib.util.spec_from_file_location("remaining_transitions", TRANSITION_SCRIPT)
TRANSITIONS = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(TRANSITIONS)


class TestRemainingLifecycleGuards(unittest.TestCase):
    def write_yaml(self, root, relative, document):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)

    def write_text(self, root, relative, text):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def git(self, root, *args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        )

    def init_git(self, root):
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.email", "test@example.com")
        self.git(root, "config", "user.name", "Test")

    def commit(self, root, message):
        self.git(root, "add", ".")
        self.git(root, "commit", "--allow-empty", "-m", message)
        return self.git(root, "rev-parse", "HEAD").stdout.strip()

    def foundation_plan(self):
        return {
            "foundationTasks": [
                {
                    "taskId": "GZ-014",
                    "title": "Foundation",
                    "status": "in_progress",
                    "completionRef": "ISSUE-17",
                    "mergeCommit": None,
                }
            ],
            "waves": [{"id": "W1", "order": 1}],
            "tasks": [
                {
                    "taskId": "GZ-004",
                    "title": "Requirements",
                    "status": "planned",
                    "riskLevel": "high",
                    "wave": "W1",
                    "dependsOn": ["GZ-014"],
                }
            ],
        }

    def active_entry(self, task_id="GZ-014", status="in_progress", base_sha=None):
        return {
            "taskId": task_id,
            "issue": 17 if task_id == "GZ-014" else 4,
            "title": "Foundation" if task_id == "GZ-014" else "Requirements",
            "status": status,
            "riskLevel": "high",
            "owner": "owner",
            "coordinator": "coordinator",
            "implementer": "implementer",
            "reviewer": "reviewer",
            "integrator": "integrator",
            "agentRole": "implementer",
            "branch": f"chore/{task_id}-work",
            "baseBranch": "main",
            "baseSha": base_sha or ("a" * 40),
            "workPackage": "WP-TEST",
            "programPlan": TRANSITIONS.PLAN,
            "programTaskId": task_id,
            "programWave": "FOUNDATION" if task_id == "GZ-014" else "W1",
            "requirementIds": ["REQ-V1-0010"],
            "moduleIds": ["MOD-GOV"],
            "producesContracts": [],
            "consumesContracts": [],
            "coordinationGroup": "test",
            "dependsOn": [],
            "exclusivePaths": ["scripts/**"],
            "sharedPaths": [],
            "handoffPath": f"evidence/{task_id}/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": 1,
            "lease": {
                "acquiredAt": "2026-08-30T00:00:00Z",
                "expiresAt": "2026-09-01T00:00:00Z",
            },
        }

    def task_spec(self, entry, status=None, branch=None, base_sha=None):
        front = {
            "schemaVersion": 2,
            "id": entry["taskId"],
            "status": status or entry["status"],
            "baseBranch": entry["baseBranch"],
            "baseSha": base_sha or entry["baseSha"],
            "workBranch": branch or entry["branch"],
            "issue": entry["issue"],
            "workPackage": entry["workPackage"],
            "taskOwner": entry["owner"],
            "coordinator": entry["coordinator"],
            "implementer": entry["implementer"],
            "reviewer": entry["reviewer"],
            "integrator": entry["integrator"],
            "riskLevel": entry["riskLevel"],
            "coordinationGroup": entry["coordinationGroup"],
            "handoffPath": entry["handoffPath"],
            "integrationStrategy": entry["integrationStrategy"],
            "integrationOrder": entry["integrationOrder"],
            "dependsOn": entry["dependsOn"],
            "requirementIds": entry["requirementIds"],
            "moduleIds": entry["moduleIds"],
            "producesContracts": entry["producesContracts"],
            "consumesContracts": entry["consumesContracts"],
            "coordinationMode": "registry",
        }
        body = "\n## 独占写范围\n\n- `scripts/**`\n\n## 共享修改范围\n\n- 无。\n"
        return "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + body

    def write_control_files(self, root, plan, active, ledger=None):
        self.write_yaml(root, TRANSITIONS.PLAN, plan)
        self.write_yaml(root, TRANSITIONS.ACTIVE, active)
        self.write_yaml(
            root,
            TRANSITIONS.LEDGER,
            ledger
            or {
                "$schema": "task-completions.schema.yaml",
                "schemaVersion": 1,
                "sourceOfTruth": TRANSITIONS.LEDGER,
                "records": [],
            },
        )

    def run_transition(self, root, task, branch):
        return subprocess.run(
            [
                sys.executable,
                TRANSITION_SCRIPT,
                "--repo-root",
                root,
                "--base-ref",
                "main",
                "--head-ref",
                "HEAD",
                "--task",
                task,
                "--branch-name",
                branch,
            ],
            capture_output=True,
            text=True,
        )

    def test_active_foundation_cannot_rewrite_other_program_task(self):
        with tempfile.TemporaryDirectory() as root:
            plan = self.foundation_plan()
            entry = self.active_entry()
            active = {"policy": {}, "tasks": [entry]}
            self.write_control_files(root, plan, active)
            self.write_text(root, "specs/tasks/GZ-014.md", self.task_spec(entry))
            self.init_git(root)
            self.commit(root, "base")
            self.git(root, "checkout", "-b", "chore/GZ-014-work")
            plan["tasks"][0]["riskLevel"] = "critical"
            self.write_control_files(root, plan, active)
            self.commit(root, "GZ-014 mutation")
            result = self.run_transition(root, "GZ-014", "chore/GZ-014-work")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("may only change that Foundation task's status", result.stdout)

    def test_active_foundation_unchanged_program_passes(self):
        with tempfile.TemporaryDirectory() as root:
            plan = self.foundation_plan()
            entry = self.active_entry()
            active = {"policy": {}, "tasks": [entry]}
            self.write_control_files(root, plan, active)
            self.write_text(root, "specs/tasks/GZ-014.md", self.task_spec(entry))
            self.init_git(root)
            self.commit(root, "base")
            self.git(root, "checkout", "-b", "chore/GZ-014-work")
            self.write_text(root, "scripts/allowed.py", "print('ok')\n")
            self.commit(root, "GZ-014 implementation")
            result = self.run_transition(root, "GZ-014", "chore/GZ-014-work")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def prepare_cancellation(self, root, unrelated=False, mutate_ledger=False):
        plan = self.foundation_plan()
        task = plan["tasks"][0]
        task.update(
            {
                "status": "in_progress",
                "workPackage": "WP-TEST",
                "coordinationGroup": "test",
                "integrationOrder": 1,
                "requirementIds": ["REQ-V1-0010"],
                "moduleIds": ["MOD-GOV"],
                "producesContracts": [],
                "consumesContracts": [],
                "issue": 4,
            }
        )
        entry = self.active_entry("GZ-004", "in_progress")
        active = {"policy": {"maxActiveTasks": 3}, "tasks": [entry]}
        self.write_control_files(root, plan, active)
        self.write_text(root, "specs/tasks/GZ-004.md", self.task_spec(entry))
        self.init_git(root)
        base_sha = self.commit(root, "base")
        self.git(root, "checkout", "-b", "chore/GZ-004-cancel")
        task["status"] = "cancelled"
        current_active = {"policy": {"maxActiveTasks": 3}, "tasks": []}
        ledger = {
            "$schema": "task-completions.schema.yaml",
            "schemaVersion": 1,
            "sourceOfTruth": TRANSITIONS.LEDGER,
            "records": [{"taskId": "GZ-999"}] if mutate_ledger else [],
        }
        self.write_control_files(root, plan, current_active, ledger)
        self.write_text(
            root,
            "specs/tasks/GZ-004.md",
            self.task_spec(
                entry,
                status="cancelled",
                branch="chore/GZ-004-cancel",
                base_sha=base_sha,
            ),
        )
        self.write_text(root, "evidence/GZ-004/summary.md", "GZ-004 cancelled\n")
        if unrelated:
            self.write_text(root, "backend/forbidden.txt", "bad\n")
        self.commit(root, "GZ-004 cancellation")

    def test_valid_cancellation_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare_cancellation(root)
            result = self.run_transition(root, "GZ-004", "chore/GZ-004-cancel")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cancellation_rejects_unrelated_files(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare_cancellation(root, unrelated=True)
            result = self.run_transition(root, "GZ-004", "chore/GZ-004-cancel")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed unrelated files", result.stdout)

    def test_cancellation_rejects_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare_cancellation(root, mutate_ledger=True)
            result = self.run_transition(root, "GZ-004", "chore/GZ-004-cancel")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not modify the completion ledger", result.stdout)

    def write_dispatch_task(self, root, status):
        self.write_text(
            root,
            "specs/tasks/GZ-101.md",
            "---\nid: GZ-101\nstatus: " + status + "\n---\n# Task\n",
        )
        checker = os.path.join(root, "fake.py")
        self.write_text(root, "fake.py", "import json,sys; print(json.dumps(sys.argv[1:]))\n")
        return checker

    def test_reservation_dispatches_global_coordination_and_scope(self):
        with tempfile.TemporaryDirectory() as root:
            checker = self.write_dispatch_task(root, "reserved")
            result = subprocess.run(
                [
                    sys.executable,
                    AGENT_DISPATCHER,
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
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Reservation PR", result.stdout)
            self.assertNotIn('"--task"', result.stdout)
            scope = subprocess.run(
                [
                    sys.executable,
                    SCOPE_DISPATCHER,
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
            self.assertEqual(scope.returncode, 0, scope.stdout + scope.stderr)
            self.assertIn("Reservation PR", scope.stdout)

    def test_cancelled_dispatches_metadata_lifecycle(self):
        with tempfile.TemporaryDirectory() as root:
            checker = self.write_dispatch_task(root, "cancelled")
            result = subprocess.run(
                [
                    sys.executable,
                    AGENT_DISPATCHER,
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
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Cancellation PR", result.stdout)
            scope = subprocess.run(
                [
                    sys.executable,
                    SCOPE_DISPATCHER,
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
            self.assertEqual(scope.returncode, 0, scope.stdout + scope.stderr)
            self.assertIn("Cancellation PR", scope.stdout)

    def test_workflow_uses_push_before_sha(self):
        with open(WORKFLOW, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("github.event.before", content)
        self.assertIn('BASE_REF="$PUSH_BEFORE"', content)
        self.assertIn("Program history range", content)


if __name__ == "__main__":
    unittest.main()

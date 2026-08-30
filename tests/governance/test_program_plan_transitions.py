import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-transitions.py")
SPEC = importlib.util.spec_from_file_location("program_transitions", SCRIPT)
TRANSITIONS = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(TRANSITIONS)


class TestProgramPlanTransitions(unittest.TestCase):
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

    def program_task(self, task_id, wave, status, output, depends=None):
        return {
            "taskId": task_id,
            "title": f"Task {task_id}",
            "kind": "contract",
            "status": status,
            "workPackage": f"WP-{task_id}",
            "riskLevel": "medium",
            "ownerRole": "owner-agent",
            "reviewerRole": "reviewer-agent",
            "coordinationGroup": "test-group",
            "wave": wave,
            "integrationOrder": 1,
            "dependsOn": depends or [],
            "requirementIds": ["REQ-V1-0001"],
            "moduleIds": ["MOD-TEST"],
            "outputPaths": [output],
            "sharedPaths": [],
            "producesContracts": [],
            "consumesContracts": [],
            "acceptanceIds": [],
            "pocIds": [],
            "issue": int(task_id.split("-")[1]),
            "branchPattern": f"chore/{task_id}-*",
            "exitGate": f"{task_id} is independently verified.",
        }

    def active_entry(self, task):
        task_id = task["taskId"]
        return {
            "taskId": task_id,
            "issue": task["issue"],
            "title": task["title"],
            "status": task["status"],
            "riskLevel": task["riskLevel"],
            "owner": "owner",
            "coordinator": "coordinator",
            "implementer": "implementer",
            "reviewer": "reviewer",
            "integrator": "integrator",
            "agentRole": "coordinator" if task["status"] == "reserved" else "implementer",
            "branch": f"chore/{task_id}-implementation",
            "baseBranch": "main",
            "baseSha": "a" * 40,
            "workPackage": task["workPackage"],
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": task_id,
            "programWave": task["wave"],
            "requirementIds": task["requirementIds"],
            "moduleIds": task["moduleIds"],
            "producesContracts": task["producesContracts"],
            "consumesContracts": task["consumesContracts"],
            "coordinationGroup": task["coordinationGroup"],
            "dependsOn": task["dependsOn"],
            "exclusivePaths": task["outputPaths"],
            "sharedPaths": task["sharedPaths"],
            "handoffPath": f"evidence/{task_id}/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": task["integrationOrder"],
            "lease": {
                "acquiredAt": "2026-08-30T00:00:00Z",
                "expiresAt": "2026-09-01T00:00:00Z",
            },
        }

    def documents(self):
        gz4 = self.program_task("GZ-004", "W1", "planned", "specs/gz004/**")
        gz5 = self.program_task(
            "GZ-005", "W2", "planned", "specs/gz005/**", depends=["GZ-004"]
        )
        plan = {
            "$schema": "program-plan.schema.yaml",
            "schemaVersion": 1,
            "planId": "TEST-PROGRAM",
            "status": "active",
            "baseline": "GZ-014",
            "sourceOfTruth": "specs/coordination/program-plan.yaml",
            "authority": {},
            "parallelPolicy": {},
            "foundationTasks": [],
            "waves": [
                {"id": "W1", "order": 1, "name": "one", "maxConcurrent": 2, "maxHighRisk": 1},
                {"id": "W2", "order": 2, "name": "two", "maxConcurrent": 2, "maxHighRisk": 1},
            ],
            "pocs": [],
            "tasks": [gz4, gz5],
            "externalBlockers": [],
            "releasePolicy": {},
        }
        active = {
            "version": 1,
            "policy": {
                "maxActiveTasks": 3,
                "maxHighRiskTasks": 1,
                "leaseMaxHours": 168,
                "bootstrapTasks": [],
            },
            "tasks": [],
        }
        ledger = {
            "$schema": "task-completions.schema.yaml",
            "schemaVersion": 1,
            "sourceOfTruth": "specs/coordination/task-completions.yaml",
            "records": [],
        }
        return plan, active, ledger

    def prepare_base(self, root):
        plan, active, ledger = self.documents()
        self.write_yaml(root, TRANSITIONS.PLAN, plan)
        self.write_yaml(root, TRANSITIONS.ACTIVE, active)
        self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
        self.init_git(root)
        self.commit(root, "base")
        return plan, active, ledger

    def write_reservation(self, root, plan, active, *, unrelated=False):
        task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
        task["status"] = "reserved"
        entry = self.active_entry(task)
        active["tasks"] = [entry]
        self.write_yaml(root, TRANSITIONS.PLAN, plan)
        self.write_yaml(root, TRANSITIONS.ACTIVE, active)
        self.write_text(root, "specs/tasks/GZ-004.md", "---\nid: GZ-004\n---\n")
        self.write_text(root, "evidence/GZ-004/handoff.md", "# Handoff\n")
        if unrelated:
            self.write_text(root, "backend/forbidden/code.txt", "implementation\n")
        return entry

    def run_script(self, root, task="GZ-004"):
        command = [
            sys.executable,
            SCRIPT,
            "--repo-root",
            root,
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
        ]
        if task:
            command += ["--task", task, "--branch-name", f"chore/{task}-reservation"]
        return subprocess.run(command, capture_output=True, text=True)

    def test_active_registry_scope_must_match_program(self):
        plan, active, _ = self.documents()
        task = plan["tasks"][0]
        task["status"] = "reserved"
        entry = self.active_entry(task)
        entry["exclusivePaths"] = ["backend/**"]
        active["tasks"] = [entry]
        errors = []
        TRANSITIONS.validate_active_program_scope(plan, active, errors)
        self.assertTrue(any("exclusivePaths" in error for error in errors))

    def test_later_wave_cannot_open_while_earlier_wave_is_unfinished(self):
        plan, _, _ = self.documents()
        plan["tasks"][1]["status"] = "reserved"
        errors = []
        TRANSITIONS.validate_wave_activation(plan, errors)
        self.assertTrue(any("earlier-wave tasks remain unfinished" in error for error in errors))

    def test_same_wave_tasks_may_open_together(self):
        plan, _, _ = self.documents()
        plan["tasks"][1]["wave"] = "W1"
        plan["tasks"][0]["status"] = "reserved"
        plan["tasks"][1]["status"] = "reserved"
        errors = []
        TRANSITIONS.validate_wave_activation(plan, errors)
        self.assertEqual(errors, [])

    def test_valid_reservation_transition_passes(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, _ = self.prepare_base(root)
            self.git(root, "checkout", "-b", "chore/GZ-004-reservation")
            self.write_reservation(root, plan, active)
            self.commit(root, "GZ-004 reservation (#40)")
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reservation_transition_rejects_implementation_files(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, _ = self.prepare_base(root)
            self.git(root, "checkout", "-b", "chore/GZ-004-reservation")
            self.write_reservation(root, plan, active, unrelated=True)
            self.commit(root, "GZ-004 reservation (#40)")
            result = self.run_script(root)
            self.assertIn("contains implementation or unrelated files", result.stdout)

    def test_reservation_transition_rejects_other_program_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, _ = self.prepare_base(root)
            self.git(root, "checkout", "-b", "chore/GZ-004-reservation")
            self.write_reservation(root, plan, active)
            plan["tasks"][1]["riskLevel"] = "critical"
            self.write_yaml(root, TRANSITIONS.PLAN, plan)
            self.commit(root, "GZ-004 reservation (#40)")
            result = self.run_script(root)
            self.assertIn("may only change that Program task's status", result.stdout)

    def test_recorded_reservation_commit_must_be_metadata_only(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, _ = self.prepare_base(root)
            self.git(root, "checkout", "-b", "chore/GZ-004-reservation")
            self.write_reservation(root, plan, active, unrelated=True)
            commit = self.commit(root, "GZ-004 reservation (#40)")
            errors = []
            TRANSITIONS.validate_recorded_reservation_commit(
                root,
                {
                    "taskId": "GZ-004",
                    "reservationCommit": commit,
                    "taskSpec": "specs/tasks/GZ-004.md",
                },
                errors,
            )
            self.assertTrue(any("contains implementation or unrelated files" in error for error in errors))

    def test_current_repository_passes(self):
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--repo-root",
                REPO_ROOT,
                "--base-ref",
                "origin/main",
                "--head-ref",
                "HEAD",
                "--task",
                "GZ-014",
                "--branch-name",
                "chore/GZ-014-post-merge-review-repair",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

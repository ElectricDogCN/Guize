import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "check-program-task-registration.py")
TRANSITIONS = os.path.join(REPO_ROOT, "scripts", "check-program-plan-transitions.py")
LIFECYCLE = os.path.join(REPO_ROOT, "scripts", "check-program-lifecycle-guards.py")


class RegistrationFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.plan = self.base_plan()
        self.active = {
            "version": 1,
            "policy": {
                "maxActiveTasks": 3,
                "maxHighRiskTasks": 1,
                "leaseMaxHours": 168,
                "bootstrapTasks": ["GZ-003"],
            },
            "tasks": [],
        }
        self.ledger = {
            "$schema": "task-completions.schema.yaml",
            "schemaVersion": 1,
            "sourceOfTruth": "specs/coordination/task-completions.yaml",
            "records": [],
        }
        self.write_yaml("specs/coordination/program-plan.yaml", self.plan)
        self.write_yaml("specs/coordination/active-work.yaml", self.active)
        self.write_yaml("specs/coordination/task-completions.yaml", self.ledger)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.commit("base")
        self.base_sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-b", "chore/OPS-006-task-registration")
        self.add_valid_registration()
        self.commit("OPS-006 registration (#52)")

    def close(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", message)

    def write_text(self, relative, content):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def write_yaml(self, relative, document):
        self.write_text(
            relative,
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        )

    def base_plan(self):
        return {
            "$schema": "program-plan.schema.yaml",
            "schemaVersion": 1,
            "planId": "TEST-PROGRAM",
            "status": "active",
            "baseline": "GZ-014",
            "sourceOfTruth": "specs/coordination/program-plan.yaml",
            "authority": {},
            "parallelPolicy": {
                "maxActiveTasks": 3,
                "maxHighRiskTasks": 1,
                "criticalStandalone": True,
                "reservationRequired": True,
                "independentReviewForHighRisk": True,
            },
            "foundationTasks": [
                {
                    "taskId": "GZ-014",
                    "title": "Foundation",
                    "status": "completed",
                    "completionRef": "PR-32",
                    "mergeCommit": "a" * 40,
                }
            ],
            "waves": [
                {
                    "id": "W1",
                    "order": 1,
                    "name": "one",
                    "maxConcurrent": 2,
                    "maxHighRisk": 1,
                },
                {
                    "id": "W17",
                    "order": 17,
                    "name": "release",
                    "maxConcurrent": 1,
                    "maxHighRisk": 1,
                },
            ],
            "pocs": [],
            "tasks": [
                self.task(
                    "GZ-004",
                    "W1",
                    "completed",
                    [],
                    "specs/requirements/**",
                    "requirements",
                    "medium",
                ),
                self.task(
                    "GZ-020",
                    "W17",
                    "planned",
                    ["GZ-004"],
                    "release/**",
                    "release",
                    "critical",
                ),
            ],
            "externalBlockers": [],
            "releasePolicy": {"requiredFinalTask": "GZ-020"},
        }

    def task(self, task_id, wave, status, depends, output, kind, risk):
        number = int(task_id.split("-")[1])
        return {
            "taskId": task_id,
            "title": (
                "建立 Program Registration 生命周期"
                if task_id == "OPS-006"
                else f"Task {task_id}"
            ),
            "kind": kind,
            "status": status,
            "workPackage": f"WP-{task_id}",
            "riskLevel": risk,
            "ownerRole": (
                "governance-lifecycle-agent"
                if task_id == "OPS-006"
                else "owner-agent"
            ),
            "reviewerRole": (
                "independent-governance-review-agent"
                if task_id == "OPS-006"
                else "reviewer-agent"
            ),
            "coordinationGroup": (
                "program-registration"
                if task_id == "OPS-006"
                else "test-group"
            ),
            "wave": wave,
            "integrationOrder": 3 if task_id == "OPS-006" else number,
            "dependsOn": depends,
            "requirementIds": ["REQ-V1-0010"],
            "moduleIds": ["MOD-GOV"],
            "outputPaths": [output],
            "sharedPaths": [],
            "producesContracts": (
                ["PROGRAM-TASK-REGISTRATION-V1"]
                if task_id == "OPS-006"
                else []
            ),
            "consumesContracts": [],
            "acceptanceIds": ["ACC-OPS-006"] if task_id == "OPS-006" else [],
            "pocIds": [],
            "issue": 52 if task_id == "OPS-006" else number,
            "branchPattern": f"chore/{task_id}-*",
            "exitGate": f"{task_id} is independently verified before Reservation.",
        }

    def task_spec(self, task):
        fields = {
            "schemaVersion": 2,
            "id": task["taskId"],
            "title": "Add Program Task Registration lifecycle",
            "titleZh": task["title"],
            "type": "chore",
            "status": "planned",
            "baseBranch": "main",
            "baseSha": self.base_sha,
            "workBranch": "chore/OPS-006-task-registration",
            "branchPattern": task["branchPattern"],
            "evidencePath": "evidence/OPS-006",
            "issue": task["issue"],
            "workPackage": task["workPackage"],
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": task["taskId"],
            "wave": task["wave"],
            "requirementIds": task["requirementIds"],
            "moduleIds": task["moduleIds"],
            "producesContracts": task["producesContracts"],
            "consumesContracts": task["consumesContracts"],
            "acceptanceIds": task["acceptanceIds"],
            "pocIds": task["pocIds"],
            "exitGate": task["exitGate"],
            "taskOwner": "ElectricDogCN",
            "coordinator": "program-coordinator-agent",
            "implementer": task["ownerRole"],
            "reviewer": task["reviewerRole"],
            "integrator": "integration-agent",
            "agentRole": "coordinator",
            "riskLevel": task["riskLevel"],
            "coordinationMode": "registration",
            "coordinationGroup": task["coordinationGroup"],
            "dependsOn": task["dependsOn"],
            "handoffPath": "evidence/OPS-006/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": task["integrationOrder"],
        }
        return (
            "---\n"
            + yaml.safe_dump(fields, sort_keys=False, allow_unicode=True)
            + "---\n\n# OPS-006\n\n"
            + "## 允许范围\n\n- `scripts/**`\n\n"
            + "## 禁止范围\n\n- `backend/**`\n\n"
            + "## 依赖与集成顺序\n\n- GZ-014 completed.\n\n"
            + "## 独占写范围\n\n- `scripts/**`\n\n"
            + "## 共享修改范围\n\n- 无。\n\n"
            + "## 协作与交接\n\n- Coordinator registers metadata only.\n\n"
            + "## 验收标准\n\n- [ ] Registration passes.\n\n"
            + "## 必须执行的测试\n\n```bash\n"
            + "python scripts/check-program-task-registration.py\n```\n"
        )

    def add_valid_registration(self):
        task = self.task(
            "OPS-006",
            "W1",
            "planned",
            ["GZ-014"],
            "scripts/**",
            "governance",
            "high",
        )
        self.plan["tasks"].insert(1, task)
        self.plan["tasks"][-1]["dependsOn"].append("OPS-006")
        self.write_yaml("specs/coordination/program-plan.yaml", self.plan)
        self.write_text("specs/tasks/OPS-006.md", self.task_spec(task))
        self.write_text(
            "evidence/OPS-006/handoff.md",
            "# Handoff\nTask: OPS-006\n",
        )

    def run(
        self,
        script=VALIDATOR,
        task="OPS-006",
        branch="chore/OPS-006-task-registration",
    ):
        command = [
            sys.executable,
            script,
            "--repo-root",
            self.root,
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
        ]
        if task:
            command += ["--task", task]
        if branch:
            command += ["--branch-name", branch]
        return subprocess.run(command, capture_output=True, text=True)

    def prove_then_mutate(self, mutate):
        baseline = self.run()
        if baseline.returncode != 0:
            raise AssertionError(baseline.stdout + baseline.stderr)
        mutate()
        self.commit("negative mutation")
        return self.run()

    def rewrite_task_front(self, change):
        path = os.path.join(self.root, "specs/tasks/OPS-006.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        parts = text.split("---", 2)
        front = yaml.safe_load(parts[1])
        change(front)
        self.write_text(
            "specs/tasks/OPS-006.md",
            "---\n"
            + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
            + "---"
            + parts[2],
        )


class TestProgramTaskRegistration(unittest.TestCase):
    def fixture(self):
        fixture = RegistrationFixture()
        self.addCleanup(fixture.close)
        return fixture

    def test_valid_task_aware_registration_passes(self):
        fixture = self.fixture()
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_push_mode_registration_passes(self):
        fixture = self.fixture()
        result = fixture.run(task="", branch="")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_transition_and_lifecycle_use_same_validator(self):
        fixture = self.fixture()
        for script in (TRANSITIONS, LIFECYCLE):
            result = fixture.run(script=script)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Registration", result.stdout)

    def test_multiple_new_tasks_fail(self):
        fixture = self.fixture()

        def mutate():
            task = fixture.task(
                "OPS-007",
                "W1",
                "planned",
                ["GZ-014"],
                "docs/**",
                "governance",
                "high",
            )
            fixture.plan["tasks"].insert(2, task)
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one", result.stdout)

    def test_medium_risk_fails(self):
        fixture = self.fixture()

        def mutate():
            next(
                task
                for task in fixture.plan["tasks"]
                if task["taskId"] == "OPS-006"
            )["riskLevel"] = "medium"
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("high or critical", result.stdout)

    def test_missing_task_spec_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: os.remove(
                os.path.join(fixture.root, "specs/tasks/OPS-006.md")
            )
        )
        self.assertNotEqual(result.returncode, 0)

    def test_wrong_task_status_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__("status", "reserved")
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status must be planned", result.stdout)

    def test_wrong_coordination_mode_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "coordinationMode", "registry"
                )
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("coordinationMode", result.stdout)

    def test_lease_field_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "leaseExpiresAt", "2026-10-01T00:00:00Z"
                )
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("leaseExpiresAt", result.stdout)

    def test_task_identity_mismatch_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__("workPackage", "WRONG")
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workPackage", result.stdout)

    def test_branch_mismatch_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "workBranch", "chore/OPS-006-other"
                )
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("actual branch", result.stdout)

    def test_base_mismatch_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__("baseSha", "b" * 40)
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("base identity", result.stdout)

    def test_active_work_drift_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.active["tasks"] = [{"taskId": "OPS-006"}]
            fixture.write_yaml(
                "specs/coordination/active-work.yaml", fixture.active
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Active Work", result.stdout)

    def test_completion_ledger_drift_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.ledger["records"] = [{"taskId": "OPS-006"}]
            fixture.write_yaml(
                "specs/coordination/task-completions.yaml", fixture.ledger
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Completion Ledger", result.stdout)

    def test_unrelated_file_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.write_text("backend/forbidden.txt", "x\n")
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrelated files", result.stdout)

    def test_existing_task_field_mutation_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["riskLevel"] = "high"
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("may not mutate", result.stdout)

    def test_dependency_reorder_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["dependsOn"] = [
                "OPS-006",
                "GZ-004",
            ]
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tail append", result.stdout)

    def test_attachment_to_non_planned_task_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["status"] = "in_progress"
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must remain planned", result.stdout)

    def test_cycle_fails(self):
        fixture = self.fixture()

        def mutate():
            next(
                task
                for task in fixture.plan["tasks"]
                if task["taskId"] == "OPS-006"
            )["dependsOn"] = ["GZ-020"]
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )
            fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "dependsOn", ["GZ-020"]
                )
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cycle", result.stdout)

    def test_missing_final_closure_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["dependsOn"] = ["GZ-004"]
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("final-task closure", result.stdout)

    def test_rename_escape_fails(self):
        fixture = self.fixture()

        def mutate():
            os.makedirs(os.path.join(fixture.root, "backend"), exist_ok=True)
            fixture.git(
                "mv",
                "evidence/OPS-006/handoff.md",
                "backend/handoff.md",
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrelated files", result.stdout)

    def test_symlink_fails(self):
        fixture = self.fixture()

        def mutate():
            path = os.path.join(fixture.root, "evidence/OPS-006/link")
            os.symlink("../../specs/coordination/program-plan.yaml", path)

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlinks", result.stdout)

    def test_duplicate_front_key_fails(self):
        fixture = self.fixture()

        def mutate():
            path = os.path.join(fixture.root, "specs/tasks/OPS-006.md")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            fixture.write_text(
                "specs/tasks/OPS-006.md",
                text.replace(
                    "status: planned\n",
                    "status: planned\nstatus: planned\n",
                    1,
                ),
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unique keys", result.stdout)

    def test_combined_registration_and_reservation_fails(self):
        fixture = self.fixture()

        def mutate():
            next(
                task
                for task in fixture.plan["tasks"]
                if task["taskId"] == "OPS-006"
            )["status"] = "reserved"
            fixture.write_yaml(
                "specs/coordination/program-plan.yaml", fixture.plan
            )

        result = fixture.prove_then_mutate(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status must be planned", result.stdout)


if __name__ == "__main__":
    unittest.main()

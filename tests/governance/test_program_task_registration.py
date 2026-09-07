import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "check-program-task-registration.py")
TRANSITIONS = os.path.join(REPO_ROOT, "scripts", "check-program-plan-transitions.py")
LIFECYCLE = os.path.join(REPO_ROOT, "scripts", "check-program-lifecycle-guards.py")
TRANSITIONS_CORE = os.path.join(
    REPO_ROOT, "scripts", "check-program-plan-transitions-core.py"
)
LIFECYCLE_CORE = os.path.join(
    REPO_ROOT, "scripts", "check-program-lifecycle-guards-core.py"
)
TRANSITIONS_CORE_SHA = "89a0e302904b12e1f3c33fbc180af1ba3b81090e"
LIFECYCLE_CORE_SHA = "cd1242fbdd8959376635d25e4f4cb4aefa0fa11a"


class RegistrationFixture:
    task_id = "OPS-006"
    branch = "chore/OPS-006-task-registration"

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
        self.init_git()
        self.write_yaml("specs/coordination/program-plan.yaml", self.plan)
        self.write_yaml("specs/coordination/active-work.yaml", self.active)
        self.write_yaml("specs/coordination/task-completions.yaml", self.ledger)
        self.write_text(
            "specs/tasks/task-template.md",
            "# Task template\n\nUse schemaVersion 2.\n",
        )
        self.write_text("private-source.txt", "sensitive-source-copy-test\n")
        self.copy_file(VALIDATOR, "scripts/check-program-task-registration.py")
        self.write_text(
            "scripts/check-agent-coordination.py",
            "import sys\nprint('ordinary coordination')\nsys.exit(0)\n",
        )
        self.write_text(
            "scripts/check-task-scope.py",
            "import sys\nprint('ordinary scope')\nsys.exit(0)\n",
        )
        self.commit("base")
        self.base_sha = self.rev_parse("HEAD")
        self.git("checkout", "-b", self.branch)
        self.add_valid_registration()
        self.commit("OPS-006 registration (#52)")
        self.source_sha = self.rev_parse("HEAD")

    def close(self):
        self.temp.cleanup()

    def init_git(self):
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")

    def git(self, *args, check=True):
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=check,
            capture_output=True,
            text=True,
        )

    def rev_parse(self, ref):
        return self.git("rev-parse", ref).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", message)
        return self.rev_parse("HEAD")

    def write_text(self, relative, content):
        path = os.path.join(self.root, relative)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def copy_file(self, source, relative):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(source, path)
        return path

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
                    "specs/requirements/v1/**",
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
                if task_id == self.task_id
                else f"Task {task_id}"
            ),
            "kind": kind,
            "status": status,
            "workPackage": f"WP-{task_id}",
            "riskLevel": risk,
            "ownerRole": (
                "governance-lifecycle-agent"
                if task_id == self.task_id
                else "owner-agent"
            ),
            "reviewerRole": (
                "independent-governance-review-agent"
                if task_id == self.task_id
                else "reviewer-agent"
            ),
            "coordinationGroup": (
                "program-registration"
                if task_id == self.task_id
                else "test-group"
            ),
            "wave": wave,
            "integrationOrder": 3 if task_id == self.task_id else number,
            "dependsOn": depends,
            "requirementIds": ["REQ-V1-0010"],
            "moduleIds": ["MOD-GOV"],
            "outputPaths": [output],
            "sharedPaths": [],
            "producesContracts": (
                ["PROGRAM-TASK-REGISTRATION-V1"]
                if task_id == self.task_id
                else []
            ),
            "consumesContracts": [],
            "acceptanceIds": ["ACC-OPS-006"] if task_id == self.task_id else [],
            "pocIds": [],
            "issue": 52 if task_id == self.task_id else number,
            "branchPattern": f"chore/{task_id}-*",
            "exitGate": f"{task_id} is independently verified before Reservation.",
        }

    def task_spec_fields(self, task):
        return {
            "schemaVersion": 2,
            "id": task["taskId"],
            "title": "Add Program Task Registration lifecycle",
            "titleZh": task["title"],
            "type": "chore",
            "status": "planned",
            "baseBranch": "main",
            "baseSha": self.base_sha,
            "workBranch": self.branch,
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

    def task_spec(self, task, fields=None):
        fields = fields or self.task_spec_fields(task)
        scope = task["outputPaths"][0]
        return (
            "---\n"
            + yaml.safe_dump(fields, sort_keys=False, allow_unicode=True)
            + "---\n\n# OPS-006\n\n"
            + f"## 允许范围\n\n- `{scope}`\n\n"
            + "## 禁止范围\n\n- `backend/**`\n\n"
            + "## 依赖与集成顺序\n\n- GZ-014 completed.\n\n"
            + f"## 独占写范围\n\n- `{scope}`\n\n"
            + "## 共享修改范围\n\n- 无。\n\n"
            + "## 协作与交接\n\n- Coordinator registers metadata only.\n\n"
            + "## 验收标准\n\n- [ ] Registration passes.\n\n"
            + "## 必须执行的测试\n\n```bash\n"
            + "python scripts/check-program-task-registration.py\n```\n"
        )

    def write_canonical_evidence(self):
        task = self.task_id
        self.write_text(
            f"evidence/{task}/summary.md",
            f"# Summary\n\nTask: {task}\nStatus: CANDIDATE\n",
        )
        self.write_text(
            f"evidence/{task}/commands.txt",
            f"Task: {task}\nCommand: python scripts/check-program-task-registration.py\nExit Code: 0\nResult: PASS\n",
        )
        self.write_text(
            f"evidence/{task}/test-results/README.md",
            f"# Tests\n\nTask: {task}\nResult: PASS\n",
        )
        self.write_text(
            f"evidence/{task}/rollback-verification/README.md",
            f"# Rollback\n\nTask: {task}\n\n```bash\ngit revert --no-edit <merge-sha>\n```\n",
        )
        for name, text in {
            "scope.md": "Scope is metadata only.",
            "changed-files.md": "Program, Task Spec and Evidence only.",
            "assumptions.md": "Target main exists.",
            "risks.md": "Invalid Registration remains fail-closed.",
            "follow-ups.md": "Reservation is the next separate phase.",
        }.items():
            self.write_text(
                f"evidence/{task}/{name}",
                f"# {name}\n\nTask: {task}\n{text}\n",
            )
        self.write_text(
            f"evidence/{task}/EVIDENCE-STRUCTURE.md",
            "# Evidence compatibility\n\n"
            "| Canonical | Compatible | Reason |\n"
            "|---|---|---|\n"
            "| `screenshots/` | N/A | Metadata validation has no user interface. |\n"
            "| `api-samples/` | N/A | Metadata validation exposes no API. |\n"
            "| `migration-report/` | N/A | Registration changes no data schema. |\n"
            "| `performance/` | N/A | No runtime performance claim is made. |\n"
            "| `security/` | N/A | Security behavior is covered by fail-closed tests. |\n",
        )
        self.write_text(
            f"evidence/{task}/handoff.md",
            f"# Handoff\n\nTask: {task}\nNext: independent Registration review.\n",
        )

    def add_valid_registration(self):
        task = self.task(
            self.task_id,
            "W1",
            "planned",
            ["GZ-014"],
            "scripts/program-registration/**",
            "governance",
            "high",
        )
        self.plan["tasks"].insert(1, task)
        self.plan["tasks"][-1]["dependsOn"].append(self.task_id)
        self.write_yaml("specs/coordination/program-plan.yaml", self.plan)
        self.write_text(
            f"specs/tasks/{self.task_id}.md", self.task_spec(task)
        )
        self.write_canonical_evidence()

    def run(
        self,
        script=VALIDATOR,
        task="OPS-006",
        branch="chore/OPS-006-task-registration",
        base_ref="main",
        head_ref="HEAD",
    ):
        command = [
            sys.executable,
            script,
            "--repo-root",
            self.root,
            "--base-ref",
            base_ref,
            "--head-ref",
            head_ref,
        ]
        if task:
            command += ["--task", task]
        if branch:
            command += ["--branch-name", branch]
        return subprocess.run(command, capture_output=True, text=True)

    def prove_then_mutate(self, mutate, contains=None):
        baseline = self.run()
        if baseline.returncode != 0:
            raise AssertionError(baseline.stdout + baseline.stderr)
        mutate()
        self.commit("negative mutation")
        result = self.run()
        if contains:
            if result.returncode == 0 or contains not in result.stdout:
                raise AssertionError(result.stdout + result.stderr)
        return result

    def rewrite_task_front(self, change):
        path = os.path.join(self.root, f"specs/tasks/{self.task_id}.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        parts = text.split("---", 2)
        front = yaml.safe_load(parts[1])
        change(front)
        self.write_text(
            f"specs/tasks/{self.task_id}.md",
            "---\n"
            + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
            + "---"
            + parts[2],
        )

    def rewrite_task_text(self, transform):
        relative = f"specs/tasks/{self.task_id}.md"
        path = os.path.join(self.root, relative)
        with open(path, encoding="utf-8") as handle:
            self.write_text(relative, transform(handle.read()))

    def registration_task(self):
        return next(
            task for task in self.plan["tasks"] if task["taskId"] == self.task_id
        )

    def merge_to_main(self):
        self.source_sha = self.rev_parse("HEAD")
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "--no-edit", self.branch)
        return self.rev_parse("HEAD")


class TestProgramTaskRegistration(unittest.TestCase):
    def fixture(self):
        fixture = RegistrationFixture()
        self.addCleanup(fixture.close)
        return fixture

    def assert_failed(self, result, text=None):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        if text:
            self.assertIn(text, result.stdout)

    def test_valid_task_aware_registration_passes(self):
        fixture = self.fixture()
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_aware_pr_merge_ref_provenance_passes(self):
        fixture = self.fixture()
        fixture.merge_to_main()
        result = fixture.run(
            task=fixture.task_id,
            branch=fixture.branch,
            base_ref=fixture.base_sha,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_push_mode_merge_registration_passes(self):
        fixture = self.fixture()
        fixture.merge_to_main()
        result = fixture.run(task="", branch="", base_ref=fixture.base_sha)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("push/no-task", result.stdout)

    def test_push_mode_direct_push_fails(self):
        fixture = self.fixture()
        fixture.git("checkout", "main")
        fixture.git("merge", "--ff-only", fixture.branch)
        result = fixture.run(task="", branch="", base_ref=fixture.base_sha)
        self.assert_failed(result, "two-parent merge")

    def test_push_mode_missing_source_branch_fails(self):
        fixture = self.fixture()
        fixture.merge_to_main()
        fixture.git("branch", "-D", fixture.branch)
        result = fixture.run(task="", branch="", base_ref=fixture.base_sha)
        self.assert_failed(result, "source branch ref")

    def test_transition_and_lifecycle_use_same_validator(self):
        fixture = self.fixture()
        for script in (TRANSITIONS, LIFECYCLE):
            result = fixture.run(script=script)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Registration", result.stdout)

    def test_merge_anchor_and_explicit_override_pass(self):
        fixture = self.fixture()

        def transform(text):
            parts = text.split("---", 2)
            front = yaml.safe_load(parts[1])
            payload = yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
            return (
                "---\n"
                "registrationDefaults: &registrationDefaults\n"
                "  agentRole: implementer\n"
                "  riskLevel: medium\n"
                "<<: *registrationDefaults\n"
                + payload
                + "---"
                + parts[2]
            )

        fixture.rewrite_task_text(transform)
        fixture.commit("use merge anchor")
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_explicit_front_key_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.rewrite_task_text(
                lambda text: text.replace(
                    "status: planned\n",
                    "status: planned\nstatus: planned\n",
                    1,
                )
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "unique explicit keys")

    def test_duplicate_new_task_rows_fail(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"].insert(2, dict(fixture.registration_task()))
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "duplicate task IDs")

    def test_multiple_new_tasks_fail(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"].insert(
                2,
                fixture.task(
                    "OPS-007",
                    "W1",
                    "planned",
                    ["GZ-014"],
                    "docs/ops007/**",
                    "governance",
                    "high",
                ),
            )
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "exactly one")

    def test_existing_planned_task_cannot_masquerade_as_registration(self):
        fixture = self.fixture()
        fixture.write_text(
            "evidence/OPS-006/follow-ups.md",
            "# Follow-ups\n\nTask: OPS-006\nNo additional phase.\n",
        )
        fixture.commit("evidence-only follow-up")
        result = fixture.run(base_ref="HEAD^")
        self.assert_failed(result, "not an absent-to-planned")

    def test_medium_risk_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.registration_task()["riskLevel"] = "medium"
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "high or critical")

    def test_missing_task_spec_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: os.remove(
                os.path.join(fixture.root, "specs/tasks/OPS-006.md")
            )
        )
        self.assert_failed(result, "exactly one canonical Task Spec")

    def test_wrong_task_status_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__("status", "reserved")
            )
        )
        self.assert_failed(result, "status must be planned")

    def test_wrong_coordination_mode_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "coordinationMode", "registry"
                )
            )
        )
        self.assert_failed(result, "coordinationMode")

    def test_lease_field_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "leaseExpiresAt", "2026-10-01T00:00:00Z"
                )
            )
        )
        self.assert_failed(result, "leaseExpiresAt")

    def test_task_identity_mismatch_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__("workPackage", "WRONG")
            )
        )
        self.assert_failed(result, "workPackage")

    def test_branch_mismatch_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__(
                    "workBranch", "chore/OPS-006-other"
                )
            )
        )
        self.assert_failed(result, "actual branch")

    def test_task_aware_missing_branch_fails(self):
        fixture = self.fixture()
        result = fixture.run(branch="")
        self.assert_failed(result, "authoritative branch name")

    def test_base_mismatch_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.rewrite_task_front(
                lambda document: document.__setitem__("baseSha", "b" * 40)
            )
        )
        self.assert_failed(result, "base identity")

    def test_active_work_drift_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.active["tasks"] = [{"taskId": "OPS-006"}]
            fixture.write_yaml("specs/coordination/active-work.yaml", fixture.active)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "Active Work")

    def test_completion_ledger_drift_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.ledger["records"] = [{"taskId": "OPS-006"}]
            fixture.write_yaml(
                "specs/coordination/task-completions.yaml", fixture.ledger
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "Completion Ledger")

    def test_unrelated_file_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.write_text("backend/forbidden.txt", "x\n")
        )
        self.assert_failed(result, "unrelated files")

    def test_existing_task_field_mutation_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["riskLevel"] = "high"
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "may not mutate")

    def test_dependency_reorder_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["dependsOn"] = ["OPS-006", "GZ-004"]
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "tail append")

    def test_duplicate_dependency_append_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["dependsOn"].append("OPS-006")
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "tail append")

    def test_attachment_to_non_planned_task_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["status"] = "in_progress"
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "must remain planned")

    def test_unknown_dependency_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.registration_task()["dependsOn"] = ["GZ-999"]
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)
            fixture.rewrite_task_front(
                lambda document: document.__setitem__("dependsOn", ["GZ-999"])
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "does not exist")

    def test_cycle_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.registration_task()["dependsOn"] = ["GZ-020"]
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)
            fixture.rewrite_task_front(
                lambda document: document.__setitem__("dependsOn", ["GZ-020"])
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "cycle")

    def test_missing_final_closure_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.plan["tasks"][-1]["dependsOn"] = ["GZ-004"]
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "final-task closure")

    def test_rename_escape_fails(self):
        fixture = self.fixture()

        def mutate():
            os.makedirs(os.path.join(fixture.root, "backend"), exist_ok=True)
            fixture.git(
                "mv", "evidence/OPS-006/handoff.md", "backend/handoff.md"
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "unrelated files")

    @unittest.skipIf(not hasattr(os, "symlink"), "symlink unavailable")
    def test_symlink_fails(self):
        fixture = self.fixture()

        def mutate():
            os.symlink(
                "../../specs/coordination/program-plan.yaml",
                os.path.join(fixture.root, "evidence/OPS-006/link"),
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "symlinks")

    def test_copy_from_unrelated_tracked_source_fails(self):
        fixture = self.fixture()

        def mutate():
            shutil.copyfile(
                os.path.join(fixture.root, "private-source.txt"),
                os.path.join(fixture.root, "evidence/OPS-006/copied.txt"),
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "copy source")

    def test_missing_collaboration_section_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.rewrite_task_text(
                lambda text: text.replace(
                    "## 协作与交接\n\n- Coordinator registers metadata only.\n\n",
                    "",
                )
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "collaboration/handoff")

    def test_missing_handoff_file_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: os.remove(
                os.path.join(fixture.root, "evidence/OPS-006/handoff.md")
            )
        )
        self.assert_failed(result, "handoffPath")

    def test_missing_support_evidence_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: os.remove(
                os.path.join(fixture.root, "evidence/OPS-006/risks.md")
            )
        )
        self.assert_failed(result, "support file")

    def test_rollback_without_executable_steps_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.write_text(
                "evidence/OPS-006/rollback-verification/README.md",
                "# Rollback\n\nTask: OPS-006\nManual review only.\n",
            )
        )
        self.assert_failed(result, "executable steps")

    def test_repository_wide_path_claim_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.registration_task()["outputPaths"] = ["./**"]
            fixture.write_yaml("specs/coordination/program-plan.yaml", fixture.plan)
            fixture.rewrite_task_text(
                lambda text: text.replace("scripts/program-registration/**", "./**")
            )

        result = fixture.prove_then_mutate(mutate)
        self.assert_failed(result, "repository-wide or unsafe")

    def test_core_blobs_remain_exact(self):
        for path, expected in (
            (TRANSITIONS_CORE, TRANSITIONS_CORE_SHA),
            (LIFECYCLE_CORE, LIFECYCLE_CORE_SHA),
        ):
            result = subprocess.run(
                ["git", "hash-object", path],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()

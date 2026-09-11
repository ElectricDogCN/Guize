import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "check-program-lifecycle-guards.py")
LIFECYCLE_GATE = os.path.join(REPO_ROOT, "scripts", "run-program-lifecycle-gate.py")
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
MAKEFILE = os.path.join(REPO_ROOT, "Makefile")
PROTOCOL = os.path.join(REPO_ROOT, "docs", "25-multi-agent-collaboration-protocol.md")
OWNERSHIP = os.path.join(REPO_ROOT, "specs", "designs", "module-ownership.yaml")
SPEC = importlib.util.spec_from_file_location("program_lifecycle_guards", SCRIPT_PATH)
GUARDS = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(GUARDS)
WRAPPER_SPEC = importlib.util.spec_from_file_location(
    "program_lifecycle_gate_wrapper", LIFECYCLE_GATE
)
WRAPPER = importlib.util.module_from_spec(WRAPPER_SPEC)
assert WRAPPER_SPEC and WRAPPER_SPEC.loader
WRAPPER_SPEC.loader.exec_module(WRAPPER)


class TestProgramLifecycleGuards(unittest.TestCase):
    def write(self, root, relative, content):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def git(self, root, *args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        )

    def init_git(self, root):
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.email", "test@example.com")
        self.git(root, "config", "user.name", "Test")

    def commit(self, root, message):
        self.git(root, "add", "-A")
        self.git(root, "commit", "--allow-empty", "-m", message)
        return self.git(root, "rev-parse", "HEAD").stdout.strip()

    def test_current_repository_passes(self):
        result = subprocess.run(
            [
                sys.executable,
                LIFECYCLE_GATE,
                "--repo-root",
                REPO_ROOT,
                "--base-ref",
                "origin/main",
                "--head-ref",
                "HEAD",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wrapper_task_derivation_does_not_recurse(self):
        base_plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "planned"}],
            "pocs": [],
            "externalBlockers": [],
        }
        current_plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "reserved"}],
            "pocs": [],
            "externalBlockers": [],
        }
        original = WRAPPER.GUARD.task_ids_from_diff
        WRAPPER.GUARD.task_ids_from_diff = WRAPPER.expanded_task_ids_from_diff
        try:
            affected = WRAPPER.expanded_task_ids_from_diff(
                base_plan,
                current_plan,
                {"tasks": []},
                {"tasks": [{"taskId": "GZ-004", "status": "reserved"}]},
                {"records": []},
                {"records": []},
                {"specs/tasks/GZ-004.md"},
            )
        finally:
            WRAPPER.GUARD.task_ids_from_diff = original
        self.assertEqual(affected, {"GZ-004"})

    def test_rename_diff_includes_source_and_destination(self):
        with tempfile.TemporaryDirectory() as root:
            self.init_git(root)
            self.write(root, "backend/file.txt", "business\n")
            self.commit(root, "base")
            self.git(root, "checkout", "-b", "chore/GZ-004-metadata")
            os.makedirs(os.path.join(root, "evidence", "GZ-004"), exist_ok=True)
            self.git(root, "mv", "backend/file.txt", "evidence/GZ-004/file.txt")
            self.commit(root, "rename")
            paths = GUARDS.changed_paths(root, "main", "HEAD")
            self.assertEqual(
                paths,
                {"backend/file.txt", "evidence/GZ-004/file.txt"},
            )

    def test_affected_task_ids_are_derived_without_branch_context(self):
        base_plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "planned"}],
        }
        current_plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "reserved"}],
        }
        affected = GUARDS.task_ids_from_diff(
            base_plan,
            current_plan,
            {"tasks": []},
            {"tasks": [{"taskId": "GZ-004", "status": "reserved"}]},
            {"records": []},
            {"records": []},
            {"specs/tasks/GZ-004.md"},
        )
        self.assertEqual(affected, {"GZ-004"})

    def test_foundation_claim_rejects_business_path_and_stale_base(self):
        entry = {
            "baseSha": "a" * 40,
            "moduleIds": ["MOD-GOV"],
            "exclusivePaths": ["backend/**"],
            "sharedPaths": [],
        }
        ownership = {
            "modules": [
                {
                    "id": "MOD-GOV",
                    "ownedPaths": ["scripts/**", "tests/governance/**"],
                }
            ]
        }
        errors = []
        GUARDS.validate_foundation_claims(
            "GZ-014", entry, ownership, "b" * 40, errors
        )
        self.assertTrue(any("baseSha must equal" in error for error in errors))
        self.assertTrue(any("outside module ownership" in error for error in errors))

    def test_foundation_claim_accepts_audited_governance_scope(self):
        entry = {
            "baseSha": "b" * 40,
            "moduleIds": ["MOD-GOV"],
            "exclusivePaths": ["scripts/**", "Makefile", ".github/**"],
            "sharedPaths": [],
        }
        ownership = {
            "modules": [{"id": "MOD-GOV", "ownedPaths": ["scripts/**"]}]
        }
        errors = []
        GUARDS.validate_foundation_claims(
            "GZ-014", entry, ownership, "b" * 40, errors
        )
        self.assertEqual(errors, [])

    def test_completed_spec_must_bind_own_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(
                root,
                "specs/tasks/GZ-004.md",
                "---\nid: GZ-004\nstatus: completed\n"
                "evidencePath: evidence/GZ-999\n"
                "handoffPath: evidence/GZ-999/handoff.md\n---\n",
            )
            errors = []
            GUARDS.validate_completed_spec_binding(
                root, "GZ-004", {"tasks": []}, errors
            )
            self.assertTrue(
                any("evidencePath must be evidence/GZ-004" in e for e in errors)
            )
            self.assertTrue(
                any(
                    "handoffPath must be evidence/GZ-004/handoff.md" in e
                    for e in errors
                )
            )

    def test_cancellation_requires_structured_fresh_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            errors = []
            GUARDS.validate_cancellation_evidence(
                root, "GZ-004", "in_progress", set(), errors
            )
            self.assertTrue(any("must refresh" in error for error in errors))
            relative = "evidence/GZ-004/cancellation.md"
            self.write(
                root,
                relative,
                "Task: GZ-004\n"
                "Transition: in_progress -> cancelled\n"
                "Reason: dependency removed\n"
                "Retained Artifacts: design notes\n"
                "Validation: PASS\n",
            )
            errors = []
            GUARDS.validate_cancellation_evidence(
                root, "GZ-004", "in_progress", {relative}, errors
            )
            self.assertEqual(errors, [])

    def write_completion_evidence(self, root, task_id, merge_sha, structured=True):
        self.write(
            root,
            f"evidence/{task_id}/summary.md",
            f"# Summary\nTask: {task_id}\nMerge: {merge_sha}\n"
            + ("Status: COMPLETED\n" if structured else "completion\n"),
        )
        self.write(
            root,
            f"evidence/{task_id}/commands.txt",
            f"Task: {task_id}\nMerge: {merge_sha}\n"
            + (
                "command: make verify\nexit code: 0\nresult: PASS\n"
                if structured
                else "completion\n"
            ),
        )
        self.write(
            root,
            f"evidence/{task_id}/test-results/README.md",
            f"# Tests\nTask: {task_id}\nMerge: {merge_sha}\n"
            + ("Result: PASS\n" if structured else "completion\n"),
        )
        self.write(
            root,
            f"evidence/{task_id}/handoff.md",
            f"# Handoff\nTask: {task_id}\nMerge: {merge_sha}\n"
            + ("Status: COMPLETED\n" if structured else "completion\n"),
        )

    def test_completion_requires_structured_results(self):
        with tempfile.TemporaryDirectory() as root:
            merge_sha = "c" * 40
            self.write_completion_evidence(root, "GZ-004", merge_sha, structured=False)
            paths = {
                "evidence/GZ-004/summary.md",
                "evidence/GZ-004/commands.txt",
                "evidence/GZ-004/test-results/README.md",
                "evidence/GZ-004/handoff.md",
            }
            errors = []
            GUARDS.validate_structured_completion_evidence(
                root, "GZ-004", merge_sha, paths, errors
            )
            self.assertTrue(any("no executed command" in e for e in errors))
            self.assertTrue(any("no successful exit code" in e for e in errors))
            self.assertTrue(any("no explicit PASS" in e for e in errors))

    def test_structured_completion_results_pass(self):
        with tempfile.TemporaryDirectory() as root:
            merge_sha = "c" * 40
            self.write_completion_evidence(root, "GZ-004", merge_sha, structured=True)
            paths = {
                "evidence/GZ-004/summary.md",
                "evidence/GZ-004/commands.txt",
                "evidence/GZ-004/test-results/README.md",
                "evidence/GZ-004/handoff.md",
            }
            errors = []
            GUARDS.validate_structured_completion_evidence(
                root, "GZ-004", merge_sha, paths, errors
            )
            self.assertEqual(errors, [])

    def test_lifecycle_guard_is_mandatory_in_workflow_and_make(self):
        with open(WORKFLOW, "r", encoding="utf-8") as handle:
            workflow = handle.read()
        with open(MAKEFILE, "r", encoding="utf-8") as handle:
            makefile = handle.read()
        self.assertGreaterEqual(
            workflow.count("python scripts/check-program-lifecycle-guards.py"), 2
        )
        self.assertIn("github.event.before", workflow)
        self.assertIn("scripts/check-program-lifecycle-guards.py", makefile)
        self.assertIn("@set -e;", makefile)


class CompletedFoundationMaintenanceFixture:
    task_id = "GZ-014"
    branch = "fix/GZ-014-test-maintenance"
    protocol_path = "docs/25-multi-agent-collaboration-protocol.md"
    ownership_path = "specs/designs/module-ownership.yaml"
    manifest_path = "evidence/GZ-014/foundation-maintenance.yaml"

    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.write_yaml(
            "specs/coordination/program-plan.yaml",
            {
                "foundationTasks": [
                    {
                        "taskId": self.task_id,
                        "title": "Foundation",
                        "status": "completed",
                        "completionRef": "PR-32",
                        "mergeCommit": "a" * 40,
                    }
                ],
                "tasks": [],
            },
        )
        self.write_yaml(
            "specs/coordination/active-work.yaml",
            {"version": 1, "policy": {}, "tasks": []},
        )
        self.write_yaml(
            "specs/coordination/task-completions.yaml",
            {"schemaVersion": 1, "records": []},
        )
        self.write_yaml(
            self.ownership_path,
            {
                "modules": [
                    {
                        "id": "MOD-GOV",
                        "ownedPaths": ["scripts/**", "tests/governance/**"],
                        "ownedSchemas": [],
                    }
                ]
            },
        )
        self.write(self.protocol_path, "# Legacy collaboration protocol\n")
        self.write(
            "specs/tasks/GZ-014.md",
            "---\n"
            "schemaVersion: 2\n"
            "id: GZ-014\n"
            "status: completed\n"
            "riskLevel: high\n"
            "moduleIds: [MOD-GOV]\n"
            "implementer: implementer-agent\n"
            "reviewer: reviewer-agent\n"
            "---\n# GZ-014\n",
        )
        self.write("evidence/GZ-014/handoff.md", "Task: GZ-014\n")
        self.commit("base")
        self.base_sha = self.rev_parse("HEAD")
        self.git("checkout", "-b", self.branch)
        self.write("scripts/checker.py", "print('maintenance')\n")
        self.append_protocol_ownership()
        self.write(
            self.protocol_path,
            "# Collaboration protocol\n\n"
            "Registration → Reservation → Activation → Implementation\n",
        )
        self.write_manifest()
        self.commit("GZ-014 audited maintenance")
        self.source_sha = self.rev_parse("HEAD")

    def close(self):
        self.temp.cleanup()

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

    def write(self, relative, content):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def write_yaml(self, relative, document):
        self.write(relative, yaml.safe_dump(document, sort_keys=False))

    def read_yaml(self, relative):
        with open(os.path.join(self.root, relative), encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "--allow-empty", "-m", message)
        return self.rev_parse("HEAD")

    def append_protocol_ownership(self):
        ownership = self.read_yaml(self.ownership_path)
        ownership["modules"][0]["ownedPaths"].append(self.protocol_path)
        self.write_yaml(self.ownership_path, ownership)

    def manifest(self):
        return {
            "schemaVersion": 1,
            "mode": "completed-foundation-maintenance",
            "taskId": self.task_id,
            "issue": 57,
            "purpose": "test audited completed Foundation maintenance",
            "baseSha": self.base_sha,
            "workBranch": self.branch,
            "riskLevel": "high",
            "oneTime": True,
            "independentReviewRequired": True,
            "postMergeGateRequired": True,
            "ownershipDelta": {
                "moduleId": "MOD-GOV",
                "field": "ownedPaths",
                "operation": "tail-append",
                "paths": [self.protocol_path],
            },
            "authorizedPaths": [
                "scripts/checker.py",
                self.protocol_path,
                self.ownership_path,
                "evidence/GZ-014/**",
            ],
        }

    def write_manifest(self, transform=None):
        document = self.manifest()
        if transform:
            transform(document)
        self.write_yaml(self.manifest_path, document)

    def validate(self, branch=None, base_ref="main"):
        return GUARDS._validate_completed_foundation_maintenance(
            self.root,
            base_ref,
            "HEAD",
            self.task_id,
            self.branch if branch is None else branch,
        )

    def assert_valid(self):
        code, details = self.validate()
        if code:
            raise AssertionError(details)

    def prove_then_mutate(self, mutate, message="negative mutation", branch=None):
        self.assert_valid()
        mutate()
        self.commit(message)
        return self.validate(branch=branch)

    def merge_to_main(self):
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "--no-edit", self.branch)
        return self.rev_parse("HEAD")


class TestCompletedFoundationMaintenance(unittest.TestCase):
    def fixture(self):
        fixture = CompletedFoundationMaintenanceFixture()
        self.addCleanup(fixture.close)
        return fixture

    def assert_failure(self, result, text):
        code, details = result
        self.assertNotEqual(code, 0, details)
        self.assertTrue(any(text in error for error in details["errors"]), details)

    def test_manifest_bound_completed_foundation_maintenance_passes(self):
        fixture = self.fixture()
        fixture.assert_valid()

    def test_completed_foundation_state_drift_fails(self):
        fixture = self.fixture()

        def mutate():
            plan = fixture.read_yaml("specs/coordination/program-plan.yaml")
            plan["foundationTasks"][0]["title"] = "mutated"
            fixture.write_yaml("specs/coordination/program-plan.yaml", plan)

        result = fixture.prove_then_mutate(mutate, "mutate completed Foundation")
        self.assert_failure(result, "Program Plan byte-identical")

    def test_unauthorized_business_path_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.write("backend/forbidden.txt", "business\n"),
            "unauthorized business path",
        )
        self.assert_failure(result, "unauthorized path")

    def test_candidate_ownership_cannot_self_authorize_business_path(self):
        fixture = self.fixture()

        def mutate():
            ownership = fixture.read_yaml(fixture.ownership_path)
            ownership["modules"][0]["ownedPaths"].append("backend/**")
            fixture.write_yaml(fixture.ownership_path, ownership)
            fixture.write("backend/forbidden.txt", "business\n")
            fixture.write_manifest(
                lambda document: document["authorizedPaths"].append(
                    "backend/forbidden.txt"
                )
            )

        result = fixture.prove_then_mutate(mutate, "attempt self-authorization")
        self.assert_failure(result, "outside the declared protocol append")
        self.assert_failure(result, "target-base module ownership")

    def test_temporary_residue_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.write("scripts/checker.tmp", "placeholder\n")
            fixture.write_manifest(
                lambda document: document["authorizedPaths"].append(
                    "scripts/checker.tmp"
                )
            )

        result = fixture.prove_then_mutate(mutate, "temporary residue")
        self.assert_failure(result, "probe/temp/placeholder residue")

    def test_general_probe_and_placeholder_names_fail(self):
        cases = (
            "evidence/GZ-014/.controller-probe",
            "scripts/runtime-probe.txt",
            "scripts/checker.placeholder",
            "scripts/controller-test.marker",
        )
        for path in cases:
            with self.subTest(path=path):
                fixture = self.fixture()

                def mutate(path=path):
                    fixture.write(path, "content\n")
                    fixture.write_manifest(
                        lambda document: document["authorizedPaths"].append(path)
                    )

                result = fixture.prove_then_mutate(mutate, f"add residue {path}")
                self.assert_failure(result, "probe/temp/placeholder residue")

    def test_placeholder_only_content_fails(self):
        fixture = self.fixture()

        def mutate():
            fixture.write("scripts/notes.md", "placeholder\n")
            fixture.write_manifest(
                lambda document: document["authorizedPaths"].append(
                    "scripts/notes.md"
                )
            )

        result = fixture.prove_then_mutate(mutate, "placeholder-only content")
        self.assert_failure(result, "placeholder-only content")

    def test_branch_mismatch_fails(self):
        fixture = self.fixture()
        fixture.assert_valid()
        result = fixture.validate(branch="fix/GZ-014-other")
        self.assert_failure(result, "actual branch")

    def test_repository_wide_authorization_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.write_manifest(
                lambda document: document.__setitem__("authorizedPaths", ["**"])
            ),
            "broad authorization",
        )
        self.assert_failure(result, "unsafe authorized path")

    def test_missing_one_time_flag_fails(self):
        fixture = self.fixture()
        result = fixture.prove_then_mutate(
            lambda: fixture.write_manifest(lambda document: document.pop("oneTime")),
            "remove one-time flag",
        )
        self.assert_failure(result, "oneTime")

    def test_second_maintenance_attempt_after_manifest_exists_fails(self):
        fixture = self.fixture()
        fixture.assert_valid()
        merged_main = fixture.merge_to_main()
        fixture.git("checkout", "-b", "fix/GZ-014-second-maintenance")
        fixture.write("evidence/GZ-014/second-attempt.md", "Task: GZ-014\n")
        fixture.commit("second completed Foundation maintenance attempt")
        result = GUARDS._validate_completed_foundation_maintenance(
            fixture.root,
            merged_main,
            "HEAD",
            fixture.task_id,
            "fix/GZ-014-second-maintenance",
        )
        self.assert_failure(result, "must be absent from the target base")

    def test_push_merge_provenance_passes(self):
        fixture = self.fixture()
        fixture.assert_valid()
        fixture.merge_to_main()
        code, details = GUARDS._validate_completed_foundation_maintenance(
            fixture.root,
            fixture.base_sha,
            "HEAD",
            fixture.task_id,
            "",
        )
        self.assertEqual(code, 0, details)

    def test_direct_push_provenance_fails(self):
        fixture = self.fixture()
        fixture.assert_valid()
        fixture.git("checkout", "main")
        fixture.git("merge", "--ff-only", fixture.branch)
        result = GUARDS._validate_completed_foundation_maintenance(
            fixture.root,
            fixture.base_sha,
            "HEAD",
            fixture.task_id,
            "",
        )
        self.assert_failure(result, "two-parent merge")

    def test_protocol_ownership_and_four_stage_sequence_are_machine_readable(self):
        with open(OWNERSHIP, "r", encoding="utf-8") as handle:
            ownership = yaml.safe_load(handle)
        module = next(
            item for item in ownership["modules"] if item["id"] == "MOD-GOV"
        )
        self.assertEqual(
            module["ownedPaths"][-1],
            "docs/25-multi-agent-collaboration-protocol.md",
        )
        with open(PROTOCOL, "r", encoding="utf-8") as handle:
            protocol = handle.read()
        self.assertIn(
            "Registration → Reservation → Activation → Implementation",
            protocol,
        )
        self.assertNotIn("## 6. 两阶段启动协议", protocol)
        self.assertIn("Registration 不得包含 `leaseExpiresAt`", protocol)
        self.assertIn(
            "A red exact-head Gate is never merge authority",
            protocol.replace("红色", "red"),
        )


if __name__ == "__main__":
    unittest.main()

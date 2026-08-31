import copy
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "check-program-lifecycle-guards.py")
LIFECYCLE_GATE = os.path.join(REPO_ROOT, "scripts", "run-program-lifecycle-gate.py")
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
MAKEFILE = os.path.join(REPO_ROOT, "Makefile")
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
        self.git(root, "add", ".")
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
                "--task",
                "GZ-003",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"affectedTaskIds": ["GZ-003"]', result.stdout)

    def _gz003_migration_inputs(self):
        plan = {
            "foundationTasks": [
                {"taskId": "GZ-003", "status": "completed", "completionRef": "PR-11"}
            ],
            "tasks": [],
        }
        active = {"version": 1, "tasks": []}
        ledger = {"records": []}
        return {
            "task_id": "GZ-003",
            "resolved_base": "a" * 40,
            "authorized_base": "a" * 40,
            "before_status": "completed",
            "after_status": "completed",
            "base_plan": plan,
            "current_plan": copy.deepcopy(plan),
            "base_active": active,
            "current_active": copy.deepcopy(active),
            "base_ledger": ledger,
            "current_ledger": copy.deepcopy(ledger),
            "paths": set(GUARDS.GZ003_BOOTSTRAP_MIGRATION_PATHS),
            "task_spec_unchanged": True,
        }

    def test_one_time_gz003_bootstrap_migration_accepts_exact_snapshot(self):
        self.assertTrue(
            GUARDS.is_one_time_gz003_bootstrap_migration(
                **self._gz003_migration_inputs()
            )
        )

    def test_one_time_gz003_bootstrap_migration_rejects_wrong_base(self):
        values = self._gz003_migration_inputs()
        values["resolved_base"] = "f" * 40
        self.assertFalse(GUARDS.is_one_time_gz003_bootstrap_migration(**values))

    def test_one_time_gz003_bootstrap_migration_rejects_extra_path(self):
        values = self._gz003_migration_inputs()
        values["paths"].add("README.md")
        self.assertFalse(GUARDS.is_one_time_gz003_bootstrap_migration(**values))

    def test_one_time_gz003_bootstrap_migration_rejects_state_document_drift(self):
        mutations = (
            ("current_plan", lambda value: value["tasks"].append({"taskId": "GZ-999"})),
            ("current_active", lambda value: value.update({"policy": {"changed": True}})),
            ("current_ledger", lambda value: value["records"].append({"taskId": "GZ-999"})),
        )
        for field, mutate in mutations:
            with self.subTest(field=field):
                values = self._gz003_migration_inputs()
                mutate(values[field])
                self.assertFalse(
                    GUARDS.is_one_time_gz003_bootstrap_migration(**values)
                )

    def test_one_time_gz003_bootstrap_migration_rejects_task_spec_drift(self):
        values = self._gz003_migration_inputs()
        values["task_spec_unchanged"] = False
        self.assertFalse(GUARDS.is_one_time_gz003_bootstrap_migration(**values))

    def test_history_derivation_returns_first_gz014_completed_snapshot(self):
        derived = GUARDS.derive_gz014_completion_base(REPO_ROOT, "HEAD")
        self.assertEqual(derived, "3be9477fb137aa33faa6320f2454b9e1e1d5ec2d")

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
            self.assertTrue(any("evidencePath must be evidence/GZ-004" in e for e in errors))
            self.assertTrue(any("handoffPath must be evidence/GZ-004/handoff.md" in e for e in errors))

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
            self.assertTrue(any("no executed command" in error for error in errors))
            self.assertTrue(any("no successful exit code" in error for error in errors))
            self.assertTrue(any("no explicit PASS" in error for error in errors))

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


if __name__ == "__main__":
    unittest.main()

import importlib.util
import os
import subprocess
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-finalization.py")
SPEC = importlib.util.spec_from_file_location("program_finalization", SCRIPT)
FINALIZATION = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(FINALIZATION)


class TestProgramPlanFinalization(unittest.TestCase):
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

    def write_task(self, root, task_id, status, schema_version=2):
        document = {"id": task_id, "status": status}
        if schema_version is not None:
            document["schemaVersion"] = schema_version
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            "---\n"
            + yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
            + "---\n# Task\n",
        )

    def git(self, root, *args):
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    def init_git(self, root):
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.email", "test@example.com")
        self.git(root, "config", "user.name", "Test")

    def commit(self, root, message):
        self.git(root, "add", ".")
        self.git(root, "commit", "--allow-empty", "-m", message)
        return self.git(root, "rev-parse", "HEAD").stdout.strip()

    def ruleset(self, strict):
        return {
            "target": "branch",
            "enforcement": "active",
            "bypass_actors": [],
            "conditions": {
                "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
            },
            "rules": [
                {
                    "type": "pull_request",
                    "parameters": {
                        "required_approving_review_count": 1,
                        "dismiss_stale_reviews_on_push": True,
                        "require_code_owner_review": True,
                        "required_review_thread_resolution": True,
                    },
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [{"context": "Governance Checks"}],
                        "strict_required_status_checks_policy": strict,
                    },
                },
                {"type": "deletion"},
                {"type": "non_fast_forward"},
            ],
        }

    def test_executing_program_task_requires_one_matching_lease(self):
        plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "reserved"}],
        }
        active = {"tasks": []}
        errors = []
        FINALIZATION.validate_execution_mapping(plan, active, errors)
        self.assertTrue(any("exactly one Active Work" in error for error in errors))

    def test_planned_program_task_rejects_active_lease(self):
        plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "planned"}],
        }
        active = {"tasks": [{"taskId": "GZ-004", "status": "reserved"}]}
        errors = []
        FINALIZATION.validate_execution_mapping(plan, active, errors)
        self.assertTrue(any("must not have an Active Work" in error for error in errors))

    def test_program_and_registry_execution_status_must_match(self):
        plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "in_progress"}],
        }
        active = {"tasks": [{"taskId": "GZ-004", "status": "reserved"}]}
        errors = []
        FINALIZATION.validate_execution_mapping(plan, active, errors)
        self.assertTrue(any("does not match Active Work status" in error for error in errors))

    def test_schema_v2_completed_foundation_rejects_approved_spec(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_task(root, "GZ-014", "approved", schema_version=2)
            plan = {
                "foundationTasks": [{"taskId": "GZ-014", "status": "completed"}]
            }
            errors = []
            FINALIZATION.validate_foundation_specs(root, plan, errors)
            self.assertTrue(any("must remain completed" in error for error in errors))

    def test_legacy_completed_foundation_allows_historical_approved_spec(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_task(root, "GZ-001", "approved", schema_version=None)
            plan = {
                "foundationTasks": [{"taskId": "GZ-001", "status": "completed"}]
            }
            errors = []
            FINALIZATION.validate_foundation_specs(root, plan, errors)
            self.assertEqual(errors, [])

    def test_ruleset_excluding_main_does_not_apply_to_main(self):
        ruleset = {
            "target": "branch",
            "enforcement": "active",
            "conditions": {
                "ref_name": {
                    "include": ["~DEFAULT_BRANCH"],
                    "exclude": ["refs/heads/main"],
                }
            },
        }
        self.assertFalse(FINALIZATION.ruleset_applies_to_main(ruleset))

    def test_ruleset_including_main_without_exclusion_applies(self):
        ruleset = {
            "target": "branch",
            "enforcement": "active",
            "conditions": {
                "ref_name": {
                    "include": ["~DEFAULT_BRANCH"],
                    "exclude": [],
                }
            },
        }
        self.assertTrue(FINALIZATION.ruleset_applies_to_main(ruleset))

    def test_ruleset_requires_latest_target_branch_testing(self):
        valid, failures = FINALIZATION.ruleset_satisfies_policy(self.ruleset(False))
        self.assertFalse(valid)
        self.assertIn(
            "pull requests are not required to test against the latest target branch",
            failures,
        )

    def test_ruleset_with_strict_latest_target_branch_policy_passes(self):
        valid, failures = FINALIZATION.ruleset_satisfies_policy(self.ruleset(True))
        self.assertTrue(valid)
        self.assertEqual(failures, [])

    def prepare_completion_repo(self, root, *, implementation_in_base=True, refresh_evidence=True):
        self.init_git(root)
        self.write_task(root, "GZ-004", "integration")
        for relative in FINALIZATION.REQUIRED_COMPLETION_EVIDENCE:
            self.write_text(root, f"evidence/GZ-004/{relative}", "GZ-004 reservation evidence\n")
        base_sha = self.commit(root, "GZ-004 implementation merged (#40)")
        self.git(root, "checkout", "-b", "chore/GZ-004-completion")

        if implementation_in_base:
            implementation_sha = base_sha
        else:
            self.write_text(root, "implementation-marker.txt", "branch-only implementation\n")
            implementation_sha = self.commit(root, "GZ-004 implementation branch only (#40)")

        self.write_task(root, "GZ-004", "completed")
        plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": "GZ-004", "status": "completed"}],
        }
        ledger = {
            "records": [{"taskId": "GZ-004", "mergeCommit": implementation_sha}]
        }
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
        if refresh_evidence:
            for relative in FINALIZATION.REQUIRED_COMPLETION_EVIDENCE:
                self.write_text(
                    root,
                    f"evidence/GZ-004/{relative}",
                    f"GZ-004 completion verified for implementation merge {implementation_sha}\n",
                )
        self.commit(root, "GZ-004 completion metadata (#41)")
        return plan, ledger, implementation_sha

    def test_completion_requires_fresh_task_bound_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            plan, ledger, _ = self.prepare_completion_repo(
                root, implementation_in_base=True, refresh_evidence=False
            )
            errors = []
            FINALIZATION.validate_completion_evidence(
                root, "main", "HEAD", "GZ-004", plan, ledger, errors
            )
            self.assertTrue(any("must refresh completion Evidence" in error for error in errors))

    def test_completion_merge_must_already_exist_in_target_base(self):
        with tempfile.TemporaryDirectory() as root:
            plan, ledger, merge_sha = self.prepare_completion_repo(
                root, implementation_in_base=False, refresh_evidence=True
            )
            errors = []
            FINALIZATION.validate_completion_evidence(
                root, "main", "HEAD", "GZ-004", plan, ledger, errors
            )
            self.assertTrue(
                any(
                    merge_sha in error and "not present in target base" in error
                    for error in errors
                )
            )

    def test_fresh_evidence_and_base_merge_pass(self):
        with tempfile.TemporaryDirectory() as root:
            plan, ledger, _ = self.prepare_completion_repo(
                root, implementation_in_base=True, refresh_evidence=True
            )
            errors = []
            FINALIZATION.validate_completion_evidence(
                root, "main", "HEAD", "GZ-004", plan, ledger, errors
            )
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

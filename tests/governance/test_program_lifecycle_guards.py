import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GUARD_PATH = os.path.join(REPO_ROOT, "scripts", "check-program-lifecycle-guards.py")
WRAPPER_PATH = os.path.join(REPO_ROOT, "scripts", "run-program-lifecycle-gate.py")
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
MAKEFILE = os.path.join(REPO_ROOT, "Makefile")

spec = importlib.util.spec_from_file_location("program_lifecycle_guards", GUARD_PATH)
GUARDS = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(GUARDS)

wrapper_spec = importlib.util.spec_from_file_location(
    "run_program_lifecycle_gate", WRAPPER_PATH
)
WRAPPER = importlib.util.module_from_spec(wrapper_spec)
assert wrapper_spec.loader is not None
wrapper_spec.loader.exec_module(WRAPPER)


class TestProgramLifecycleGuards(unittest.TestCase):
    def git(self, root, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_current_repository_passes(self):
        try:
            head_sha = self.git(REPO_ROOT, "rev-parse", "HEAD").stdout.strip()
            base_sha = self.git(REPO_ROOT, "rev-parse", "origin/main").stdout.strip()
        except subprocess.CalledProcessError as exc:
            self.skipTest(f"current checkout lacks origin/main for repository guard: {exc}")

        command = [
            sys.executable,
            WRAPPER_PATH,
            "--repo-root",
            REPO_ROOT,
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
        ]
        if head_sha != base_sha:
            branch = os.environ.get("GITHUB_HEAD_REF", "").strip()
            if not branch:
                branch = self.git(REPO_ROOT, "branch", "--show-current").stdout.strip()
            match = re.search(r"(?:^|/)([A-Z]+-\d+)-", branch)
            self.assertIsNotNone(
                match,
                "non-main repository lifecycle checks require a derivable task branch",
            )
            task_id = match.group(1)
            self.assertTrue(task_id)
            command.extend(["--task", task_id, "--branch-name", branch])

        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completion_evidence_requires_merge_identity(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = "GZ-004"
            merge_sha = "a" * 40
            files = {
                "summary.md": "# Summary\nStatus: COMPLETED\n",
                "commands.txt": "command: make verify\nexit code: 0\nresult: PASS\n",
                "test-results/README.md": "# Tests\nResult: PASS\n",
                "handoff.md": "# Handoff\nStatus: COMPLETED\n",
            }
            for relative, content in files.items():
                self.write(root, f"evidence/{task_id}/{relative}", content)
            changed = {f"evidence/{task_id}/{relative}" for relative in files}
            errors = []
            GUARDS.validate_structured_completion_evidence(
                root, task_id, merge_sha, changed, errors
            )
            self.assertTrue(any("does not identify merge" in error for error in errors))

    def test_completion_evidence_requires_task_identity(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = "GZ-004"
            merge_sha = "a" * 40
            files = {
                "summary.md": f"# Summary\nMerge: {merge_sha}\nStatus: COMPLETED\n",
                "commands.txt": f"Merge: {merge_sha}\ncommand: make verify\nexit code: 0\nresult: PASS\n",
                "test-results/README.md": f"# Tests\nMerge: {merge_sha}\nResult: PASS\n",
                "handoff.md": f"# Handoff\nMerge: {merge_sha}\nStatus: COMPLETED\n",
            }
            for relative, content in files.items():
                self.write(root, f"evidence/{task_id}/{relative}", content)
            changed = {f"evidence/{task_id}/{relative}" for relative in files}
            errors = []
            GUARDS.validate_structured_completion_evidence(
                root, task_id, merge_sha, changed, errors
            )
            self.assertTrue(any("does not identify task" in error for error in errors))

    def test_completed_task_lifecycle_requires_completion_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            plan = {
                "tasks": [
                    {
                        "taskId": "GZ-004",
                        "status": "completed",
                    }
                ]
            }
            base_plan = {
                "tasks": [
                    {
                        "taskId": "GZ-004",
                        "status": "integration",
                    }
                ]
            }
            ledger = {
                "records": [
                    {
                        "taskId": "GZ-004",
                        "mergeCommit": "a" * 40,
                        "taskSpec": "specs/tasks/GZ-004.md",
                        "evidencePath": "evidence/GZ-004",
                        "handoffPath": "evidence/GZ-004/handoff.md",
                    }
                ]
            }
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
            self.write(
                root,
                "specs/tasks/GZ-004.md",
                "---\nid: GZ-004\nstatus: completed\n---\n",
            )
            changed = {
                "specs/coordination/program-plan.yaml",
                "specs/coordination/task-completions.yaml",
                "specs/tasks/GZ-004.md",
            }
            errors = []
            GUARDS.validate_completion_lifecycle(
                root, plan, base_plan, ledger, changed, errors
            )
            self.assertTrue(any("must refresh completion Evidence" in error for error in errors))

    def test_completed_task_lifecycle_accepts_structured_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            plan = {
                "tasks": [
                    {
                        "taskId": "GZ-004",
                        "status": "completed",
                    }
                ]
            }
            base_plan = {
                "tasks": [
                    {
                        "taskId": "GZ-004",
                        "status": "integration",
                    }
                ]
            }
            merge_sha = "a" * 40
            ledger = {
                "records": [
                    {
                        "taskId": "GZ-004",
                        "mergeCommit": merge_sha,
                        "taskSpec": "specs/tasks/GZ-004.md",
                        "evidencePath": "evidence/GZ-004",
                        "handoffPath": "evidence/GZ-004/handoff.md",
                    }
                ]
            }
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
            self.write(
                root,
                "specs/tasks/GZ-004.md",
                "---\nid: GZ-004\nstatus: completed\n---\n",
            )
            self.write_completion_evidence(root, "GZ-004", merge_sha, structured=True)
            changed = {
                "specs/coordination/program-plan.yaml",
                "specs/coordination/task-completions.yaml",
                "specs/tasks/GZ-004.md",
                "evidence/GZ-004/summary.md",
                "evidence/GZ-004/commands.txt",
                "evidence/GZ-004/test-results/README.md",
                "evidence/GZ-004/handoff.md",
            }
            errors = []
            GUARDS.validate_completion_lifecycle(
                root, plan, base_plan, ledger, changed, errors
            )
            self.assertEqual(errors, [])

    def test_foundation_completion_lifecycle_requires_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            merge_sha = "b" * 40
            plan = {
                "foundationTasks": [
                    {
                        "taskId": "GZ-014",
                        "status": "completed",
                        "completionRef": "PR-29",
                        "mergeCommit": merge_sha,
                    }
                ]
            }
            base_plan = {
                "foundationTasks": [
                    {
                        "taskId": "GZ-014",
                        "status": "integration",
                        "completionRef": "ISSUE-17",
                        "mergeCommit": None,
                    }
                ]
            }
            changed = {"specs/coordination/program-plan.yaml"}
            errors = []
            GUARDS.validate_completion_lifecycle(
                root, plan, base_plan, {"records": []}, changed, errors
            )
            self.assertTrue(any("must refresh completion Evidence" in e for e in errors))

    def test_program_plan_evidence_references_are_task_bound(self):
        with tempfile.TemporaryDirectory() as root:
            plan = {
                "tasks": [
                    {
                        "taskId": "GZ-004",
                        "status": "completed",
                    }
                ]
            }
            ledger = {
                "records": [
                    {
                        "taskId": "GZ-004",
                        "taskSpec": "specs/tasks/GZ-005.md",
                        "evidencePath": "evidence/GZ-005",
                        "handoffPath": "evidence/GZ-005/handoff.md",
                    }
                ]
            }
            errors = []
            GUARDS.validate_task_bound_completion_records(plan, ledger, errors)
            self.assertTrue(any("taskSpec must be specs/tasks/GZ-004.md" in e for e in errors))
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

    def write(self, root, relative, content):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def write_yaml(self, root, relative, document):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)

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

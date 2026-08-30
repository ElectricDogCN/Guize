import copy
import os
import subprocess
import sys
import tempfile
import unittest

import jsonschema
import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_PATH = os.path.join(
    REPO_ROOT, "specs", "coordination", "program-plan.schema.yaml"
)
PLAN_PATH = os.path.join(REPO_ROOT, "specs", "coordination", "program-plan.yaml")
LIFECYCLE_GUARD = os.path.join(
    REPO_ROOT, "scripts", "check-program-lifecycle-guards.py"
)


class TestFoundationLifecycleStates(unittest.TestCase):
    def load_yaml(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def write_yaml(self, root, relative, document):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)

    def write_text(self, root, relative, content):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def validate_plan(self, plan):
        schema = self.load_yaml(SCHEMA_PATH)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(plan)

    def test_current_plan_accepts_foundation_review_and_integration(self):
        plan = self.load_yaml(PLAN_PATH)
        for state in ("review", "integration"):
            candidate = copy.deepcopy(plan)
            foundation = next(
                item
                for item in candidate["foundationTasks"]
                if item["taskId"] == "GZ-014"
            )
            foundation["status"] = state
            self.validate_plan(candidate)

    def test_foundation_schema_rejects_unknown_state(self):
        plan = self.load_yaml(PLAN_PATH)
        foundation = next(
            item for item in plan["foundationTasks"] if item["taskId"] == "GZ-014"
        )
        foundation["status"] = "ready_to_ship"
        with self.assertRaises(jsonschema.ValidationError):
            self.validate_plan(plan)

    def git(self, root, *args):
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    def commit(self, root, message):
        self.git(root, "add", ".")
        self.git(root, "commit", "--allow-empty", "-m", message)
        return self.git(root, "rev-parse", "HEAD").stdout.strip()

    def test_foundation_can_complete_from_integration_with_structured_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            self.git(root, "init", "-b", "main")
            self.git(root, "config", "user.email", "test@example.com")
            self.git(root, "config", "user.name", "Test")

            self.write_text(root, "implementation.txt", "verified implementation\n")
            implementation_sha = self.commit(root, "GZ-014 implementation (#26)")

            base_plan = {
                "foundationTasks": [
                    {
                        "taskId": "GZ-014",
                        "title": "Foundation",
                        "status": "integration",
                        "completionRef": "ISSUE-17",
                        "mergeCommit": None,
                    }
                ],
                "tasks": [],
            }
            base_active = {
                "version": 1,
                "policy": {},
                "tasks": [
                    {
                        "taskId": "GZ-014",
                        "status": "integration",
                        "moduleIds": ["MOD-GOV"],
                        "exclusivePaths": ["specs/coordination/**"],
                        "sharedPaths": [],
                    }
                ],
            }
            self.write_yaml(root, "specs/coordination/program-plan.yaml", base_plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", base_active)
            self.write_yaml(
                root,
                "specs/coordination/task-completions.yaml",
                {"records": []},
            )
            self.write_yaml(
                root,
                "specs/designs/module-ownership.yaml",
                {
                    "modules": [
                        {
                            "id": "MOD-GOV",
                            "ownedPaths": ["specs/**", "evidence/**"],
                        }
                    ]
                },
            )
            self.write_text(
                root,
                "specs/tasks/GZ-014.md",
                "---\nid: GZ-014\nstatus: integration\n"
                "evidencePath: evidence/GZ-014\n"
                "handoffPath: evidence/GZ-014/handoff.md\n---\n",
            )
            self.commit(root, "GZ-014 integration state (#27)")

            self.git(root, "checkout", "-b", "chore/GZ-014-foundation-completion")
            completed_plan = copy.deepcopy(base_plan)
            completed_plan["foundationTasks"][0].update(
                {
                    "status": "completed",
                    "completionRef": "PR-26",
                    "mergeCommit": implementation_sha,
                }
            )
            self.write_yaml(
                root, "specs/coordination/program-plan.yaml", completed_plan
            )
            self.write_yaml(
                root,
                "specs/coordination/active-work.yaml",
                {"version": 1, "policy": {}, "tasks": []},
            )
            self.write_text(
                root,
                "specs/tasks/GZ-014.md",
                "---\nid: GZ-014\nstatus: completed\n"
                "evidencePath: evidence/GZ-014\n"
                "handoffPath: evidence/GZ-014/handoff.md\n---\n",
            )
            self.write_text(
                root,
                "evidence/GZ-014/summary.md",
                f"# Summary\nTask: GZ-014\nMerge: {implementation_sha}\nStatus: COMPLETED\n",
            )
            self.write_text(
                root,
                "evidence/GZ-014/commands.txt",
                f"Task: GZ-014\nMerge: {implementation_sha}\n"
                "command: make verify\nexit code: 0\nresult: PASS\n",
            )
            self.write_text(
                root,
                "evidence/GZ-014/test-results/README.md",
                f"# Tests\nTask: GZ-014\nMerge: {implementation_sha}\nResult: PASS\n",
            )
            self.write_text(
                root,
                "evidence/GZ-014/handoff.md",
                f"# Handoff\nTask: GZ-014\nMerge: {implementation_sha}\nStatus: COMPLETED\n",
            )
            self.commit(root, "GZ-014 foundation completion metadata (#28)")

            result = subprocess.run(
                [
                    sys.executable,
                    LIFECYCLE_GUARD,
                    "--repo-root",
                    root,
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "HEAD",
                    "--task",
                    "GZ-014",
                    "--branch-name",
                    "chore/GZ-014-foundation-completion",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

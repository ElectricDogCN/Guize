import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-integrity.py")
COMPLETION_SCHEMA = os.path.join(
    REPO_ROOT, "specs", "coordination", "task-completions.schema.yaml"
)


class TestProgramPlanExecutionIntegrity(unittest.TestCase):
    def _write_yaml(self, root, relative, document):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)

    def _write_text(self, root, relative, content):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _documents(self):
        authority = {
            "requirements": "specs/requirements/product-requirements.md",
            "requirementIndex": "specs/requirements/requirements-index.yaml",
            "moduleOwnership": "specs/designs/module-ownership.yaml",
            "collaborationProtocol": "docs/25-multi-agent-collaboration-protocol.md",
        }
        plan = {
            "sourceOfTruth": "specs/coordination/program-plan.yaml",
            "authority": authority,
            "foundationTasks": [
                {
                    "taskId": "GZ-014",
                    "title": "Foundation",
                    "status": "in_progress",
                    "completionRef": "ISSUE-17",
                    "mergeCommit": None,
                }
            ],
            "waves": [
                {"id": "W1", "order": 1},
                {"id": "W2", "order": 2},
                {"id": "W3", "order": 3},
            ],
            "tasks": [
                {
                    "taskId": "GZ-004",
                    "title": "Requirements",
                    "kind": "requirements",
                    "status": "planned",
                    "riskLevel": "high",
                    "wave": "W1",
                    "dependsOn": ["GZ-014"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/gz004/**"],
                    "sharedPaths": [],
                    "exitGate": "Requirements baseline is independently verified.",
                },
                {
                    "taskId": "GZ-005",
                    "title": "Contract",
                    "kind": "contract",
                    "status": "planned",
                    "riskLevel": "high",
                    "wave": "W2",
                    "dependsOn": ["GZ-004"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/gz005/**"],
                    "sharedPaths": [],
                    "exitGate": "Contract baseline is independently verified.",
                },
                {
                    "taskId": "GZ-020",
                    "title": "Release",
                    "kind": "release",
                    "status": "planned",
                    "riskLevel": "critical",
                    "wave": "W3",
                    "dependsOn": ["GZ-005"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/release/**"],
                    "sharedPaths": [],
                    "exitGate": "Production release is independently approved.",
                },
            ],
            "externalBlockers": [
                {
                    "id": "BRANCH-PROTECTION",
                    "status": "open",
                    "requiredFor": ["GZ-020"],
                }
            ],
            "releasePolicy": {"requiredFinalTask": "GZ-020"},
        }
        active = {
            "tasks": [
                {
                    "taskId": "GZ-014",
                    "status": "in_progress",
                    "dependsOn": [],
                }
            ]
        }
        modules = {
            "modules": [
                {
                    "id": "MOD-GOV",
                    "ownedPaths": ["specs/**", "scripts/**", "docs/governance/**"],
                },
                {
                    "id": "MOD-AI",
                    "ownedPaths": ["backend/ai/**"],
                },
            ],
            "contractNamespaces": [
                {
                    "id": "CONTRACT-AI",
                    "pattern": "contracts/ai/**",
                    "ownerModule": "MOD-AI",
                    "sharedWriterModules": [],
                }
            ],
        }
        completions = {
            "$schema": "task-completions.schema.yaml",
            "schemaVersion": 1,
            "sourceOfTruth": "specs/coordination/task-completions.yaml",
            "records": [],
        }
        return plan, active, modules, completions

    def _write_task_spec(self, root, task_id, status, exit_gate=None):
        lines = [
            "---",
            "schemaVersion: 2",
            f"id: {task_id}",
            f"status: {status}",
        ]
        if exit_gate is not None:
            lines.append(f"exitGate: {exit_gate}")
        lines += ["---", f"# {task_id}", ""]
        self._write_text(root, f"specs/tasks/{task_id}.md", "\n".join(lines))

    def _prepare(self, root, plan, active, modules, completions):
        self._write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self._write_yaml(root, "specs/coordination/active-work.yaml", active)
        self._write_yaml(root, "specs/designs/module-ownership.yaml", modules)
        self._write_yaml(root, "specs/coordination/task-completions.yaml", completions)
        schema_target = os.path.join(
            root, "specs", "coordination", "task-completions.schema.yaml"
        )
        os.makedirs(os.path.dirname(schema_target), exist_ok=True)
        shutil.copyfile(COMPLETION_SCHEMA, schema_target)
        self._write_task_spec(root, "GZ-014", "in_progress")

    def _run(self, root):
        return subprocess.run(
            [sys.executable, SCRIPT, "--repo-root", root],
            capture_output=True,
            text=True,
        )

    def _init_git(self, root, message):
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=root, check=True
        )
        self._write_text(root, "commit.txt", message + "\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=root,
            check=True,
            capture_output=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_current_repository_passes(self):
        result = self._run(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_minimal_fixture_passes(self):
        with tempfile.TemporaryDirectory() as root:
            documents = self._documents()
            self._prepare(root, *documents)
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_active_task_requires_completed_dependencies(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-005")
            task["status"] = "reserved"
            active["tasks"].append(
                {"taskId": "GZ-005", "status": "reserved", "dependsOn": ["GZ-004"]}
            )
            self._prepare(root, plan, active, modules, completions)
            self._write_task_spec(root, "GZ-005", "reserved", task["exitGate"])
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("dependency GZ-004 is planned", result.stdout)

    def test_open_blocker_rejects_required_task_activation(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-020")
            task["status"] = "reserved"
            task["dependsOn"] = []
            active["tasks"].append(
                {"taskId": "GZ-020", "status": "reserved", "dependsOn": []}
            )
            self._prepare(root, plan, active, modules, completions)
            self._write_task_spec(root, "GZ-020", "reserved", task["exitGate"])
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("external blocker BRANCH-PROTECTION is open", result.stdout)

    def test_foundation_commit_must_match_task_and_pr(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            self._prepare(root, plan, active, modules, completions)
            sha = self._init_git(root, "GZ-001 foundation (#8)")
            plan["foundationTasks"] = [
                {
                    "taskId": "GZ-002",
                    "status": "completed",
                    "completionRef": "PR-9",
                    "mergeCommit": sha,
                }
            ]
            active["tasks"] = []
            self._write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self._write_yaml(root, "specs/coordination/active-work.yaml", active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not identify GZ-002", result.stdout)
            self.assertIn("does not identify PR-9", result.stdout)

    def test_shared_path_requires_declared_owner_module(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
            task["sharedPaths"] = ["backend/ai/**"]
            self._prepare(root, plan, active, modules, completions)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("sharedPaths claim backend/ai/**", result.stdout)
            self.assertIn("without declaring MOD-AI", result.stdout)

    def test_active_task_exit_gate_must_match_program_plan(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
            task["status"] = "reserved"
            task["dependsOn"] = []
            active["tasks"].append(
                {"taskId": "GZ-004", "status": "reserved", "dependsOn": []}
            )
            self._prepare(root, plan, active, modules, completions)
            self._write_task_spec(root, "GZ-004", "reserved", "Different exit gate")
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("exitGate does not match Program Plan", result.stdout)

    def test_authority_paths_are_canonical(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            plan["authority"]["moduleOwnership"] = "README.md"
            self._prepare(root, plan, active, modules, completions)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("authority.moduleOwnership must be", result.stdout)

    def test_completed_task_requires_completion_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
            task["status"] = "completed"
            task["dependsOn"] = []
            self._prepare(root, plan, active, modules, completions)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("has no completion ledger record", result.stdout)

    def test_final_task_is_canonical_gz020_release(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, completions = self._documents()
            plan["releasePolicy"]["requiredFinalTask"] = "GZ-005"
            self._prepare(root, plan, active, modules, completions)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("must be canonical task GZ-020", result.stdout)


if __name__ == "__main__":
    unittest.main()

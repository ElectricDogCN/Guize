import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-agent-coordination.py")
SCHEMA = os.path.join(REPO_ROOT, "specs", "coordination", "active-work.schema.yaml")


def task(task_id, branch, *, risk="medium", group="g", exclusive=None, shared=None, order=1, depends=None, expires="2026-09-02T00:00:00Z"):
    return {
        "taskId": task_id,
        "issue": int(task_id.split("-")[1]),
        "title": task_id,
        "status": "in_progress",
        "riskLevel": risk,
        "owner": "agent-a",
        "agentRole": "implementer",
        "branch": branch,
        "baseBranch": "main",
        "baseSha": "a" * 40,
        "workPackage": "WP-TEST",
        "coordinationGroup": group,
        "dependsOn": depends or [],
        "exclusivePaths": exclusive or [],
        "sharedPaths": shared or [],
        "handoffPath": f"evidence/{task_id}/handoff.md",
        "integrationStrategy": "merge",
        "integrationOrder": order,
        "lease": {"acquiredAt": "2026-08-29T00:00:00Z", "expiresAt": expires},
    }


class TestAgentCoordination(unittest.TestCase):
    def _run(self, root, registry, task_id=""):
        path = os.path.join(root, "active-work.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(registry, handle, sort_keys=False, allow_unicode=True)
        command = [sys.executable, SCRIPT, "--repo-root", root, "--registry", "active-work.yaml", "--schema", SCHEMA, "--now", "2026-08-30T00:00:00Z"]
        if task_id:
            command += ["--task", task_id]
        return subprocess.run(command, capture_output=True, text=True)

    def _registry(self, tasks):
        return {"version": 1, "policy": {"maxActiveTasks": 3, "maxHighRiskTasks": 1, "leaseMaxHours": 168, "bootstrapTasks": ["GZ-003"]}, "tasks": tasks}

    def _write_specs(self, root, tasks):
        directory = os.path.join(root, "specs", "tasks")
        os.makedirs(directory, exist_ok=True)
        for item in tasks:
            with open(os.path.join(directory, f"{item['taskId']}.md"), "w", encoding="utf-8") as handle:
                handle.write(f"---\nid: {item['taskId']}\n---\n")

    def test_empty_registry_passes(self):
        with tempfile.TemporaryDirectory() as root:
            result = self._run(root, self._registry([]))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exclusive_overlap_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task("GZ-101", "feat/GZ-101-a", exclusive=["backend/asset/**"]),
                task("GZ-102", "feat/GZ-102-b", exclusive=["backend/asset/domain/**"]),
            ]
            self._write_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("Exclusive path conflict", result.stdout)

    def test_expired_lease_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [task("GZ-101", "feat/GZ-101-a", exclusive=["a/**"], expires="2026-08-29T12:00:00Z")]
            self._write_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("lease expired", result.stdout)

    def test_coordinated_shared_paths_pass(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task("GZ-101", "feat/GZ-101-a", shared=["contracts/common/**"], group="contract", order=1),
                task("GZ-102", "feat/GZ-102-b", shared=["contracts/common/schema/**"], group="contract", order=2),
            ]
            self._write_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task("GZ-101", "feat/GZ-101-a", exclusive=["a/**"], depends=["GZ-102"]),
                task("GZ-102", "feat/GZ-102-b", exclusive=["b/**"], depends=["GZ-101"]),
            ]
            self._write_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("dependency graph contains a cycle", result.stdout)

    def test_bootstrap_task_passes_without_registry_entry(self):
        with tempfile.TemporaryDirectory() as root:
            directory = os.path.join(root, "specs", "tasks")
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, "GZ-003.md"), "w", encoding="utf-8") as handle:
                handle.write("---\nschemaVersion: 2\nid: GZ-003\ncoordinationMode: bootstrap\n---\n")
            result = self._run(root, self._registry([]), "GZ-003")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

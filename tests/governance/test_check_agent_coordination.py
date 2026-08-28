import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-agent-coordination.py")
SCHEMA = os.path.join(REPO_ROOT, "specs", "coordination", "active-work.schema.yaml")


def task(task_id, branch, *, risk="medium", group="g", exclusive=None, shared=None, order=1, depends=None, expires="2026-09-02T00:00:00Z", status="in_progress", implementer="agent-a", reviewer="agent-b"):
    return {
        "taskId": task_id,
        "issue": int(task_id.split("-")[1]),
        "title": task_id,
        "status": status,
        "riskLevel": risk,
        "owner": "owner-a",
        "coordinator": "coordinator-a",
        "implementer": implementer,
        "reviewer": reviewer,
        "integrator": "integrator-a",
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
    def _run(self, root, registry, task_id="", extra=None):
        path = os.path.join(root, "active-work.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(registry, handle, sort_keys=False, allow_unicode=True)
        command = [sys.executable, SCRIPT, "--repo-root", root, "--registry", "active-work.yaml", "--schema", SCHEMA, "--now", "2026-08-30T00:00:00Z"]
        if task_id:
            command += ["--task", task_id]
        if extra:
            command += extra
        return subprocess.run(command, capture_output=True, text=True)

    def _registry(self, tasks):
        return {"version": 1, "policy": {"maxActiveTasks": 3, "maxHighRiskTasks": 1, "leaseMaxHours": 168, "bootstrapTasks": ["GZ-003"]}, "tasks": tasks}

    def _write_minimal_specs(self, root, tasks):
        directory = os.path.join(root, "specs", "tasks")
        os.makedirs(directory, exist_ok=True)
        for item in tasks:
            with open(os.path.join(directory, f"{item['taskId']}.md"), "w", encoding="utf-8") as handle:
                handle.write(f"---\nid: {item['taskId']}\n---\n")

    def _write_registry_spec(self, root, item, exclusive=None, shared=None):
        task_id = item["taskId"]
        directory = os.path.join(root, "specs", "tasks")
        evidence = os.path.join(root, "evidence", task_id)
        os.makedirs(directory, exist_ok=True)
        os.makedirs(evidence, exist_ok=True)
        with open(os.path.join(evidence, "handoff.md"), "w", encoding="utf-8") as handle:
            handle.write("# Handoff\n")
        exclusive = item["exclusivePaths"] if exclusive is None else exclusive
        shared = item["sharedPaths"] if shared is None else shared
        exclusive_lines = "\n".join(f"- `{path}`" for path in exclusive) or "- 无。"
        shared_lines = "\n".join(f"- `{path}`" for path in shared) or "- 无。"
        depends = ",".join(item["dependsOn"]) or "NONE"
        content = f"""---
schemaVersion: 2
id: {task_id}
title: Registry Task
titleZh: 登记任务
type: feat
status: {item['status']}
baseBranch: {item['baseBranch']}
baseSha: {item['baseSha']}
workBranch: {item['branch']}
evidencePath: evidence/{task_id}
issue: {item['issue']}
workPackage: {item['workPackage']}
taskOwner: {item['owner']}
coordinator: {item['coordinator']}
implementer: {item['implementer']}
reviewer: {item['reviewer']}
integrator: {item['integrator']}
agentRole: {item['agentRole']}
riskLevel: {item['riskLevel']}
coordinationMode: registry
coordinationGroup: {item['coordinationGroup']}
dependsOn: {depends}
handoffPath: {item['handoffPath']}
integrationStrategy: {item['integrationStrategy']}
integrationOrder: {item['integrationOrder']}
leaseExpiresAt: {item['lease']['expiresAt']}
---

## 独占写范围

{exclusive_lines}

## 共享修改范围

{shared_lines}
"""
        with open(os.path.join(directory, f"{task_id}.md"), "w", encoding="utf-8") as handle:
            handle.write(content)

    def _init_git(self, root):
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        with open(os.path.join(root, "base.txt"), "w", encoding="utf-8") as handle:
            handle.write("base\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()

    def test_empty_registry_passes(self):
        with tempfile.TemporaryDirectory() as root:
            result = self._run(root, self._registry([]))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exclusive_overlap_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [task("GZ-101", "feat/GZ-101-a", exclusive=["backend/asset/**"]), task("GZ-102", "feat/GZ-102-b", exclusive=["backend/asset/domain/**"])]
            self._write_minimal_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("Exclusive path conflict", result.stdout)

    def test_expired_lease_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [task("GZ-101", "feat/GZ-101-a", exclusive=["a/**"], expires="2026-08-29T12:00:00Z")]
            self._write_minimal_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("lease expired", result.stdout)

    def test_coordinated_shared_paths_pass(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [task("GZ-101", "feat/GZ-101-a", shared=["contracts/common/**"], group="contract", order=1), task("GZ-102", "feat/GZ-102-b", shared=["contracts/common/schema/**"], group="contract", order=2)]
            self._write_minimal_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [task("GZ-101", "feat/GZ-101-a", exclusive=["a/**"], depends=["GZ-102"]), task("GZ-102", "feat/GZ-102-b", exclusive=["b/**"], depends=["GZ-101"])]
            self._write_minimal_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("dependency graph contains a cycle", result.stdout)

    def test_high_risk_role_separation_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [task("GZ-101", "feat/GZ-101-a", risk="high", exclusive=["a/**"], implementer="agent-a", reviewer="agent-a")]
            self._write_minimal_specs(root, tasks)
            result = self._run(root, self._registry(tasks))
            self.assertEqual(result.returncode, 1)
            self.assertIn("implementer and reviewer must differ", result.stdout)

    def test_bootstrap_task_passes_without_registry_entry(self):
        with tempfile.TemporaryDirectory() as root:
            directory = os.path.join(root, "specs", "tasks")
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, "GZ-003.md"), "w", encoding="utf-8") as handle:
                handle.write("---\nschemaVersion: 2\nid: GZ-003\ncoordinationMode: bootstrap\nworkBranch: chore/GZ-003-bootstrap\n---\n")
            result = self._run(root, self._registry([]), "GZ-003", ["--branch-name", "chore/GZ-003-bootstrap"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_path_claims_must_match_registry(self):
        with tempfile.TemporaryDirectory() as root:
            item = task("GZ-101", "feat/GZ-101-a", exclusive=["backend/a/**"])
            self._write_registry_spec(root, item, exclusive=["backend/b/**"])
            result = self._run(root, self._registry([item]), "GZ-101")
            self.assertEqual(result.returncode, 1)
            self.assertIn("exclusive path claims do not exactly match", result.stdout)

    def test_unclaimed_changed_file_fails(self):
        with tempfile.TemporaryDirectory() as root:
            base_sha = self._init_git(root)
            subprocess.run(["git", "checkout", "-b", "feat/GZ-101-a"], cwd=root, check=True, capture_output=True)
            item = task("GZ-101", "feat/GZ-101-a", exclusive=["backend/allowed/**"])
            item["baseSha"] = base_sha
            self._write_registry_spec(root, item)
            os.makedirs(os.path.join(root, "backend", "other"), exist_ok=True)
            with open(os.path.join(root, "backend", "other", "bad.txt"), "w", encoding="utf-8") as handle:
                handle.write("bad\n")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "change"], cwd=root, check=True, capture_output=True)
            result = self._run(root, self._registry([item]), "GZ-101", ["--base-ref", "main", "--head-ref", "HEAD", "--branch-name", "feat/GZ-101-a"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("outside registered path claims", result.stdout)

    def test_stale_branch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            base_sha = self._init_git(root)
            subprocess.run(["git", "checkout", "-b", "feat/GZ-101-a"], cwd=root, check=True, capture_output=True)
            item = task("GZ-101", "feat/GZ-101-a", exclusive=["backend/allowed/**"])
            item["baseSha"] = base_sha
            self._write_registry_spec(root, item)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "task"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "main"], cwd=root, check=True, capture_output=True)
            with open(os.path.join(root, "main-new.txt"), "w", encoding="utf-8") as handle:
                handle.write("new\n")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "main advanced"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "feat/GZ-101-a"], cwd=root, check=True, capture_output=True)
            result = self._run(root, self._registry([item]), "GZ-101", ["--base-ref", "main", "--head-ref", "HEAD", "--branch-name", "feat/GZ-101-a"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not contain latest base", result.stdout)


if __name__ == "__main__":
    unittest.main()

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-schemas.py")
COORDINATION_FILES = [
    "active-work.yaml",
    "active-work.schema.yaml",
    "program-plan.yaml",
    "program-plan.schema.yaml",
]


class TestCheckSchemas(unittest.TestCase):
    def _resolve_task_spec(self, directory, task_id):
        exact = os.path.join(directory, f"{task_id}.md")
        if os.path.isfile(exact):
            return exact
        matches = sorted(
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.startswith(f"{task_id}-") and name.endswith(".md")
        )
        self.assertEqual(
            len(matches),
            1,
            f"expected exactly one Task Spec for {task_id}, found {matches}",
        )
        return matches[0]

    def _copy_coordination(self, root):
        target = os.path.join(root, "specs", "coordination")
        os.makedirs(target, exist_ok=True)
        source = os.path.join(REPO_ROOT, "specs", "coordination")
        for name in COORDINATION_FILES:
            shutil.copyfile(os.path.join(source, name), os.path.join(target, name))
        task_target = os.path.join(root, "specs", "tasks")
        os.makedirs(task_target, exist_ok=True)
        active = self._load(os.path.join(source, "active-work.yaml"))
        task_ids = {"GZ-014"}
        task_ids.update(
            item["taskId"]
            for item in active.get("tasks", [])
            if item.get("taskId")
        )
        source_tasks = os.path.join(REPO_ROOT, "specs", "tasks")
        for task_id in sorted(task_ids):
            source_path = self._resolve_task_spec(source_tasks, task_id)
            shutil.copyfile(
                source_path,
                os.path.join(task_target, os.path.basename(source_path)),
            )
        return target

    def _load(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def _write(self, path, document):
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)

    def _run(self, root):
        return subprocess.run(
            [sys.executable, SCRIPT, "--repo-root", root],
            capture_output=True,
            text=True,
        )

    def _write_task_spec(self, root, registry):
        def csv(values):
            return ",".join(values) if values else "NONE"

        path = os.path.join(root, "specs", "tasks", f"{registry['taskId']}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = f"""---
schemaVersion: 2
id: {registry['taskId']}
title: Test task
titleZh: {registry['title']}
type: chore
status: {registry['status']}
baseBranch: {registry['baseBranch']}
baseSha: {registry['baseSha']}
workBranch: {registry['branch']}
evidencePath: evidence/{registry['taskId']}
issue: {registry['issue']}
workPackage: {registry['workPackage']}
programPlan: {registry['programPlan']}
programTaskId: {registry['programTaskId']}
wave: {registry['programWave']}
requirementIds: {csv(registry['requirementIds'])}
moduleIds: {csv(registry['moduleIds'])}
producesContracts: {csv(registry['producesContracts'])}
consumesContracts: {csv(registry['consumesContracts'])}
taskOwner: {registry['owner']}
coordinator: {registry['coordinator']}
implementer: {registry['implementer']}
reviewer: {registry['reviewer']}
integrator: {registry['integrator']}
agentRole: {registry['agentRole']}
riskLevel: {registry['riskLevel']}
coordinationMode: registry
coordinationGroup: {registry['coordinationGroup']}
dependsOn: {csv(registry['dependsOn'])}
handoffPath: {registry['handoffPath']}
integrationStrategy: {registry['integrationStrategy']}
integrationOrder: {registry['integrationOrder']}
leaseExpiresAt: {registry['lease']['expiresAt']}
---

# Test Task
"""
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _activate_foundation_gz014(self, root, coordination_dir):
        plan_path = os.path.join(coordination_dir, "program-plan.yaml")
        active_path = os.path.join(coordination_dir, "active-work.yaml")
        plan = self._load(plan_path)
        active = self._load(active_path)

        foundation = next(
            item for item in plan["foundationTasks"] if item["taskId"] == "GZ-014"
        )
        foundation["status"] = "integration"
        foundation["completionRef"] = "ISSUE-17"
        foundation["mergeCommit"] = None

        registry = {
            "taskId": "GZ-014",
            "issue": 17,
            "title": foundation["title"],
            "status": "integration",
            "riskLevel": "high",
            "owner": "ElectricDogCN",
            "coordinator": "program-coordinator-agent",
            "implementer": "governance-hardening-agent",
            "reviewer": "independent-governance-review-agent",
            "integrator": "integration-agent",
            "agentRole": "integrator",
            "branch": "chore/GZ-014-foundation-integration",
            "baseBranch": "main",
            "baseSha": "b" * 40,
            "workPackage": "WP-M0-08",
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": "GZ-014",
            "programWave": "FOUNDATION",
            "requirementIds": ["REQ-V1-0010"],
            "moduleIds": ["MOD-GOV"],
            "producesContracts": [],
            "consumesContracts": [],
            "coordinationGroup": "program-plan-reconciliation",
            "dependsOn": ["GZ-003"],
            "exclusivePaths": ["tests/governance/**"],
            "sharedPaths": [],
            "handoffPath": "evidence/GZ-014/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": 1,
            "lease": {
                "acquiredAt": "2026-08-31T00:00:00Z",
                "expiresAt": "2026-09-07T00:00:00Z",
            },
        }
        active["tasks"] = [registry]
        self._write(plan_path, plan)
        self._write(active_path, active)
        self._write_task_spec(root, registry)
        return registry

    def _activate_gz004(
        self, root, coordination_dir, branch="chore/GZ-004-requirements-baseline"
    ):
        plan_path = os.path.join(coordination_dir, "program-plan.yaml")
        active_path = os.path.join(coordination_dir, "active-work.yaml")
        plan = self._load(plan_path)
        active = self._load(active_path)

        for foundation in plan["foundationTasks"]:
            if foundation["taskId"] == "GZ-014":
                foundation["status"] = "completed"
                foundation["completionRef"] = "PR-29"
                foundation["mergeCommit"] = "a" * 40

        planned = next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")
        planned["status"] = "reserved"
        registry = {
            "taskId": "GZ-004",
            "issue": planned["issue"],
            "title": planned["title"],
            "status": planned["status"],
            "riskLevel": planned["riskLevel"],
            "owner": "ElectricDogCN",
            "coordinator": "program-coordinator-agent",
            "implementer": "requirements-agent",
            "reviewer": "independent-review-agent",
            "integrator": "integration-agent",
            "agentRole": "coordinator",
            "branch": branch,
            "baseBranch": "main",
            "baseSha": "b" * 40,
            "workPackage": planned["workPackage"],
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": planned["taskId"],
            "programWave": planned["wave"],
            "requirementIds": planned["requirementIds"],
            "moduleIds": planned["moduleIds"],
            "producesContracts": planned["producesContracts"],
            "consumesContracts": planned["consumesContracts"],
            "coordinationGroup": planned["coordinationGroup"],
            "dependsOn": planned["dependsOn"],
            "exclusivePaths": planned["outputPaths"],
            "sharedPaths": planned["sharedPaths"],
            "handoffPath": "evidence/GZ-004/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": planned["integrationOrder"],
            "lease": {
                "acquiredAt": "2026-08-29T04:00:00Z",
                "expiresAt": "2026-09-05T04:00:00Z",
            },
        }
        active["tasks"] = [registry]
        self._write(plan_path, plan)
        self._write(active_path, active)
        self._write_task_spec(root, registry)

    def test_current_repository_coordination_files_pass(self):
        result = self._run(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        active = self._load(
            os.path.join(REPO_ROOT, "specs", "coordination", "active-work.yaml")
        )
        plan = self._load(
            os.path.join(REPO_ROOT, "specs", "coordination", "program-plan.yaml")
        )
        foundations = {
            item["taskId"]: item for item in plan.get("foundationTasks", [])
        }
        self.assertIn("GZ-014", foundations)
        gz014 = foundations["GZ-014"]
        active_by_id = {item["taskId"]: item for item in active.get("tasks", [])}

        if gz014.get("status") == "completed":
            self.assertNotIn("GZ-014", active_by_id)
            self.assertRegex(str(gz014.get("completionRef") or ""), r"^PR-\d+$")
            self.assertRegex(str(gz014.get("mergeCommit") or ""), r"^[0-9a-f]{40}$")
            self.assertNotIn("OK FOUNDATION ACTIVATION: GZ-014", result.stdout)
        else:
            self.assertIn(
                gz014.get("status"),
                {"reserved", "in_progress", "blocked", "review", "integration"},
            )
            self.assertIn("GZ-014", active_by_id)
            self.assertIn("OK TASK REGISTRY LINK: GZ-014", result.stdout)
            self.assertIn("OK FOUNDATION ACTIVATION: GZ-014", result.stdout)

        for item in active.get("tasks", []):
            self.assertIn(f"OK TASK REGISTRY LINK: {item['taskId']}", result.stdout)
            if item.get("programWave") == "FOUNDATION":
                self.assertIn(
                    f"OK FOUNDATION ACTIVATION: {item['taskId']}", result.stdout
                )
        self.assertIn(
            "OK: Schema, Task Spec, Active Work and Program Plan validation completed",
            result.stdout,
        )

    def test_copied_current_instances_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._copy_coordination(root)
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_program_task_id_must_equal_registry_task_id(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_foundation_gz014(root, coordination)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["tasks"][0]["programTaskId"] = "GZ-999"
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("programTaskId must equal taskId", result.stdout)

    def test_task_spec_wave_must_match_registry(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_foundation_gz014(root, coordination)
            path = os.path.join(root, "specs", "tasks", "GZ-014.md")
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text.replace("wave: FOUNDATION", "wave: W99", 1))
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Task Spec GZ-014 wave", result.stdout)

    def test_foundation_wave_must_be_foundation(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_foundation_gz014(root, coordination)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["tasks"][0]["programWave"] = "W99"
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("programWave must be FOUNDATION", result.stdout)

    def test_program_active_task_requires_registry_lease(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            active_path = os.path.join(coordination, "active-work.yaml")
            active = self._load(active_path)
            active["tasks"] = []
            self._write(active_path, active)
            path = os.path.join(coordination, "program-plan.yaml")
            plan = self._load(path)
            next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")[
                "status"
            ] = "reserved"
            self._write(path, plan)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("has no lease: GZ-004", result.stdout)

    def test_active_policy_must_match_program_policy(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["policy"]["maxActiveTasks"] = 2
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match Program Plan parallelPolicy", result.stdout)

    def test_core_program_safety_policy_cannot_be_disabled(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            path = os.path.join(coordination, "program-plan.yaml")
            plan = self._load(path)
            plan["parallelPolicy"]["reservationRequired"] = False
            self._write(path, plan)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("parallelPolicy/reservationRequired", result.stdout)

    def test_regular_program_task_activation_passes(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(root, coordination)
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK TASK REGISTRY LINK: GZ-004", result.stdout)
            self.assertIn("OK PROGRAM ACTIVATION: GZ-004 <- W1", result.stdout)

    def test_regular_program_task_branch_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(root, coordination, branch="fix/GZ-004-wrong-prefix")
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match Program Plan branchPattern", result.stdout)

    def test_regular_program_task_contract_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(root, coordination)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["tasks"][0]["producesContracts"] = []
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("producesContracts", result.stdout)

    def test_regular_program_task_cannot_expand_exclusive_paths(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(root, coordination)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["tasks"][0]["exclusivePaths"].append("unplanned/**")
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("exclusivePaths", result.stdout)

    def test_regular_program_task_cannot_downgrade_output_to_shared(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(root, coordination)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            moved = active["tasks"][0]["exclusivePaths"].pop()
            active["tasks"][0]["sharedPaths"].append(moved)
            self._write(path, active)
            self._write_task_spec(root, active["tasks"][0])
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("exclusivePaths", result.stdout)


if __name__ == "__main__":
    unittest.main()

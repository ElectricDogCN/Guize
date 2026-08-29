import copy
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
    def _copy_coordination(self, root):
        target = os.path.join(root, "specs", "coordination")
        os.makedirs(target, exist_ok=True)
        source = os.path.join(REPO_ROOT, "specs", "coordination")
        for name in COORDINATION_FILES:
            shutil.copyfile(os.path.join(source, name), os.path.join(target, name))
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

    def _activate_gz004(self, coordination_dir, branch="chore/GZ-004-requirements-baseline"):
        plan_path = os.path.join(coordination_dir, "program-plan.yaml")
        active_path = os.path.join(coordination_dir, "active-work.yaml")
        plan = self._load(plan_path)
        active = self._load(active_path)

        for foundation in plan["foundationTasks"]:
            if foundation["taskId"] == "GZ-014":
                foundation["status"] = "completed"
                foundation["mergeCommit"] = "a" * 40

        planned = next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")
        planned["status"] = "reserved"
        active["tasks"] = [{
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
        }]
        self._write(plan_path, plan)
        self._write(active_path, active)

    def test_current_repository_coordination_files_pass(self):
        result = self._run(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK FOUNDATION ACTIVATION: GZ-014", result.stdout)

    def test_copied_current_instances_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._copy_coordination(root)
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_program_task_id_must_equal_registry_task_id(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["tasks"][0]["programTaskId"] = "GZ-999"
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("programTaskId must equal taskId", result.stdout)

    def test_foundation_wave_must_be_foundation(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
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
            path = os.path.join(coordination, "program-plan.yaml")
            plan = self._load(path)
            next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")["status"] = "reserved"
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

    def test_regular_program_task_activation_passes(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(coordination)
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK PROGRAM ACTIVATION: GZ-004 <- W1", result.stdout)

    def test_regular_program_task_branch_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(coordination, branch="fix/GZ-004-wrong-prefix")
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match Program Plan branchPattern", result.stdout)

    def test_regular_program_task_contract_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            coordination = self._copy_coordination(root)
            self._activate_gz004(coordination)
            path = os.path.join(coordination, "active-work.yaml")
            active = self._load(path)
            active["tasks"][0]["producesContracts"] = []
            self._write(path, active)
            result = self._run(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("producesContracts", result.stdout)


if __name__ == "__main__":
    unittest.main()

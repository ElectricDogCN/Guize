import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-project-readiness.py")


class TestProjectReadiness(unittest.TestCase):
    def _write(self, root, relative, content):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(content, dict):
            with open(path, "w", encoding="utf-8") as handle:
                yaml.safe_dump(content, handle, sort_keys=False, allow_unicode=True)
        else:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)

    def _documents(self):
        requirement_id = "REQ-V1-0001"
        module_id = "MOD-TEST"
        req = {
            "version": 1,
            "baseline": "GZ-003",
            "sourceOfTruth": "specs/requirements/product.md",
            "requirements": [{
                "id": requirement_id,
                "aliases": ["G-1"],
                "title": "R",
                "status": "frozen",
                "source": "specs/requirements/product.md",
                "designRefs": ["docs/design.md"],
                "moduleIds": [module_id],
                "workPackages": ["WP-1"],
                "acceptanceIds": ["A-1"],
                "machineContractState": "gap",
                "implementationState": "not_started",
                "blockers": ["B"],
                "nextTasks": ["GZ-101"],
            }],
        }
        modules = {
            "version": 1,
            "baseline": "GZ-003",
            "modules": [{
                "id": module_id,
                "name": "M",
                "status": "planned",
                "owner": "o",
                "ownedPaths": ["backend/m/**"],
                "ownedSchemas": ["m"],
                "publicContracts": [],
                "dependsOn": [],
                "requirementIds": [requirement_id],
                "workPackages": ["WP-1"],
            }],
        }
        plan = {
            "version": 1,
            "foundationTasks": ["GZ-003"],
            "tasks": [{
                "taskId": "GZ-101",
                "title": "T",
                "workPackage": "WP-1",
                "riskLevel": "medium",
                "parallelGroup": "g",
                "dependsOn": ["GZ-003"],
                "requirementIds": [requirement_id],
                "moduleIds": [module_id],
                "outputPaths": ["backend/m/**"],
                "exitGate": "verified",
            }],
        }
        return req, modules, plan

    def _run(self, root, req, modules, plan):
        self._write(root, "requirements.yaml", req)
        self._write(root, "modules.yaml", modules)
        self._write(root, "plan.yaml", plan)
        self._write(root, "specs/requirements/product.md", "V1 不设置对外 Beta\n")
        self._write(root, "docs/design.md", "# Design\n")
        self._write(root, "README.md", "V1 不设置对外 Beta\n")
        headings = "\n".join(f"## {number}. Section" for number in [7, 8, 9, 10, 13, 14, 16, 18])
        self._write(root, "docs/00-guize-engineering-design-baseline.md", "V1 不设置对外 Beta\n" + headings)
        self._write(root, "specs/tasks/GZ-003.md", "---\nid: GZ-003\n---\n")
        command = [
            sys.executable,
            SCRIPT,
            "--repo-root", root,
            "--requirements", "requirements.yaml",
            "--modules", "modules.yaml",
            "--plan", "plan.yaml",
        ]
        return subprocess.run(command, capture_output=True, text=True)

    def test_repository_indexes_pass(self):
        result = subprocess.run(
            [sys.executable, SCRIPT, "--repo-root", REPO_ROOT],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_indexes_pass(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_requirement_source_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            req["requirements"][0]["source"] = "missing.md"
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("source does not exist", result.stdout)

    def test_unknown_module_reference_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            req["requirements"][0]["moduleIds"] = ["MOD-MISSING"]
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown module", result.stdout)

    def test_module_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            modules["modules"].append({
                "id": "MOD-SECOND",
                "name": "N",
                "status": "planned",
                "owner": "o",
                "ownedPaths": ["backend/n/**"],
                "ownedSchemas": ["n"],
                "publicContracts": [],
                "dependsOn": ["MOD-TEST"],
                "requirementIds": ["REQ-V1-0001"],
                "workPackages": ["WP-1"],
            })
            modules["modules"][0]["dependsOn"] = ["MOD-SECOND"]
            req["requirements"][0]["moduleIds"].append("MOD-SECOND")
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("dependency graph contains a cycle", result.stdout)

    def test_duplicate_schema_owner_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            modules["modules"].append({
                "id": "MOD-SECOND",
                "name": "N",
                "status": "planned",
                "owner": "o",
                "ownedPaths": ["backend/n/**"],
                "ownedSchemas": ["m"],
                "publicContracts": [],
                "dependsOn": [],
                "requirementIds": ["REQ-V1-0001"],
                "workPackages": ["WP-1"],
            })
            req["requirements"][0]["moduleIds"].append("MOD-SECOND")
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Schema m is owned by both", result.stdout)

    def test_overlapping_module_path_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            modules["modules"].append({
                "id": "MOD-SECOND",
                "name": "N",
                "status": "planned",
                "owner": "o",
                "ownedPaths": ["backend/m/domain/**"],
                "ownedSchemas": [],
                "publicContracts": [],
                "dependsOn": [],
                "requirementIds": ["REQ-V1-0001"],
                "workPackages": ["WP-1"],
            })
            req["requirements"][0]["moduleIds"].append("MOD-SECOND")
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Module path ownership overlaps", result.stdout)

    def test_asymmetric_requirement_module_mapping_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            modules["modules"][0]["requirementIds"] = []
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("mapping is asymmetric", result.stdout)

    def test_unknown_next_task_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            req["requirements"][0]["nextTasks"] = ["GZ-999"]
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown next task", result.stdout)


if __name__ == "__main__":
    unittest.main()

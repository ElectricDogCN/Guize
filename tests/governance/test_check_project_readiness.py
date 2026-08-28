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
        req = {"version": 1, "requirements": [{"id": "REQ-1", "aliases": ["G-1"], "title": "R", "status": "frozen", "source": "specs/requirements/product.md", "designRefs": ["docs/design.md"], "moduleIds": ["MOD-1"], "workPackages": ["WP-1"], "acceptanceIds": ["A-1"], "machineContractState": "gap", "implementationState": "not_started", "blockers": ["B"], "nextTasks": ["GZ-101"]}]}
        modules = {"version": 1, "modules": [{"id": "MOD-1", "name": "M", "status": "planned", "owner": "o", "ownedPaths": ["backend/m/**"], "ownedSchemas": [], "publicContracts": [], "dependsOn": [], "requirementIds": ["REQ-1"], "workPackages": ["WP-1"]}]}
        plan = {"version": 1, "foundationTasks": ["GZ-003"], "tasks": [{"taskId": "GZ-101", "title": "T", "workPackage": "WP-1", "riskLevel": "medium", "parallelGroup": "g", "dependsOn": ["GZ-003"], "requirementIds": ["REQ-1"], "moduleIds": ["MOD-1"], "outputPaths": ["backend/m/**"], "exitGate": "verified"}]}
        return req, modules, plan

    def _run(self, root, req, modules, plan):
        self._write(root, "requirements.yaml", req)
        self._write(root, "modules.yaml", modules)
        self._write(root, "plan.yaml", plan)
        self._write(root, "specs/requirements/product.md", "V1 不设置对外 Beta\n")
        self._write(root, "docs/design.md", "# Design\n")
        self._write(root, "README.md", "V1 不设置对外 Beta\n")
        headings = "\n".join(f"## {n}. Section" for n in [7, 8, 9, 10, 13, 14, 16, 18])
        self._write(root, "docs/00-guize-engineering-design-baseline.md", "V1 不设置对外 Beta\n" + headings)
        command = [sys.executable, SCRIPT, "--repo-root", root, "--requirements", "requirements.yaml", "--modules", "modules.yaml", "--plan", "plan.yaml"]
        return subprocess.run(command, capture_output=True, text=True)

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
            req["requirements"][0]["moduleIds"] = ["MOD-404"]
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown module", result.stdout)

    def test_module_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as root:
            req, modules, plan = self._documents()
            modules["modules"].append({"id": "MOD-2", "name": "N", "status": "planned", "owner": "o", "ownedPaths": ["backend/n/**"], "ownedSchemas": [], "publicContracts": [], "dependsOn": ["MOD-1"], "requirementIds": ["REQ-1"], "workPackages": ["WP-1"]})
            modules["modules"][0]["dependsOn"] = ["MOD-2"]
            result = self._run(root, req, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("dependency graph contains a cycle", result.stdout)


if __name__ == "__main__":
    unittest.main()

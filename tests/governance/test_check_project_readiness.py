import copy
import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-project-readiness.py")
PROGRAM_SCHEMA = os.path.join(REPO_ROOT, "specs", "coordination", "program-plan.schema.yaml")


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
        requirements = {
            "version": 2,
            "baseline": "GZ-014",
            "sourceOfTruth": "specs/requirements/product-requirements.md",
            "requirements": [{
                "id": requirement_id,
                "aliases": ["G-1"],
                "title": "R",
                "status": "frozen",
                "source": "specs/requirements/product-requirements.md",
                "designRefs": ["docs/design.md"],
                "moduleIds": [module_id],
                "workPackages": ["WP-1"],
                "acceptanceIds": ["A-1"],
                "machineContractState": "gap",
                "implementationState": "not_started",
                "blockers": ["BRANCH-PROTECTION"],
                "nextTasks": ["GZ-101"],
            }],
        }
        modules = {
            "version": 2,
            "baseline": "GZ-014",
            "contractNamespaces": [{
                "id": "CONTRACT-TEST",
                "pattern": "contracts/test/**",
                "ownerModule": module_id,
                "consumerModules": [],
                "sharedWriterModules": [],
            }],
            "modules": [{
                "id": module_id,
                "name": "M",
                "status": "planned",
                "owner": "o",
                "ownedPaths": ["backend/m/**"],
                "ownedSchemas": ["m"],
                "providedContracts": ["CONTRACT-TEST"],
                "consumedContracts": [],
                "dependsOn": [],
                "requirementIds": [requirement_id],
                "workPackages": ["WP-1"],
            }],
        }

        waves = []
        tasks = []
        for index in range(1, 13):
            waves.append({
                "id": f"W{index}",
                "order": index,
                "name": f"Wave {index}",
                "maxConcurrent": 1,
                "maxHighRisk": 1,
            })

        tasks.append({
            "taskId": "GZ-101",
            "title": "Requirement task",
            "kind": "requirements",
            "status": "planned",
            "workPackage": "WP-1",
            "riskLevel": "high",
            "ownerRole": "owner-agent",
            "reviewerRole": "reviewer-agent",
            "coordinationGroup": "requirements",
            "wave": "W1",
            "integrationOrder": 1,
            "dependsOn": ["GZ-014"],
            "requirementIds": [requirement_id],
            "moduleIds": [module_id],
            "outputPaths": ["specs/test/**"],
            "sharedPaths": [],
            "producesContracts": ["REQ-V1"],
            "consumesContracts": [],
            "acceptanceIds": [],
            "pocIds": [],
            "issue": None,
            "branchPattern": "chore/GZ-101-*",
            "exitGate": "Requirement baseline is validated.",
        })

        pocs = []
        for index in range(1, 11):
            poc_id = f"POC-{index:02d}"
            task_id = f"POC-{index:03d}"
            wave = f"W{index + 1}"
            pocs.append({
                "pocId": poc_id,
                "taskId": task_id,
                "title": poc_id,
                "status": "planned",
                "riskLevel": "medium",
                "requirementIds": [requirement_id],
                "moduleIds": [module_id],
                "evidencePath": f"evidence/{task_id}",
            })
            tasks.append({
                "taskId": task_id,
                "title": poc_id,
                "kind": "poc",
                "status": "planned",
                "workPackage": f"WP-{poc_id}",
                "riskLevel": "medium",
                "ownerRole": "owner-agent",
                "reviewerRole": "reviewer-agent",
                "coordinationGroup": "poc",
                "wave": wave,
                "integrationOrder": 1,
                "dependsOn": ["GZ-101"],
                "requirementIds": [requirement_id],
                "moduleIds": [module_id],
                "outputPaths": [f"poc/{poc_id}/**"],
                "sharedPaths": [],
                "producesContracts": [f"{poc_id}-EVIDENCE"],
                "consumesContracts": ["REQ-V1"],
                "acceptanceIds": [],
                "pocIds": [poc_id],
                "issue": None,
                "branchPattern": f"chore/{task_id}-*",
                "exitGate": f"{poc_id} evidence is reproducible.",
            })

        tasks.append({
            "taskId": "GZ-199",
            "title": "Release",
            "kind": "release",
            "status": "planned",
            "workPackage": "WP-RC",
            "riskLevel": "critical",
            "ownerRole": "release-agent",
            "reviewerRole": "reviewer-agent",
            "coordinationGroup": "release",
            "wave": "W12",
            "integrationOrder": 1,
            "dependsOn": ["GZ-101"] + [f"POC-{index:03d}" for index in range(1, 11)],
            "requirementIds": [requirement_id],
            "moduleIds": [module_id],
            "outputPaths": ["release/**"],
            "sharedPaths": [],
            "producesContracts": [],
            "consumesContracts": ["REQ-V1"],
            "acceptanceIds": ["A-1"],
            "pocIds": [],
            "issue": None,
            "branchPattern": "chore/GZ-199-*",
            "exitGate": "Production release is independently approved.",
        })

        plan = {
            "$schema": "program-plan.schema.yaml",
            "schemaVersion": 1,
            "planId": "GUIZE-TEST-PROGRAM",
            "status": "active",
            "baseline": "GZ-014",
            "sourceOfTruth": "specs/coordination/program-plan.yaml",
            "authority": {
                "requirements": "specs/requirements/product-requirements.md",
                "requirementIndex": "specs/requirements/requirements-index.yaml",
                "moduleOwnership": "specs/designs/module-ownership.yaml",
                "collaborationProtocol": "docs/protocol.md",
            },
            "parallelPolicy": {
                "maxActiveTasks": 3,
                "maxHighRiskTasks": 1,
                "criticalStandalone": True,
                "reservationRequired": True,
                "independentReviewForHighRisk": True,
            },
            "foundationTasks": [
                {"taskId": "GZ-003", "title": "Foundation", "status": "completed", "completionRef": "PR-1", "mergeCommit": "a" * 40},
                {"taskId": "GZ-014", "title": "Current", "status": "in_progress", "completionRef": "ISSUE-1", "mergeCommit": None},
            ],
            "waves": waves,
            "pocs": pocs,
            "tasks": tasks,
            "externalBlockers": [{
                "id": "BRANCH-PROTECTION",
                "title": "Branch protection",
                "status": "open",
                "issue": 1,
                "requiredFor": ["GZ-199"],
                "verification": ["protected"],
            }],
            "releasePolicy": {
                "noPublicBeta": True,
                "productionApprovalRequired": True,
                "allInScopeCapabilitiesMustPass": True,
                "requiredFinalTask": "GZ-199",
            },
        }
        return requirements, modules, plan

    def _run(self, root, requirements, modules, plan):
        self._write(root, "specs/requirements/requirements-index.yaml", requirements)
        self._write(root, "specs/designs/module-ownership.yaml", modules)
        self._write(root, "specs/coordination/program-plan.yaml", plan)
        with open(PROGRAM_SCHEMA, "r", encoding="utf-8") as handle:
            self._write(root, "specs/coordination/program-plan.schema.yaml", handle.read())
        self._write(root, "specs/requirements/product-requirements.md", "V1 不设置对外 Beta\n")
        self._write(root, "docs/design.md", "# Design\n")
        self._write(root, "docs/protocol.md", "# Protocol\n")
        self._write(root, "README.md", "V1 不设置对外 Beta\n")
        headings = "\n".join(f"## {number}. Section" for number in [7, 8, 9, 10, 13, 14, 16, 18])
        self._write(root, "docs/00-guize-engineering-design-baseline.md", "V1 不设置对外 Beta\n" + headings)
        self._write(root, "specs/tasks/GZ-003.md", "---\nschemaVersion: 2\nid: GZ-003\nstatus: completed\n---\n")
        self._write(root, "specs/tasks/GZ-014.md", "---\nschemaVersion: 2\nid: GZ-014\nstatus: in_progress\n---\n")
        return subprocess.run([sys.executable, SCRIPT, "--repo-root", root], capture_output=True, text=True)

    def test_valid_indexes_pass(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_requirement_source_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            requirements["requirements"][0]["source"] = "missing.md"
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("source does not exist", result.stdout)

    def test_unknown_module_reference_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            requirements["requirements"][0]["moduleIds"] = ["MOD-MISSING"]
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown module", result.stdout)

    def test_module_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            second = copy.deepcopy(modules["modules"][0])
            second["id"] = "MOD-SECOND"
            second["ownedPaths"] = ["backend/n/**"]
            second["ownedSchemas"] = ["n"]
            second["providedContracts"] = []
            second["dependsOn"] = ["MOD-TEST"]
            modules["modules"].append(second)
            modules["modules"][0]["dependsOn"] = ["MOD-SECOND"]
            requirements["requirements"][0]["moduleIds"].append("MOD-SECOND")
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("dependency graph contains a cycle", result.stdout)

    def test_duplicate_schema_owner_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            second = copy.deepcopy(modules["modules"][0])
            second["id"] = "MOD-SECOND"
            second["ownedPaths"] = ["backend/n/**"]
            second["providedContracts"] = []
            modules["modules"].append(second)
            requirements["requirements"][0]["moduleIds"].append("MOD-SECOND")
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Schema m is owned by both", result.stdout)

    def test_overlapping_module_path_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            second = copy.deepcopy(modules["modules"][0])
            second["id"] = "MOD-SECOND"
            second["ownedPaths"] = ["backend/m/domain/**"]
            second["ownedSchemas"] = []
            second["providedContracts"] = []
            modules["modules"].append(second)
            requirements["requirements"][0]["moduleIds"].append("MOD-SECOND")
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Module path ownership overlaps", result.stdout)

    def test_asymmetric_requirement_module_mapping_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            modules["modules"][0]["requirementIds"] = []
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("mapping is asymmetric", result.stdout)

    def test_unknown_next_task_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            requirements["requirements"][0]["nextTasks"] = ["GZ-999"]
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown next task", result.stdout)

    def test_program_plan_schema_violation_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            del plan["tasks"][0]["exitGate"]
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Program Plan schema violation", result.stdout)

    def test_same_wave_output_conflict_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            plan["waves"][0]["maxConcurrent"] = 2
            plan["waves"][0]["maxHighRisk"] = 2
            second = copy.deepcopy(plan["tasks"][0])
            second["taskId"] = "GZ-102"
            second["title"] = "Second"
            second["branchPattern"] = "chore/GZ-102-*"
            second["integrationOrder"] = 2
            second["producesContracts"] = ["SECOND"]
            plan["tasks"].append(second)
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("output path conflict", result.stdout)

    def test_contract_namespace_overlap_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            modules["contractNamespaces"].append({
                "id": "CONTRACT-SECOND",
                "pattern": "contracts/test/sub/**",
                "ownerModule": "MOD-TEST",
                "consumerModules": [],
                "sharedWriterModules": [],
            })
            modules["modules"][0]["providedContracts"].append("CONTRACT-SECOND")
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Contract namespace patterns overlap", result.stdout)

    def test_contract_owner_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            modules["modules"][0]["providedContracts"] = []
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing from owner module", result.stdout)

    def test_unproduced_contract_consumption_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            plan["tasks"][0]["consumesContracts"] = ["MISSING-CONTRACT"]
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("consumes unproduced contract", result.stdout)

    def test_poc_mapping_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            requirements, modules, plan = self._documents()
            plan["pocs"][0]["moduleIds"] = ["MOD-OTHER"]
            result = self._run(root, requirements, modules, plan)
            self.assertEqual(result.returncode, 1)
            self.assertIn("module mapping differs", result.stdout)

    def test_current_repository_indexes_pass(self):
        result = subprocess.run([sys.executable, SCRIPT, "--repo-root", REPO_ROOT], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

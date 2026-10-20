import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, ensure_evidence_dir, write_task_spec


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestCheckTaskFile(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-task-file.py"),
            "--task",
            task_id,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _copy_registry_task(self, root, transform=None):
        source = os.path.join(REPO_ROOT, "specs", "tasks", "GZ-014.md")
        with open(source, "r", encoding="utf-8") as handle:
            text = handle.read()
        if transform:
            text = transform(text)
        target = os.path.join(root, "specs", "tasks", "GZ-014.md")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        evidence = os.path.join(root, "evidence", "GZ-014")
        os.makedirs(evidence, exist_ok=True)
        with open(os.path.join(evidence, "handoff.md"), "w", encoding="utf-8") as handle:
            handle.write("# Handoff\n")

    def test_valid_task_file_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_missing_task_id_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, id=None)
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)

    def test_invalid_branch_name_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, workBranch="feature/invalid-branch")
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)

    def test_empty_acceptance_section_fails_even_if_other_checklist_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_task_spec(tmpdir, acceptance_criteria="")
            ensure_evidence_dir(tmpdir)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("\n## 其他清单\n\n- [ ] unrelated\n")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Acceptance criteria section", result.stdout)

    def test_empty_validation_commands_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, validation_commands="```bash\n```")
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Validation commands section", result.stdout)

    def test_registry_v2_requires_program_plan_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace(
                    "programPlan: specs/coordination/program-plan.yaml\n",
                    "",
                    1,
                ),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing or empty registry coordination field: programPlan", result.stdout)

    def test_registry_v2_requires_valid_requirement_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace(
                    "requirementIds: REQ-V1-0010",
                    "requirementIds: REQUIREMENT-10",
                    1,
                ),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid requirementIds entry", result.stdout)

    def test_registry_v2_program_task_id_must_match_task_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace(
                    "programTaskId: GZ-014",
                    "programTaskId: GZ-999",
                    1,
                ),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("programTaskId must equal", result.stdout)

    def test_registry_without_program_cannot_accept_edge_requirement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace("requirementIds: REQ-V1-0010", "requirementIds: REQ-EDGE-104-0001", 1),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid requirementIds entry: REQ-EDGE-104-0001", result.stdout)

    def test_registry_requirement_ids_match_actual_program_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(tmpdir)
            directory = os.path.join(tmpdir, "specs", "coordination")
            os.makedirs(directory, exist_ok=True)
            plan = {"tasks": [{"taskId": "GZ-014", "requirementIds": ["REQ-V1-0009"]}], "foundationTasks": []}
            with open(os.path.join(directory, "program-plan.yaml"), "w", encoding="utf-8") as handle:
                json.dump(plan, handle)
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Task requirementIds must equal the actual Program task requirementIds", result.stdout)

    def test_requirement_binding_preserves_planner_and_business_namespaces(self):
        specification = importlib.util.spec_from_file_location("task_requirement_binding", os.path.join(SCRIPTS_DIR, "check-task-file.py"))
        task_file = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(task_file)
        for task_id, scope, selected in [
            ("GZ-005", "V1", ["REQ-V1-0001"]),
            ("OPS-011", "FOUNDATION", ["REQ-V1-0010"]),
            ("GZ-022", "AGENT-EDGE-104", ["REQ-V1-0010"]),
            ("GZ-023", "AGENT-EDGE-104", ["REQ-EDGE-104-0001"]),
        ]:
            with self.subTest(task=task_id, scope=scope):
                errors = []
                planned = None if scope == "FOUNDATION" else {"requirementIds": selected}
                task_file.validate_requirement_binding(selected, task_id, scope, planned, {"REQ-EDGE-104-0001": {}}, errors)
                self.assertEqual(errors, [])
        for task_id, scope, selected, planned_ids, reason in [
            ("GZ-005", "V1", ["REQ-EDGE-104-0001"], ["REQ-EDGE-104-0001"], "Invalid requirementIds entry"),
            ("GZ-023", "AGENT-EDGE-104", ["REQ-V1-0010"], ["REQ-V1-0010"], "Invalid requirementIds entry"),
            ("GZ-023", "AGENT-EDGE-104", ["REQ-EDGE-104-0002"], ["REQ-EDGE-104-0002"], "Unknown independent EDGE"),
            ("GZ-023", "AGENT-EDGE-104", ["REQ-EDGE-104-0001"], ["REQ-EDGE-104-0002"], "must equal the actual Program"),
            ("GZ-022", "AGENT-EDGE-104", ["REQ-V1-0001"], ["REQ-V1-0001"], "must retain only"),
        ]:
            with self.subTest(task=task_id, scope=scope, requirement=selected, planned=planned_ids):
                errors = []
                task_file.validate_requirement_binding(selected, task_id, scope, {"requirementIds": planned_ids}, {"REQ-EDGE-104-0001": {}}, errors)
                self.assertTrue(any(reason in error for error in errors), errors)


    def test_registry_foundation_checks_follow_real_membership(self):
        for case in ("foundation_v1", "foundation_edge", "ordinary_claims_foundation"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmpdir:
                transform = None
                if case == "foundation_edge":
                    transform = lambda text: text.replace(
                        "requirementIds: REQ-V1-0010",
                        "requirementIds: REQ-EDGE-104-0001",
                        1,
                    )
                self._copy_registry_task(tmpdir, transform=transform)
                plan = {
                    "foundationTasks": [{"taskId": "GZ-014", "status": "completed"}],
                    "tasks": [{"taskId": "OPS-100", "requirementIds": ["REQ-V1-0010"]}],
                    "scopeBoundary": {
                        "v1TaskIds": ["OPS-100"],
                        "v1FinalTask": "GZ-020",
                        "agentEdge104": {
                            "state": "defined",
                            "requirementIndex": "specs/requirements/agent-edge-104.yaml",
                            "acceptanceIndex": "specs/acceptance/agent-edge-104.yaml",
                        },
                    },
                }
                if case == "ordinary_claims_foundation":
                    plan["foundationTasks"] = []
                    plan["tasks"].append({"taskId": "GZ-014", "requirementIds": ["REQ-V1-0010"]})
                    plan["scopeBoundary"]["v1TaskIds"].append("GZ-014")
                for relative, value in (
                    ("specs/coordination/program-plan.yaml", plan),
                    ("specs/requirements/agent-edge-104.yaml", {"unrelatedBadCatalog": True}),
                    ("specs/acceptance/agent-edge-104.yaml", {"unrelatedBadCatalog": True}),
                ):
                    target = os.path.join(tmpdir, relative)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "w", encoding="utf-8") as handle:
                        json.dump(value, handle)
                with open(os.path.join(tmpdir, "specs/tasks/GZ-014.md"), encoding="utf-8") as handle:
                    self.assertIn("\nwave: FOUNDATION\n", handle.read())
                result = self._run(tmpdir, "GZ-014")
                if case == "foundation_v1":
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    expected = (
                        "Invalid requirementIds entry: REQ-EDGE-104-0001"
                        if case == "foundation_edge"
                        else "Program scope or independent EDGE indexes are invalid"
                    )
                    self.assertIn(expected, result.stdout)



if __name__ == "__main__":
    unittest.main()

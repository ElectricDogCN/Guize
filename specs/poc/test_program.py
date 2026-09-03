#!/usr/bin/env python3
"""Positive and negative tests for POC-PROTOCOL-V1."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("poc_check_program", HERE / "check_program.py")
CHECK = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CHECK)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True, width=120)


class TestPocProgram(unittest.TestCase):
    def setUp(self):
        self.repo = HERE.parents[1]

    def temp_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        shutil.copytree(self.repo / "specs" / "poc", root / "specs" / "poc")
        coordination = root / "specs" / "coordination"
        coordination.mkdir(parents=True)
        shutil.copy2(
            self.repo / "specs" / "coordination" / "program-plan.yaml",
            coordination / "program-plan.yaml",
        )
        active = self.repo / "specs" / "coordination" / "active-work.yaml"
        if active.is_file():
            shutil.copy2(active, coordination / "active-work.yaml")
        return temp, root

    def assert_invalid(self, mutator, needle=None):
        temp, root = self.temp_repo()
        try:
            mutator(root)
            errors = CHECK.validate_repository(root)
            self.assertTrue(errors, "negative mutation unexpectedly passed")
            if needle:
                self.assertTrue(
                    any(needle in error for error in errors),
                    "\n".join(errors),
                )
        finally:
            temp.cleanup()

    def plan_path(self, root, task_id):
        return root / "specs" / "poc" / "plans" / f"{task_id}.yaml"

    def index_path(self, root):
        return root / "specs" / "poc" / "results-index.yaml"

    def pp_path(self, root):
        return root / "specs" / "coordination" / "program-plan.yaml"

    def task_path(self, root, task_id):
        return root / "specs" / "tasks" / f"{task_id}.md"

    def write_task_spec(self, root, task_id, implementer=None, reviewer=None):
        implementer = implementer or f"{task_id.lower()}-implementer"
        reviewer = reviewer or f"{task_id.lower()}-reviewer"
        path = self.task_path(root, task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "schemaVersion: 2\n"
            f"id: {task_id}\n"
            "status: in_progress\n"
            "coordinationMode: registry\n"
            f"implementer: {implementer}\n"
            f"reviewer: {reviewer}\n"
            "---\n\n"
            f"# {task_id} fixture\n",
            encoding="utf-8",
        )
        return implementer, reviewer

    def make_terminal(self, root, task_id="POC-003", status="pass"):
        plan = load_yaml(self.plan_path(root, task_id))
        implementer, reviewer = self.write_task_spec(root, task_id)
        evidence_dir = root / plan["evidencePath"]
        evidence_dir.mkdir(parents=True, exist_ok=True)

        raw_ref = f"{plan['evidencePath']}/raw/execution.log"
        raw_path = root / raw_ref
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("bounded raw output\n", encoding="utf-8")

        samples = []
        for sample_id in plan["sampleIds"]:
            checksum = "sha256:" + "b" * 64
            immutable_id = f"fixture-{sample_id.lower()}"
            approval_ref = f"{plan['evidencePath']}/approvals/{sample_id}.yaml"
            approval = {
                "schemaVersion": 1,
                "pocId": plan["pocId"],
                "taskId": task_id,
                "sampleId": sample_id,
                "immutableId": immutable_id,
                "checksum": checksum,
                "decision": "approved",
                "approver": f"{task_id.lower()}-sample-approver",
                "approvedAt": "2026-09-03T00:00:00Z",
            }
            write_yaml(root / approval_ref, approval)
            samples.append(
                {
                    "id": sample_id,
                    "immutableId": immutable_id,
                    "checksum": checksum,
                    "approved": True,
                    "approvalRef": approval_ref,
                }
            )

        environment = {
            key: (
                {"fixed": "value"}
                if key == "inference_parameters"
                else f"captured-{key}"
            )
            for key in plan["environment"]["captureBeforeExecution"]
        }

        measurements = []
        for measurement in plan["protocol"]["measurements"]:
            actual = True if str(measurement["unit"]).lower() == "boolean" else 1
            if status != "pass" and str(measurement["unit"]).lower() == "boolean":
                actual = False
            measurements.append({"id": measurement["id"], "actual": actual})

        provenance = {}
        if plan["pocId"] == "POC-02":
            provenance = {
                "input_sha256": samples[0]["checksum"],
                "output_sha256": "sha256:" + "c" * 64,
                "encoder_parameters": {
                    "codec": "av1",
                    "crf": 30,
                    "preset": "medium",
                },
            }

        execution_ref = f"{plan['evidencePath']}/execution.yaml"
        execution = {
            "schemaVersion": 1,
            "pocId": plan["pocId"],
            "taskId": task_id,
            "evidencePath": plan["evidencePath"],
            "executor": implementer,
            "environmentCaptured": environment,
            "commands": ["bounded-test-command --fixture approved"],
            "rawOutputRefs": [raw_ref],
            "samples": samples,
            "measurements": measurements,
            "provenance": provenance,
            "notes": None,
        }
        write_yaml(root / execution_ref, execution)

        result_ref = f"{plan['evidencePath']}/result.yaml"
        result = {
            "schemaVersion": 1,
            "pocId": plan["pocId"],
            "taskId": task_id,
            "status": status,
            "evidencePath": plan["evidencePath"],
            "executionRef": execution_ref,
            "decision": status,
            "rationale": "fixture result backed by existing raw evidence and complete measurements",
            "reviewer": reviewer,
            "approvedAt": "2026-09-03T00:00:00Z",
            "approval": "approved",
        }
        write_yaml(root / result_ref, result)

        index = load_yaml(self.index_path(root))
        entry = next(item for item in index["entries"] if item["taskId"] == task_id)
        entry.update(
            {
                "status": status,
                "resultRef": result_ref,
                "decision": status,
                "reviewer": reviewer,
                "approvedAt": "2026-09-03T00:00:00Z",
            }
        )
        write_yaml(self.index_path(root), index)
        return plan, root / execution_ref, root / result_ref

    def approval_path(self, root, execution_path):
        execution = load_yaml(execution_path)
        return root / execution["samples"][0]["approvalRef"]

    def test_01_positive_baseline(self):
        self.assertEqual(CHECK.validate_repository(self.repo), [])

    def test_02_missing_plan(self):
        self.assert_invalid(
            lambda root: self.plan_path(root, "POC-001").unlink(),
            "missing POC plan",
        )

    def test_03_poc_task_mismatch(self):
        def mutate(root):
            path = self.plan_path(root, "POC-001")
            data = load_yaml(path)
            data["taskId"] = "POC-002"
            write_yaml(path, data)
        self.assert_invalid(mutate, "POC↔Task mismatch")

    def test_04_wrong_risk(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003")
            data = load_yaml(path)
            data["riskLevel"] = "high"
            write_yaml(path, data)
        self.assert_invalid(mutate, "riskLevel")

    def test_05_wrong_wave(self):
        def mutate(root):
            path = self.plan_path(root, "POC-005")
            data = load_yaml(path)
            data["wave"] = "W9"
            write_yaml(path, data)
        self.assert_invalid(mutate, "wave")

    def test_06_wrong_requirement(self):
        def mutate(root):
            path = self.plan_path(root, "POC-006")
            data = load_yaml(path)
            data["requirementIds"] = ["REQ-V1-0002"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "requirementIds")

    def test_07_wrong_module(self):
        def mutate(root):
            path = self.plan_path(root, "POC-008")
            data = load_yaml(path)
            data["moduleIds"] = ["MOD-AI"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "moduleIds")

    def test_08_wrong_evidence_path(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009")
            data = load_yaml(path)
            data["evidencePath"] = "evidence/POC-008"
            write_yaml(path, data)
        self.assert_invalid(mutate, "evidencePath")

    def test_09_wrong_dependency(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            data["dependsOn"] = ["GZ-010"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "dependsOn")

    def test_10_duplicate_evidence_path(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            data["evidencePath"] = "evidence/POC-001"
            write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate POC evidence path")

    def test_11_unknown_resource(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003")
            data = load_yaml(path)
            data["resourceIds"] = ["RES-UNKNOWN"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "unknown resource")

    def test_12_unknown_sample(self):
        def mutate(root):
            path = self.plan_path(root, "POC-004")
            data = load_yaml(path)
            data["sampleIds"] = ["SAMPLE-UNKNOWN"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "unknown sample")

    def test_13_plan_status_is_immutable(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003")
            data = load_yaml(path)
            data["status"] = "running"
            data["resultStatus"] = "running"
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_14_prefilled_plan_command_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-005")
            data = load_yaml(path)
            data["protocol"]["commands"] = ["x"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_15_prefilled_plan_measurement_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009")
            data = load_yaml(path)
            data["protocol"]["measurements"][0]["actual"] = 1
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_16_prefilled_plan_decision_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-010")
            data = load_yaml(path)
            data["decision"]["status"] = "pass"
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_17_prefilled_plan_reviewer_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-008")
            data = load_yaml(path)
            data["review"]["reviewer"] = "x"
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_18_catalogue_sample_must_remain_pending(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"][0]["approvalState"] = "approved"
            write_yaml(path, data)
        self.assert_invalid(mutate, "approvalState must remain pending")

    def test_19_catalogue_sample_identity_must_remain_tbd(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"][0]["immutableId"] = "fixture-sample"
            write_yaml(path, data)
        self.assert_invalid(mutate, "immutableId must remain TBD")

    def test_20_required_measurement_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-001")
            data = load_yaml(path)
            data["protocol"]["measurements"] = [
                item for item in data["protocol"]["measurements"]
                if item["id"] != "vm_reboot_recovery"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_21_poc002_encode_provenance_gate_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            data["protocol"]["measurements"] = [
                item for item in data["protocol"]["measurements"]
                if item["id"] != "encode_provenance_complete"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_22_poc010_secret_roundtrip_gate_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-010")
            data = load_yaml(path)
            data["protocol"]["measurements"] = [
                item for item in data["protocol"]["measurements"]
                if item["id"] != "secret_value_roundtrip"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_23_ai_provenance_capture_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009")
            data = load_yaml(path)
            data["environment"]["captureBeforeExecution"].remove("prompt_template_version")
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing required environment provenance fields")

    def test_24_downstream_task_must_own_evidence_path(self):
        def mutate(root):
            path = self.pp_path(root)
            data = load_yaml(path)
            task = next(item for item in data["tasks"] if item["taskId"] == "POC-003")
            task["outputPaths"] = [
                item for item in task["outputPaths"]
                if not item.startswith("evidence/POC-003")
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "must own its Evidence path")

    def test_25_downstream_task_must_share_results_index(self):
        def mutate(root):
            path = self.pp_path(root)
            data = load_yaml(path)
            task = next(item for item in data["tasks"] if item["taskId"] == "POC-003")
            task["sharedPaths"] = [
                item for item in task.get("sharedPaths", [])
                if item != "specs/poc/results-index.yaml"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "must share specs/poc/results-index.yaml")

    def test_26_terminal_pass_fixture_is_valid(self):
        temp, root = self.temp_repo()
        try:
            self.make_terminal(root)
            self.assertEqual(CHECK.validate_repository(root), [])
        finally:
            temp.cleanup()

    def test_27_terminal_result_ref_must_exist(self):
        def mutate(root):
            _, _, result = self.make_terminal(root)
            result.unlink()
        self.assert_invalid(mutate, "terminal resultRef must point to an existing file")

    def test_28_terminal_execution_ref_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            execution.unlink()
        self.assert_invalid(mutate, "executionRef must point to an existing file")

    def test_29_raw_evidence_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            (root / data["rawOutputRefs"][0]).unlink()
        self.assert_invalid(mutate, "raw evidence file must exist")

    def test_30_approval_ref_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            self.approval_path(root, execution).unlink()
        self.assert_invalid(mutate, "approvalRef must exist")

    def test_31_bad_checksum_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["samples"][0]["checksum"] = "x"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "checksum must be sha256")

    def test_32_placeholder_immutable_id_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["samples"][0]["immutableId"] = "TBD"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "immutableId")

    def test_33_empty_environment_value_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            key = next(iter(data["environmentCaptured"]))
            data["environmentCaptured"][key] = ""
            write_yaml(execution, data)
        self.assert_invalid(mutate, "empty/placeholder environment values")

    def test_34_placeholder_environment_value_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            key = next(iter(data["environmentCaptured"]))
            data["environmentCaptured"][key] = "TBD"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "empty/placeholder environment values")

    def test_35_empty_string_measurement_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["measurements"][0]["actual"] = ""
            write_yaml(execution, data)
        self.assert_invalid(mutate, "invalid/placeholder measurement values")

    def test_36_nonfinite_measurement_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["measurements"][0]["actual"] = float("inf")
            write_yaml(execution, data)
        self.assert_invalid(mutate, "invalid/placeholder measurement values")

    def test_37_pass_false_boolean_gate_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            target = next(
                item for item in data["measurements"]
                if isinstance(item["actual"], bool)
            )
            target["actual"] = False
            write_yaml(execution, data)
        self.assert_invalid(mutate, "PASS has false/non-true boolean gates")

    def test_38_missing_measurement_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["measurements"].pop()
            write_yaml(execution, data)
        self.assert_invalid(mutate, "measurement IDs must exactly match plan")

    def test_39_poc002_missing_input_hash_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"].pop("input_sha256")
            write_yaml(execution, data)
        self.assert_invalid(mutate, "missing required provenance fields")

    def test_40_poc002_invalid_output_hash_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"]["output_sha256"] = "sha256:x"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "provenance output_sha256")

    def test_41_poc002_empty_encoder_parameters_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"]["encoder_parameters"] = {}
            write_yaml(execution, data)
        self.assert_invalid(mutate, "encoder_parameters")

    def test_42_wrong_executor_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["executor"] = "another-implementer"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "executor")

    def test_43_self_review_rejected(self):
        def mutate(root):
            _, execution, result = self.make_terminal(root)
            executor = load_yaml(execution)["executor"]
            result_data = load_yaml(result)
            result_data["reviewer"] = executor
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["reviewer"] = executor
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "reviewer")

    def test_44_result_index_metadata_mismatch_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["approvedAt"] = "2026-09-04T00:00:00Z"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "approvedAt")

    def test_45_nonterminal_fields_must_be_null(self):
        def mutate(root):
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["status"] = "blocked"
            entry["decision"] = "pass"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "nonterminal blocked decision must be null")

    def test_46_compound_secret_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0]["productionApiKeyValue"] = "opaque"
            write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_47_compound_auth_token_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0]["authTokenValue"] = "opaque"
            write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_48_secret_value_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["commands"] = ["tool --token=super-secret-value"]
            write_yaml(execution, data)
        self.assert_invalid(mutate, "secret-like value")

    def test_49_result_path_escape_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["resultRef"] = "evidence/POC-003/../POC-999/result.yaml"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "terminal resultRef")

    def test_50_raw_path_escape_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["rawOutputRefs"] = ["evidence/POC-003/../POC-999/raw.log"]
            write_yaml(execution, data)
        self.assert_invalid(mutate, "raw evidence file must exist")

    def test_51_symlink_escape_rejected(self):
        temp, root = self.temp_repo()
        try:
            _, execution, _ = self.make_terminal(root)
            outside = root / "outside.log"
            outside.write_text("outside", encoding="utf-8")
            link = root / "evidence" / "POC-003" / "raw" / "link.log"
            link.unlink(missing_ok=True)
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks unavailable")
            data = load_yaml(execution)
            data["rawOutputRefs"] = ["evidence/POC-003/raw/link.log"]
            write_yaml(execution, data)
            errors = CHECK.validate_repository(root)
            self.assertTrue(
                any("raw evidence file must exist" in error for error in errors),
                "\n".join(errors),
            )
        finally:
            temp.cleanup()

    def test_52_fail_terminal_allows_false_boolean_gate(self):
        temp, root = self.temp_repo()
        try:
            self.make_terminal(root, "POC-003", "fail")
            self.assertEqual(CHECK.validate_repository(root), [])
        finally:
            temp.cleanup()

    def test_53_program_manifest_requires_record_contracts(self):
        def mutate(root):
            path = root / "specs" / "poc" / "program.yaml"
            data = load_yaml(path)
            data["executionRecordSchema"] = "wrong.yaml"
            write_yaml(path, data)
        self.assert_invalid(mutate, "executionRecordSchema")

    def test_54_policy_requires_immutable_plans(self):
        def mutate(root):
            path = root / "specs" / "poc" / "policy.yaml"
            data = load_yaml(path)
            data["canonicalPlansImmutable"] = False
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonicalPlansImmutable")

    def test_55_missing_concrete_task_spec_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            self.task_path(root, "POC-003").unlink()
        self.assert_invalid(mutate, "concrete Task Spec is required")

    def test_56_generic_role_labels_rejected(self):
        def mutate(root):
            _, execution, result = self.make_terminal(root)
            self.write_task_spec(
                root,
                "POC-003",
                implementer="task-owner-agent",
                reviewer="independent-review-agent",
            )
            execution_data = load_yaml(execution)
            execution_data["executor"] = "task-owner-agent"
            write_yaml(execution, execution_data)
            result_data = load_yaml(result)
            result_data["reviewer"] = "independent-review-agent"
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["reviewer"] = "independent-review-agent"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "must not reuse generic Program role labels")

    def test_57_task_spec_self_review_rejected(self):
        def mutate(root):
            _, execution, result = self.make_terminal(root)
            executor = load_yaml(execution)["executor"]
            self.write_task_spec(
                root, "POC-003", implementer=executor, reviewer=executor
            )
            result_data = load_yaml(result)
            result_data["reviewer"] = executor
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["reviewer"] = executor
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "implementer and reviewer must be distinct")

    def test_58_active_work_role_drift_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            path = root / "specs" / "coordination" / "active-work.yaml"
            active = load_yaml(path) if path.is_file() else {
                "version": 1, "policy": {}, "tasks": []
            }
            active.setdefault("tasks", []).append(
                {
                    "taskId": "POC-003",
                    "implementer": "drifted-implementer",
                    "reviewer": "poc-003-reviewer",
                }
            )
            write_yaml(path, active)
        self.assert_invalid(mutate, "Active Work implementer does not match Task Spec")

    def test_59_safe_credential_metadata_requires_false(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0]["credentialsStoredInRepository"] = "opaque-secret"
            write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_60_approval_decision_must_be_approved(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["decision"] = "denied"
            write_yaml(path, data)
        self.assert_invalid(mutate, "sample approval")

    def test_61_approval_checksum_must_match_execution_sample(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["checksum"] = "sha256:" + "d" * 64
            write_yaml(path, data)
        self.assert_invalid(mutate, "checksum must equal")

    def test_62_approval_approver_must_differ_from_implementer(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            executor = load_yaml(execution)["executor"]
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["approver"] = executor
            write_yaml(path, data)
        self.assert_invalid(mutate, "approver must differ")

    def test_63_approval_timestamp_must_be_real_utc_instant(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["approvedAt"] = "2026-99-99T99:99:99Z"
            write_yaml(path, data)
        self.assert_invalid(mutate, "valid UTC instant")

    def test_64_ai_model_identity_must_be_text(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-009")
            data = load_yaml(execution)
            data["environmentCaptured"]["model_identity"] = True
            write_yaml(execution, data)
        self.assert_invalid(mutate, "AI provenance model_identity")

    def test_65_ai_model_version_must_be_text(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-009")
            data = load_yaml(execution)
            data["environmentCaptured"]["model_version"] = 1
            write_yaml(execution, data)
        self.assert_invalid(mutate, "AI provenance model_version")

    def test_66_poc002_input_hash_must_match_approved_sample(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"]["input_sha256"] = "sha256:" + "d" * 64
            write_yaml(execution, data)
        self.assert_invalid(mutate, "must match an approved execution sample checksum")

    def test_67_high_risk_running_concurrency_is_limited(self):
        def mutate(root):
            index = load_yaml(self.index_path(root))
            for task_id in ("POC-001", "POC-002"):
                entry = next(item for item in index["entries"] if item["taskId"] == task_id)
                entry["status"] = "running"
                self.write_task_spec(root, task_id)
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "running high/critical POC count")

    def test_68_critical_poc_runs_standalone(self):
        def mutate(root):
            index = load_yaml(self.index_path(root))
            for task_id in ("POC-010", "POC-003"):
                entry = next(item for item in index["entries"] if item["taskId"] == task_id)
                entry["status"] = "running"
                self.write_task_spec(root, task_id)
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "critical POC must run standalone")

    def test_69_duplicate_resource_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"].append(dict(data["resources"][0]))
            write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate id")

    def test_70_missing_resource_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0].pop("id")
            write_yaml(path, data)
        self.assert_invalid(mutate, "requires nonempty id")

    def test_71_duplicate_sample_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"].append(dict(data["samples"][0]))
            write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate id")

    def test_72_missing_sample_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"][0].pop("id")
            write_yaml(path, data)
        self.assert_invalid(mutate, "requires nonempty id")

    def test_73_missing_execution_template_rejected(self):
        def mutate(root):
            (root / "specs" / "poc" / "templates" / "execution-record.yaml").unlink()
        self.assert_invalid(mutate, "executionRecordTemplate")

    def test_74_missing_approval_template_rejected(self):
        def mutate(root):
            (root / "specs" / "poc" / "templates" / "sample-approval.yaml").unlink()
        self.assert_invalid(mutate, "sampleApprovalTemplate")

    def test_75_duplicate_yaml_mapping_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "program.yaml"
            with path.open("a", encoding="utf-8") as handle:
                handle.write("executionEnabled: true\n")
        self.assert_invalid(mutate, "duplicate key")

    def test_76_downstream_task_cannot_own_immutable_poc_plan(self):
        def mutate(root):
            path = self.pp_path(root)
            data = load_yaml(path)
            task = next(item for item in data["tasks"] if item["taskId"] == "POC-003")
            task["outputPaths"].append("specs/poc/plans/POC-003.yaml")
            write_yaml(path, data)
        self.assert_invalid(mutate, "may not own immutable specs/poc paths")

    def test_77_result_timestamp_must_be_valid(self):
        def mutate(root):
            _, _, result = self.make_terminal(root)
            result_data = load_yaml(result)
            result_data["approvedAt"] = "2026-99-99T99:99:99Z"
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["approvedAt"] = "2026-99-99T99:99:99Z"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "valid UTC instant")

    def test_78_row_ownership_rejects_other_task_change(self):
        base = load_yaml(self.repo / "specs" / "poc" / "results-index.yaml")
        current = yaml.safe_load(yaml.safe_dump(base))
        entry = next(item for item in current["entries"] if item["taskId"] == "POC-004")
        entry["status"] = "running"
        errors = []
        CHECK.validate_result_index_row_ownership(base, current, "POC-003", errors)
        self.assertTrue(any("changed other task rows" in error for error in errors), errors)

    def test_79_row_ownership_allows_only_own_row_change(self):
        base = load_yaml(self.repo / "specs" / "poc" / "results-index.yaml")
        current = yaml.safe_load(yaml.safe_dump(base))
        entry = next(item for item in current["entries"] if item["taskId"] == "POC-003")
        entry["status"] = "running"
        errors = []
        CHECK.validate_result_index_row_ownership(base, current, "POC-003", errors)
        self.assertEqual(errors, [])

    def test_80_template_missing_required_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "templates" / "result-record.yaml"
            data = load_yaml(path)
            data.pop("reviewer")
            write_yaml(path, data)
        self.assert_invalid(mutate, "template missing keys")


if __name__ == "__main__":
    unittest.main(verbosity=2)

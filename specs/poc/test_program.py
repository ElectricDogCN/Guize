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
        (root / "specs" / "coordination").mkdir(parents=True)
        shutil.copy2(
            self.repo / "specs" / "coordination" / "program-plan.yaml",
            root / "specs" / "coordination" / "program-plan.yaml",
        )
        return temp, root

    def assert_invalid(self, mutator, needle=None):
        temp, root = self.temp_repo()
        try:
            mutator(root)
            errors = CHECK.validate_repository(root)
            self.assertTrue(errors, "negative mutation unexpectedly passed")
            if needle:
                self.assertTrue(any(needle in error for error in errors), "\n".join(errors))
        finally:
            temp.cleanup()

    def plan_path(self, root: Path, task_id: str) -> Path:
        return root / "specs" / "poc" / "plans" / f"{task_id}.yaml"

    def approve_samples(self, root: Path, plan: dict):
        path = root / "specs" / "poc" / "samples.yaml"
        samples = load_yaml(path)
        wanted = set(plan.get("sampleIds") or [])
        for sample in samples["samples"]:
            if sample["id"] in wanted:
                sample["approvalState"] = "approved"
                sample["immutableId"] = f"immutable-{sample['id'].lower()}"
                sample["checksum"] = "sha256:" + "a" * 64
        write_yaml(path, samples)

    def make_terminal(self, root: Path, task_id="POC-003", result_status="pass"):
        path = self.plan_path(root, task_id)
        plan = load_yaml(path)
        plan["status"] = "completed"
        plan["resultStatus"] = result_status
        self.approve_samples(root, plan)
        plan["environment"]["capturedValues"] = {
            key: "captured" for key in plan["environment"]["captureBeforeExecution"]
        }
        evidence = plan["evidencePath"]
        plan["protocol"]["commands"] = ["bounded-test-command --fixture approved"]
        plan["protocol"]["rawOutputRefs"] = [f"{evidence}/raw/execution.log"]
        for measurement in plan["protocol"]["measurements"]:
            measurement["actual"] = True if str(measurement.get("unit")).lower() == "boolean" else 1
        plan["decision"] = {
            "status": result_status,
            "rationale": "fixture result backed by measurements and raw evidence",
            "resultRef": f"{evidence}/result.yaml",
        }
        plan["review"] = {
            "reviewer": "independent-reviewer",
            "approvedAt": "2026-09-02T00:00:00Z",
            "approval": "approved",
        }
        write_yaml(path, plan)

        index_path = root / "specs" / "poc" / "results-index.yaml"
        index = load_yaml(index_path)
        for entry in index["entries"]:
            if entry["taskId"] == task_id:
                entry.update({
                    "status": result_status,
                    "resultRef": f"{evidence}/result.yaml",
                    "decision": result_status,
                    "reviewer": "independent-reviewer",
                    "approvedAt": "2026-09-02T00:00:00Z",
                })
        write_yaml(index_path, index)
        return path, index_path

    def test_01_positive_baseline(self):
        errors = CHECK.validate_repository(self.repo)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_02_missing_plan(self):
        self.assert_invalid(lambda root: self.plan_path(root, "POC-001").unlink(), "missing POC plan")

    def test_03_poc_task_mismatch(self):
        def mutate(root):
            path = self.plan_path(root, "POC-001"); data = load_yaml(path); data["taskId"] = "POC-002"; write_yaml(path, data)
        self.assert_invalid(mutate, "POC↔Task mismatch")

    def test_04_wrong_risk(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003"); data = load_yaml(path); data["riskLevel"] = "high"; write_yaml(path, data)
        self.assert_invalid(mutate, "riskLevel")

    def test_05_wrong_wave(self):
        def mutate(root):
            path = self.plan_path(root, "POC-005"); data = load_yaml(path); data["wave"] = "W9"; write_yaml(path, data)
        self.assert_invalid(mutate, "wave")

    def test_06_wrong_requirement(self):
        def mutate(root):
            path = self.plan_path(root, "POC-006"); data = load_yaml(path); data["requirementIds"] = ["REQ-V1-0002"]; write_yaml(path, data)
        self.assert_invalid(mutate, "requirementIds")

    def test_07_wrong_module(self):
        def mutate(root):
            path = self.plan_path(root, "POC-008"); data = load_yaml(path); data["moduleIds"] = ["MOD-AI"]; write_yaml(path, data)
        self.assert_invalid(mutate, "moduleIds")

    def test_08_wrong_evidence_path(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009"); data = load_yaml(path); data["evidencePath"] = "evidence/POC-008"; write_yaml(path, data)
        self.assert_invalid(mutate, "evidencePath")

    def test_09_wrong_dependency(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002"); data = load_yaml(path); data["dependsOn"] = ["GZ-010"]; write_yaml(path, data)
        self.assert_invalid(mutate, "dependsOn")

    def test_10_duplicate_evidence_path(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002"); data = load_yaml(path); data["evidencePath"] = "evidence/POC-001"; write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate POC evidence path")

    def test_11_unknown_resource(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003"); data = load_yaml(path); data["resourceIds"] = ["RES-UNKNOWN"]; write_yaml(path, data)
        self.assert_invalid(mutate, "unknown resource")

    def test_12_unknown_sample(self):
        def mutate(root):
            path = self.plan_path(root, "POC-004"); data = load_yaml(path); data["sampleIds"] = ["SAMPLE-UNKNOWN"]; write_yaml(path, data)
        self.assert_invalid(mutate, "unknown sample")

    def test_13_unapproved_sample_cannot_execute(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003"); data = load_yaml(path)
            data["status"] = "running"; data["resultStatus"] = "running"; data["protocol"]["commands"] = ["placeholder-execution-command"]
            write_yaml(path, data)
            index_path = root / "specs/poc/results-index.yaml"; index = load_yaml(index_path)
            next(e for e in index["entries"] if e["taskId"] == "POC-003")["status"] = "running"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "execution cannot use unapproved sample")

    def test_14_prefilled_command_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-005"); data = load_yaml(path); data["protocol"]["commands"] = ["prefilled-command"]; write_yaml(path, data)
        self.assert_invalid(mutate, "must not contain execution commands")

    def test_15_prefilled_measurement_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009"); data = load_yaml(path); data["protocol"]["measurements"][0]["actual"] = 0.99; write_yaml(path, data)
        self.assert_invalid(mutate, "measurement actual must be null")

    def test_16_prefilled_decision_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-010"); data = load_yaml(path); data["decision"]["status"] = "pass"; write_yaml(path, data)
        self.assert_invalid(mutate, "decision fields")

    def test_17_prefilled_reviewer_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-008"); data = load_yaml(path); data["review"]["reviewer"] = "someone"; write_yaml(path, data)
        self.assert_invalid(mutate, "review fields")

    def test_18_secret_like_content_rejected(self):
        def mutate(root):
            path = root / "specs/poc/resources.yaml"; data = load_yaml(path); data["resources"][0]["description"] = "token=super-secret-value"; write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like value")

    def test_19_critical_scheduling_violation_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009"); data = load_yaml(path); data["wave"] = "W11"; write_yaml(path, data)
        self.assert_invalid(mutate, "wave")

    def test_20_result_index_status_must_match_plan(self):
        def mutate(root):
            path = root / "specs/poc/results-index.yaml"; data = load_yaml(path); data["entries"][0]["status"] = "running"; write_yaml(path, data)
        self.assert_invalid(mutate, "does not match plan resultStatus")

    def test_21_running_execution_requires_environment_capture(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003"); data = load_yaml(path); self.approve_samples(root, data)
            data["status"] = "running"; data["resultStatus"] = "running"; data["protocol"]["commands"] = ["bounded-test-command"]
            write_yaml(path, data)
            index_path = root / "specs/poc/results-index.yaml"; index = load_yaml(index_path); next(e for e in index["entries"] if e["taskId"] == "POC-003")["status"] = "running"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "execution requires captured environment")

    def test_22_pass_without_measurement_evidence_review_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003"); data = load_yaml(path); self.approve_samples(root, data)
            data["status"] = "completed"; data["resultStatus"] = "pass"; data["environment"]["capturedValues"] = {k: "captured" for k in data["environment"]["captureBeforeExecution"]}
            data["protocol"]["commands"] = ["bounded-test-command"]
            data["decision"] = {"status": "pass", "rationale": "prose alone", "resultRef": "evidence/POC-003/result.json"}
            write_yaml(path, data)
            index_path = root / "specs/poc/results-index.yaml"; result = load_yaml(index_path); entry = next(e for e in result["entries"] if e["taskId"] == "POC-003")
            entry.update({"status": "pass", "resultRef": "evidence/POC-003/result.json", "decision": "pass", "reviewer": "reviewer-a", "approvedAt": "2026-09-01T00:00:00Z"}); write_yaml(index_path, result)
        self.assert_invalid(mutate, "requires raw evidence references")

    def test_23_terminal_pass_fixture_is_valid(self):
        temp, root = self.temp_repo()
        try:
            self.make_terminal(root)
            self.assertEqual(CHECK.validate_repository(root), [])
        finally:
            temp.cleanup()

    def test_24_required_measurement_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-001"); data = load_yaml(path); data["protocol"]["measurements"] = [m for m in data["protocol"]["measurements"] if m["id"] != "vm_reboot_recovery"]; write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_25_ai_provenance_capture_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009"); data = load_yaml(path); data["environment"]["captureBeforeExecution"].remove("prompt_template_version"); write_yaml(path, data)
        self.assert_invalid(mutate, "missing required environment provenance fields")

    def test_26_approved_placeholder_sample_cannot_execute(self):
        def mutate(root):
            sample_path = root / "specs/poc/samples.yaml"; samples = load_yaml(sample_path); sample = next(s for s in samples["samples"] if s["id"] == "SAMPLE-RANGE-LARGEFILE"); sample["approvalState"] = "approved"; write_yaml(sample_path, samples)
            path = self.plan_path(root, "POC-003"); data = load_yaml(path); data["status"] = "running"; data["resultStatus"] = "running"; data["protocol"]["commands"] = ["bounded"] ; data["environment"]["capturedValues"] = {k: "captured" for k in data["environment"]["captureBeforeExecution"]}; write_yaml(path, data)
            index_path = root / "specs/poc/results-index.yaml"; index = load_yaml(index_path); next(e for e in index["entries"] if e["taskId"] == "POC-003")["status"] = "running"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "immutable sample identity/checksum")

    def test_27_raw_evidence_outside_task_path_rejected(self):
        def mutate(root):
            path, _ = self.make_terminal(root); data = load_yaml(path); data["protocol"]["rawOutputRefs"] = ["evidence/POC-999/raw.log"]; write_yaml(path, data)
        self.assert_invalid(mutate, "raw evidence reference")

    def test_28_blank_raw_evidence_rejected(self):
        def mutate(root):
            path, _ = self.make_terminal(root); data = load_yaml(path); data["protocol"]["rawOutputRefs"] = [""]; write_yaml(path, data)
        self.assert_invalid(mutate, "raw evidence reference")

    def test_29_decision_result_ref_outside_path_rejected(self):
        def mutate(root):
            path, _ = self.make_terminal(root); data = load_yaml(path); data["decision"]["resultRef"] = "evidence/POC-999/result.yaml"; write_yaml(path, data)
        self.assert_invalid(mutate, "resultRef under")

    def test_30_result_index_ref_outside_path_rejected(self):
        def mutate(root):
            _, index_path = self.make_terminal(root); index = load_yaml(index_path); next(e for e in index["entries"] if e["taskId"] == "POC-003")["resultRef"] = "evidence/POC-999/result.yaml"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "completed resultRef")

    def test_31_compound_secret_key_rejected(self):
        def mutate(root):
            path = root / "specs/poc/resources.yaml"; data = load_yaml(path); data["resources"][0]["clientSecret"] = "actual-value"; write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_32_pass_with_false_boolean_gate_rejected(self):
        def mutate(root):
            path, _ = self.make_terminal(root); data = load_yaml(path); boolean_item = next(m for m in data["protocol"]["measurements"] if str(m.get("unit")).lower() == "boolean"); boolean_item["actual"] = False; write_yaml(path, data)
        self.assert_invalid(mutate, "PASS has false/non-true boolean gates")

    def test_33_terminal_result_requires_completed_plan(self):
        def mutate(root):
            path, _ = self.make_terminal(root); data = load_yaml(path); data["status"] = "running"; write_yaml(path, data)
        self.assert_invalid(mutate, "inconsistent lifecycle")

    def test_34_running_result_requires_running_plan(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003"); data = load_yaml(path); self.approve_samples(root, data); data["status"] = "ready"; data["resultStatus"] = "running"; data["protocol"]["commands"] = ["bounded"]; data["environment"]["capturedValues"] = {k: "captured" for k in data["environment"]["captureBeforeExecution"]}; write_yaml(path, data)
            index_path = root / "specs/poc/results-index.yaml"; index = load_yaml(index_path); next(e for e in index["entries"] if e["taskId"] == "POC-003")["status"] = "running"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "inconsistent lifecycle")

    def test_35_result_index_decision_must_match(self):
        def mutate(root):
            _, index_path = self.make_terminal(root); index = load_yaml(index_path); next(e for e in index["entries"] if e["taskId"] == "POC-003")["decision"] = "fail"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "decision does not match")

    def test_36_result_index_approved_at_must_match(self):
        def mutate(root):
            _, index_path = self.make_terminal(root); index = load_yaml(index_path); next(e for e in index["entries"] if e["taskId"] == "POC-003")["approvedAt"] = "2026-09-03T00:00:00Z"; write_yaml(index_path, index)
        self.assert_invalid(mutate, "approvedAt does not match")


if __name__ == "__main__":
    unittest.main(verbosity=2)

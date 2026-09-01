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

    def test_positive_baseline(self):
        errors = CHECK.validate_repository(self.repo)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_missing_plan(self):
        self.assert_invalid(
            lambda root: (root / "specs/poc/plans/POC-001.yaml").unlink(),
            "missing POC plan",
        )

    def test_poc_task_mismatch(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-001.yaml"
            data = load_yaml(path)
            data["taskId"] = "POC-002"
            write_yaml(path, data)
        self.assert_invalid(mutate, "POC↔Task mismatch")

    def test_wrong_risk(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-003.yaml"
            data = load_yaml(path); data["riskLevel"] = "high"; write_yaml(path, data)
        self.assert_invalid(mutate, "riskLevel")

    def test_wrong_wave(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-005.yaml"
            data = load_yaml(path); data["wave"] = "W9"; write_yaml(path, data)
        self.assert_invalid(mutate, "wave")

    def test_wrong_requirement(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-006.yaml"
            data = load_yaml(path); data["requirementIds"] = ["REQ-V1-0002"]; write_yaml(path, data)
        self.assert_invalid(mutate, "requirementIds")

    def test_wrong_module(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-008.yaml"
            data = load_yaml(path); data["moduleIds"] = ["MOD-AI"]; write_yaml(path, data)
        self.assert_invalid(mutate, "moduleIds")

    def test_wrong_evidence_path(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-009.yaml"
            data = load_yaml(path); data["evidencePath"] = "evidence/POC-008"; write_yaml(path, data)
        self.assert_invalid(mutate, "evidencePath")

    def test_wrong_dependency(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-002.yaml"
            data = load_yaml(path); data["dependsOn"] = ["GZ-010"]; write_yaml(path, data)
        self.assert_invalid(mutate, "dependsOn")

    def test_duplicate_evidence_path(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-002.yaml"
            data = load_yaml(path); data["evidencePath"] = "evidence/POC-001"; write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate POC evidence path")

    def test_unknown_resource(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-003.yaml"
            data = load_yaml(path); data["resourceIds"] = ["RES-UNKNOWN"]; write_yaml(path, data)
        self.assert_invalid(mutate, "unknown resource")

    def test_unknown_sample(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-004.yaml"
            data = load_yaml(path); data["sampleIds"] = ["SAMPLE-UNKNOWN"]; write_yaml(path, data)
        self.assert_invalid(mutate, "unknown sample")

    def test_unapproved_sample_cannot_execute(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-003.yaml"
            data = load_yaml(path)
            data["status"] = "running"; data["resultStatus"] = "running"
            data["protocol"]["commands"] = ["placeholder-execution-command"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "execution cannot use unapproved sample")

    def test_prefilled_command_rejected(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-005.yaml"
            data = load_yaml(path); data["protocol"]["commands"] = ["prefilled-command"]; write_yaml(path, data)
        self.assert_invalid(mutate, "must not contain execution commands")

    def test_prefilled_measurement_rejected(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-009.yaml"
            data = load_yaml(path); data["protocol"]["measurements"][0]["actual"] = 0.99; write_yaml(path, data)
        self.assert_invalid(mutate, "measurement actual must be null")

    def test_prefilled_decision_rejected(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-010.yaml"
            data = load_yaml(path); data["decision"]["status"] = "pass"; write_yaml(path, data)
        self.assert_invalid(mutate, "decision fields")

    def test_prefilled_reviewer_rejected(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-008.yaml"
            data = load_yaml(path); data["review"]["reviewer"] = "someone"; write_yaml(path, data)
        self.assert_invalid(mutate, "review fields")

    def test_secret_like_content_rejected(self):
        def mutate(root):
            path = root / "specs/poc/resources.yaml"
            data = load_yaml(path); data["resources"][0]["description"] = "token=super-secret-value"; write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like value")

    def test_critical_scheduling_violation_rejected(self):
        def mutate(root):
            path = root / "specs/poc/plans/POC-009.yaml"
            data = load_yaml(path); data["wave"] = "W11"; write_yaml(path, data)
        self.assert_invalid(mutate, "wave")


if __name__ == "__main__":
    unittest.main(verbosity=2)

import os
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORKFLOW_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")


class TestGovernanceWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as handle:
            cls.content = handle.read()
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as handle:
            cls.workflow = yaml.safe_load(handle)
        cls.steps = cls.workflow["jobs"]["governance-check"]["steps"]

    def _step(self, step_id):
        for step in self.steps:
            if step.get("id") == step_id:
                return step
        self.fail(f"Missing workflow step id: {step_id}")

    def test_spec_sync_is_a_gate(self):
        step = self._step("spec-sync")
        self.assertIn("scripts/check-spec-sync.py", step.get("run", ""))
        self.assertFalse(step.get("continue-on-error", False))

    def test_evidence_integrity_is_a_gate(self):
        step = self._step("evidence-integrity")
        self.assertIn("scripts/check-evidence-integrity.py", step.get("run", ""))
        self.assertFalse(step.get("continue-on-error", False))

    def test_task_context_allows_non_pr_non_task_refs(self):
        step = self._step("task-context")
        run = step.get("run", "")
        self.assertIn("task_specific=false", run)
        self.assertIn("github.head_ref", run)
        self.assertIn("Pull-request branch", run)

    def test_schema_check_uses_jsonschema_validator(self):
        step = self._step("schema-check")
        run = step.get("run", "")
        self.assertIn("jsonschema.validators.validator_for", run)
        self.assertIn("check_schema", run)

    def test_contract_changes_trigger_push_validation(self):
        on_section = self.workflow.get(True, self.workflow.get("on", {}))
        paths = on_section.get("push", {}).get("paths", [])
        self.assertIn("contracts/**", paths)


if __name__ == "__main__":
    unittest.main()

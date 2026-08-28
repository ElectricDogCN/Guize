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

    def test_project_readiness_is_a_gate(self):
        step = self._step("project-readiness")
        self.assertIn("scripts/check-project-readiness.py", step.get("run", ""))
        self.assertFalse(step.get("continue-on-error", False))

    def test_agent_coordination_is_a_gate(self):
        step = self._step("agent-coordination")
        run = step.get("run", "")
        self.assertIn("scripts/check-agent-coordination.py", run)
        self.assertIn("task-context.outputs.task_id", run)
        self.assertFalse(step.get("continue-on-error", False))

    def test_task_context_allows_non_pr_non_task_refs(self):
        step = self._step("task-context")
        run = step.get("run", "")
        self.assertIn("task_specific=false", run)
        self.assertIn("github.head_ref", run)
        self.assertIn("Pull-request branch", run)

    def test_schema_check_uses_shared_schema_script(self):
        step = self._step("schema-check")
        self.assertIn("scripts/check-schemas.py", step.get("run", ""))

    def test_all_main_pushes_trigger_validation(self):
        on_section = self.workflow.get(True, self.workflow.get("on", {}))
        push = on_section.get("push", {})
        self.assertIn("main", push.get("branches", []))
        self.assertNotIn("paths", push)
        self.assertNotIn("paths-ignore", push)

    def test_summary_reports_new_gates(self):
        step = self._step("summary")
        env = step.get("env", {})
        self.assertIn("PROJECT_READINESS", env)
        self.assertIn("AGENT_COORDINATION", env)
        run = step.get("run", "")
        self.assertIn("project_readiness", run)
        self.assertIn("agent_coordination", run)


if __name__ == "__main__":
    unittest.main()

import os
import re
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

    def test_program_integrity_and_history_are_mandatory_gates(self):
        step = self._step("program-integrity")
        run = step.get("run", "")
        self.assertIn("scripts/check-program-plan-integrity.py", run)
        self.assertIn("scripts/check-program-plan-history.py", run)
        self.assertIn("--base-ref", run)
        self.assertIn("--head-ref", run)
        self.assertIn("--task", run)
        self.assertFalse(step.get("continue-on-error", False))

    def test_agent_coordination_is_a_gate_with_real_refs(self):
        step = self._step("agent-coordination")
        run = step.get("run", "")
        self.assertIn("scripts/check-agent-coordination.py", run)
        self.assertIn("--base-ref", run)
        self.assertIn("origin/${{ github.base_ref }}", run)
        self.assertIn("--head-ref", run)
        self.assertIn('"HEAD"', run)
        self.assertIn("--branch-name", run)
        self.assertFalse(step.get("continue-on-error", False))

    def test_task_context_allows_non_pr_non_task_refs(self):
        run = self._step("task-context").get("run", "")
        self.assertIn("task_specific=false", run)
        self.assertIn("github.head_ref", run)
        self.assertIn("Pull-request branch", run)

    def test_schema_check_uses_shared_schema_script(self):
        self.assertIn("scripts/check-schemas.py", self._step("schema-check").get("run", ""))

    def test_all_main_pushes_trigger_validation(self):
        on_section = self.workflow.get(True, self.workflow.get("on", {}))
        push = on_section.get("push", {})
        self.assertIn("main", push.get("branches", []))
        self.assertNotIn("paths", push)
        self.assertNotIn("paths-ignore", push)

    def test_actions_are_immutable(self):
        for use in re.findall(r"^\s*uses:\s*(.+)$", self.content, re.MULTILINE):
            self.assertRegex(use.strip().split("@", 1)[1], r"^[0-9a-f]{40}$")

    def test_stale_runs_are_cancelled(self):
        concurrency = self.workflow.get("concurrency", {})
        self.assertTrue(concurrency.get("cancel-in-progress"))
        self.assertIn("github.event.pull_request.number", str(concurrency.get("group")))

    def test_governance_tests_run_after_earlier_validation_failure(self):
        condition = str(self._step("governance-tests").get("if", ""))
        self.assertIn("failure()", condition)

    def test_summary_reports_new_gates(self):
        step = self._step("summary")
        env = step.get("env", {})
        self.assertIn("PROJECT_READINESS", env)
        self.assertIn("PROGRAM_INTEGRITY", env)
        self.assertIn("AGENT_COORDINATION", env)
        run = step.get("run", "")
        self.assertIn("project_readiness", run)
        self.assertIn("program_integrity", run)
        self.assertIn("agent_coordination", run)


if __name__ == "__main__":
    unittest.main()

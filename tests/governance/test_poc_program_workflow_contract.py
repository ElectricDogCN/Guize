import os
import re
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORKFLOW_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "poc-program-gate.yml")


class TestPocProgramWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as handle:
            cls.content = handle.read()
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as handle:
            cls.workflow = yaml.safe_load(handle)
        cls.steps = cls.workflow["jobs"]["poc-program"]["steps"]

    def _step(self, step_id):
        for step in self.steps:
            if step.get("id") == step_id:
                return step
        self.fail(f"Missing workflow step id: {step_id}")

    def test_runs_on_pull_requests_and_all_main_pushes(self):
        on_section = self.workflow.get(True, self.workflow.get("on", {}))
        self.assertIn("pull_request", on_section)
        push = on_section.get("push", {})
        self.assertIn("main", push.get("branches", []))
        self.assertNotIn("paths", push)
        self.assertNotIn("paths-ignore", push)

    def test_actions_are_pinned_and_checkout_drops_credentials(self):
        for use in re.findall(r"^\s*uses:\s*(.+)$", self.content, re.MULTILINE):
            self.assertRegex(use.strip().split("@", 1)[1], r"^[0-9a-f]{40}$")
        checkout = self._step("checkout")
        self.assertFalse(checkout.get("with", {}).get("persist-credentials", True))
        self.assertEqual(checkout.get("with", {}).get("fetch-depth"), 0)

    def test_context_derives_task_from_registered_branch_shape(self):
        step = self._step("poc-context")
        run = step.get("run", "")
        self.assertIn('^(feat|fix|docs|refactor|chore)/([A-Z]+-[0-9]+)-.+$', run)
        self.assertIn('TASK_ID="${BASH_REMATCH[2]}"', run)
        self.assertIn('BASE_REF="origin/$BASE_BRANCH"', run)
        self.assertNotIn("|| true", run)

    def test_validation_is_fail_closed_and_runs_both_commands(self):
        step = self._step("poc-program-validation")
        run = step.get("run", "")
        self.assertIn('CHECKER="specs/poc/check_program.py"', run)
        self.assertIn('TESTS="specs/poc/test_program.py"', run)
        self.assertIn('python "$CHECKER" "${CHECK_ARGS[@]}"', run)
        self.assertIn('python "$TESTS"', run)
        self.assertIn('if [ ! -f "$CHECKER" ] || [ ! -f "$TESTS" ]', run)
        self.assertIn("exit 1", run)
        self.assertNotIn("|| true", run)
        self.assertFalse(step.get("continue-on-error", False))

    def test_pr_task_context_is_forwarded_to_validator(self):
        step = self._step("poc-program-validation")
        run = step.get("run", "")
        self.assertIn('CHECK_ARGS+=(--task "$TASK_ID" --base-ref "$BASE_REF" --head-ref HEAD)', run)
        env = step.get("env", {})
        self.assertIn("TASK_ID", env)
        self.assertIn("BASE_REF", env)

    def test_absent_contract_is_the_only_skip_case(self):
        run = self._step("poc-program-validation").get("run", "")
        self.assertIn('if [ ! -e "$CHECKER" ] && [ ! -e "$TESTS" ]', run)
        self.assertIn("no POC Program validation is required", run)

    def test_summary_reports_validation_and_context_outcomes(self):
        step = self._step("summary")
        self.assertEqual(step.get("if"), "always()")
        env = step.get("env", {})
        self.assertIn("POC_CONTEXT", env)
        self.assertIn("POC_PROGRAM_VALIDATION", env)
        run = step.get("run", "")
        self.assertIn("poc_context", run)
        self.assertIn("poc_program_validation", run)
        self.assertIn("Resolved task", run)

    def test_stale_runs_are_cancelled(self):
        concurrency = self.workflow.get("concurrency", {})
        self.assertTrue(concurrency.get("cancel-in-progress"))
        self.assertIn("github.event.pull_request.number", str(concurrency.get("group")))


if __name__ == "__main__":
    unittest.main()

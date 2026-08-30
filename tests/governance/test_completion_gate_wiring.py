import os
import re
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
MAKEFILE = os.path.join(REPO_ROOT, "Makefile")


class TestCompletionGateWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW, "r", encoding="utf-8") as handle:
            cls.workflow = handle.read()
        with open(MAKEFILE, "r", encoding="utf-8") as handle:
            cls.makefile = handle.read()
        match = re.search(
            r"(?ms)^program-integrity-check:\n(?P<body>.*?)(?=^[A-Za-z0-9_-]+:\n)",
            cls.makefile,
        )
        if not match:
            raise AssertionError("program-integrity-check recipe is missing")
        cls.program_recipe = match.group("body")

    def test_workflow_routes_scope_through_dispatcher(self):
        self.assertIn("python scripts/run-task-scope-gate.py", self.workflow)
        self.assertNotRegex(
            self.workflow,
            re.compile(r"python\s+scripts/check-task-scope\.py\s+--task"),
        )

    def test_makefile_routes_scope_through_dispatcher(self):
        self.assertIn("scripts/run-task-scope-gate.py", self.makefile)
        self.assertNotIn(
            "$(PYTHON) scripts/check-task-scope.py --task $(TASK)",
            self.makefile,
        )

    def test_workflow_requires_program_history_transitions_and_finalization(self):
        self.assertIn("python scripts/check-program-plan-history.py", self.workflow)
        self.assertIn("python scripts/check-program-plan-transitions.py", self.workflow)
        self.assertIn("python scripts/check-program-plan-finalization.py", self.workflow)
        self.assertIn("--base-ref \"$BASE_REF\"", self.workflow)
        self.assertIn("--head-ref \"$HEAD_REF\"", self.workflow)

    def test_make_verify_requires_program_history_transitions_and_finalization(self):
        self.assertIn("scripts/check-program-plan-history.py", self.program_recipe)
        self.assertIn("scripts/check-program-plan-transitions.py", self.program_recipe)
        self.assertIn("scripts/check-program-plan-finalization.py", self.program_recipe)
        self.assertIn("program-integrity-check", self.makefile)

    def test_makefile_program_recipe_is_fail_fast(self):
        self.assertIn("@set -e;", self.program_recipe)
        history = self.program_recipe.index("scripts/check-program-plan-history.py")
        transitions = self.program_recipe.index("scripts/check-program-plan-transitions.py")
        finalization = self.program_recipe.index("scripts/check-program-plan-finalization.py")
        self.assertLess(history, transitions)
        self.assertLess(transitions, finalization)

    def test_workflow_routes_coordination_through_dispatcher(self):
        self.assertIn("python scripts/run-agent-coordination-gate.py", self.workflow)


if __name__ == "__main__":
    unittest.main()

import copy
import os
import unittest

import jsonschema
import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_PATH = os.path.join(REPO_ROOT, "specs", "coordination", "program-plan.schema.yaml")
PLAN_PATH = os.path.join(REPO_ROOT, "specs", "coordination", "program-plan.yaml")


class TestProgramPlanSafetyLimits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
            cls.schema = yaml.safe_load(handle)
        with open(PLAN_PATH, "r", encoding="utf-8") as handle:
            cls.plan = yaml.safe_load(handle)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def _assert_invalid(self, key, value):
        document = copy.deepcopy(self.plan)
        document["parallelPolicy"][key] = value
        errors = list(self.validator.iter_errors(document))
        self.assertTrue(errors, f"Expected {key}={value!r} to violate Program Plan schema")
        locations = ["/".join(str(part) for part in error.absolute_path) for error in errors]
        self.assertTrue(any(f"parallelPolicy/{key}" in location for location in locations), locations)

    def test_max_active_tasks_cannot_exceed_repository_limit(self):
        self._assert_invalid("maxActiveTasks", 4)

    def test_max_high_risk_tasks_cannot_exceed_repository_limit(self):
        self._assert_invalid("maxHighRiskTasks", 2)

    def test_critical_work_cannot_be_made_non_standalone(self):
        self._assert_invalid("criticalStandalone", False)

    def test_independent_high_risk_review_cannot_be_disabled(self):
        self._assert_invalid("independentReviewForHighRisk", False)


if __name__ == "__main__":
    unittest.main()

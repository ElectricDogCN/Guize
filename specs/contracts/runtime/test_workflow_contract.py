import json
from pathlib import Path
import unittest

import yaml

from check_workflow_contract import CONTRACT, UniqueCatalogLoader, unique_mapping, validate_activity_options, validate_catalog


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = yaml.load((CONTRACT / "catalog.yaml").read_text(encoding="utf-8"), Loader=UniqueCatalogLoader)
        fixture = Path(__file__).parent / "fixtures" / "workflow-policy-v1.json"
        self.policy = json.loads(fixture.read_bytes())

    def test_registered_catalog_and_versioned_fixture(self):
        validate_catalog(self.catalog)
        validate_activity_options(self.policy)

    def test_registered_workflow_cannot_be_replaced(self):
        self.catalog["workflowTypes"]["工作流V1-0004"]["type"] = "NewWorkflow"
        with self.assertRaisesRegex(ValueError, "registered Workflow type"):
            validate_catalog(self.catalog)

    def test_long_work_requires_heartbeat_before_attempt_deadline(self):
        options = self.policy["activityClasses"]["longRunning"]
        del options["heartbeatSeconds"]
        with self.assertRaisesRegex(ValueError, "heartbeatSeconds"):
            validate_activity_options(self.policy)
        options["heartbeatSeconds"] = options["startToCloseSeconds"]
        with self.assertRaisesRegex(ValueError, "heartbeat must precede"):
            validate_activity_options(self.policy)

    def test_attempts_and_aggregate_deadline_are_bounded(self):
        options = self.policy["activityClasses"]["command"]
        options["retry"]["maximumAttempts"] = 0
        with self.assertRaisesRegex(ValueError, "maximumAttempts"):
            validate_activity_options(self.policy)
        options["retry"]["maximumAttempts"] = 3
        options["scheduleToCloseSeconds"] = options["startToCloseSeconds"] - 1
        with self.assertRaisesRegex(ValueError, "attempt exceeds"):
            validate_activity_options(self.policy)
        options["scheduleToCloseSeconds"] = options["startToCloseSeconds"]
        options["retry"]["backoff"] = 10**400
        with self.assertRaisesRegex(ValueError, "backoff are inconsistent"):
            validate_activity_options(self.policy)

    def test_terminal_rejection_is_not_retried(self):
        self.policy["activityClasses"]["command"]["retry"]["nonRetryableTypes"].remove("AUTHORIZATION_INVALID")
        with self.assertRaisesRegex(ValueError, "terminal errors"):
            validate_activity_options(self.policy)

    def test_duplicate_configuration_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate configuration field"):
            json.loads('{"maximumAttempts":1,"maximumAttempts":0}', object_pairs_hook=unique_mapping)
        with self.assertRaisesRegex(ValueError, "Duplicate configuration field"):
            yaml.load("workflowTypes: {}\nworkflowTypes: {}\n", Loader=UniqueCatalogLoader)


if __name__ == "__main__":
    unittest.main()

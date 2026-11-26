import json
from pathlib import Path
import unittest

import yaml

from check_workflow_contract import CONTRACT, UniqueCatalogLoader, replay_progress, validate_activity_options, validate_catalog
from validation import read_json, unique_mapping

FIXTURES = Path(__file__).parent / "fixtures"


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = yaml.load((CONTRACT / "catalog.yaml").read_text(encoding="utf-8"), Loader=UniqueCatalogLoader)
        self.policy = read_json(FIXTURES / "workflow-policy-v1.json")
        self.replay = read_json(FIXTURES / "workflow-replay-v1.json")

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

    def test_replay_reuses_outcomes_and_schedules_only_unrecorded_ready_steps(self):
        expected = {
            "status": "EXECUTING",
            "recordedOutcomes": {"step_probe": "out_probe"},
            "readySteps": [{"stepId": "step_b", "idempotencyKey": "task_replay:plan_replay:1:step_b:transcode"}],
        }
        self.assertEqual(replay_progress(self.catalog, self.replay), expected)
        self.assertEqual(replay_progress(self.catalog, self.replay), expected)

    def test_cancellation_stops_new_work_and_keeps_recorded_outcomes(self):
        self.replay["cancellationRequested"] = True
        self.assertEqual(replay_progress(self.catalog, self.replay), {
            "status": "CANCELLATION_PENDING", "recordedOutcomes": {"step_probe": "out_probe"}, "readySteps": [],
        })

    def test_completed_plan_requires_reconciliation_with_task(self):
        entries = self.replay["recorded"]
        entries[1].update(status="COMPLETED", outcomeRef="out_a")
        entries.extend([
            {"stepId": "step_b", "idempotencyKey": "task_replay:plan_replay:1:step_b:transcode",
             "policyVersionId": "polv_01", "status": "COMPLETED", "outcomeRef": "out_b"},
            {"stepId": "step_publish", "idempotencyKey": "task_replay:plan_replay:1:step_publish:publish",
             "policyVersionId": "polv_01", "status": "COMPLETED", "outcomeRef": "out_publish"},
        ])
        self.assertEqual(replay_progress(self.catalog, self.replay), {
            "status": "RECONCILE_WITH_TASK", "readySteps": [],
            "recordedOutcomes": {"step_probe": "out_probe", "step_a": "out_a", "step_b": "out_b",
                                 "step_publish": "out_publish"},
        })

    def test_replay_rejects_changed_policy_key_and_unready_or_duplicate_records(self):
        original = self.replay["recorded"]
        for invalid in (
            [dict(original[0], policyVersionId="polv_other"), original[1]],
            [dict(original[0], idempotencyKey="task_replay:plan_replay:2:step_probe:probe"), original[1]],
            list(reversed(original)),
            [original[0], original[0], original[1]],
        ):
            self.replay["recorded"] = invalid
            with self.subTest(recorded=invalid), self.assertRaisesRegex(ValueError, "Recorded history"):
                replay_progress(self.catalog, self.replay)

    def test_replay_rejects_unordered_plan(self):
        self.replay["steps"].reverse()
        with self.assertRaisesRegex(ValueError, "unordered step"):
            replay_progress(self.catalog, self.replay)


if __name__ == "__main__":
    unittest.main()

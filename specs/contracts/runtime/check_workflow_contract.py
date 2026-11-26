"""Validate the GZ-008 workflow catalog and a versioned activity policy offline."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from sys import float_info

from jsonschema import Draft202012Validator
import yaml

from validation import read_json, unique_mapping, validate_shape

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "contracts" / "workflows" / "v1"
CLASSES = {"read", "command", "longRunning"}
TERMINAL_ERRORS = {"BUSINESS_REJECTED", "INPUT_IDENTITY_MISMATCH", "AUTHORIZATION_INVALID", "CANCELLED"}


class UniqueCatalogLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        return unique_mapping(self.construct_pairs(node, deep=deep))


def validate_catalog(catalog):
    if not isinstance(catalog, dict) or set(catalog) != {"schemaVersion", "contractId", "stateAuthority", "workflowTypes"} or (
        catalog["schemaVersion"], catalog["contractId"], catalog["stateAuthority"]
    ) != (1, "WORKFLOW-CONTRACT-V1", "TASK") or type(catalog["schemaVersion"]) is not int:
        raise ValueError("Unexpected workflow catalog identity or authority")
    baseline = (ROOT / "docs" / "00-guize-engineering-design-baseline.md").read_text(encoding="utf-8")
    expected = dict(re.findall(r"(?m)^\| `(工作流V1-\d{4})` \| `([A-Za-z]+Workflow)` \|", baseline))
    entries = catalog["workflowTypes"]
    if not expected or not isinstance(entries, dict) or entries.keys() != expected.keys():
        raise ValueError("The workflow catalog must retain every registered V1 type and identity")
    for workflow_id, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("type") != expected[workflow_id]:
            raise ValueError(f"{workflow_id} must retain its registered Workflow type")
        activities = entry.get("activities")
        if set(entry) != {"type", "activities"} or not isinstance(activities, dict) or not activities:
            raise ValueError(f"{workflow_id} requires a named activity mapping")
        if any(not isinstance(activity, str) or not re.fullmatch(r"[a-z][A-Za-z0-9]*", activity)
               or not isinstance(kind, str) or kind not in CLASSES
               for activity, kind in activities.items()):
            raise ValueError(f"{workflow_id} declares an invalid activity class")


def validate_activity_options(policy):
    schema = yaml.safe_load((CONTRACT / "activity-options.schema.yaml").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    if error := next(validator.iter_errors(policy), None):
        location = ".".join(map(str, error.absolute_path))
        raise ValueError(f"Activity policy {location}: {error.message}")
    for name, options in policy["activityClasses"].items():
        if options["startToCloseSeconds"] > options["scheduleToCloseSeconds"]:
            raise ValueError(f"{name} single attempt exceeds its schedule deadline")
        if options.get("heartbeatSeconds", 0) >= options["startToCloseSeconds"]:
            raise ValueError(f"{name} heartbeat must precede the single attempt deadline")
        retry = options["retry"]
        if not 1 <= retry["backoff"] <= float_info.max or retry["initialSeconds"] > retry["maximumSeconds"]:
            raise ValueError(f"{name} retry intervals or backoff are inconsistent")
        if not TERMINAL_ERRORS.issubset(retry["nonRetryableTypes"]):
            raise ValueError(f"{name} must classify terminal errors as non-retryable")


def replay_progress(catalog, snapshot):
    """Check TASK's normalized replay inputs without executing any Activity."""
    validate_catalog(catalog)
    validate_shape(CONTRACT / "replay.schema.yaml", snapshot)
    workflows = {entry["type"]: entry["activities"] for entry in catalog["workflowTypes"].values()}
    activities = workflows.get(snapshot["workflowType"])
    if activities is None:
        raise ValueError("Unknown workflow type")
    steps = {}
    keys = {}
    for step in snapshot["steps"]:
        identifier = step["stepId"]
        if identifier in steps or step["activity"] not in activities or not set(step["dependsOn"]).issubset(steps):
            raise ValueError("The accepted plan has a duplicate, unknown, or unordered step")
        steps[identifier] = step
        keys[identifier] = ":".join((snapshot["taskId"], snapshot["planId"], str(snapshot["planVersion"]),
                                    identifier, step["activity"]))

    recorded = set()
    completed = {}
    for entry in snapshot["recorded"]:
        identifier = entry["stepId"]
        if (identifier not in steps or identifier in recorded or keys[identifier] != entry["idempotencyKey"]
                or snapshot["policyVersionId"] != entry["policyVersionId"]
                or not set(steps[identifier]["dependsOn"]).issubset(completed)):
            raise ValueError("Recorded history does not match the accepted plan or policy")
        recorded.add(identifier)
        if entry["status"] == "COMPLETED":
            completed[identifier] = entry["outcomeRef"]

    ready = []
    if snapshot["cancellationRequested"]:
        status = "CANCELLATION_PENDING"
    elif len(completed) == len(steps):
        status = "RECONCILE_WITH_TASK"
    else:
        status = "EXECUTING"
        ready = [{"stepId": key, "idempotencyKey": keys[key]} for key, step in steps.items()
                 if key not in recorded and set(step["dependsOn"]).issubset(completed)]
    return {"status": status, "recordedOutcomes": completed, "readySteps": ready}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path, help="Versioned JSON deployment policy to validate")
    parser.add_argument("--replay", type=Path, help="Normalized accepted plan and recorded progress to validate")
    args = parser.parse_args()
    try:
        catalog = yaml.load((CONTRACT / "catalog.yaml").read_text(encoding="utf-8"), Loader=UniqueCatalogLoader)
        raw_policy = args.policy.read_bytes()
        policy = json.loads(raw_policy, object_pairs_hook=unique_mapping)
        validate_catalog(catalog)
        validate_activity_options(policy)
        result = {"workflowTypes": len(catalog["workflowTypes"]), "policyVersion": policy["policyVersion"],
                  "policySha256": "sha256:" + sha256(raw_policy).hexdigest()}
        if args.replay:
            result["replay"] = replay_progress(catalog, read_json(args.replay))
    except (OSError, ValueError, yaml.YAMLError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

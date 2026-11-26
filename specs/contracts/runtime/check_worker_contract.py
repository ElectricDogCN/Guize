"""Evaluate a Worker protocol message against a trusted TASK conformance snapshot."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from validation import read_json, validate_shape

PROTOCOL = Path(__file__).resolve().with_name("protocol.schema.yaml")
if not PROTOCOL.is_file():
    PROTOCOL = Path(__file__).resolve().parents[3] / "contracts" / "workers" / "v1" / "protocol.schema.yaml"
VERSION = "worker-v1"
RELEASE_FIELDS = ("protocolVersion", "capabilityId", "capabilityVersion", "executionGroupId", "packageSha256")


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_offer(offer):
    validate_shape(PROTOCOL, offer)
    if offer["kind"] != "offer":
        raise ValueError("Expected a TASK offer")
    lease, grant, binding = offer["lease"], offer["grant"], offer["binding"]
    if binding["protocolVersion"] != VERSION:
        raise ValueError("Unsupported offer protocol version")
    if lease["id"] == grant["id"] or lease["id"] != grant["leaseId"] or not (
        instant(lease["issuedAt"]) < instant(lease["expiresAt"]) <= instant(grant["expiresAt"])
    ):
        raise ValueError("The grant does not cover the exact execution lease")
    span = grant.get("inputFrameSpan")
    if span and span["firstFrame"] + span["frameCount"] > 9007199254740991:
        raise ValueError("The frame span exceeds the protocol integer boundary")


def resource_denial(offer, observation, now):
    validate_shape(PROTOCOL, observation)
    if observation["kind"] != "resourceObservation" or any(
        observation[key] != offer["binding"][key] for key in ("nodeId", "executionGroupId")
    ):
        return "RESOURCE_SCOPE_MISMATCH"
    if observation["status"] != "AVAILABLE":
        return "RESOURCE_UNAVAILABLE"
    if not (instant(observation["sampledAt"]) <= instant(observation["receivedAt"]) <= now < instant(observation["expiresAt"])):
        return "RESOURCE_OBSERVATION_STALE"
    capacity = observation["available"]
    if any(offer["budget"][key] > value for key, value in capacity.items()):
        return "RESOURCE_LIMIT_EXCEEDED"
    return None


def decide(offer, message, trusted):
    """Return the guard result the TASK adapter can apply using a conditional write."""
    validate_offer(offer)
    validate_shape(PROTOCOL, message)
    if message["kind"] != "message":
        raise ValueError("Expected a Worker message")
    now = instant(trusted["now"])
    binding = message["binding"]
    session = trusted["session"]
    if (not session["verified"] or session["id"] != message["nodeSessionId"]
            or session["nodeId"] != binding["nodeId"] or session["id"] == offer["lease"]["id"]
            or not now < instant(session["expiresAt"])):
        return "NODE_SESSION_REQUIRED"
    if binding["protocolVersion"] != VERSION:
        return "PROTOCOL_UNSUPPORTED"
    if any(binding[key] != trusted["release"][key] for key in RELEASE_FIELDS):
        return "CAPABILITY_MISMATCH"
    if binding["fencing"] != offer["binding"]["fencing"]:
        return "FENCING_MISMATCH"
    if binding != offer["binding"]:
        return "BINDING_MISMATCH"
    if message["executionLeaseId"] != offer["lease"]["id"]:
        return "EXECUTION_LEASE_MISMATCH"

    operation, payload, state = message["operation"], message["payload"], trusted["state"]
    if state == "SUCCEEDED" and operation == "SUBMIT":
        return "ALREADY_ACCEPTED" if trusted.get("acceptedResult") == payload else "RESULT_CONFLICT"
    if state == "CANCELLED" and operation == "CANCEL_ACK" and payload["cancellationId"] == trusted.get("cancellationId"):
        return "ALREADY_CANCELLED"
    if not instant(offer["lease"]["issuedAt"]) <= now < instant(offer["lease"]["expiresAt"]):
        return "EXECUTION_LEASE_EXPIRED"
    if instant(offer["lease"]["expiresAt"]) > instant(trusted["executionDeadline"]):
        return "LEASE_OUTSIDE_DEADLINE"
    if operation == "CANCEL_ACK":
        return "CANCEL_ACK_ACCEPTABLE" if state == "CANCELLING" and payload["cancellationId"] == trusted.get("cancellationId") else "CANCELLATION_MISMATCH"
    if state in {"CANCELLING", "CANCELLED"}:
        return "CANCELLED"
    if not trusted["grantActive"] or not now < instant(offer["grant"]["expiresAt"]):
        return "GRANT_INACTIVE"
    admitted = trusted["admittedPolicy"]
    if admitted["binding"] != offer["policyBinding"] or admitted["priority"] != offer["priority"]:
        return "POLICY_BINDING_MISMATCH"
    reservation = trusted["reservation"]
    if (not reservation["active"] or reservation["id"] != offer["reservationId"]
            or reservation["nodeId"] != binding["nodeId"] or reservation["budget"] != offer["budget"]
            or not now < instant(reservation["expiresAt"])):
        return "RESERVATION_INACTIVE"

    if operation == "CLAIM":
        if state != "OFFERED":
            return "ATTEMPT_NOT_OFFERED"
        return resource_denial(offer, trusted["observation"], now) or "CLAIM_ACCEPTABLE"
    if state != "RUNNING":
        return "ATTEMPT_NOT_RUNNING"
    if operation == "RENEW":
        denial = resource_denial(offer, trusted["observation"], now)
        if denial:
            return denial
        proposed = instant(trusted["renewUntil"])
        bound = min(instant(offer["grant"]["expiresAt"]), instant(trusted["executionDeadline"]),
                    instant(reservation["expiresAt"]))
        return "RENEW_ACCEPTABLE" if instant(offer["lease"]["expiresAt"]) < proposed <= bound else "RENEWAL_OUT_OF_SCOPE"
    if operation == "PROGRESS":
        if payload["processedUnits"] > offer["maximumProcessedUnits"]:
            return "PROGRESS_OUT_OF_SCOPE"
        if payload["sequence"] <= trusted["lastProgressSequence"] or payload["processedUnits"] < trusted["lastProcessedUnits"]:
            return "PROGRESS_OUT_OF_ORDER"
        if "checkpointRef" in payload and (
            offer["checkpointMode"] != "INDEPENDENT_UNIT" or payload["checkpointRef"] != trusted.get("verifiedCheckpointRef")
        ):
            return "CHECKPOINT_UNSUPPORTED"
        return "PROGRESS_ACCEPTABLE"

    if any(value > offer["budget"][key] for key, value in payload["usage"].items()):
        return "USAGE_EXCEEDED"
    if payload["outcome"] == "FAILED":
        return "RETRYABLE_FAILURE" if payload["error"] in {"TRANSIENT_FAILURE", "PROCESS_ABORTED"} else "FAILURE_RECORDED"
    keys = ("artifactManifestId", "artifactManifestSha256", "outputScopeId", "byteCount")
    if (payload["outputScopeId"] != offer["grant"]["outputScopeId"]
            or payload["byteCount"] > offer["grant"]["maximumOutputBytes"]
            or {key: payload[key] for key in keys} != trusted.get("verifiedArtifact")):
        return "RESULT_SCOPE_MISMATCH"
    return "RESULT_ACCEPTABLE"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    case = commands.add_parser("check", help="Check one offer, message and TASK snapshot")
    case.add_argument("offer", type=Path)
    case.add_argument("message", type=Path)
    case.add_argument("trusted", type=Path)
    conformance = commands.add_parser("conformance", help="Run the shared protocol vectors")
    conformance.add_argument("fixture", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = {"protocolVersion": VERSION, "decision": decide(
                read_json(args.offer), read_json(args.message), read_json(args.trusted))}
        else:
            outcomes = run_conformance(read_json(args.fixture))
            result = {"protocolVersion": VERSION, "cases": outcomes,
                      "verifiedCases": len(outcomes), "fixtureSha256": sha256(args.fixture.read_bytes()).hexdigest()}
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, separators=(",", ":")))


def run_conformance(fixture):
    if fixture["schemaVersion"] != 1 or not fixture["cases"]:
        raise ValueError("No Worker protocol v1 vectors")
    outcomes = {}
    for case in fixture["cases"]:
        name = case["name"]
        if name in outcomes:
            raise ValueError(f"Duplicate Worker conformance case: {name}")
        override = case.get("message", {})
        message = fixture["message"] | override
        message["binding"] = fixture["message"]["binding"] | override.get("binding", {})
        override = case.get("trusted", {})
        trusted = fixture["trusted"] | override
        for key in ("session", "observation", "reservation", "admittedPolicy", "verifiedArtifact"):
            if key in override:
                trusted[key] = fixture["trusted"][key] | override[key]
        actual = decide(fixture["offer"], message, trusted)
        if actual != case["expected"]:
            raise ValueError(f"{name}: expected {case['expected']}, received {actual}")
        outcomes[name] = actual
    return outcomes


if __name__ == "__main__":
    main()

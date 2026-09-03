#!/usr/bin/env python3
"""Fail-closed validator for Guize POC-PROTOCOL-V1."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

EXPECTED_POC_IDS = {f"POC-{index:02d}" for index in range(1, 11)}
EXPECTED_TASK_IDS = {f"POC-{index:03d}" for index in range(1, 11)}
HIGH_RISKS = {"high", "critical"}
TERMINAL_RESULTS = {"pass", "fail", "inconclusive"}
PLACEHOLDER_IDENTITIES = {"", "TBD", "TBD_BEFORE_EXECUTION", "UNKNOWN", "PENDING"}
SAFE_CREDENTIAL_METADATA_KEYS = {
    "credentials_stored",
    "credentials_stored_in_repository",
}
SENSITIVE_KEY_TERMS = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_key",
    "accesskey",
    "private_key",
    "privatekey",
    "credentials",
}
SECRET_PATTERNS = [
    re.compile(r"glpat-[A-Za-z0-9_-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*\S+"),
]
REQUIRED_MEASUREMENTS = {
    "POC-01": {"gpu_passthrough_visible", "driver_runtime_ready", "vm_reboot_recovery", "device_reset_recovery"},
    "POC-02": {"av1_quality", "encode_throughput", "first_segment_latency", "sustained_encode_stability", "sustained_encode_duration"},
    "POC-03": {"range_correctness", "etag_semantics", "if_range_semantics", "cache_key_isolation", "large_file_streaming"},
    "POC-04": {"iscsi_transport_ready", "sequential_throughput", "io_latency", "watermark_behavior", "failure_recovery"},
    "POC-05": {"file_count", "directory_count", "directory_depth_max", "average_file_size", "source_api_quota", "enumeration_rate", "incremental_scan_cost", "memory_peak"},
    "POC-09": {"quality_score", "throughput", "cost_estimate", "license_privacy_pass", "caller_permission_gate", "asset_acl_gate", "hard_budget_gate", "request_quota_gate", "concurrency_quota_gate"},
}
REQUIRED_ENV_CAPTURE = {
    "POC-09": {"model_identity", "model_version", "prompt_template_version", "inference_parameters", "input_sample_version"},
}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_schema(instance: Any, schema: Any, label: str, errors: list[str]) -> None:
    try:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        failures = sorted(cls(schema).iter_errors(instance), key=lambda e: list(e.absolute_path))
        for failure in failures:
            location = "/".join(str(p) for p in failure.absolute_path) or "<root>"
            errors.append(f"{label} schema violation at {location}: {failure.message}")
    except Exception as exc:
        errors.append(f"{label} schema validation failed: {exc}")


def normalize_key(value: Any) -> str:
    text = str(value).replace("-", "_")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower()


def key_is_secret_like(value: Any) -> bool:
    normalized = normalize_key(value)
    if normalized in SAFE_CREDENTIAL_METADATA_KEYS:
        return False
    if normalized in SENSITIVE_KEY_TERMS:
        return True
    if normalized.endswith("_credentials"):
        return True
    for term in ("password", "passwd", "token", "secret", "api_key", "access_key", "private_key"):
        if normalized.endswith(f"_{term}"):
            return True
    return False


def walk_for_secrets(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key_is_secret_like(key):
                errors.append(f"secret-like key forbidden at {path}/{key}")
            walk_for_secrets(item, f"{path}/{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk_for_secrets(item, f"{path}/{index}", errors)
    elif isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                errors.append(f"secret-like value forbidden at {path}")
                break


def canonical_maps(program_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    pocs = {item["pocId"]: item for item in program_plan.get("pocs", [])}
    tasks = {
        item["taskId"]: item
        for item in program_plan.get("tasks", [])
        if str(item.get("taskId", "")).startswith("POC-")
    }
    return pocs, tasks


def evidence_ref_is_valid(ref: Any, evidence_path: str) -> bool:
    if not isinstance(ref, str):
        return False
    value = ref.strip()
    if not value or value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    prefix = f"{evidence_path}/"
    return value.startswith(prefix) and len(value) > len(prefix)


def identity_is_final(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(text) and text.upper() not in PLACEHOLDER_IDENTITIES


def lifecycle_is_consistent(plan_status: str, result_status: str) -> bool:
    if result_status == "not_started":
        return plan_status in {"planned", "ready"}
    if result_status == "running":
        return plan_status == "running"
    if result_status in TERMINAL_RESULTS:
        return plan_status == "completed"
    if result_status == "blocked":
        return plan_status == "blocked"
    if result_status == "cancelled":
        return plan_status == "cancelled"
    return False


def validate_repository(repo_root: Path) -> list[str]:
    errors: list[str] = []
    base = repo_root / "specs" / "poc"

    program = load_yaml(base / "program.yaml")
    program_schema = load_yaml(base / "program.schema.yaml")
    plan_schema = load_yaml(base / "plan.schema.yaml")
    protocol_schema = load_yaml(base / "protocol.schema.yaml")
    result_schema = load_yaml(base / "result-index.schema.yaml")
    resources = load_yaml(base / "resources.yaml")
    samples = load_yaml(base / "samples.yaml")
    results = load_yaml(base / "results-index.yaml")
    policy = load_yaml(base / "policy.yaml")
    program_plan = load_yaml(repo_root / "specs" / "coordination" / "program-plan.yaml")

    validate_schema(program, program_schema, "program.yaml", errors)
    validate_schema(results, result_schema, "results-index.yaml", errors)

    if program.get("executionEnabled") is not False:
        errors.append("GZ-010 program executionEnabled must be false")
    if policy.get("executionAllowedInGz010") is not False:
        errors.append("policy executionAllowedInGz010 must be false")
    for required_true in (
        "sampleExecutionRequiresApproval",
        "highCriticalIsolation",
        "criticalStandalone",
    ):
        if policy.get(required_true) is not True:
            errors.append(f"policy {required_true} must be true")
    if policy.get("maxConcurrentHighCritical") != 1:
        errors.append("policy maxConcurrentHighCritical must be 1")

    canonical_pocs, canonical_tasks = canonical_maps(program_plan)
    if set(canonical_pocs) != EXPECTED_POC_IDS:
        errors.append(f"canonical Program Plan POC IDs mismatch: {sorted(canonical_pocs)}")
    if set(canonical_tasks) != EXPECTED_TASK_IDS:
        errors.append(f"canonical Program Plan POC task IDs mismatch: {sorted(canonical_tasks)}")

    plan_files = program.get("planFiles") or []
    expected_plan_files = {f"plans/POC-{index:03d}.yaml" for index in range(1, 11)}
    if set(plan_files) != expected_plan_files:
        errors.append("program.yaml planFiles must contain exactly POC-001..POC-010")

    resource_items = resources.get("resources") or []
    resource_map = {item.get("id"): item for item in resource_items}
    if len(resource_map) != len(resource_items):
        errors.append("resource IDs must be unique")
    sample_items = samples.get("samples") or []
    sample_map = {item.get("id"): item for item in sample_items}
    if len(sample_map) != len(sample_items):
        errors.append("sample IDs must be unique")

    plan_by_poc: dict[str, dict[str, Any]] = {}
    plan_by_task: dict[str, dict[str, Any]] = {}
    evidence_paths: set[str] = set()
    high_by_wave: dict[str, list[str]] = {}

    for relative in plan_files:
        path = base / relative
        if not path.is_file():
            errors.append(f"missing POC plan: {relative}")
            continue
        plan = load_yaml(path)
        label = relative
        validate_schema(plan, plan_schema, label, errors)
        validate_schema(plan.get("protocol"), protocol_schema, f"{label}/protocol", errors)
        walk_for_secrets(plan, label, errors)

        poc_id = plan.get("pocId")
        task_id = plan.get("taskId")
        if poc_id in plan_by_poc:
            errors.append(f"duplicate POC ID in plans: {poc_id}")
        plan_by_poc[poc_id] = plan
        if task_id in plan_by_task:
            errors.append(f"duplicate POC task ID in plans: {task_id}")
        plan_by_task[task_id] = plan

        cpoc = canonical_pocs.get(poc_id)
        ctask = canonical_tasks.get(task_id)
        if not cpoc:
            errors.append(f"{label}: unknown canonical pocId {poc_id}")
        if not ctask:
            errors.append(f"{label}: unknown canonical taskId {task_id}")
        if cpoc and cpoc.get("taskId") != task_id:
            errors.append(f"{label}: POC↔Task mismatch; Program Plan maps {poc_id} to {cpoc.get('taskId')}")
        if cpoc and ctask:
            comparisons = {
                "riskLevel": (plan.get("riskLevel"), ctask.get("riskLevel")),
                "wave": (plan.get("wave"), ctask.get("wave")),
                "requirementIds": (set(plan.get("requirementIds") or []), set(ctask.get("requirementIds") or [])),
                "moduleIds": (set(plan.get("moduleIds") or []), set(ctask.get("moduleIds") or [])),
                "evidencePath": (plan.get("evidencePath"), cpoc.get("evidencePath")),
                "dependsOn": (set(plan.get("dependsOn") or []), set(ctask.get("dependsOn") or [])),
            }
            for name, (actual, expected) in comparisons.items():
                if actual != expected:
                    errors.append(f"{label}: {name}={actual!r} does not match Program Plan {expected!r}")
            if set(cpoc.get("requirementIds") or []) != set(ctask.get("requirementIds") or []):
                errors.append(f"Program Plan itself has POC/task requirement drift for {poc_id}/{task_id}")
            if set(cpoc.get("moduleIds") or []) != set(ctask.get("moduleIds") or []):
                errors.append(f"Program Plan itself has POC/task module drift for {poc_id}/{task_id}")
            if cpoc.get("riskLevel") != ctask.get("riskLevel"):
                errors.append(f"Program Plan itself has POC/task risk drift for {poc_id}/{task_id}")

        evidence = plan.get("evidencePath")
        if evidence in evidence_paths:
            errors.append(f"duplicate POC evidence path: {evidence}")
        evidence_paths.add(evidence)

        measurement_items = (plan.get("protocol") or {}).get("measurements") or []
        measurement_ids = [item.get("id") for item in measurement_items]
        if len(set(measurement_ids)) != len(measurement_ids):
            errors.append(f"{label}: measurement IDs must be unique")
        required_measurements = REQUIRED_MEASUREMENTS.get(poc_id, set())
        missing_measurements = required_measurements - set(measurement_ids)
        if missing_measurements:
            errors.append(f"{label}: missing frozen required measurements {sorted(missing_measurements)}")
        required_capture = REQUIRED_ENV_CAPTURE.get(poc_id, set())
        capture_fields = set((plan.get("environment") or {}).get("captureBeforeExecution") or [])
        if not required_capture.issubset(capture_fields):
            errors.append(f"{label}: missing required environment provenance fields {sorted(required_capture - capture_fields)}")

        for resource_id in plan.get("resourceIds") or []:
            if resource_id not in resource_map:
                errors.append(f"{label}: unknown resource {resource_id}")
        for sample_id in plan.get("sampleIds") or []:
            sample = sample_map.get(sample_id)
            if not sample:
                errors.append(f"{label}: unknown sample {sample_id}")
            elif poc_id not in (sample.get("allowedPocs") or []):
                errors.append(f"{label}: sample {sample_id} does not allow {poc_id}")

        status = plan.get("status")
        result_status = plan.get("resultStatus")
        if not lifecycle_is_consistent(status, result_status):
            errors.append(f"{label}: inconsistent lifecycle status={status!r}, resultStatus={result_status!r}")

        protocol = plan.get("protocol") or {}
        if result_status == "not_started":
            if protocol.get("commands"):
                errors.append(f"{label}: planned/not_started plan must not contain execution commands")
            if protocol.get("rawOutputRefs"):
                errors.append(f"{label}: planned/not_started plan must not contain raw output refs")
            for measurement in measurement_items:
                if measurement.get("actual") is not None:
                    errors.append(f"{label}: planned/not_started measurement actual must be null")
            decision = plan.get("decision") or {}
            if decision.get("status") != "not_evaluated" or decision.get("rationale") is not None or decision.get("resultRef") is not None:
                errors.append(f"{label}: planned/not_started decision fields must be empty/not_evaluated")
            review = plan.get("review") or {}
            if any(review.get(key) is not None for key in ("reviewer", "approvedAt", "approval")):
                errors.append(f"{label}: planned/not_started review fields must be null")

        execution_started = bool(protocol.get("commands")) or result_status in {"running", *TERMINAL_RESULTS}
        if execution_started:
            for sample_id in plan.get("sampleIds") or []:
                sample = sample_map.get(sample_id)
                if not sample:
                    continue
                if sample.get("approvalState") != "approved":
                    errors.append(f"{label}: execution cannot use unapproved sample {sample_id}")
                if not identity_is_final(sample.get("immutableId")) or not identity_is_final(sample.get("checksum")):
                    errors.append(f"{label}: execution requires immutable sample identity/checksum for {sample_id}")
            captured_values = (plan.get("environment") or {}).get("capturedValues") or {}
            if not captured_values:
                errors.append(f"{label}: execution requires captured environment values")
            missing_capture_values = capture_fields - set(captured_values)
            if missing_capture_values:
                errors.append(f"{label}: execution missing captured environment values {sorted(missing_capture_values)}")

        if plan.get("riskLevel") in HIGH_RISKS:
            high_by_wave.setdefault(plan.get("wave"), []).append(task_id)

    if set(plan_by_poc) != EXPECTED_POC_IDS:
        errors.append(f"plan POC IDs must be exactly POC-01..10; got {sorted(plan_by_poc)}")
    if set(plan_by_task) != EXPECTED_TASK_IDS:
        errors.append(f"plan task IDs must be exactly POC-001..010; got {sorted(plan_by_task)}")
    for wave, task_ids in high_by_wave.items():
        if len(task_ids) > 1:
            errors.append(f"high/critical POCs share wave {wave}: {task_ids}")
    critical = [plan for plan in plan_by_task.values() if plan.get("riskLevel") == "critical"]
    if len(critical) != 1 or critical[0].get("taskId") != "POC-010":
        errors.append("POC-010 must be the only critical POC")
    if critical and critical[0].get("wave") != "W11":
        errors.append("POC-010 critical POC must remain in W11")
    if any(p.get("wave") == "W11" and p.get("taskId") != "POC-010" for p in plan_by_task.values()):
        errors.append("POC-010 must be standalone among POC plans in W11")

    result_entries = results.get("entries") or []
    result_map = {item.get("taskId"): item for item in result_entries}
    if len(result_map) != len(result_entries):
        errors.append("results-index task IDs must be unique")
    if set(result_map) != EXPECTED_TASK_IDS:
        errors.append("results-index must contain exactly POC-001..POC-010")
    result_evidence: set[str] = set()
    for task_id, entry in result_map.items():
        plan = plan_by_task.get(task_id)
        if not plan:
            continue
        if entry.get("pocId") != plan.get("pocId"):
            errors.append(f"results-index {task_id}: pocId mismatch")
        if entry.get("evidencePath") != plan.get("evidencePath"):
            errors.append(f"results-index {task_id}: evidencePath mismatch")
        if entry.get("status") != plan.get("resultStatus"):
            errors.append(
                f"results-index {task_id}: status {entry.get('status')!r} "
                f"does not match plan resultStatus {plan.get('resultStatus')!r}"
            )
        if entry.get("evidencePath") in result_evidence:
            errors.append(f"results-index duplicate evidence path: {entry.get('evidencePath')}")
        result_evidence.add(entry.get("evidencePath"))

        result_status = entry.get("status")
        if result_status == "not_started":
            for key in ("resultRef", "decision", "reviewer", "approvedAt"):
                if entry.get(key) is not None:
                    errors.append(f"results-index {task_id}: not_started {key} must be null")
        elif result_status == "running":
            for key in ("resultRef", "decision", "reviewer", "approvedAt"):
                if entry.get(key) is not None:
                    errors.append(f"results-index {task_id}: running {key} must remain null")
        elif result_status in {"blocked", "cancelled"}:
            for key in ("resultRef", "reviewer", "approvedAt"):
                if entry.get(key) is not None:
                    errors.append(f"results-index {task_id}: {result_status} {key} must remain null until terminal review")
        elif result_status in TERMINAL_RESULTS:
            protocol = plan.get("protocol") or {}
            review = plan.get("review") or {}
            decision = plan.get("decision") or {}
            evidence_path = plan.get("evidencePath")
            missing_actual = [item.get("id") for item in protocol.get("measurements") or [] if item.get("actual") is None]
            if not protocol.get("commands"):
                errors.append(f"{task_id}: completed result requires recorded execution commands")
            raw_refs = protocol.get("rawOutputRefs") or []
            if not raw_refs:
                errors.append(f"{task_id}: completed result requires raw evidence references")
            for ref in raw_refs:
                if not evidence_ref_is_valid(ref, evidence_path):
                    errors.append(f"{task_id}: raw evidence reference must be a nonempty path under {evidence_path}: {ref!r}")
            if missing_actual:
                errors.append(f"{task_id}: completed result has unmeasured metrics {missing_actual}")
            if result_status == "pass":
                failed_boolean_gates = [
                    item.get("id")
                    for item in protocol.get("measurements") or []
                    if str(item.get("unit")).lower() == "boolean" and item.get("actual") is not True
                ]
                if failed_boolean_gates:
                    errors.append(f"{task_id}: PASS has false/non-true boolean gates {failed_boolean_gates}")
            if not (plan.get("environment") or {}).get("capturedValues"):
                errors.append(f"{task_id}: completed result requires captured environment values")
            if decision.get("status") != result_status:
                errors.append(f"{task_id}: decision status must match result status")
            if not decision.get("rationale") or not evidence_ref_is_valid(decision.get("resultRef"), evidence_path):
                errors.append(f"{task_id}: completed result requires rationale and resultRef under {evidence_path}")
            if not review.get("reviewer") or not review.get("approvedAt") or review.get("approval") != "approved":
                errors.append(f"{task_id}: completed result requires independent approved review")
            if not evidence_ref_is_valid(entry.get("resultRef"), evidence_path):
                errors.append(f"results-index {task_id}: completed resultRef must remain under {evidence_path}")
            if entry.get("resultRef") != decision.get("resultRef"):
                errors.append(f"results-index {task_id}: resultRef does not match plan decision")
            if entry.get("decision") != decision.get("status"):
                errors.append(f"results-index {task_id}: decision does not match plan decision status")
            if entry.get("reviewer") != review.get("reviewer"):
                errors.append(f"results-index {task_id}: reviewer does not match plan review")
            if entry.get("approvedAt") != review.get("approvedAt"):
                errors.append(f"results-index {task_id}: approvedAt does not match plan review")

    for sample_id, sample in sample_map.items():
        required = {"id", "description", "source", "classification", "approvalState", "immutableId", "checksum", "allowedPocs"}
        missing = required - set(sample)
        if missing:
            errors.append(f"sample {sample_id}: missing fields {sorted(missing)}")
        if not set(sample.get("allowedPocs") or []).issubset(EXPECTED_POC_IDS):
            errors.append(f"sample {sample_id}: contains unknown allowedPocs")
        if sample.get("approvalState") not in {"pending_before_execution", "approved", "rejected"}:
            errors.append(f"sample {sample_id}: invalid approvalState")
    for resource_id, resource in resource_map.items():
        required = {"id", "type", "availability", "bookingRequired", "credentialsStored", "description"}
        missing = required - set(resource)
        if missing:
            errors.append(f"resource {resource_id}: missing fields {sorted(missing)}")
        if resource.get("availability") not in {"unknown", "requires_booking", "available"}:
            errors.append(f"resource {resource_id}: invalid availability")
        if resource.get("credentialsStored") is not False:
            errors.append(f"resource {resource_id}: credentialsStored must be false")

    walk_for_secrets(resources, "resources.yaml", errors)
    walk_for_secrets(samples, "samples.yaml", errors)
    walk_for_secrets(results, "results-index.yaml", errors)
    walk_for_secrets(policy, "policy.yaml", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=None)
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    errors = validate_repository(repo_root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: POC-PROTOCOL-V1 program, 10 plans, resources, samples and results index are consistent with Program Plan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

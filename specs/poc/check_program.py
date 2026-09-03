#!/usr/bin/env python3
"""Fail-closed validator for POC-PROTOCOL-V1."""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml

POCS = {f"POC-{i:02d}" for i in range(1, 11)}
TASKS = {f"POC-{i:03d}" for i in range(1, 11)}
TERMINAL = {"pass", "fail", "inconclusive"}
NONTERMINAL = {"not_started", "running", "blocked", "cancelled"}
PLACEHOLDER = {"", "TBD", "TBD_BEFORE_EXECUTION", "UNKNOWN", "PENDING", "NONE", "N/A", "NA"}
SAFE_KEYS = {"credentials_stored", "credentials_stored_in_repository"}
SENSITIVE = {
    "password", "passwd", "token", "secret", "api_key", "apikey",
    "access_key", "accesskey", "private_key", "privatekey",
    "credential", "credentials",
}
SECRET_PATTERNS = [
    re.compile(r"glpat-[A-Za-z0-9_-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*\S+"),
]
SHA256 = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
IMMUTABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{7,127}$")
TEXTUAL_AI_PROVENANCE = {
    "model_identity", "model_version", "prompt_template_version", "input_sample_version"
}

REQUIRED_MEASUREMENTS = {
    "POC-01": {
        "gpu_passthrough_visible", "driver_runtime_ready",
        "vm_reboot_recovery", "device_reset_recovery",
    },
    "POC-02": {
        "av1_quality", "encode_throughput", "first_segment_latency",
        "sustained_encode_stability", "sustained_encode_duration",
        "encode_provenance_complete",
    },
    "POC-03": {
        "range_correctness", "etag_semantics", "if_range_semantics",
        "cache_key_isolation", "large_file_streaming",
    },
    "POC-04": {
        "iscsi_transport_ready", "sequential_throughput", "io_latency",
        "watermark_behavior", "failure_recovery",
    },
    "POC-05": {
        "file_count", "directory_count", "directory_depth_max",
        "average_file_size", "source_api_quota", "enumeration_rate",
        "incremental_scan_cost", "memory_peak",
    },
    "POC-09": {
        "quality_score", "throughput", "cost_estimate", "license_privacy_pass",
        "caller_permission_gate", "asset_acl_gate", "hard_budget_gate",
        "request_quota_gate", "concurrency_quota_gate",
    },
    "POC-10": {
        "db_restore", "secret_store_restore", "secret_value_roundtrip",
        "secret_unreadable_failure_detected", "file_restore",
        "rpo_observed", "rto_observed",
    },
}
REQUIRED_ENV = {
    "POC-09": {
        "model_identity", "model_version", "prompt_template_version",
        "inference_parameters", "input_sample_version",
    },
}
REQUIRED_PROVENANCE = {
    "POC-02": {"input_sha256", "output_sha256", "encoder_parameters"},
}


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of overwriting them."""


def _construct_unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found unhashable key: {key!r}",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=UniqueKeyLoader)


def schema_check(schema: Any, label: str, errors: list[str]) -> None:
    try:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
    except Exception as exc:
        errors.append(f"{label} invalid JSON Schema: {exc}")


def validate_schema(value: Any, schema: Any, label: str, errors: list[str]) -> None:
    try:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        failures = sorted(
            cls(schema).iter_errors(value),
            key=lambda item: list(item.absolute_path),
        )
        for failure in failures:
            location = "/".join(map(str, failure.absolute_path)) or "<root>"
            errors.append(
                f"{label} schema violation at {location}: {failure.message}"
            )
    except Exception as exc:
        errors.append(f"{label} schema validation failed: {exc}")


def normalize_key(key: Any) -> str:
    text = str(key).replace("-", "_")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower()


def secret_key(key: Any, value: Any) -> bool:
    normalized = normalize_key(key)
    if normalized in SAFE_KEYS:
        return value is not False
    return any(
        re.search(rf"(?:^|_){re.escape(term)}(?:_|$)", normalized)
        for term in SENSITIVE
    )


def secret_scan(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if secret_key(key, item):
                errors.append(f"secret-like key forbidden at {path}/{key}")
            secret_scan(item, f"{path}/{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            secret_scan(item, f"{path}/{index}", errors)
    elif isinstance(value, str) and any(
        pattern.search(value) for pattern in SECRET_PATTERNS
    ):
        errors.append(f"secret-like value forbidden at {path}")


def maps(program_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    pocs = {item["pocId"]: item for item in program_plan.get("pocs", [])}
    tasks = {
        item["taskId"]: item
        for item in program_plan.get("tasks", [])
        if str(item.get("taskId", "")).startswith("POC-")
    }
    return pocs, tasks


def recorded(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.isfinite(float(value))
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and text.upper() not in PLACEHOLDER
    if isinstance(value, list):
        return bool(value) and all(recorded(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(
            str(key).strip() and recorded(item) for key, item in value.items()
        )
    return False


def recorded_text(value: Any) -> bool:
    return isinstance(value, str) and recorded(value)


def good_checksum(value: Any) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value.strip()) is not None


def good_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.strip().upper() not in PLACEHOLDER
        and IMMUTABLE_ID.fullmatch(value.strip()) is not None
    )


def good_actual(unit: Any, value: Any) -> bool:
    if str(unit).lower() == "boolean":
        return isinstance(value, bool)
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def lexical_ref(ref: Any, evidence: str) -> bool:
    if not isinstance(ref, str):
        return False
    value = ref.strip()
    if not value or value.startswith("/") or "\\" in value:
        return False
    if any(part in {"", ".", ".."} for part in value.split("/")):
        return False
    return value.startswith(evidence + "/") and len(value) > len(evidence) + 1


def existing_ref(root: Path, ref: Any, evidence: str) -> Path | None:
    if not lexical_ref(ref, evidence):
        return None
    evidence_root = (root / evidence).resolve()
    path = (root / str(ref)).resolve()
    try:
        path.relative_to(evidence_root)
    except ValueError:
        return None
    return path if path.is_file() else None


def unique_catalogue(items: Any, label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{label}: entries must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}: entry {index} must be a mapping")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{label}: entry {index} requires nonempty id")
            continue
        if item_id in result:
            errors.append(f"{label}: duplicate id {item_id}")
            continue
        result[item_id] = item
    return result


def task_frontmatter(root: Path, task_id: str, errors: list[str]) -> dict[str, Any] | None:
    path = root / "specs" / "tasks" / f"{task_id}.md"
    if not path.is_file():
        errors.append(f"{task_id}: concrete Task Spec is required for non-not_started POC state")
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        errors.append(f"{task_id}: Task Spec must contain YAML front matter")
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append(f"{task_id}: Task Spec front matter is malformed")
        return None
    try:
        front = yaml.load(parts[1], Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        errors.append(f"{task_id}: Task Spec front matter is invalid YAML: {exc}")
        return None
    if not isinstance(front, dict):
        errors.append(f"{task_id}: Task Spec front matter must be a mapping")
        return None
    if str(front.get("id")) != task_id:
        errors.append(f"{task_id}: Task Spec id must equal task ID")
    if str(front.get("schemaVersion")) != "2":
        errors.append(f"{task_id}: Task Spec schemaVersion must be 2")
    return front


def concrete_roles(
    root: Path,
    task_id: str,
    program_task: dict[str, Any],
    errors: list[str],
) -> tuple[str, str] | None:
    front = task_frontmatter(root, task_id, errors)
    if front is None:
        return None
    implementer = str(front.get("implementer") or "").strip()
    reviewer = str(front.get("reviewer") or "").strip()
    generic = {
        str(program_task.get("ownerRole") or "").strip(),
        str(program_task.get("reviewerRole") or "").strip(),
    }
    generic.discard("")
    if not recorded_text(implementer) or not recorded_text(reviewer):
        errors.append(f"{task_id}: Task Spec must assign concrete implementer/reviewer identities")
        return None
    if implementer == reviewer:
        errors.append(f"{task_id}: Task Spec implementer and reviewer must be distinct")
        return None
    if implementer in generic or reviewer in generic:
        errors.append(f"{task_id}: Task Spec identities must not reuse generic Program role labels")
        return None

    active_path = root / "specs" / "coordination" / "active-work.yaml"
    if active_path.is_file():
        try:
            active = load(active_path) or {}
        except Exception as exc:
            errors.append(f"{task_id}: cannot read Active Work for role validation: {exc}")
            return None
        matches = [
            item for item in active.get("tasks", [])
            if str(item.get("taskId")) == task_id
        ]
        if len(matches) > 1:
            errors.append(f"{task_id}: Active Work contains duplicate task entries")
            return None
        if matches:
            entry = matches[0]
            if str(entry.get("implementer") or "").strip() != implementer:
                errors.append(f"{task_id}: Active Work implementer does not match Task Spec")
            if str(entry.get("reviewer") or "").strip() != reviewer:
                errors.append(f"{task_id}: Active Work reviewer does not match Task Spec")
    return implementer, reviewer


def baseline_plan(plan: dict[str, Any], label: str, errors: list[str]) -> None:
    if plan.get("status") != "planned":
        errors.append(f"{label}: canonical plan status must remain planned")
    if plan.get("resultStatus") != "not_started":
        errors.append(f"{label}: canonical plan resultStatus must remain not_started")
    if (plan.get("environment") or {}).get("capturedValues") not in ({}, None):
        errors.append(f"{label}: canonical plan capturedValues must remain empty")
    protocol = plan.get("protocol") or {}
    if protocol.get("commands") or protocol.get("rawOutputRefs"):
        errors.append(f"{label}: canonical plan must not contain execution commands/raw refs")
    if any(
        item.get("actual") is not None
        for item in protocol.get("measurements") or []
    ):
        errors.append(f"{label}: canonical plan measurement actual must remain null")
    decision = plan.get("decision") or {}
    if (
        decision.get("status") != "not_evaluated"
        or decision.get("rationale") is not None
        or decision.get("resultRef") is not None
    ):
        errors.append(f"{label}: canonical plan decision must remain not_evaluated/null")
    review = plan.get("review") or {}
    if any(review.get(key) is not None for key in ("reviewer", "approvedAt", "approval")):
        errors.append(f"{label}: canonical plan review fields must remain null")


def validate_approval_record(
    root: Path,
    plan: dict[str, Any],
    implementer: str,
    sample: dict[str, Any],
    approval_schema: dict[str, Any],
    errors: list[str],
) -> None:
    evidence = plan["evidencePath"]
    sample_id = sample.get("id")
    path = existing_ref(root, sample.get("approvalRef"), evidence)
    label = f"sample approval {plan['taskId']}/{sample_id}"
    if path is None:
        errors.append(f"{label}: approvalRef must exist under {evidence}")
        return
    try:
        approval = load(path)
    except Exception as exc:
        errors.append(f"{label}: cannot parse approval record: {exc}")
        return
    if not isinstance(approval, dict):
        errors.append(f"{label}: approval record must be a mapping")
        return
    validate_schema(approval, approval_schema, label, errors)
    secret_scan(approval, label, errors)
    expected = {
        "pocId": plan["pocId"],
        "taskId": plan["taskId"],
        "sampleId": sample_id,
        "immutableId": sample.get("immutableId"),
        "checksum": sample.get("checksum"),
        "decision": "approved",
    }
    for key, value in expected.items():
        if approval.get(key) != value:
            errors.append(f"{label}: {key} must equal {value!r}")
    if not recorded_text(approval.get("approver")):
        errors.append(f"{label}: approver must be a concrete non-placeholder identity")
    if approval.get("approver") == implementer:
        errors.append(f"{label}: approver must differ from execution implementer")
    if not valid_utc_timestamp(approval.get("approvedAt")):
        errors.append(f"{label}: approvedAt must be a valid UTC instant")


def validate_execution(
    root: Path,
    plan: dict[str, Any],
    implementer: str,
    execution: dict[str, Any],
    schema: dict[str, Any],
    approval_schema: dict[str, Any],
    status: str,
    errors: list[str],
) -> None:
    task_id = plan["taskId"]
    poc_id = plan["pocId"]
    evidence = plan["evidencePath"]
    label = f"execution record {task_id}"
    validate_schema(execution, schema, label, errors)
    secret_scan(execution, label, errors)
    for key, expected in (
        ("pocId", poc_id),
        ("taskId", task_id),
        ("evidencePath", evidence),
        ("executor", implementer),
    ):
        if execution.get(key) != expected:
            errors.append(f"{label}: {key} must equal {expected!r}")

    environment = execution.get("environmentCaptured") or {}
    required_environment = set(plan["environment"]["captureBeforeExecution"])
    missing = required_environment - set(environment)
    if missing:
        errors.append(f"{label}: missing environment fields {sorted(missing)}")
    bad = [
        key for key in required_environment
        if key in environment and not recorded(environment[key])
    ]
    if bad:
        errors.append(f"{label}: empty/placeholder environment values {sorted(bad)}")
    if poc_id == "POC-09":
        for key in TEXTUAL_AI_PROVENANCE:
            if key in environment and not recorded_text(environment[key]):
                errors.append(f"{label}: AI provenance {key} must be a non-placeholder string")
        if "inference_parameters" in environment and not recorded(environment["inference_parameters"]):
            errors.append(f"{label}: AI provenance inference_parameters must be nonempty")

    commands = execution.get("commands") or []
    if not commands or any(
        not isinstance(command, str) or not command.strip()
        for command in commands
    ):
        errors.append(f"{label}: commands must contain nonempty recorded commands")

    raw_refs = execution.get("rawOutputRefs") or []
    if not raw_refs:
        errors.append(f"{label}: at least one raw output reference is required")
    for ref in raw_refs:
        if existing_ref(root, ref, evidence) is None:
            errors.append(f"{label}: raw evidence file must exist under {evidence}: {ref!r}")

    samples = execution.get("samples") or []
    sample_ids = [sample.get("id") for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        errors.append(f"{label}: execution sample IDs must be unique")
    if set(sample_ids) != set(plan.get("sampleIds") or []):
        errors.append(f"{label}: execution sample IDs must exactly match plan")
    for sample in samples:
        sample_id = sample.get("id")
        if sample.get("approved") is not True:
            errors.append(f"{label}: sample {sample_id} must be explicitly approved")
        if not good_id(sample.get("immutableId")):
            errors.append(f"{label}: sample {sample_id} immutableId is invalid/placeholder")
        if not good_checksum(sample.get("checksum")):
            errors.append(f"{label}: sample {sample_id} checksum must be sha256:<64 hex>")
        validate_approval_record(root, plan, implementer, sample, approval_schema, errors)

    planned_measurements = {
        item["id"]: item for item in plan["protocol"]["measurements"]
    }
    actual_measurements = execution.get("measurements") or []
    actual_map = {
        item.get("id"): item.get("actual") for item in actual_measurements
    }
    if len(actual_map) != len(actual_measurements):
        errors.append(f"{label}: measurement IDs must be unique")
    if set(actual_map) != set(planned_measurements):
        errors.append(f"{label}: measurement IDs must exactly match plan")
    bad = [
        measurement_id
        for measurement_id, definition in planned_measurements.items()
        if measurement_id in actual_map
        and not good_actual(definition.get("unit"), actual_map[measurement_id])
    ]
    if bad:
        errors.append(f"{label}: invalid/placeholder measurement values {sorted(bad)}")
    false_gates = [
        measurement_id
        for measurement_id, definition in planned_measurements.items()
        if status == "pass"
        and str(definition.get("unit")).lower() == "boolean"
        and actual_map.get(measurement_id) is not True
    ]
    if false_gates:
        errors.append(f"{label}: PASS has false/non-true boolean gates {sorted(false_gates)}")

    provenance = execution.get("provenance") or {}
    required_provenance = REQUIRED_PROVENANCE.get(poc_id, set())
    missing = required_provenance - set(provenance)
    if missing:
        errors.append(f"{label}: missing required provenance fields {sorted(missing)}")
    for key in required_provenance & set(provenance):
        if key in {"input_sha256", "output_sha256"}:
            if not good_checksum(provenance[key]):
                errors.append(f"{label}: provenance {key} must be sha256:<64 hex>")
        elif not recorded(provenance[key]):
            errors.append(f"{label}: provenance {key} must be nonempty/non-placeholder")
    if poc_id == "POC-02" and good_checksum(provenance.get("input_sha256")):
        approved_checksums = {sample.get("checksum") for sample in samples}
        if provenance["input_sha256"] not in approved_checksums:
            errors.append(
                f"{label}: POC-002 input_sha256 must match an approved execution sample checksum"
            )


def validate_terminal(
    root: Path,
    plan: dict[str, Any],
    task: dict[str, Any],
    entry: dict[str, Any],
    result_schema: dict[str, Any],
    execution_schema: dict[str, Any],
    approval_schema: dict[str, Any],
    errors: list[str],
) -> None:
    task_id = plan["taskId"]
    evidence = plan["evidencePath"]
    status = entry.get("status")
    label = f"results-index {task_id}"
    roles = concrete_roles(root, task_id, task, errors)
    if roles is None:
        return
    implementer, reviewer = roles

    result_path = existing_ref(root, entry.get("resultRef"), evidence)
    if result_path is None:
        errors.append(
            f"{label}: terminal resultRef must point to an existing file under {evidence}"
        )
        return
    try:
        result = load(result_path)
    except Exception as exc:
        errors.append(f"result record {task_id}: cannot parse result: {exc}")
        return
    if not isinstance(result, dict):
        errors.append(f"result record {task_id}: must be a mapping")
        return
    validate_schema(result, result_schema, f"result record {task_id}", errors)
    secret_scan(result, f"result record {task_id}", errors)

    for key, expected in (
        ("pocId", plan["pocId"]),
        ("taskId", task_id),
        ("status", status),
        ("evidencePath", evidence),
        ("decision", status),
        ("reviewer", reviewer),
        ("approvedAt", entry.get("approvedAt")),
    ):
        if result.get(key) != expected:
            errors.append(f"result record {task_id}: {key} must equal {expected!r}")
    if entry.get("decision") != status:
        errors.append(f"{label}: decision must equal terminal status")
    if entry.get("reviewer") != reviewer:
        errors.append(f"{label}: reviewer must equal concrete Task Spec reviewer")
    if entry.get("reviewer") == implementer:
        errors.append(f"{label}: reviewer must differ from concrete Task Spec implementer")
    if not valid_utc_timestamp(entry.get("approvedAt")):
        errors.append(f"{label}: approvedAt must be a valid UTC instant")
    if result.get("approval") != "approved":
        errors.append(f"result record {task_id}: approval must be approved")
    if not isinstance(result.get("rationale"), str) or not result["rationale"].strip():
        errors.append(f"result record {task_id}: rationale must be nonempty")
    if not valid_utc_timestamp(result.get("approvedAt")):
        errors.append(f"result record {task_id}: approvedAt must be a valid UTC instant")

    execution_path = existing_ref(root, result.get("executionRef"), evidence)
    if execution_path is None:
        errors.append(
            f"result record {task_id}: executionRef must point to an existing file under {evidence}"
        )
        return
    try:
        execution = load(execution_path)
    except Exception as exc:
        errors.append(f"execution record {task_id}: cannot parse execution: {exc}")
        return
    if not isinstance(execution, dict):
        errors.append(f"execution record {task_id}: must be a mapping")
        return
    if result.get("reviewer") == execution.get("executor"):
        errors.append(f"result record {task_id}: reviewer must differ from execution executor")
    validate_execution(
        root, plan, implementer, execution, execution_schema,
        approval_schema, status, errors,
    )


def validate_templates(
    base: Path,
    program: dict[str, Any],
    errors: list[str],
) -> None:
    expected_keys = {
        "executionRecordTemplate": {
            "schemaVersion", "pocId", "taskId", "evidencePath", "executor",
            "environmentCaptured", "commands", "rawOutputRefs", "samples",
            "measurements", "provenance", "notes",
        },
        "resultRecordTemplate": {
            "schemaVersion", "pocId", "taskId", "status", "evidencePath",
            "executionRef", "decision", "rationale", "reviewer",
            "approvedAt", "approval",
        },
        "sampleApprovalTemplate": {
            "schemaVersion", "pocId", "taskId", "sampleId", "immutableId",
            "checksum", "decision", "approver", "approvedAt",
        },
    }
    for manifest_key, keys in expected_keys.items():
        relative = program.get(manifest_key)
        path = base / str(relative or "")
        if not relative or not path.is_file():
            errors.append(f"program.yaml {manifest_key} must point to an existing regular file")
            continue
        try:
            value = load(path)
        except Exception as exc:
            errors.append(f"{relative}: cannot parse template: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{relative}: template must be a mapping")
            continue
        missing = keys - set(value)
        if missing:
            errors.append(f"{relative}: template missing keys {sorted(missing)}")


def validate_concurrency(
    index: dict[str, dict[str, Any]],
    plans: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    errors: list[str],
) -> None:
    running = [
        task_id for task_id, entry in index.items()
        if entry.get("status") == "running"
    ]
    high_critical = [
        task_id for task_id in running
        if plans.get(task_id, {}).get("riskLevel") in {"high", "critical"}
    ]
    limit = policy.get("maxConcurrentHighCritical")
    if not isinstance(limit, int) or limit < 1:
        errors.append("policy maxConcurrentHighCritical must be a positive integer")
    elif len(high_critical) > limit:
        errors.append(
            f"running high/critical POC count {len(high_critical)} exceeds limit {limit}: {high_critical}"
        )
    critical_running = [
        task_id for task_id in running
        if plans.get(task_id, {}).get("riskLevel") == "critical"
    ]
    if critical_running and policy.get("criticalStandalone") is True and len(running) != 1:
        errors.append(
            f"critical POC must run standalone; running tasks are {running}"
        )


def validate_result_index_row_ownership(
    base_index: dict[str, Any],
    current_index: dict[str, Any],
    task_id: str,
    errors: list[str],
) -> None:
    if task_id not in TASKS:
        errors.append(f"row-ownership task must be one of POC-001..POC-010, got {task_id}")
        return
    base_map = {
        item.get("taskId"): item for item in base_index.get("entries", [])
    }
    current_map = {
        item.get("taskId"): item for item in current_index.get("entries", [])
    }
    if set(base_map) != TASKS or set(current_map) != TASKS:
        errors.append("row-ownership validation requires exactly POC-001..POC-010 in both indexes")
        return
    changed = sorted(
        item_id for item_id in TASKS
        if base_map[item_id] != current_map[item_id]
    )
    if any(item_id != task_id for item_id in changed):
        errors.append(
            f"{task_id}: results-index update changed other task rows: {changed}"
        )


def load_index_from_git(root: Path, base_ref: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            ["git", "show", f"{base_ref}:specs/poc/results-index.yaml"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        errors.append(f"cannot execute git for row-ownership validation: {exc}")
        return None
    if proc.returncode != 0:
        errors.append(
            f"cannot read specs/poc/results-index.yaml from {base_ref}: {proc.stderr.strip()}"
        )
        return None
    try:
        value = yaml.load(proc.stdout, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        errors.append(f"base results-index from {base_ref} is invalid YAML: {exc}")
        return None
    return value if isinstance(value, dict) else None


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    base = root / "specs" / "poc"
    try:
        program = load(base / "program.yaml")
        program_schema = load(base / "program.schema.yaml")
        plan_schema = load(base / "plan.schema.yaml")
        protocol_schema = load(base / "protocol.schema.yaml")
        result_index_schema = load(base / "result-index.schema.yaml")
        execution_schema = load(base / "execution-record.schema.yaml")
        result_record_schema = load(base / "result-record.schema.yaml")
        approval_schema = load(base / "sample-approval.schema.yaml")
        resources = load(base / "resources.yaml")
        samples = load(base / "samples.yaml")
        results = load(base / "results-index.yaml")
        policy = load(base / "policy.yaml")
        program_plan = load(root / "specs" / "coordination" / "program-plan.yaml")
    except Exception as exc:
        return [f"cannot load POC Program: {exc}"]

    for name, schema in (
        ("program.schema.yaml", program_schema),
        ("plan.schema.yaml", plan_schema),
        ("protocol.schema.yaml", protocol_schema),
        ("result-index.schema.yaml", result_index_schema),
        ("execution-record.schema.yaml", execution_schema),
        ("result-record.schema.yaml", result_record_schema),
        ("sample-approval.schema.yaml", approval_schema),
    ):
        schema_check(schema, name, errors)
    validate_schema(program, program_schema, "program.yaml", errors)
    validate_schema(results, result_index_schema, "results-index.yaml", errors)

    expected_manifest = {
        "executionRecordSchema": "execution-record.schema.yaml",
        "resultRecordSchema": "result-record.schema.yaml",
        "sampleApprovalSchema": "sample-approval.schema.yaml",
        "executionRecordTemplate": "templates/execution-record.yaml",
        "resultRecordTemplate": "templates/result-record.yaml",
        "sampleApprovalTemplate": "templates/sample-approval.yaml",
    }
    for key, expected in expected_manifest.items():
        if program.get(key) != expected:
            errors.append(f"program.yaml {key} must equal {expected!r}")
        elif not (base / expected).is_file():
            errors.append(f"program.yaml {key} must reference an existing regular file")
    validate_templates(base, program, errors)

    if program.get("executionEnabled") is not False:
        errors.append("GZ-010 program executionEnabled must be false")
    if policy.get("executionAllowedInGz010") is not False:
        errors.append("policy executionAllowedInGz010 must be false")
    for key in (
        "sampleExecutionRequiresApproval", "canonicalPlansImmutable",
        "cataloguesImmutableInPocTasks", "terminalEvidenceMustExist",
        "terminalReviewRoleBound", "highCriticalIsolation", "criticalStandalone",
        "resultIndexRowOwnershipRequired",
    ):
        if policy.get(key) is not True:
            errors.append(f"policy {key} must be true")

    canonical_pocs, canonical_tasks = maps(program_plan)
    if set(canonical_pocs) != POCS:
        errors.append("canonical Program Plan POC IDs mismatch")
    if set(canonical_tasks) != TASKS:
        errors.append("canonical Program Plan POC task IDs mismatch")

    plan_files = program.get("planFiles") or []
    expected_plan_files = {f"plans/POC-{index:03d}.yaml" for index in range(1, 11)}
    if set(plan_files) != expected_plan_files:
        errors.append("program.yaml planFiles must contain exactly POC-001..POC-010")

    resource_map = unique_catalogue(resources.get("resources"), "resources.yaml", errors)
    sample_map = unique_catalogue(samples.get("samples"), "samples.yaml", errors)

    by_poc: dict[str, dict[str, Any]] = {}
    by_task: dict[str, dict[str, Any]] = {}
    evidence_paths: set[str] = set()

    for relative in plan_files:
        path = base / relative
        if not path.is_file():
            errors.append(f"missing POC plan: {relative}")
            continue
        try:
            plan = load(path)
        except Exception as exc:
            errors.append(f"{relative}: cannot parse POC plan: {exc}")
            continue
        if not isinstance(plan, dict):
            errors.append(f"{relative}: POC plan must be a mapping")
            continue

        validate_schema(plan, plan_schema, relative, errors)
        validate_schema(plan.get("protocol"), protocol_schema, relative + "/protocol", errors)
        secret_scan(plan, relative, errors)
        baseline_plan(plan, relative, errors)

        poc_id = plan.get("pocId")
        task_id = plan.get("taskId")
        if poc_id in by_poc:
            errors.append(f"duplicate POC plan pocId {poc_id}")
        if task_id in by_task:
            errors.append(f"duplicate POC plan taskId {task_id}")
        by_poc[poc_id] = plan
        by_task[task_id] = plan

        canonical_poc = canonical_pocs.get(poc_id)
        canonical_task = canonical_tasks.get(task_id)
        if not canonical_poc:
            errors.append(f"{relative}: unknown canonical pocId {poc_id}")
        if not canonical_task:
            errors.append(f"{relative}: unknown canonical taskId {task_id}")
        if canonical_poc and canonical_poc.get("taskId") != task_id:
            errors.append(f"{relative}: POC↔Task mismatch")

        if canonical_poc and canonical_task:
            checks = {
                "riskLevel": (plan.get("riskLevel"), canonical_task.get("riskLevel")),
                "wave": (plan.get("wave"), canonical_task.get("wave")),
                "requirementIds": (
                    set(plan.get("requirementIds") or []),
                    set(canonical_task.get("requirementIds") or []),
                ),
                "moduleIds": (
                    set(plan.get("moduleIds") or []),
                    set(canonical_task.get("moduleIds") or []),
                ),
                "evidencePath": (
                    plan.get("evidencePath"), canonical_poc.get("evidencePath")
                ),
                "dependsOn": (
                    set(plan.get("dependsOn") or []),
                    set(canonical_task.get("dependsOn") or []),
                ),
            }
            for key, (actual, expected) in checks.items():
                if actual != expected:
                    errors.append(f"{relative}: {key} does not match Program Plan")

            evidence_path = plan.get("evidencePath")
            output_paths = set(canonical_task.get("outputPaths") or [])
            shared_paths = set(canonical_task.get("sharedPaths") or [])
            if not output_paths.intersection({evidence_path, f"{evidence_path}/**"}):
                errors.append(
                    f"{relative}: downstream task must own its Evidence path {evidence_path!r}"
                )
            if "specs/poc/results-index.yaml" not in shared_paths:
                errors.append(
                    f"{relative}: downstream task must share specs/poc/results-index.yaml"
                )
            forbidden_poc_paths = {
                value for value in output_paths | shared_paths
                if value.startswith("specs/poc/")
                and value != "specs/poc/results-index.yaml"
            }
            if forbidden_poc_paths:
                errors.append(
                    f"{relative}: downstream task may not own immutable specs/poc paths {sorted(forbidden_poc_paths)}"
                )

        evidence_path = plan.get("evidencePath")
        if evidence_path in evidence_paths:
            errors.append(f"duplicate POC evidence path: {evidence_path}")
        evidence_paths.add(evidence_path)

        measurement_ids = [
            item.get("id")
            for item in (plan.get("protocol") or {}).get("measurements", [])
        ]
        missing_measurements = REQUIRED_MEASUREMENTS.get(poc_id, set()) - set(measurement_ids)
        if missing_measurements:
            errors.append(
                f"{relative}: missing frozen required measurements {sorted(missing_measurements)}"
            )
        capture_fields = set(
            (plan.get("environment") or {}).get("captureBeforeExecution", [])
        )
        missing_environment = REQUIRED_ENV.get(poc_id, set()) - capture_fields
        if missing_environment:
            errors.append(
                f"{relative}: missing required environment provenance fields {sorted(missing_environment)}"
            )

        for resource_id in plan.get("resourceIds") or []:
            if resource_id not in resource_map:
                errors.append(f"{relative}: unknown resource {resource_id}")
        for sample_id in plan.get("sampleIds") or []:
            if sample_id not in sample_map:
                errors.append(f"{relative}: unknown sample {sample_id}")
            elif poc_id not in (sample_map[sample_id].get("allowedPocs") or []):
                errors.append(f"{relative}: sample {sample_id} does not allow {poc_id}")

    if set(by_poc) != POCS:
        errors.append("plan POC IDs must be exactly POC-01..10")
    if set(by_task) != TASKS:
        errors.append("plan task IDs must be exactly POC-001..010")

    for sample_id, sample in sample_map.items():
        required = {
            "id", "description", "source", "classification", "approvalState",
            "immutableId", "checksum", "allowedPocs",
        }
        missing = required - set(sample)
        if missing:
            errors.append(f"sample {sample_id}: missing fields {sorted(missing)}")
        if sample.get("approvalState") != "pending_before_execution":
            errors.append(f"sample {sample_id}: approvalState must remain pending_before_execution")
        if sample.get("immutableId") != "TBD_BEFORE_EXECUTION":
            errors.append(f"sample {sample_id}: immutableId must remain TBD_BEFORE_EXECUTION")
        if sample.get("checksum") != "TBD_BEFORE_EXECUTION":
            errors.append(f"sample {sample_id}: checksum must remain TBD_BEFORE_EXECUTION")
        if not set(sample.get("allowedPocs") or []).issubset(POCS):
            errors.append(f"sample {sample_id}: contains unknown allowedPocs")

    for resource_id, resource in resource_map.items():
        required = {
            "id", "type", "availability", "bookingRequired",
            "credentialsStored", "description",
        }
        missing = required - set(resource)
        if missing:
            errors.append(f"resource {resource_id}: missing fields {sorted(missing)}")
        if resource.get("credentialsStored") is not False:
            errors.append(f"resource {resource_id}: credentialsStored must be false")

    entries = results.get("entries") or []
    index = {item.get("taskId"): item for item in entries if isinstance(item, dict)}
    if set(index) != TASKS or len(index) != len(entries):
        errors.append("results-index must contain exactly unique POC-001..POC-010")

    validate_concurrency(index, by_task, policy, errors)

    for task_id, entry in index.items():
        plan = by_task.get(task_id)
        canonical_task = canonical_tasks.get(task_id)
        if not plan or not canonical_task:
            continue
        if entry.get("pocId") != plan.get("pocId"):
            errors.append(f"results-index {task_id}: pocId mismatch")
        if entry.get("evidencePath") != plan.get("evidencePath"):
            errors.append(f"results-index {task_id}: evidencePath mismatch")
        status = entry.get("status")
        if status in NONTERMINAL:
            for key in ("resultRef", "decision", "reviewer", "approvedAt"):
                if entry.get(key) is not None:
                    errors.append(
                        f"results-index {task_id}: nonterminal {status} {key} must be null"
                    )
            if status != "not_started":
                concrete_roles(root, task_id, canonical_task, errors)
        elif status in TERMINAL:
            validate_terminal(
                root, plan, canonical_task, entry,
                result_record_schema, execution_schema,
                approval_schema, errors,
            )
        else:
            errors.append(f"results-index {task_id}: unsupported status {status!r}")

    for name, value in (
        ("resources.yaml", resources),
        ("samples.yaml", samples),
        ("results-index.yaml", results),
        ("policy.yaml", policy),
    ):
        secret_scan(value, name, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root")
    parser.add_argument("--task", help="Executing POC task for results-index row ownership validation")
    parser.add_argument("--base-ref", help="Git base ref used to prove only --task row changed")
    args = parser.parse_args()
    root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else Path(__file__).resolve().parents[2]
    )
    errors = validate_repository(root)

    if bool(args.task) != bool(args.base_ref):
        errors.append("--task and --base-ref must be supplied together")
    elif args.task and args.base_ref:
        current = load(root / "specs" / "poc" / "results-index.yaml")
        base = load_index_from_git(root, args.base_ref, errors)
        if base is not None:
            validate_result_index_row_ownership(base, current, args.task, errors)

    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1
    print(
        "PASS: POC-PROTOCOL-V1 immutable planning baseline and "
        "task-owned Evidence contracts are consistent with Program Plan"
    )
    if args.task:
        print(
            f"PASS: results-index row ownership verified for {args.task} "
            f"against {args.base_ref}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

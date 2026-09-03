#!/usr/bin/env python3
"""Fail-closed validator for POC-PROTOCOL-V1."""

from __future__ import annotations

import argparse
import math
import re
import sys
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


def load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def secret_key(key: Any) -> bool:
    normalized = normalize_key(key)
    if normalized in SAFE_KEYS:
        return False
    return any(
        re.search(rf"(?:^|_){re.escape(term)}(?:_|$)", normalized)
        for term in SENSITIVE
    )


def secret_scan(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if secret_key(key):
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
        front = yaml.safe_load(parts[1])
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
    if not recorded(implementer) or not recorded(reviewer):
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
    if any(item.get("actual") is not None for item in protocol.get("measurements") or []):
        errors.append(f"{label}: canonical plan measurement actual must remain null")
    decision = plan.get("decision") or {}
    if decision.get("status") != "not_evaluated" or decision.get("rationale") is not None or decision.get("resultRef") is not None:
        errors.append(f"{label}: canonical plan decision must remain not_evaluated/null")
    review = plan.get("review") or {}
    if any(review.get(key) is not None for key in ("reviewer", "approvedAt", "approval")):
        errors.append(f"{label}: canonical plan review fields must remain null")


def validate_execution(root: Path, plan: dict[str, Any], implementer: str, execution: dict[str, Any], schema: dict[str, Any], status: str, errors: list[str]) -> None:
    task_id = plan["taskId"]
    poc_id = plan["pocId"]
    evidence = plan["evidencePath"]
    label = f"execution record {task_id}"
    validate_schema(execution, schema, label, errors)
    secret_scan(execution, label, errors)
    for key, expected in (("pocId", poc_id), ("taskId", task_id), ("evidencePath", evidence), ("executor", implementer)):
        if execution.get(key) != expected:
            errors.append(f"{label}: {key} must equal {expected!r}")
    environment = execution.get("environmentCaptured") or {}
    required_environment = set(plan["environment"]["captureBeforeExecution"])
    missing = required_environment - set(environment)
    if missing:
        errors.append(f"{label}: missing environment fields {sorted(missing)}")
    bad = [key for key in required_environment if key in environment and not recorded(environment[key])]
    if bad:
        errors.append(f"{label}: empty/placeholder environment values {sorted(bad)}")
    commands = execution.get("commands") or []
    if not commands or any(not isinstance(command, str) or not command.strip() for command in commands):
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
        if existing_ref(root, sample.get("approvalRef"), evidence) is None:
            errors.append(f"{label}: sample {sample_id} approvalRef must exist under {evidence}")
    planned_measurements = {item["id"]: item for item in plan["protocol"]["measurements"]}
    actual_measurements = execution.get("measurements") or []
    actual_map = {item.get("id"): item.get("actual") for item in actual_measurements}
    if len(actual_map) != len(actual_measurements):
        errors.append(f"{label}: measurement IDs must be unique")
    if set(actual_map) != set(planned_measurements):
        errors.append(f"{label}: measurement IDs must exactly match plan")
    bad = [measurement_id for measurement_id, definition in planned_measurements.items() if measurement_id in actual_map and not good_actual(definition.get("unit"), actual_map[measurement_id])]
    if bad:
        errors.append(f"{label}: invalid/placeholder measurement values {sorted(bad)}")
    false_gates = [measurement_id for measurement_id, definition in planned_measurements.items() if status == "pass" and str(definition.get("unit")).lower() == "boolean" and actual_map.get(measurement_id) is not True]
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


def validate_terminal(root: Path, plan: dict[str, Any], task: dict[str, Any], entry: dict[str, Any], result_schema: dict[str, Any], execution_schema: dict[str, Any], errors: list[str]) -> None:
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
        errors.append(f"{label}: terminal resultRef must point to an existing file under {evidence}")
        return
    result = load(result_path)
    if not isinstance(result, dict):
        errors.append(f"result record {task_id}: must be a mapping")
        return
    validate_schema(result, result_schema, f"result record {task_id}", errors)
    secret_scan(result, f"result record {task_id}", errors)
    for key, expected in (("pocId", plan["pocId"]), ("taskId", task_id), ("status", status), ("evidencePath", evidence), ("decision", status), ("reviewer", reviewer), ("approvedAt", entry.get("approvedAt"))):
        if result.get(key) != expected:
            errors.append(f"result record {task_id}: {key} must equal {expected!r}")
    if entry.get("decision") != status:
        errors.append(f"{label}: decision must equal terminal status")
    if entry.get("reviewer") != reviewer:
        errors.append(f"{label}: reviewer must equal concrete Task Spec reviewer")
    if entry.get("reviewer") == implementer:
        errors.append(f"{label}: reviewer must differ from concrete Task Spec implementer")
    if not isinstance(entry.get("approvedAt"), str) or not entry["approvedAt"].strip():
        errors.append(f"{label}: approvedAt must be nonempty")
    if result.get("approval") != "approved":
        errors.append(f"result record {task_id}: approval must be approved")
    if not isinstance(result.get("rationale"), str) or not result["rationale"].strip():
        errors.append(f"result record {task_id}: rationale must be nonempty")
    execution_path = existing_ref(root, result.get("executionRef"), evidence)
    if execution_path is None:
        errors.append(f"result record {task_id}: executionRef must point to an existing file under {evidence}")
        return
    execution = load(execution_path)
    if not isinstance(execution, dict):
        errors.append(f"execution record {task_id}: must be a mapping")
        return
    if result.get("reviewer") == execution.get("executor"):
        errors.append(f"result record {task_id}: reviewer must differ from execution executor")
    validate_execution(root, plan, implementer, execution, execution_schema, status, errors)


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
        resources = load(base / "resources.yaml")
        samples = load(base / "samples.yaml")
        results = load(base / "results-index.yaml")
        policy = load(base / "policy.yaml")
        program_plan = load(root / "specs" / "coordination" / "program-plan.yaml")
    except Exception as exc:
        return [f"cannot load POC Program: {exc}"]
    for name, schema in (("program.schema.yaml", program_schema), ("plan.schema.yaml", plan_schema), ("protocol.schema.yaml", protocol_schema), ("result-index.schema.yaml", result_index_schema), ("execution-record.schema.yaml", execution_schema), ("result-record.schema.yaml", result_record_schema)):
        schema_check(schema, name, errors)
    validate_schema(program, program_schema, "program.yaml", errors)
    validate_schema(results, result_index_schema, "results-index.yaml", errors)
    expected_manifest = {"executionRecordSchema": "execution-record.schema.yaml", "resultRecordSchema": "result-record.schema.yaml", "executionRecordTemplate": "templates/execution-record.yaml", "resultRecordTemplate": "templates/result-record.yaml"}
    for key, expected in expected_manifest.items():
        if program.get(key) != expected:
            errors.append(f"program.yaml {key} must equal {expected!r}")
    if program.get("executionEnabled") is not False:
        errors.append("GZ-010 program executionEnabled must be false")
    if policy.get("executionAllowedInGz010") is not False:
        errors.append("policy executionAllowedInGz010 must be false")
    for key in ("sampleExecutionRequiresApproval", "canonicalPlansImmutable", "cataloguesImmutableInPocTasks", "terminalEvidenceMustExist", "terminalReviewRoleBound", "highCriticalIsolation", "criticalStandalone"):
        if policy.get(key) is not True:
            errors.append(f"policy {key} must be true")
    if policy.get("maxConcurrentHighCritical") != 1:
        errors.append("policy maxConcurrentHighCritical must be 1")
    canonical_pocs, canonical_tasks = maps(program_plan)
    if set(canonical_pocs) != POCS:
        errors.append("canonical Program Plan POC IDs mismatch")
    if set(canonical_tasks) != TASKS:
        errors.append("canonical Program Plan POC task IDs mismatch")
    plan_files = program.get("planFiles") or []
    expected_plan_files = {f"plans/POC-{index:03d}.yaml" for index in range(1, 11)}
    if set(plan_files) != expected_plan_files:
        errors.append("program.yaml planFiles must contain exactly POC-001..POC-010")
    resource_map = {item.get("id"): item for item in resources.get("resources", [])}
    sample_map = {item.get("id"): item for item in samples.get("samples", [])}
    by_poc: dict[str, dict[str, Any]] = {}
    by_task: dict[str, dict[str, Any]] = {}
    evidence_paths: set[str] = set()
    for relative in plan_files:
        path = base / relative
        if not path.is_file():
            errors.append(f"missing POC plan: {relative}")
            continue
        plan = load(path)
        validate_schema(plan, plan_schema, relative, errors)
        validate_schema(plan.get("protocol"), protocol_schema, relative + "/protocol", errors)
        secret_scan(plan, relative, errors)
        baseline_plan(plan, relative, errors)
        poc_id = plan.get("pocId")
        task_id = plan.get("taskId")
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
                "requirementIds": (set(plan.get("requirementIds") or []), set(canonical_task.get("requirementIds") or [])),
                "moduleIds": (set(plan.get("moduleIds") or []), set(canonical_task.get("moduleIds") or [])),
                "evidencePath": (plan.get("evidencePath"), canonical_poc.get("evidencePath")),
                "dependsOn": (set(plan.get("dependsOn") or []), set(canonical_task.get("dependsOn") or [])),
            }
            for key, (actual, expected) in checks.items():
                if actual != expected:
                    errors.append(f"{relative}: {key} does not match Program Plan")
            evidence_path = plan.get("evidencePath")
            output_paths = set(canonical_task.get("outputPaths") or [])
            if not output_paths.intersection({evidence_path, f"{evidence_path}/**"}):
                errors.append(f"{relative}: downstream task must own its Evidence path {evidence_path!r}")
            if "specs/poc/results-index.yaml" not in (canonical_task.get("sharedPaths") or []):
                errors.append(f"{relative}: downstream task must share specs/poc/results-index.yaml")
        evidence_path = plan.get("evidencePath")
        if evidence_path in evidence_paths:
            errors.append(f"duplicate POC evidence path: {evidence_path}")
        evidence_paths.add(evidence_path)
        measurement_ids = [item.get("id") for item in (plan.get("protocol") or {}).get("measurements", [])]
        missing_measurements = REQUIRED_MEASUREMENTS.get(poc_id, set()) - set(measurement_ids)
        if missing_measurements:
            errors.append(f"{relative}: missing frozen required measurements {sorted(missing_measurements)}")
        capture_fields = set((plan.get("environment") or {}).get("captureBeforeExecution", []))
        missing_environment = REQUIRED_ENV.get(poc_id, set()) - capture_fields
        if missing_environment:
            errors.append(f"{relative}: missing required environment provenance fields {sorted(missing_environment)}")
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
        if sample.get("approvalState") != "pending_before_execution":
            errors.append(f"sample {sample_id}: approvalState must remain pending_before_execution")
        if sample.get("immutableId") != "TBD_BEFORE_EXECUTION":
            errors.append(f"sample {sample_id}: immutableId must remain TBD_BEFORE_EXECUTION")
        if sample.get("checksum") != "TBD_BEFORE_EXECUTION":
            errors.append(f"sample {sample_id}: checksum must remain TBD_BEFORE_EXECUTION")
    for resource_id, resource in resource_map.items():
        if resource.get("credentialsStored") is not False:
            errors.append(f"resource {resource_id}: credentialsStored must be false")
    entries = results.get("entries") or []
    index = {item.get("taskId"): item for item in entries}
    if set(index) != TASKS or len(index) != len(entries):
        errors.append("results-index must contain exactly unique POC-001..POC-010")
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
                    errors.append(f"results-index {task_id}: nonterminal {status} {key} must be null")
            if status != "not_started":
                concrete_roles(root, task_id, canonical_task, errors)
        elif status in TERMINAL:
            validate_terminal(root, plan, canonical_task, entry, result_record_schema, execution_schema, errors)
        else:
            errors.append(f"results-index {task_id}: unsupported status {status!r}")
    for name, value in (("resources.yaml", resources), ("samples.yaml", samples), ("results-index.yaml", results), ("policy.yaml", policy)):
        secret_scan(value, name, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    errors = validate_repository(root)
    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1
    print("PASS: POC-PROTOCOL-V1 immutable planning baseline and task-owned Evidence contracts are consistent with Program Plan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

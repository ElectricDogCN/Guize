#!/usr/bin/env python3
"""Fail-closed validator for POC-PROTOCOL-V1."""

from __future__ import annotations

import argparse
import copy
import json
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
        'above_4g_enabled', 'bios_iommu_configuration_verified', 'device_reset_recovery',
        'driver_runtime_ready', 'esxi_host_reboot_reenumeration', 'gpu_passthrough_visible',
        'iommu_group_isolation_verified', 'multi_day_stability', 'multi_day_stability_duration',
        'resizable_bar_enabled', 'vm_reboot_recovery',
    },
    "POC-02": {
        'a380_range_first_byte_latency', 'av1_quality', 'cancellation_cleanup_complete',
        'disallowed_input_targets_denied', 'encode_provenance_complete', 'encode_throughput',
        'encoder_power_peak_watts', 'encoder_temperature_peak_celsius', 'first_segment_latency',
        'resource_limits_enforced', 'sustained_encode_duration', 'sustained_encode_stability',
        'worker_interruption_idempotent_recovery',
    },
    "POC-03": {
        'ats_slice_behavior', 'cache_disk_observation', 'cache_hit_observation',
        'cache_key_isolation', 'etag_semantics', 'if_range_semantics',
        'large_file_streaming', 'origin_interruption_recovery', 'partial_cache_integrity',
        'range_cold_cache_latency', 'range_correctness', 'range_hot_cache_latency',
        'range_multi_user_latency', 'range_slow_origin_latency', 'source_update_invalidation',
    },
    "POC-04": {
        'cache_eviction_preserves_authoritative_state', 'concurrent_workload_stability', 'disconnect_recovery',
        'failure_recovery', 'free_space_floor_preserved', 'hash_mismatch_replica_rejected',
        'incomplete_replica_rejected', 'io_latency', 'iscsi_transport_ready',
        'minimum_free_space_gib', 'replica_migration_preserves_old_valid_copy', 'sequential_throughput',
        'snapshot_restore', 'watermark_behavior',
    },
    "POC-05": {
        'average_file_size', 'directory_count', 'directory_depth_max',
        'enumeration_rate', 'etag_behavior_profiled', 'file_count',
        'filename_characteristics_profiled', 'incremental_scan_cost', 'memory_peak',
        'provider_characteristics_profiled', 'range_support_profiled', 'source_api_quota',
        'source_change_frequency',
    },
    "POC-06": {
        'auth_flow_supported', 'duplicate_objects_prevented', 'interrupted_sync_resume_or_idempotent_rerun',
        'license_review_approved', 'listing_stability', 'maintainability',
        'network_failure_classified_retried', 'privacy_review_approved', 'rate_limit_429_classified_retried',
        'source_deletion_preserves_logical_asset', 'upstream_5xx_classified_retried',
    },
    "POC-07": {
        'cross_user_cache_isolation', 'ddns_propagation', 'expired_authorization_denied',
        'high_port_route', 'ipv6_reachability', 'public_large_file_streaming',
        'range_through_path', 'rate_limit_enforced', 'tls_valid',
        'unauthorized_identity_denied',
    },
    "POC-08": {
        'bundle_baseline', 'decision_table_equivalent', 'design_token_equivalent',
        'dynamic_form_equivalent', 'flowchart_equivalent', 'maintainability_score',
        'million_row_virtual_list_equivalent', 'mobile_experience_equivalent', 'monitoring_view_equivalent',
        'permission_model_equivalent', 'player_integration_equivalent', 'prototype_coverage',
        'sse_websocket_equivalent',
    },
    "POC-09": {
        'asr_cer', 'asr_wer', 'asset_acl_gate',
        'caller_permission_gate', 'concurrency_quota_gate', 'cost_estimate',
        'factual_consistency', 'fixed_query_set_bound', 'hard_budget_gate',
        'license_privacy_pass', 'multimodal_correction_accuracy', 'ocr_accuracy',
        'provider_budget_limit', 'provider_concurrency_limit', 'provider_request_rate_limit',
        'quality_score', 'quality_strata_coverage', 'query_latency',
        'request_quota_gate', 'retrieval_mrr', 'retrieval_ndcg',
        'retrieval_recall', 'speaker_der', 'tag_f1',
        'throughput', 'thumbnail_human_selection_rate', 'translation_bleu',
        'translation_comet',
    },
    "POC-10": {
        'ai_manual_revisions_restore', 'assets_restore', 'audit_restore',
        'authoritative_relationships_restore', 'core_browsing_recovery_time', 'db_restore',
        'file_restore', 'formal_replicas_restore', 'image_signature_restore',
        'outbox_restore', 'playback_recovery_time', 'playback_restore',
        'retention_restore', 'rpo_observed', 'rto_observed',
        'search_index_consistency_restore', 'secret_store_restore', 'secret_unreadable_failure_detected',
        'secret_value_roundtrip', 'service_recovery_time', 'source_mappings_restore',
        'tasks_restore', 'users_permissions_restore', 'vm_recovery_time',
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

PROFILE_SCOPES = {"local-v1": "LOCAL_FULL_V1", "production": "PRODUCTION_RELEASE"}
PROFILE_EVIDENCE_BINDING = {
    'revision':1,'legacyResultIndexPurpose':'TASK_PROGRESS_ONLY_NOT_PROFILE_ACCEPTANCE',
    'localOwner':'POC_TASK','productionOwner':'GZ-020',
    'localIndexPattern':'evidence/{pocTaskId}/profiles/local-v1/v1/index.yaml',
    'productionIndexPattern':'evidence/GZ-020/poc/{pocTaskId}/production/v1/index.yaml',
    'indexSchema':'program.schema.yaml#/$defs/profileEvidenceIndex',
    'productionExecutionSchema':'program.schema.yaml#/$defs/productionExecution',
    'productionResultSchema':'program.schema.yaml#/$defs/productionResult',
    'productionSampleApprovalSchema':'program.schema.yaml#/$defs/productionSampleApproval',
    'productionComplianceSchema':'program.schema.yaml#/$defs/productionComplianceReview',
    'resourceConfigurationSchema':'program.schema.yaml#/$defs/resourceConfiguration',
    'resourceBookingSchema':'program.schema.yaml#/$defs/resourceBooking',
    'executionWindowSchema':'program.schema.yaml#/$defs/executionWindow',
    'measurementDomainReviewSchema':'program.schema.yaml#/$defs/measurementDomainReview',
    'testedSourceSchema':'program.schema.yaml#/$defs/testedSource',
}
LOCAL_REQUIRED_MEASUREMENTS = {
    **REQUIRED_MEASUREMENTS,
    "POC-01": {
        "worker_capabilities_reproducible", "worker_resource_limits_enforced",
        "worker_restart_recovery", "worker_physical_scope_recorded",
        "worker_network_boundary_enforced",
    },
    "POC-02": (REQUIRED_MEASUREMENTS["POC-02"] - {
        "a380_range_first_byte_latency", "encoder_power_peak_watts",
        "encoder_temperature_peak_celsius",
    }) | {
        "parallel_av1_concat_decodes", "hls_ready_only_contiguous",
        "attempt_fencing_single_publish", "playback_priority_reserved_capacity",
        "seek_epoch_rejects_stale_demand", "hls_acl_and_revocation",
    },
    "POC-04": (REQUIRED_MEASUREMENTS["POC-04"] - {
        "iscsi_transport_ready", "minimum_free_space_gib", "free_space_floor_preserved",
        "disconnect_recovery", "snapshot_restore",
    }) | {
        "local_capacity_reservations_preserved", "openlist_disconnect_recovery",
        "local_backup_restore_verified",
        "local_authenticated_reads", "local_range_correctness", "local_read_hash_verified",
    },
    "POC-06": REQUIRED_MEASUREMENTS["POC-06"] | {"generic_source_scope_verified"},
    "POC-07": (REQUIRED_MEASUREMENTS["POC-07"] - {
        "ipv6_reachability", "high_port_route", "ddns_propagation",
        "range_through_path", "public_large_file_streaming",
    }) | {"local_range_through_path", "local_large_file_streaming", "local_direct_origin_denied"},
}
LOCAL_RESOURCES = {
    "POC-01": {"RES-HETEROGENEOUS-WORKERS"},
    "POC-02": {"RES-HETEROGENEOUS-WORKERS", "RES-OPENLIST-LOCAL"},
    "POC-03": {"RES-ATS-SANDBOX"},
    "POC-04": {"RES-OPENLIST-LOCAL"},
    "POC-05": {"RES-METADATA-SCALE", "RES-OPENLIST-LOCAL"},
    "POC-06": {"RES-OPENLIST-LOCAL"},
    "POC-07": {"RES-LOCAL-ACCESS-PATH", "RES-OPENLIST-LOCAL"},
}

REQUIRED_LOCAL_ENV = {
    "POC-01": {"worker_node_inventory", "physical_host_scope", "encoder_capability_matrix", "android_validation_scope", "vm_validation_scope"},
    "POC-02": {"worker_node_inventory", "physical_host_scope", "encoder_capability_matrix", "segment_profile", "scheduler_configuration"},
    "POC-03": set(),
    "POC-04": {"openlist_version", "sandbox_root_boundary", "capacity_watermark_configuration"},
    "POC-05": {"openlist_version", "synthetic_hierarchy_manifest"},
    "POC-06": {"openlist_version", "source_validation_scope", "injected_failure_matrix"},
    "POC-07": {"local_tls_path_configuration", "openlist_version"},
}

LOCAL_BOOLEAN_GATES = {
    "POC-01": LOCAL_REQUIRED_MEASUREMENTS["POC-01"],
    "POC-02": LOCAL_REQUIRED_MEASUREMENTS["POC-02"] - {
        "av1_quality", "encode_throughput", "first_segment_latency", "sustained_encode_duration",
    },
    "POC-03": LOCAL_REQUIRED_MEASUREMENTS["POC-03"] - {
        "range_correctness", "range_cold_cache_latency", "range_hot_cache_latency",
        "range_multi_user_latency", "range_slow_origin_latency",
    },
    "POC-04": LOCAL_REQUIRED_MEASUREMENTS["POC-04"] - {"sequential_throughput", "io_latency"},
    "POC-05": {"filename_characteristics_profiled", "provider_characteristics_profiled",
               "range_support_profiled", "etag_behavior_profiled"},
    "POC-06": LOCAL_REQUIRED_MEASUREMENTS["POC-06"] - {"maintainability"},
    "POC-07": LOCAL_REQUIRED_MEASUREMENTS["POC-07"],
}
LOCAL_REQUIRED_MEASUREMENTS["POC-04"] = LOCAL_REQUIRED_MEASUREMENTS["POC-04"] | {
    "local_minimum_free_bytes", "local_maximum_reserved_bytes",
}

PRODUCTION_COMPAT_MEASUREMENTS = {
    'POC-01': LOCAL_BOOLEAN_GATES['POC-01'] | {'android_thermal_background_profiled'},
    'POC-02': {'parallel_av1_concat_decodes','hls_ready_only_contiguous',
               'attempt_fencing_single_publish','playback_priority_reserved_capacity',
               'seek_epoch_rejects_stale_demand','hls_acl_and_revocation'},
}
PRODUCTION_COMPAT_ENV = {
    'POC-01': (REQUIRED_LOCAL_ENV['POC-01'] - {'vm_validation_scope'}) | {'android_thermal_background_observation'},
    'POC-02': REQUIRED_LOCAL_ENV['POC-02'],
}


def execution_route(plan: dict[str, Any], profile: str) -> dict[str, Any]:
    """Production remains the original plan; only authorized local routes differ."""
    if profile == "local-v1" and isinstance(plan.get("localValidation"), dict):
        return plan["localValidation"]
    return {
        "mode": "required", "resourceIds": plan.get("resourceIds") or [],
        "captureBeforeExecution": (plan.get("environment") or {}).get("captureBeforeExecution") or [],
        "protocol": plan.get("protocol") or {},
    }


def profile_identity(profile: str) -> dict[str, Any]:
    return {"id": profile, "version": 1, "bindingRevision": 1,
            "scope": PROFILE_SCOPES[profile]}


def validate_local_route(plan, resource_map, protocol_schema, errors):
    poc_id = plan.get("pocId")
    local = plan.get("localValidation")
    label = f"{plan.get('taskId')}: local-v1"
    if poc_id not in LOCAL_RESOURCES:
        if local is not None or plan.get("schemaVersion") != 1:
            errors.append(f"{label}: unchanged shared POC must retain schemaVersion 1 and original protocol")
        return
    if not isinstance(local, dict) or plan.get("schemaVersion") != 2:
        errors.append(f"{label}: revised POC requires schemaVersion 2 and localValidation")
        return
    expected_mode = "required"
    if local.get("mode") != expected_mode or local.get("profileVersion") != 1:
        errors.append(f"{label}: mode/version does not match authorized route")
    ids = local.get("resourceIds") or []
    if set(ids) != LOCAL_RESOURCES[poc_id] or len(ids) != len(set(ids)):
        errors.append(f"{label}: resource IDs must match authorized local route")
    for resource_id in ids:
        if resource_id not in resource_map:
            errors.append(f"{label}: unknown resource {resource_id}")
    protocol = local.get("protocol")
    validate_schema(protocol, protocol_schema, label + "/protocol", errors)
    if not isinstance(protocol, dict):
        return
    # The original frozen measurement obligations are still checked separately.
    measurements = protocol.get("measurements") or []
    measurement_ids = [m.get("id") for m in measurements if isinstance(m, dict)]
    if len(measurement_ids) != len(set(measurement_ids)):
        errors.append(f"{label}: measurement IDs must be unique")
    missing = LOCAL_REQUIRED_MEASUREMENTS[poc_id] - set(measurement_ids)
    if missing:
        errors.append(f"{label}: missing required local measurements {sorted(missing)}")
    for measurement in measurements:
        if measurement.get("id") in LOCAL_BOOLEAN_GATES[poc_id] and measurement.get("unit") != "boolean":
            errors.append(f"{label}: safety gate {measurement.get('id')} unit must remain boolean")
        if measurement.get("id") in {"local_minimum_free_bytes", "local_maximum_reserved_bytes"} and measurement.get("unit") != "bytes":
            errors.append(f"{label}: capacity measurement unit must remain bytes")
    if protocol.get("commands") or protocol.get("rawOutputRefs") or any(m.get("actual") is not None for m in measurements):
        errors.append(f"{label}: canonical local protocol must not contain execution evidence")
    capture = set(local.get("captureBeforeExecution") or [])
    if not set(plan["environment"]["captureBeforeExecution"]).issubset(capture):
        errors.append(f"{label}: local route must retain common environment capture")
    missing_capture = REQUIRED_LOCAL_ENV[poc_id] - capture
    if missing_capture:
        errors.append(f"{label}: missing required local environment fields {sorted(missing_capture)}")


def validate_execution_profile(root, plan, execution, errors, reference_prefix=None):
    environment = execution.get("environmentCaptured") or {}
    identity = environment.get("acceptanceProfile") if isinstance(environment, dict) else None
    profile = identity.get("id") if isinstance(identity, dict) else None
    label = f"execution record {plan['taskId']}"
    if not isinstance(profile, str) or profile not in PROFILE_SCOPES:
        errors.append(f"{label}: known acceptanceProfile is required")
        profile = "production"  # Continue original strict checks after reporting the error.
    expected = profile_identity(profile)
    if identity != expected or not isinstance(identity, dict) or any(type(identity.get(k)) is not int for k in ("version", "bindingRevision")):
        errors.append(f"{label}: acceptanceProfile version/revision/scope must equal {expected!r}")
    route = execution_route(plan, profile)
    if route.get("mode") != "required":
        errors.append(f"{label}: deferred local route cannot produce a terminal result or PASS")
    config_path = existing_ref(root, environment.get("acceptanceProfileConfigurationRef"), reference_prefix or plan['evidencePath'])
    configuration = None
    if config_path is None:
        errors.append(f"{label}: acceptanceProfileConfigurationRef must exist under task Evidence")
    else:
        try:
            configuration = load(config_path)
            secret_scan(configuration, f"{label}/profile configuration", errors)
            configured_identity = configuration.get('acceptanceProfile') if isinstance(configuration, dict) else None
            if not isinstance(configured_identity, dict) or any(type(configured_identity.get(k)) is not int for k in ('version', 'bindingRevision')):
                errors.append(f"{label}: profile configuration version/revision must be integers")
            expected_configuration = {
                "pocId": plan['pocId'], "taskId": plan['taskId'], "acceptanceProfile": expected,
                "resourceIds": sorted(route.get("resourceIds") or []),
                "measurementIds": sorted(m['id'] for m in (route.get("protocol") or {}).get("measurements", [])),
            }
            if plan['pocId'] == 'POC-06':
                expected_configuration['sourceValidationScope'] = (
                    'GENERIC_OPENLIST_SANDBOX' if profile == 'local-v1' else 'BAIDU_PRODUCTION_SANDBOX'
                )
                if environment.get('source_validation_scope') != expected_configuration['sourceValidationScope']:
                    errors.append(f"{label}: source_validation_scope must match selected generic/production route")
            if not isinstance(configuration, dict) or any(configuration.get(k) != v for k, v in expected_configuration.items()):
                errors.append(f"{label}: profile configuration must bind the exact task, profile, resources and measurements")
        except Exception as exc:
            errors.append(f"{label}: cannot parse profile configuration: {exc}")
    return route, configuration


def validate_local_capacity(plan, execution, configuration, status, errors):
    if plan['pocId'] != 'POC-04' or execution.get('environmentCaptured', {}).get('acceptanceProfile') != profile_identity('local-v1'):
        return
    label = f"execution record {plan['taskId']}: local capacity"
    capacity = configuration.get('localCapacity') if isinstance(configuration, dict) else None
    fields = {'capacityBytes', 'safetyFloorBytes', 'pauseFreeBytes', 'resumeFreeBytes', 'maxReservedBytes'}
    if not isinstance(capacity, dict) or set(capacity) != fields or any(type(capacity.get(k)) is not int for k in fields):
        errors.append(f"{label}: localCapacity requires exact integer byte configuration")
        return
    total, floor, pause, resume, reservation = (capacity[k] for k in ('capacityBytes', 'safetyFloorBytes', 'pauseFreeBytes', 'resumeFreeBytes', 'maxReservedBytes'))
    if not (0 < floor < pause < resume <= total and 0 < reservation <= total - floor):
        errors.append(f"{label}: positive floor and ordered free-space watermarks/reservation budget required")
    environment = execution.get('environmentCaptured') or {}
    observed_configuration = environment.get('capacity_watermark_configuration')
    if observed_configuration != capacity or not isinstance(observed_configuration, dict) or any(type(observed_configuration.get(k)) is not int for k in fields):
        errors.append(f"{label}: environment capacity configuration must match profile configuration")
    actual = {m.get('id'): m.get('actual') for m in execution.get('measurements') or []}
    minimum, reserved = (actual.get(k) for k in ('local_minimum_free_bytes', 'local_maximum_reserved_bytes'))
    if type(minimum) is not int or type(reserved) is not int or not (0 <= minimum <= total and 0 <= reserved <= reservation):
        errors.append(f"{label}: measured free/reserved bytes must be bounded integers")
    elif status == 'pass' and (reserved <= 0 or minimum - reserved < floor):
        errors.append(f"{label}: PASS requires positive observed reservations and measured free bytes minus maximum reservations to preserve floor")


def compliance_subject_version(plan, execution):
    environment = execution.get('environmentCaptured') or {}
    if plan['pocId'] == 'POC-06' and (environment.get('acceptanceProfile') or {}).get('id') == 'local-v1':
        return json.dumps({key: environment.get(key) for key in ('openlist_version', 'provider_api_or_sdk_version')}, sort_keys=True, separators=(',', ':'))
    if plan['pocId'] == 'POC-09':
        return json.dumps({key: environment.get(key) for key in ('model_identity', 'model_version', 'runtime', 'tool_versions', 'prompt_template_version', 'inference_parameters', 'input_sample_version')}, sort_keys=True, separators=(',', ':'))
    key = {'POC-06':'provider_api_or_sdk_version','POC-09':'model_version'}.get(plan['pocId'],'tool_versions')
    value = environment.get(key)
    return json.dumps(value,sort_keys=True,separators=(',',':')) if isinstance(value,dict) else value


def validate_source_compliance(root, plan, execution, implementer, status, errors, schema_override=None, reference_prefix=None, execution_window=None):
    """Declared approval booleans cannot substitute for version-bound review records."""
    required = {kind for kind in ('privacy','license') if plan['security'].get(kind+'ReviewRequired') is True}
    if not required:
        return
    label = f"execution record {plan['taskId']}: compliance"
    environment = execution.get('environmentCaptured') or {}
    if plan['pocId'] == 'POC-09':
        for key in ('runtime','tool_versions'):
            if not isinstance(environment.get(key), (str,dict)) or not recorded(environment.get(key)):
                errors.append(f'{label}: concrete captured AI runtime/tool identity required')
    version = compliance_subject_version(plan,execution)
    profile = (environment.get('acceptanceProfile') or {}).get('id')
    scope = ('GENERIC_OPENLIST_SANDBOX' if profile == 'local-v1' else 'BAIDU_PRODUCTION_SANDBOX') if plan['pocId']=='POC-06' else PROFILE_SCOPES.get(profile)
    reviews = execution.get('complianceReviews') or []
    kinds = [r.get('type') for r in reviews if isinstance(r, dict)]
    if len(kinds) != len(set(kinds)):
        errors.append(f"{label}: review types must be unique")
    if status == 'pass' and not required.issubset(set(kinds)):
        errors.append(f"{label}: PASS requires privacy/license review references")
    schema = schema_override or load(root/'specs/poc/compliance-review.schema.yaml')
    for review in reviews:
        if not isinstance(review, dict):
            continue
        if review.get('subjectVersion') != version or not recorded_text(version):
            errors.append(f"{label}: review subjectVersion must bind exact captured API/tool version")
        path = existing_ref(root, review.get('reviewRef'), reference_prefix or plan['evidencePath'])
        if path is None:
            errors.append(f"{label}: reviewRef must exist under task Evidence")
            continue
        try:
            record = load(path)
        except Exception as exc:
            errors.append(f"{label}: cannot read review: {exc}")
            continue
        validate_schema(record, schema, label+'/review', errors)
        secret_scan(record, label+'/review', errors)
        expected = dict(pocId=plan['pocId'], taskId=plan['taskId'], type=review.get('type'),
                        subjectVersion=version, decision='approved', scope=scope)
        if not isinstance(record, dict) or any(record.get(k) != v for k,v in expected.items()):
            errors.append(f"{label}: review must bind exact task, type, version, approved decision and source scope")
            continue
        if not recorded_text(record.get('reviewer')) or record.get('reviewer') == implementer:
            errors.append(f"{label}: review requires a concrete independent reviewer")
        if not valid_utc_timestamp(record.get('approvedAt')):
            errors.append(f"{label}: review approvedAt must be valid UTC")
        elif execution_window and utc(record['approvedAt']) > execution_window[0]:
            errors.append(f'{label}: privacy/license approval must precede execution')


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if valid_utc_timestamp(value) else None


def qualified_window(execution, schema, label, errors):
    window = (execution.get('environmentCaptured') or {}).get('executionWindow')
    validate_schema(window, schema, label+'/executionWindow', errors)
    if not isinstance(window, dict):
        errors.append(f'{label}: qualified executionWindow is required')
        return None
    start, end = utc(window.get('startedAt')), utc(window.get('finishedAt'))
    if start is None or end is None or not start < end:
        errors.append(f'{label}: executionWindow requires ordered valid UTC instants')
        return None
    return start, end


def qualified_record(root, ref, prefix, schema, expected, label, errors):
    path = existing_ref(root, ref, prefix)
    if path is None:
        errors.append(f'{label}: record must exist inside the selected profile slot')
        return None
    try:
        record = load(path)
    except Exception as exc:
        errors.append(f'{label}: cannot parse record: {exc}')
        return None
    validate_schema(record, schema, label, errors)
    secret_scan(record, label, errors)
    if not isinstance(record, dict) or any(json.dumps(record.get(k),sort_keys=True,separators=(',',':')) != json.dumps(v,sort_keys=True,separators=(',',':')) for k,v in expected.items()):
        errors.append(f'{label}: record must bind exact POC, owner, resource/metric and profile')
        return None
    return record


def validate_qualified_source(root, plan, execution, configuration, defs, prefix, errors):
    label = f"qualified tested source {plan['taskId']}"
    source = (execution.get('environmentCaptured') or {}).get('testedSource')
    validate_schema(source, defs.get('testedSource', {}), label, errors)
    configured = configuration.get('testedSource') if isinstance(configuration, dict) else None
    if not isinstance(source, dict) or json.dumps(source, sort_keys=True) != json.dumps(configured, sort_keys=True):
        errors.append(f'{label}: execution and profile configuration must bind the same immutable testedSource')
        return
    commit, tree = source.get('commit'), source.get('tree')
    if not all(isinstance(v,str) and re.fullmatch('[0-9a-f]{40}',v) for v in (commit,tree)):
        errors.append(f'{label}: exact Git commit/tree object IDs are required')
        return
    def git(*args):
        output = subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8',stderr=subprocess.PIPE)
        return output if args[0] == 'show' and len(args) == 2 else output.strip()
    try:
        context = git('rev-parse','HEAD')
        if git('cat-file','-t',commit) != 'commit' or git('cat-file','-t',tree) != 'tree':
            raise ValueError('testedSource must identify a commit object and its tree object')
        if git('show','-s','--format=%T',commit) != tree:
            raise ValueError('tested commit does not have the recorded tree')
        git('merge-base','--is-ancestor',commit,context)
        changed = git('diff','--name-only',commit,context).splitlines()
        dirty = git('diff','--name-only','HEAD').splitlines()
        untracked = git('ls-files','--others','--exclude-standard').splitlines()
        poc_task = f"POC-{int(plan['pocId'].split('-')[-1]):03d}"
        own_prefixes = tuple(str(Path(profile_index_ref(poc_task,profile)).parent).replace('\\','/')+'/'
                             for profile in PROFILE_SCOPES)
        phase_paths = {f'specs/tasks/{owner}.md' for owner in (poc_task,'GZ-020')}
        def phase_only(before, after):
            # Authenticate the existing document, permitting only the terminal status transition.
            pattern = r'\A(---\r?\n(?:(?!^---).)*?^status: )in_progress(\r?\n(?:(?!^---).)*?^---(?:\r?\n|\Z).*)\Z'
            match = re.fullmatch(pattern,before,re.MULTILINE|re.DOTALL)
            header = before.split('---',2)[1] if before.startswith('---') else ''
            return (match is not None and len(re.findall(r'^status:',header,re.MULTILINE)) == 1
                    and after == match[1]+'completed'+match[2])
        for paths, before_ref, after_ref in ((changed,commit,context),(dirty,context,None)):
            for path in paths:
                if path.startswith(own_prefixes):
                    continue
                if path in phase_paths:
                    before = git('show',f'{before_ref}:{path}')
                    after = git('show',f'{after_ref}:{path}') if after_ref else (root/path).read_text(encoding='utf-8')
                    if phase_only(before,after):
                        continue
                raise ValueError('current validation context changes non-Own-Evidence source content')
        if any(not path.startswith(own_prefixes) for path in untracked):
            raise ValueError('current validation context contains untracked non-Own-Evidence source content')
    except (subprocess.CalledProcessError,ValueError,OSError) as exc:
        errors.append(f'{label}: immutable source must match actual Git objects and current validation context: {exc}')


def validate_qualified_resources(root, plan, execution, resource_catalog, defs, prefix, reviewer, status, window, errors):
    identity = (execution.get('environmentCaptured') or {}).get('acceptanceProfile')
    for resource in execution.get('resources') or []:
        if not isinstance(resource, dict):
            continue
        rid = resource.get('id')
        common = dict(schemaVersion=2, pocId=plan['pocId'], taskId=plan['taskId'], resourceId=rid, acceptanceProfile=identity)
        for field, kind, definition in (('configurationRef','resource_configuration','resourceConfiguration'), ('bookingRef','resource_booking','resourceBooking')):
            if field == 'bookingRef' and resource.get(field) is None and not resource_catalog.get(rid, {}).get('bookingRequired'):
                continue
            label = f"qualified resource {plan['taskId']}/{rid}/{kind}"
            record = qualified_record(root, resource.get(field), prefix, defs.get(definition, {}), {**common, 'kind':kind}, label, errors)
            if record is None:
                continue
            approved, first, last = (utc(record.get(k)) for k in ('approvedAt','validFrom','validUntil'))
            if approved is None or first is None or last is None or first >= last:
                errors.append(f'{label}: valid approval and resource validity UTC instants are required')
            elif status == 'pass' and window and not (approved <= window[0] and first <= window[0] and window[1] <= last):
                errors.append(f'{label}: approval must precede and validity must cover the captured executionWindow')
            if status == 'pass' and (record.get('status') != 'approved' or record.get('approvedBy') != reviewer or not recorded_text(reviewer)):
                errors.append(f'{label}: PASS requires approved independent Task reviewer authorization')
            if field == 'configurationRef' and not recorded(record.get('configuration')):
                errors.append(f'{label}: configuration must be a nonempty captured record')


def validate_qualified_domains(root, plan, execution, route, configuration, defs, prefix, reviewer, window, errors):
    known = NONNEGATIVE_UNITS | {'boolean','percent','ratio','celsius'}
    required = {m['id']:m for m in route['protocol']['measurements'] if m['unit'] not in known}
    refs = configuration.get('numericDomainReviewRefs', {}) if isinstance(configuration, dict) else {}
    if not isinstance(refs, dict) or set(refs) != set(required):
        errors.append(f"qualified domains {plan['taskId']}: exact model/rubric-specific domain review references required")
        return
    env = execution.get('environmentCaptured') or {}
    captured = {key:env.get(key) for key in route['captureBeforeExecution']}
    actual = {m.get('id'):m.get('actual') for m in execution.get('measurements') or []}
    for mid, measurement in required.items():
        label = f"qualified domain {plan['taskId']}/{mid}"
        expected = dict(schemaVersion=2, kind='measurement_domain_review', pocId=plan['pocId'], taskId=plan['taskId'],
                        acceptanceProfile=env.get('acceptanceProfile'), measurementId=mid, unit=measurement['unit'], environmentCaptured=captured)
        record = qualified_record(root, refs[mid], prefix, defs.get('measurementDomainReview', {}), expected, label, errors)
        if record is None:
            continue
        if record.get('decision') != 'approved' or record.get('reviewer') != reviewer or not recorded_text(reviewer):
            errors.append(f'{label}: independent Task reviewer approval required')
        approved = utc(record.get('approvedAt'))
        if approved is None or (window and approved > window[0]):
            errors.append(f'{label}: domain approval must precede the captured executionWindow')
        if existing_ref(root, record.get('definitionRef'), prefix) is None:
            errors.append(f'{label}: reviewed scale definition must exist inside selected slot')
        domain = record.get('domain') or {}
        if not isinstance(domain, dict):
            errors.append(f'{label}: numeric domain must be a structured record')
            continue
        lower, upper = domain.get('minimum'), domain.get('maximum')
        bounded = domain.get('mode') == 'bounded'
        if bounded:
            if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(float(v)) for v in (lower,upper)) or lower > upper:
                errors.append(f'{label}: bounded scale requires finite ordered numeric limits')
                continue
        elif domain.get('mode') != 'finite' or lower is not None or upper is not None:
            errors.append(f'{label}: unbounded model scale must explicitly declare finite mode and null limits')
            continue
        value = actual.get(mid)
        if not good_actual(measurement['unit'], value, mid) or (bounded and not lower <= value <= upper) or (domain.get('integral') is True and value != int(value)):
            errors.append(f'{label}: actual value violates approved numeric domain')


def validate_android_execution(root, plan, execution, status, prefix, errors):
    if plan['pocId'] != 'POC-01' or status != 'pass':
        return
    env = execution.get('environmentCaptured') or {}
    if env.get('acceptanceProfile') == profile_identity('local-v1'):
        scope = env.get('vm_validation_scope')
        label = f"execution record {plan['taskId']}: actual VM"
        if not isinstance(scope, dict) or scope.get('status') != 'VALIDATED_ON_VM':
            errors.append(f'{label}: PASS requires captured VM encoding, never an untested marker')
            return
        for key in ('nodeId','guestId','physicalHostId','encoderBuild','hypervisor','guestOs'):
            if not recorded_text(scope.get(key)):
                errors.append(f'{label}: concrete {key} required')
        if scope.get('guestOs') != 'android':
            errors.append(f'{label}: Android guest encoding required for virtual phone validation')
        inventory = env.get('worker_node_inventory')
        match = any(isinstance(node,dict) and node.get('platform') == 'android' and node.get('isEmulator') is True and node.get('isVirtualMachine') is True and all(node.get(k) == scope.get(k) for k in ('nodeId','guestId','physicalHostId','encoderBuild','hypervisor','guestOs')) for node in inventory) if isinstance(inventory,list) else False
        if scope.get('isVirtualMachine') is not True or scope.get('physicalMultiHostValidated') is not False or not match:
            errors.append(f'{label}: tested VM must match inventory and disclose same-host limits')
        approved_inputs = {sample.get('checksum') for sample in execution.get('samples') or []}
        ref = scope.get('rawOutputRef')
        if scope.get('inputSha256') not in approved_inputs or not good_checksum(scope.get('outputSha256')) or ref not in (execution.get('rawOutputRefs') or []) or existing_ref(root,ref,prefix) is None:
            errors.append(f'{label}: actual encode must bind approved input, output hashes and raw evidence')
        if env.get('android_validation_scope') != 'ANDROID_DEVICE_NOT_TESTED':
            errors.append(f'{label}: VM-only local profile must declare physical Android untested')
        return
    scope, observation = env.get('android_validation_scope'), env.get('android_thermal_background_observation')
    label = f"execution record {plan['taskId']}: actual Android"
    if not isinstance(scope, dict) or scope.get('status') != 'VALIDATED_ON_DEVICE' or not isinstance(observation, dict):
        errors.append(f'{label}: PASS requires structured actual device validation, never an untested marker')
        return
    for key in ('nodeId','deviceId','physicalHostId','encoderBuild'):
        if not recorded_text(scope.get(key)):
            errors.append(f'{label}: concrete {key} required')
    inventory = env.get('worker_node_inventory')
    match = any(isinstance(node,dict) and node.get('platform') == 'android' and node.get('isEmulator') is False and all(node.get(k) == scope.get(k) for k in ('nodeId','deviceId','physicalHostId','encoderBuild')) for node in inventory) if isinstance(inventory,list) else False
    if scope.get('isEmulator') is not False or not match:
        errors.append(f'{label}: tested physical Android node must match captured worker inventory')
    approved_inputs = {sample.get('checksum') for sample in execution.get('samples') or []}
    if scope.get('inputSha256') not in approved_inputs or not good_checksum(scope.get('outputSha256')):
        errors.append(f'{label}: actual encode must bind approved input and output hashes')
    if observation.get('deviceId') != scope.get('deviceId'):
        errors.append(f'{label}: thermal/background observation must bind exact tested device')
    for record in (scope, observation):
        ref = record.get('rawOutputRef')
        if ref not in (execution.get('rawOutputRefs') or []) or existing_ref(root,ref,prefix) is None:
            errors.append(f'{label}: device and observation raw evidence must bind execution outputs')
    temp, power = observation.get('temperaturePeakCelsius'), observation.get('powerPeakWatts')
    duration, survived = observation.get('testDurationSeconds'), observation.get('backgroundSurvivedSeconds')
    if not good_actual('celsius', temp) or not good_actual('W', power) or not good_actual('s', duration) or not good_actual('s', survived) or duration <= 0 or survived < duration:
        errors.append(f'{label}: valid thermal/power observations and positive completed background interval required')


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of overwriting them."""


def _construct_unique_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
):
    explicit: set[Any] = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=False)
        try:
            duplicate = key in explicit
            explicit.add(key)
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
    loader.flatten_mapping(node)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


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


COUNT_UNITS = {'files', 'directories', 'levels', 'requests', 'streams'}
NONNEGATIVE_UNITS = COUNT_UNITS | {'hours', 'minutes', 's', 'ms', 'W', 'MB/s', 'GiB', 'bytes', 'MiB', 'KiB', 'requests_per_minute', 'changes_per_hour', 'objects/s', 'items/s', 'currency', 'currency_per_1000_items'}
BOUNDED_RATIO_METRICS = {'retrieval_recall', 'retrieval_mrr', 'retrieval_ndcg', 'ocr_accuracy', 'factual_consistency', 'tag_f1', 'thumbnail_human_selection_rate', 'multimodal_correction_accuracy'}


def good_actual(unit: Any, value: Any, metric_id: str | None = None) -> bool:
    if str(unit).lower() == "boolean":
        return isinstance(value, bool)
    finite = (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
    if not finite:
        return False
    if unit in COUNT_UNITS:
        return value >= 0 and value == int(value)
    if unit in NONNEGATIVE_UNITS:
        return value >= 0
    if unit == 'percent':
        return 0 <= value <= 100
    if unit == 'ratio':
        return value >= 0 and (metric_id not in BOUNDED_RATIO_METRICS or value <= 1)
    if unit == 'celsius':
        return value >= -273.15
    # Model/rubric-specific scores are bounded by approved qualified scale records.
    return True


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
    reference_prefix: str | None = None,
    execution_window=None,
) -> None:
    evidence = reference_prefix or plan["evidencePath"]
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
    elif execution_window and utc(approval['approvedAt']) > execution_window[0]:
        errors.append(f'{label}: sample approval must precede execution')


def validate_execution(
    root: Path,
    plan: dict[str, Any],
    implementer: str,
    execution: dict[str, Any],
    resource_catalog: dict[str, dict[str, Any]],
    schema: dict[str, Any],
    approval_schema: dict[str, Any],
    status: str,
    errors: list[str],
    compliance_schema: dict[str, Any] | None = None,
    reference_prefix: str | None = None,
    record_definitions: dict[str, Any] | None = None,
    task_reviewer: str | None = None,
) -> None:
    task_id = plan["taskId"]
    poc_id = plan["pocId"]
    evidence = plan["evidencePath"]
    reference_boundary = reference_prefix or evidence
    label = f"execution record {task_id}"
    validate_schema(execution, schema, label, errors)
    secret_scan(execution, label, errors)
    route, profile_configuration = validate_execution_profile(root, plan, execution, errors, reference_boundary)
    window = qualified_window(execution,record_definitions.get('executionWindow',{}),label,errors) if record_definitions is not None else None
    validate_local_capacity(plan, execution, profile_configuration, status, errors)
    validate_source_compliance(root, plan, execution, implementer, status, errors, compliance_schema, reference_boundary, window)
    validate_android_execution(root, plan, execution, status, reference_boundary, errors)
    if record_definitions is not None:
        validate_qualified_source(root,plan,execution,profile_configuration,record_definitions,reference_boundary,errors)
        validate_qualified_resources(root,plan,execution,resource_catalog,record_definitions,reference_boundary,task_reviewer,status,window,errors)
        validate_qualified_domains(root,plan,execution,route,profile_configuration,record_definitions,reference_boundary,task_reviewer,window,errors)
    for key, expected in (
        ("pocId", poc_id),
        ("taskId", task_id),
        ("evidencePath", evidence),
        ("executor", implementer),
    ):
        if execution.get(key) != expected:
            errors.append(f"{label}: {key} must equal {expected!r}")

    resources = execution.get("resources") or []
    resource_ids: list[str] = []
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            errors.append(f"{label}: resource[{index}] must be a structured record")
            continue
        resource_id = resource.get("id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            errors.append(f"{label}: resource[{index}] id must be nonempty text")
            continue
        resource_ids.append(resource_id)
    if len(resource_ids) != len(resources) or len(resource_ids) != len(set(resource_ids)):
        errors.append(f"{label}: resources must contain unique structured records")
    planned_resource_ids = set(route.get("resourceIds") or [])
    if set(resource_ids) != planned_resource_ids:
        errors.append(f"{label}: resource IDs must exactly match plan")
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        resource_id = resource.get("id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            continue
        definition = resource_catalog.get(resource_id)
        if definition is None:
            errors.append(f"{label}: unknown execution resource {resource_id!r}")
            continue
        configuration_ref = resource.get("configurationRef")
        if existing_ref(root, configuration_ref, reference_boundary) is None:
            errors.append(
                f"{label}: resource {resource_id} configurationRef must point to an existing file under {reference_boundary}"
            )
        booking_ref = resource.get("bookingRef")
        if definition.get("bookingRequired") is True:
            if existing_ref(root, booking_ref, reference_boundary) is None:
                errors.append(
                    f"{label}: resource {resource_id} bookingRef must point to an existing file under {reference_boundary}"
                )
        elif booking_ref is not None and existing_ref(root, booking_ref, reference_boundary) is None:
            errors.append(
                f"{label}: resource {resource_id} bookingRef must be null or an existing file under {reference_boundary}"
            )

    environment = execution.get("environmentCaptured") or {}
    required_environment = set(route.get("captureBeforeExecution") or [])
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

    raw_refs = execution.get("rawOutputRefs") or []
    if not raw_refs:
        errors.append(f"{label}: at least one raw output reference is required")
    for ref in raw_refs:
        if existing_ref(root, ref, reference_boundary) is None:
            errors.append(f"{label}: raw evidence file must exist under {reference_boundary}: {ref!r}")

    commands = execution.get("commands") or []
    if not commands:
        errors.append(f"{label}: at least one structured command record is required")
    for index, command in enumerate(commands):
        command_label = f"{label}: command[{index}]"
        if not isinstance(command, dict):
            errors.append(f"{command_label} must be a structured record")
            continue
        if not recorded_text(command.get("command")):
            errors.append(f"{command_label} command must be nonempty/non-placeholder")
        expected_codes = command.get("expectedExitCodes")
        if (
            not isinstance(expected_codes, list)
            or not expected_codes
            or any(
                not isinstance(code, int) or isinstance(code, bool)
                for code in expected_codes
            )
        ):
            errors.append(f"{command_label} expectedExitCodes must contain integers")
        exit_code = command.get("exitCode")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            errors.append(f"{command_label} exitCode must be an integer")
        elif isinstance(expected_codes, list) and exit_code not in expected_codes:
            errors.append(f"{command_label} exitCode must be one of expectedExitCodes")
        output_ref = command.get("outputRef")
        if output_ref not in raw_refs:
            errors.append(f"{command_label} outputRef must be listed in rawOutputRefs")
        if existing_ref(root, output_ref, reference_boundary) is None:
            errors.append(
                f"{command_label} outputRef must point to an existing file under {reference_boundary}"
            )

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
        validate_approval_record(root, plan, implementer, sample, approval_schema, errors, reference_boundary, window)

    planned_measurements = {
        item["id"]: item for item in (route.get("protocol") or {}).get("measurements", [])
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
        and not good_actual(definition.get("unit"), actual_map[measurement_id], measurement_id)
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
    if poc_id == 'POC-03':
        correctness = actual_map.get('range_correctness')
        if planned_measurements.get('range_correctness', {}).get('unit') != 'percent':
            errors.append(f"{label}: Range correctness unit must remain percent")
        if isinstance(correctness, bool) or not isinstance(correctness, (int,float)) or not math.isfinite(correctness) or not 0 <= correctness <= 100:
            errors.append(f"{label}: Range correctness must be a finite percentage in [0,100]")
        elif status == 'pass' and correctness != 100:
            errors.append(f"{label}: PASS requires 100 percent Range byte correctness")

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
    resource_catalog: dict[str, dict[str, Any]],
    result_schema: dict[str, Any],
    execution_schema: dict[str, Any],
    approval_schema: dict[str, Any],
    errors: list[str],
    compliance_schema: dict[str, Any] | None = None,
    reference_prefix: str | None = None,
    record_definitions: dict[str, Any] | None = None,
) -> None:
    task_id = plan["taskId"]
    evidence = plan["evidencePath"]
    reference_boundary = reference_prefix or evidence
    status = entry.get("status")
    label = f"results-index {task_id}"
    roles = concrete_roles(root, task_id, task, errors)
    if roles is None:
        return
    implementer, reviewer = roles

    result_path = existing_ref(root, entry.get("resultRef"), reference_boundary)
    if result_path is None:
        errors.append(
            f"{label}: terminal resultRef must point to an existing file under {reference_boundary}"
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

    execution_path = existing_ref(root, result.get("executionRef"), reference_boundary)
    if execution_path is None:
        errors.append(
            f"result record {task_id}: executionRef must point to an existing file under {reference_boundary}"
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
        root, plan, implementer, execution, resource_catalog,
        execution_schema, approval_schema, status, errors,
        compliance_schema, reference_boundary, record_definitions, reviewer,
    )
    if record_definitions is not None:
        captured_window = (execution.get('environmentCaptured') or {}).get('executionWindow')
        end = utc(captured_window.get('finishedAt')) if isinstance(captured_window,dict) else None
        approval = utc(result.get('approvedAt'))
        if end is not None and (approval is None or approval < end):
            errors.append(f'result record {task_id}: result review must follow completed executionWindow')


def profile_index_ref(poc_task_id: str, profile: str) -> str:
    key = 'localIndexPattern' if profile == 'local-v1' else 'productionIndexPattern'
    return PROFILE_EVIDENCE_BINDING[key].format(pocTaskId=poc_task_id)


def validate_profile_evidence(root, plans, tasks, program_schema, result_schema,
                              execution_schema, approval_schema, resources,
                              selected_profile, require_results, selected_pocs, errors):
    """Qualified slots coexist; production is newly owned by GZ020, never rewritten POC history."""
    defs = program_schema.get('$defs') or {}
    for poc_task_id, plan in plans.items():
        if selected_pocs and plan['pocId'] not in selected_pocs:
            continue
        for profile in PROFILE_SCOPES:
            ref = profile_index_ref(poc_task_id,profile)
            owner = poc_task_id if profile == 'local-v1' else 'GZ-020'
            evidence = 'evidence/'+owner
            index_path = existing_ref(root,ref,evidence)
            label = f"profile evidence {poc_task_id}/{profile}"
            required = require_results and profile == selected_profile
            if index_path is None:
                if required: errors.append(f"{label}: selected profile index is required")
                continue
            try:
                index = load(index_path)
            except Exception as exc:
                errors.append(f"{label}: cannot parse profile index: {exc}")
                continue
            validate_schema(index,defs.get('profileEvidenceIndex',{}),label,errors)
            secret_scan(index,label,errors)
            identity = profile_identity(profile)
            expected = dict(schemaVersion=2,pocId=plan['pocId'],pocTaskId=poc_task_id,
                            ownerTask=owner,acceptanceProfile=identity)
            if not isinstance(index,dict) or any(index.get(k) != v for k,v in expected.items()):
                errors.append(f"{label}: index must bind exact experiment, owner and profile")
                continue
            configured = index.get('acceptanceProfile') or {}
            if any(type(configured.get(k)) is not int for k in ('version','bindingRevision')):
                errors.append(f"{label}: profile versions must be integers")
            prefix = str(Path(ref).parent).replace('\\','/')
            result_path = existing_ref(root,index.get('resultRef'),prefix)
            if result_path is None:
                errors.append(f"{label}: resultRef must exist under the selected profile slot")
                continue
            try:
                result = load(result_path)
            except Exception as exc:
                errors.append(f"{label}: cannot parse profile result: {exc}")
                continue
            if not isinstance(result,dict):
                errors.append(f"{label}: profile result must be a mapping")
                continue
            execution_path = existing_ref(root,result.get('executionRef'),prefix)
            if execution_path is None:
                errors.append(f"{label}: executionRef must exist under the selected profile slot")
                continue
            try:
                execution = load(execution_path)
            except Exception as exc:
                errors.append(f"{label}: cannot parse execution: {exc}")
                continue
            if not isinstance(execution,dict) or (execution.get('environmentCaptured') or {}).get('acceptanceProfile') != identity:
                errors.append(f"{label}: execution must bind selected profile identity")
                continue
            if required and result.get('status') != 'pass':
                errors.append(f"{label}: selected profile requires independently approved PASS")
            projected_plan = copy.deepcopy(plan)
            projected_plan.update(taskId=owner,evidencePath=evidence)
            entry = dict(pocId=plan['pocId'],taskId=owner,evidencePath=evidence,
                         status=result.get('status'),decision=result.get('decision'),
                         resultRef=index.get('resultRef'),reviewer=result.get('reviewer'),
                         approvedAt=result.get('approvedAt'))
            production = profile == 'production'
            validate_terminal(root,projected_plan,tasks[owner],entry,resources,
                defs.get('productionResult',{}) if production else result_schema,
                defs.get('productionExecution',{}) if production else execution_schema,
                defs.get('productionSampleApproval',{}) if production else approval_schema,
                errors,defs.get('productionComplianceReview',{}) if production else None,prefix,defs)


def validate_templates(
    base: Path,
    program: dict[str, Any],
    errors: list[str],
) -> None:
    expected_keys = {
        "executionRecordTemplate": {
            "schemaVersion", "pocId", "taskId", "evidencePath", "executor",
            "resources", "environmentCaptured", "commands", "rawOutputRefs",
            "samples", "measurements", "provenance", "complianceReviews",
            "notes",
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


def validate_repository(root: Path, selected_profile=None, require_results=False,
                        milestone=None, selected_pocs=None) -> list[str]:
    errors: list[str] = []
    if selected_profile is not None and selected_profile not in PROFILE_SCOPES:
        errors.append('unknown selected acceptance profile')
    if milestone is not None:
        expected_profile = {'GZ-018':'local-v1','GZ-020':'production'}.get(milestone)
        if expected_profile is None or selected_profile != expected_profile:
            errors.append('milestone must bind its exact local/production profile')
        if selected_pocs:
            errors.append('full milestone cannot select a POC subset')
        require_results = True
    if require_results and selected_profile not in PROFILE_SCOPES:
        errors.append('qualified results require an explicit known profile')
    if selected_pocs and not set(selected_pocs).issubset(POCS):
        errors.append('unknown selected POC')
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
        nfr_document = load(root / "specs/requirements/v1/nfr.yaml")
        nfr_binding = nfr_document["acceptanceProfileBinding"]
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
    if program.get('profileEvidenceBinding') != PROFILE_EVIDENCE_BINDING:
        errors.append('profile-qualified evidence binding must retain exact owners, paths and schemas')
    validate_schema(results, result_index_schema, "results-index.yaml", errors)
    if program.get("acceptanceProfileBinding") != nfr_binding:
        errors.append("program.yaml acceptanceProfileBinding must equal authoritative NFR binding")
    compatibility = next((n for n in nfr_document.get('items',[]) if n.get('id') == 'NFR-V1-COMP-003'), {})
    if not {'POC-01','POC-02','GZ-011','GZ-020'}.issubset(set(compatibility.get('measurement',{}).get('verificationOwners') or [])):
        errors.append('NFR-V1-COMP-003 must bind actual production compatibility verifiers and GZ-020')
    for profile in (program.get("acceptanceProfileBinding") or {}).get("profiles", []):
        if set(profile.get("requirementIds") or []) != {f"REQ-V1-{i:04d}" for i in range(1, 11)} or set(profile.get("acceptanceIds") or []) != {f"验收V1-{i:04d}" for i in range(1, 13)}:
            errors.append("program.yaml profile must preserve original full 10 requirements and 12 acceptances")

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
        validate_local_route(plan, resource_map, protocol_schema, errors)

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
        missing_compatibility = PRODUCTION_COMPAT_MEASUREMENTS.get(poc_id,set()) - set(measurement_ids)
        if missing_compatibility:
            errors.append(f"{relative}: missing production compatibility measurements {sorted(missing_compatibility)}")
        for measurement in (plan.get('protocol') or {}).get('measurements',[]):
            if measurement.get('id') in PRODUCTION_COMPAT_MEASUREMENTS.get(poc_id,set()) and measurement.get('unit') != 'boolean':
                errors.append(f"{relative}: production compatibility gate unit must remain boolean")
        capture_fields = set(
            (plan.get("environment") or {}).get("captureBeforeExecution", [])
        )
        missing_environment = REQUIRED_ENV.get(poc_id, set()) - capture_fields
        if missing_environment:
            errors.append(
                f"{relative}: missing required environment provenance fields {sorted(missing_environment)}"
            )
        missing_production_environment = PRODUCTION_COMPAT_ENV.get(poc_id,set()) - capture_fields
        if missing_production_environment:
            errors.append(f"{relative}: missing production compatibility environment fields {sorted(missing_production_environment)}")
        if poc_id in PRODUCTION_COMPAT_MEASUREMENTS and 'RES-HETEROGENEOUS-WORKERS' not in (plan.get('resourceIds') or []):
            errors.append(f"{relative}: production compatibility requires captured heterogeneous worker pool")

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
                root, plan, canonical_task, entry, resource_map,
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
    all_tasks = {t['taskId']:t for t in program_plan.get('tasks',[])}
    validate_profile_evidence(root,by_task,all_tasks,program_schema,result_record_schema,
        execution_schema,approval_schema,resource_map,selected_profile,require_results,
        set(selected_pocs or []),errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root")
    parser.add_argument("--task", help="Executing POC task for results-index row ownership validation")
    parser.add_argument("--base-ref", help="Git base ref used to prove only --task row changed")
    parser.add_argument('--profile',choices=sorted(PROFILE_SCOPES),help='Select qualified acceptance profile')
    parser.add_argument('--require-results',action='store_true',help='Require independently reviewed PASS in every selected profile slot')
    parser.add_argument('--poc',action='append',choices=sorted(POCS),help='Select a scoped POC contract; forbidden for full milestones')
    parser.add_argument('--milestone',choices=['GZ-018','GZ-020'],help='Require all ten qualified POC results for the exact milestone profile')
    args = parser.parse_args()
    root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else Path(__file__).resolve().parents[2]
    )
    errors = validate_repository(root,args.profile,args.require_results,args.milestone,args.poc)

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
    if args.require_results or args.milestone:
        print(f"PASS: qualified POC prerequisites for {args.profile}; milestone={args.milestone or 'scoped contract'}; no platform/runtime/production release granted")
    elif args.profile:
        print(f"Profile declarations checked: {args.profile}; qualified result acceptance not requested")
    if args.task:
        print(
            f"PASS: results-index row ownership verified for {args.task} "
            f"against {args.base_ref}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

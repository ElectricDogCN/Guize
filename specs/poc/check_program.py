#!/usr/bin/env python3
"""Fail-closed validator for POC-PROTOCOL-V1."""

from __future__ import annotations

import argparse
import base64
import copy
import codecs
import hashlib
import importlib.util
import ipaddress
import json
import math
import re
import sqlite3
import subprocess
import sys
import tempfile
import urllib.parse
import zlib
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
    'rawExecutionArtifactSchema':'program.schema.yaml#/$defs/rawExecutionArtifact',
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


def validate_deferred_production_qualification(plan,execution,status,errors):
    # Production physical-phone/passthrough soak, storage and Baidu outcomes
    # remain deferred; never certify these routes with partial observations.
    if status=='pass' and plan['pocId'] in ('POC-01','POC-04','POC-06') and (execution.get('environmentCaptured') or {}).get('acceptanceProfile')==profile_identity('production'):
        errors.append(f"deferred production qualification {plan['pocId']}: production outcome validation is not implemented; PASS unavailable")


def validate_qualified_production_capacity(plan, execution, status, errors):
    if plan['pocId'] != 'POC-04' or status != 'pass' or execution.get('environmentCaptured',{}).get('acceptanceProfile') != profile_identity('production'):
        return
    minimum = next((m.get('actual') for m in execution.get('measurements') or [] if m.get('id') == 'minimum_free_space_gib'),None)
    if not good_actual('GiB',minimum) or minimum < 500:
        errors.append(f"qualified production capacity {plan['taskId']}: PASS requires measured minimum_free_space_gib >= frozen 500 GiB floor (NFR-V1-CAP-002)")


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
    if end > datetime.now(timezone.utc):
        errors.append(f'{label}: executionWindow must have finished by validation time')
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
    approved = utc(record.get('approvedAt')) if isinstance(record,dict) else None
    if approved is not None and approved > datetime.now(timezone.utc):
        errors.append(f'{label}: approval must have occurred by validation time')
    if not isinstance(record, dict) or any(json.dumps(record.get(k),sort_keys=True,separators=(',',':')) != json.dumps(v,sort_keys=True,separators=(',',':')) for k,v in expected.items()):
        errors.append(f'{label}: record must bind exact POC, owner, resource/metric and profile')
        return None
    return record


LOCAL_STRUCTURED_CAPTURES = {
    'POC-02': {'segment_profile':'localSegmentCapture','scheduler_configuration':'localSchedulerCapture'},
    'POC-05': {'synthetic_hierarchy_manifest':'localHierarchyCapture'},
    'POC-06': {'injected_failure_matrix':'localFailureCapture'},
    'POC-07': {'local_tls_path_configuration':'localTlsCapture'},
}


def validate_qualified_configuration(root, plan, execution, configuration, defs, prefix, reviewer, implementer, window, errors, status=None):
    label=f"qualified profile configuration {plan['taskId']}"
    validate_schema(configuration,defs.get('profileConfiguration',{}),label,errors)
    if not isinstance(configuration,dict):return
    approved=utc(configuration.get('approvedAt'))
    if configuration.get('decision') != 'approved' or not recorded_text(reviewer) or configuration.get('approvedBy') != reviewer or reviewer == implementer:
        errors.append(f'{label}: current independent Task reviewer must approve configuration')
    if approved is None or window is None or approved > window[0] or approved > datetime.now(timezone.utc):
        errors.append(f'{label}: valid UTC approval must precede captured execution start')
    env=execution.get('environmentCaptured') or {}
    fields=LOCAL_STRUCTURED_CAPTURES.get(plan['pocId'],{}) if env.get('acceptanceProfile') == profile_identity('local-v1') else {}
    captured={key:env.get(key) for key in fields}
    if configuration.get('capturedSettings') != captured:
        errors.append(f'{label}: approval must bind exact captured structured settings')
    for field,schema in fields.items():
        value=env.get(field)
        capture_label=f"qualified local capture {plan['taskId']}/{field}"
        validate_schema(value,defs.get(schema,{}),capture_label,errors)
        if field=='synthetic_hierarchy_manifest' and status=='pass' and isinstance(value,dict):
            actual={measurement.get('id'):measurement.get('actual') for measurement in execution.get('measurements') or [] if isinstance(measurement,dict)}
            generator=value.get('generator')
            if not isinstance(generator,dict):generator={}
            for measured,captured in (('file_count','fileCount'),('directory_count','directoryCount'),('directory_depth_max','maximumDepth')):
                if type(actual.get(measured)) is not int or actual.get(measured)!=generator.get(captured):
                    errors.append(f'{capture_label}: {measured} must match the exact approved generated hierarchy {captured}')
        if field=='local_tls_path_configuration' and isinstance(value,dict):
            for key,schemes in (('entryOrigin',{'https'}),('openlistOrigin',{'http','https'})):
                if not valid_local_origin(value.get(key),schemes):
                    errors.append(f'{capture_label}: {key} requires a canonical loopback/private origin and any port in 1..65535')
        if field=='injected_failure_matrix' and isinstance(value,dict):
            cases=value.get('cases')
            if isinstance(cases,list):
                ids=[case.get('caseId') for case in cases if isinstance(case,dict)]
                faults={case.get('fault') for case in cases if isinstance(case,dict)}
                if len(ids)!=len(set(ids)) or not {'http_429','http_5xx','network_disconnect','auth_expired'}.issubset(faults):
                    errors.append(f'{capture_label}: distinct exercised case identities must retain HTTP429/5xx/network/auth faults')
                records=env.get('rawExecutionArtifacts') or []
                for case in cases:
                    if not isinstance(case,dict):continue
                    ref=case.get('rawOutputRef')
                    record=next((r for r in records if isinstance(r,dict) and r.get('ref')==ref),None) if isinstance(records,list) else None
                    if record is None or record.get('artifactType')!='scope_observation' or ref not in (execution.get('rawOutputRefs') or []) or existing_ref(root,ref,prefix) is None:
                        errors.append(f'{capture_label}: exercised fault must retain a selected-slot typed observation artifact')


def retained_local_source_transport_artifact(root,execution,prefix,ref,kind,maximum,label,errors,cache,paths):
    """Bind one bounded retained native-client file to its selected typed artifact."""
    env=execution.get('environmentCaptured') or {};path=existing_ref(root,ref,prefix)
    records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==ref]
    if path is None or ref not in (execution.get('rawOutputRefs') or []) or len(records)!=1 or records[0].get('artifactType')!=kind:
        errors.append(f'{label}: selected typed independent request/transport bytes required');return
    try:
        actual=inspect_artifact(path,cache)
        if actual['size']>maximum or records[0].get('byteCount')!=actual['size'] or records[0].get('sha256')!=actual['sha256']:raise ValueError('retained byte binding')
        if any(path.samefile(peer) for peer in paths if peer is not None):raise ValueError('physical alias')
    except (OSError,ValueError):
        errors.append(f'{label}: retained transport files must have exact physical hash/size, bounds and independent paths');return
    paths.append(path);return path


def parse_local_source_http_response(raw):
    """Parse a bounded retained final HTTP response without following any URL."""
    head,separator,body=raw.partition(b'\r\n\r\n');lines=head.decode('ascii').split('\r\n')
    match=re.fullmatch(r'HTTP/(?:1\.[01]|2(?:\.0)?|3(?:\.0)?) ([1-5][0-9]{2})(?: [^\r\n]*)?',lines[0])
    if not separator or match is None or len(head)>65536:raise ValueError('HTTP response')
    headers={}
    for line in lines[1:]:
        key,colon,value=line.partition(':');key=key.lower()
        if not colon or re.fullmatch(r'[a-z0-9-]+',key) is None or key in headers:raise ValueError('ambiguous/malformed HTTP header')
        headers[key]=value.strip()
    if 'transfer-encoding' in headers or 'content-length' in headers and (re.fullmatch(r'[0-9]+',headers['content-length']) is None or int(headers['content-length'])!=len(body)):raise ValueError('response framing')
    return int(match.group(1)),headers,body


def derive_local_source_fault_attempt(root,execution,prefix,report,policy,row,claim,following,window,defs,label,errors,cache,paths,traces):
    """Read one approved client's retained request/HTTP/progress/exit bytes; never execute it."""
    before=len(errors);env=execution.get('environmentCaptured') or {}
    run=selected_observation(root,execution,prefix,claim.get('transportExecutionRef'),defs,'localSourceFaultTransportExecution',label,errors,cache)
    if run is None or len(errors)!=before:return
    common={k:report[k] for k in ('configurationRef','acceptanceProfile','subjectVersion','inputSamples','scope','sandboxId')}
    common.update(sourceId=policy['sourceId'],objectId=policy['objectId'],objectVersion=policy['objectVersion'],caseId=row['caseId'],attemptNo=claim['attemptNo'],requestId=claim['requestId'],traceId=claim['traceId'])
    start,end=utc(run['startedAt']),utc(run['finishedAt'])
    if any(run.get(k)!=v for k,v in common.items()) or not recorded_text(run['traceId']) or run['traceId'] in traces or start is None or end is None or window is None or not window[0]<=start<end<=window[1]:
        errors.append(f'{label}: independent executed attempt must bind exact request/trace/source/input scope and positive UTC interval');return
    traces.add(run['traceId'])
    def retained(ref,kind,maximum):
        return retained_local_source_transport_artifact(root,execution,prefix,ref,kind,maximum,label,errors,cache,paths)
    run_path=retained(claim['transportExecutionRef'],'measurement_output',262144)
    request_path=retained(run['requestRef'],'command_output',262144)
    response_path=retained(run['responseRef'],'produced_media',(32<<20)+65536)
    progress_path=retained(run['progressRef'],'command_output',262144)
    stderr_path=retained(run['stderrRef'],'command_output',65536)
    if any(p is None for p in (run_path,request_path,response_path,progress_path,stderr_path)):return
    argv=policy['transportCommandArgs']+['--request',run['requestRef'],'--response',run['responseRef'],'--progress',run['progressRef'],'--stderr',run['stderrRef']]
    if run['commandArgs']!=argv or run['toolBuild']!=policy['transportToolBuild'] or any(not recorded_text(v) for v in policy['transportCommandArgs']) or not recorded_text(policy['transportToolBuild']):
        errors.append(f'{label}: actual attempt command/build must equal the independently approved client and exact retained paths');return
    before=len(errors)
    request=bounded_evaluator_json(root,execution,prefix,run['requestRef'],'command_output',defs,'localSourceFaultRequest',label,errors,cache)
    progress=bounded_evaluator_json(root,execution,prefix,run['progressRef'],'command_output',defs,'localSourceFaultProgress',label,errors,cache)
    if request is None or progress is None or len(errors)!=before:return
    span=policy['transportInputSpan'];sample=next((s for s in execution.get('samples') or [] if s.get('id')==span['sampleId']),None)
    inputs=[i for i in env.get('inputSampleArtifacts') or [] if isinstance(i,dict) and i.get('sampleId')==span['sampleId']]
    source=existing_ref(root,inputs[0].get('inputArtifactRef'),prefix) if len(inputs)==1 else None
    if sample is None or source is None or any(source.samefile(peer) for peer in paths):
        errors.append(f'{label}: approved input span must bind separate selected immutable sample bytes');return
    first,last=span['byteOffset'],span['byteOffset']+span['byteCount']-1;actual=inspect_artifact(source,cache,byte_range=(first,last))
    if span['byteCount']>32<<20 or last>=actual['size'] or actual['sha256']!=sample['checksum'] or inputs[0].get('sha256')!=actual['sha256'] or inputs[0].get('byteCount')!=actual['size']:
        errors.append(f'{label}: approved input byte span must exist within the actual immutable input');return
    input_span={**span,'immutableId':sample['immutableId'],'sha256':sample['checksum']}
    expected_request=dict(common,idempotencyKey=policy['idempotencyKey'],requestedAt=run['startedAt'],inputSpan=input_span,endpointURL=policy['transportEndpointURL'],httpMethod='DELETE' if row['case']=='source_delete' else 'GET')
    if any(request.get(k)!=v for k,v in expected_request.items()) or any(progress.get(k)!=v for k,v in dict(requestId=run['requestId'],traceId=run['traceId'],observedAt=run['finishedAt']).items()):
        errors.append(f'{label}: raw request/progress must bind the exact request ID, trace, input span, checkpoint and observed timing');return
    try:
        endpoint=urllib.parse.urlsplit(policy['transportEndpointURL']);origin=endpoint.scheme+'://'+endpoint.netloc
        if not valid_local_origin(origin,{'http','https'}) or endpoint.path in ('','/') or endpoint.query or endpoint.fragment or endpoint.username or endpoint.password:raise ValueError('endpoint')
        raw=response_path.read_bytes();status_code=None;retry_after=0;code=run['exitCode']
        if raw and code==0:
            status_code,headers,body=parse_local_source_http_response(raw)
            if 'retry-after' in headers:
                value=headers['retry-after']
                if re.fullmatch(r'[0-9]+',value):retry_after=int(value)
                else:
                    from email.utils import parsedate_to_datetime
                    retry_after=max(0,(parsedate_to_datetime(value).astimezone(timezone.utc)-end).total_seconds())
        diagnostic=stderr_path.read_text(encoding='utf8')
        if code==0:
            if status_code is None or diagnostic.strip():raise ValueError('HTTP exit/diagnostic')
            transport='http_response';classification='http_429' if status_code==429 else 'http_5xx' if 500<=status_code<600 else 'auth_expired' if status_code in (401,403) else 'source_delete' if row['case']=='source_delete' and status_code in (200,204) else 'success' if 200<=status_code<300 else None
            if classification=='success' and (len(body)!=span['byteCount'] or 'sha256:'+hashlib.sha256(body).hexdigest()!=actual['rangeHashes'][(first,last)] or status_code==200 and span['byteCount']!=actual['size']):raise ValueError('recovery returned bytes')
        elif code in (7,18,28,52,55,56) and re.search(r'curl: \('+str(code)+r'\)',diagnostic):transport='network_disconnect';classification='network_disconnect';status_code=None;retry_after=0
        elif code in (-2,130) or code==42 and re.search(r'curl: \(42\)',diagnostic):transport='interrupted';classification='interrupted_sync';status_code=None;retry_after=0
        else:raise ValueError('unsupported actual client exit/transport error')
        if classification is None:raise ValueError('unclassified actual response')
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError,AttributeError):
        errors.append(f'{label}: classification/recovery must derive retained HTTP response bytes and actual native client exit/diagnostic');return
    delay=0
    if following is not None:
        before=len(errors);next_run=selected_observation(root,execution,prefix,following.get('transportExecutionRef'),defs,'localSourceFaultTransportExecution',label,errors,cache)
        if next_run is None or len(errors)!=before:return
        next_at=utc(next_run['startedAt']);delay=(next_at-end).total_seconds() if next_at is not None else -1
    observed=dict(attemptNo=run['attemptNo'],requestId=run['requestId'],traceId=run['traceId'],idempotencyKey=request['idempotencyKey'],requestedAt=run['startedAt'],finishedAt=run['finishedAt'],transport=transport,httpStatus=status_code,classification=classification,authorization=request['authorization'],retryAfterSeconds=retry_after,backoffAfterSeconds=delay,checkpointBefore=request['checkpointBefore'],**{k:progress[k] for k in ('checkpointAfter','completedObjectIds','returnedAssetIds','createdAssetIds')})
    if any(claim.get(k)!=v for k,v in observed.items()):errors.append(f'{label}: aggregate attempt claims must equal independently derived request/transport/progress outcomes')
    return {**claim,**observed}


def validate_qualified_local_source_faults(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-06' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('local-v1'):return
    label=f"qualified local source faults {plan['taskId']}";ref=env.get('sourceFaultOutcomeRef');path=existing_ref(root,ref,prefix)
    artifacts=[r for r in env.get('rawExecutionArtifacts') or [] if isinstance(r,dict) and r.get('ref')==ref]
    if path is None or ref not in (execution.get('rawOutputRefs') or []) or len(artifacts)!=1 or artifacts[0].get('artifactType')!='scope_observation':
        errors.append(f'{label}: selected-slot typed source fault output required');return
    before=len(errors);report=qualified_observation_report(path,defs,'localSourceFaultOutcomes',label,errors,cache)
    if report is None or len(errors)!=before:return
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-OPENLIST-LOCAL'),None)
    if resource is None or report['configurationRef']!=resource.get('configurationRef'):
        errors.append(f'{label}: exact approved local OpenList configuration required');return
    config_path=existing_ref(root,report['configurationRef'],prefix)
    try:policy=load(config_path).get('configuration',{}).get('localSourceFaultPolicy') if config_path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    before=len(errors);validate_schema(policy,defs.get('localSourceFaultPolicy',{}),label+'/approved policy',errors)
    if len(errors)!=before or not isinstance(policy,dict):return
    expected=dict(subjectVersion=compliance_subject_version(plan,execution),acceptanceProfile=env.get('acceptanceProfile'),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],scope='GENERIC_OPENLIST_SANDBOX',sandboxId=policy['sandboxId'])
    if any(report.get(k)!=v for k,v in expected.items()) or policy['subjectVersion']!=expected['subjectVersion'] or env.get('source_validation_scope')!='GENERIC_OPENLIST_SANDBOX' or any(not recorded_text(policy[k]) for k in ('sandboxId','sourceId','objectId','objectVersion','assetId','assetVersion','idempotencyKey')):
        errors.append(f'{label}: exact approved generic service/API versions, inputs and source/object/asset/sandbox required')
    rows=report['cases'];required={'http_429','http_5xx','network_disconnect','auth_expired','interrupted_sync','duplicate_replay','source_delete'}
    if len(rows)!=7 or {r['case'] for r in rows}!=required or len({r['caseId'] for r in rows})!=7:
        errors.append(f'{label}: exact unique faults, interruption, duplicate replay and source deletion cases required');return
    matrix=env.get('injected_failure_matrix');configured=matrix.get('cases') if isinstance(matrix,dict) else None
    if not isinstance(configured,list):return  # Original capture validator retains its schema error.
    by_fault={r['case']:r for r in rows}
    if any(not isinstance(c,dict) or c.get('fault') not in by_fault or c.get('caseId')!=by_fault[c.get('fault')]['caseId'] or c.get('rawOutputRef')!=ref for c in configured):errors.append(f'{label}: every approved injected fault must bind its exact parsed outcome')
    asset=dict(assetId=policy['assetId'],versionId=policy['assetVersion']);source=dict(sourceId=policy['sourceId'],objectId=policy['objectId'],versionId=policy['objectVersion'],availability='available');link=dict(sourceId=policy['sourceId'],objectId=policy['objectId'],assetId=policy['assetId']);full=dict(assets=[asset],sourceObjects=[source],links=[link]);request_ids=set();transport_paths=[path,config_path];traces=set()
    for row in rows:
        case=row['case'];old,new=row['before'],row['after'];claims=row['attempts'];attempts=[]
        for index,claim in enumerate(claims):
            observed=derive_local_source_fault_attempt(root,execution,prefix,report,policy,row,claim,claims[index+1] if index+1<len(claims) else None,window,defs,label,errors,cache,transport_paths,traces)
            if observed is not None:attempts.append(observed)
        if len(attempts)!=len(claims):continue
        for state in (old,new):
            expected_state=full if state['assets'] else dict(assets=[],sourceObjects=[],links=[])
            normalized={**state,'sourceObjects':[{**s,'availability':'available'} for s in state['sourceObjects']]}
            if normalized!=expected_state:errors.append(f'{label}: parsed state must contain exact unique governed source/object/asset/version/link identities')
        if len(attempts)>policy['maxAttempts'] or [a['attemptNo'] for a in attempts]!=list(range(1,len(attempts)+1)):errors.append(f'{label}: attempts must be ordered and bounded by approved retry budget')
        created=[];completed=set()
        for index,attempt in enumerate(attempts):
            start,end=utc(attempt['requestedAt']),utc(attempt['finishedAt'])
            if start is None or end is None or window is None or not window[0]<=start<=end<=window[1]:errors.append(f'{label}: request outcomes need ordered UTC execution timestamps')
            if attempt['requestId'] in request_ids or attempt['idempotencyKey']!=policy['idempotencyKey']:errors.append(f'{label}: unique observed requests must reuse the approved idempotency identity')
            request_ids.add(attempt['requestId']);created.extend(attempt['createdAssetIds'])
            if attempt['authorization']!=('expired' if case=='auth_expired' else 'valid'):errors.append(f'{label}: authorization expiry must be isolated from otherwise authorized fault cases')
            if len(attempt['completedObjectIds'])!=len(set(attempt['completedObjectIds'])) or not set(attempt['completedObjectIds']).issubset({policy['objectId']}) or len(attempt['returnedAssetIds'])!=len(set(attempt['returnedAssetIds'])) or not set(attempt['returnedAssetIds']).issubset({policy['assetId']}) or any(a!=policy['assetId'] for a in attempt['createdAssetIds']):errors.append(f'{label}: responses/progress must bind exact logical identities without duplicates')
            completed.update(attempt['completedObjectIds'])
            values=(attempt['retryAfterSeconds'],attempt['backoffAfterSeconds'],policy['maxBackoffSeconds'])
            if not all(ai_finite(v) for v in values) or attempt['backoffAfterSeconds']>policy['maxBackoffSeconds']:errors.append(f'{label}: finite observed backoff must respect approved ceiling')
            if index+1<len(attempts):
                following=attempts[index+1];next_at=utc(following['requestedAt']);delay=(next_at-end).total_seconds() if end is not None and next_at is not None else -1
                if delay<0 or not math.isclose(delay,attempt['backoffAfterSeconds'],rel_tol=1e-9,abs_tol=1e-9) or delay<attempt['retryAfterSeconds']:errors.append(f'{label}: observed retry timing must honor backoff and upstream Retry-After')
                if row['recoveryMode']=='resume' and following['checkpointBefore']!=attempt['checkpointAfter']:errors.append(f'{label}: resumed attempt must use the retained preceding checkpoint')
                if row['recoveryMode']=='idempotent_rerun' and following['checkpointBefore'] is not None:errors.append(f'{label}: idempotent rerun must disclose reset checkpoint')
            elif attempt['backoffAfterSeconds']!=0:errors.append(f'{label}: terminal outcome cannot invent an unexecuted retry')
            status_code=attempt['httpStatus'];classification=attempt['classification'];transport=attempt['transport']
            valid=(transport=='http_response' and type(status_code) is int and ((classification=='success' and 200<=status_code<300 and attempt['authorization']=='valid') or (classification=='http_429' and status_code==429) or (classification=='http_5xx' and 500<=status_code<600) or (classification=='auth_expired' and status_code in (401,403) and attempt['authorization']=='expired') or (classification=='source_delete' and status_code in (200,204)))) or (status_code is None and ((classification=='network_disconnect' and transport=='network_disconnect') or (classification=='interrupted_sync' and transport=='interrupted')))
            if not valid:errors.append(f'{label}: HTTP/network/auth/interruption classifications must match observed responses')
        if len(created)>(0 if old['assets'] else 1):errors.append(f'{label}: retries cannot create a duplicate logical asset')
        first,last=attempts[0],attempts[-1]
        if case=='network_disconnect' and row['outcome']=='explicit_failure':
            if row['recoveryMode']!='none' or old!=new or any(a['classification']!='network_disconnect' or a['returnedAssetIds'] or a['createdAssetIds'] or a['completedObjectIds'] or a['checkpointAfter']!=a['checkpointBefore'] for a in attempts) or any(b['checkpointBefore']!=a['checkpointAfter'] for a,b in zip(attempts,attempts[1:])):
                errors.append(f'{label}: explicit network failure must preserve logical state and retained checkpoint without protected result or promotion')
        elif case in ('http_429','http_5xx','network_disconnect','interrupted_sync'):
            if len(attempts)<2 or first['classification']!=case or row['recoveryMode'] not in ('resume','idempotent_rerun') or row['outcome']!='recovered' or last['classification']!='success' or last['returnedAssetIds']!=[policy['assetId']] or completed!={policy['objectId']} or new!=full:errors.append(f'{label}: classified faults must recover through bounded observed retry without state corruption')
            if case=='interrupted_sync' and not recorded_text(first['checkpointAfter']):errors.append(f'{label}: interrupted progress must retain a checkpoint before resume/rerun')
        elif case=='auth_expired':
            if len(attempts)!=1 or first['classification']!='auth_expired' or row['outcome']!='explicit_failure' or old!=new or first['returnedAssetIds'] or first['createdAssetIds']:errors.append(f'{label}: expired authorization must fail explicitly without protected result or logical mutation')
        elif case=='duplicate_replay':
            if len(attempts)<2 or any(a['classification']!='success' or a['returnedAssetIds']!=[policy['assetId']] for a in attempts) or row['outcome']!='recovered' or new!=full:errors.append(f'{label}: duplicate replay must return the same unique logical asset')
        else:
            unavailable={**full,'sourceObjects':[{**source,'availability':'source_unavailable'}]}
            if old!=full or new!=unavailable or row['outcome']!='source_unavailable' or len(attempts)!=1 or first['classification']!='source_delete' or first['createdAssetIds']:errors.append(f'{label}: source deletion must preserve exact asset/version/link with governed unavailable source state')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    gates={'rate_limit_429_classified_retried','upstream_5xx_classified_retried','network_failure_classified_retried','interrupted_sync_resume_or_idempotent_rerun','duplicate_objects_prevented','source_deletion_preserves_logical_asset','generic_source_scope_verified'}
    if any(actual.get(gate) is not True for gate in gates):errors.append(f'{label}: true sync safety gates require the parsed observed outcomes')


def validate_qualified_local_source_authentication(root,plan,execution,prefix,status,window,defs,errors,cache):
    """Derive local authentication from retained request outcomes, never execute credentials."""
    from urllib.parse import urlsplit
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-06' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('local-v1'):return
    label=f"qualified local source authentication {plan['taskId']}";before=len(errors)
    ref=env.get('sourceAuthenticationRef')
    report=selected_observation(root,execution,prefix,ref,defs,'localSourceAuthenticationObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-OPENLIST-LOCAL'),None)
    config_path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    config=qualified_observation_report(config_path,defs,'resourceConfiguration',label+'/configuration',errors,cache) if config_path else None
    settings=config.get('configuration',{}) if isinstance(config,dict) else {}
    policy=settings.get('localSourceAuthenticationPolicy') if isinstance(settings,dict) else None
    validate_schema(policy,defs.get('localSourceAuthenticationPolicy',{}),label+'/approved policy',errors)
    if report is None or len(errors)!=before:return
    fault=settings.get('localSourceFaultPolicy');listing=settings.get('localSourceListingPolicy')
    sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==policy['sampleId']),None)
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],scope='GENERIC_OPENLIST_SANDBOX',**{k:policy[k] for k in ('sourceId','sandboxId','endpointURL','objectId','objectVersion','authMethod','principalId')})
    if any(report[k]!=v for k,v in expected.items()) or policy['subjectVersion']!=expected['subjectVersion'] or env.get('source_validation_scope')!='GENERIC_OPENLIST_SANDBOX' or not isinstance(fault,dict) or not isinstance(listing,dict) or any(policy[k]!=fault.get(k) for k in ('sourceId','sandboxId','subjectVersion','objectId','objectVersion')) or any(policy[k]!=listing.get(k) for k in ('sourceId','sandboxId','subjectVersion')) or sample is None or (sample['immutableId'],sample['checksum'])!=(policy['immutableId'],policy['payloadSha256']) or policy['authorizedAuthRef']==policy['invalidAuthRef']:
        errors.append(f'{label}: approved method, principal, service/API versions, source/object/sandbox and immutable input must match');return
    try:
        endpoint=urlsplit(policy['endpointURL']);listing_endpoint=urlsplit(listing['endpointURL'])
        origin=endpoint.scheme+'://'+endpoint.netloc
        valid=valid_local_origin(origin,{'http','https'}) and origin==listing_endpoint.scheme+'://'+listing_endpoint.netloc and endpoint.path not in ('','/') and not endpoint.username and not endpoint.password and not endpoint.query and not endpoint.fragment
    except (ValueError,TypeError):valid=False
    if not valid:errors.append(f'{label}: exact approved protected endpoint must share the local listing origin');return
    rows=report['requests'];cases={'authenticated','anonymous_denied','invalid_auth_denied'}
    if len(rows)!=3 or {r['case'] for r in rows}!=cases or len({r['requestId'] for r in rows})!=3:
        errors.append(f'{label}: distinct actual authenticated, anonymous and invalid-auth requests required');return
    artifacts=env.get('rawExecutionArtifacts') or [];paths=[existing_ref(root,ref,prefix),config_path]
    input_records=env.get('inputSampleArtifacts') or []
    for record in input_records:
        if isinstance(record,dict):
            path=existing_ref(root,record.get('inputArtifactRef'),prefix)
            if path is not None:paths.append(path)
    for row in rows:
        success=row['case']=='authenticated';anonymous=row['case']=='anonymous_denied'
        requested,finished=utc(row['requestedAt']),utc(row['finishedAt'])
        expected_auth=None if anonymous else policy['authorizedAuthRef'] if success else policy['invalidAuthRef']
        if row['httpMethod']!='GET' or row['endpointURL']!=policy['endpointURL'] or row['authMethod']!=('none' if anonymous else policy['authMethod']) or row['authRef']!=expected_auth or row['requestPrincipalId']!=(None if anonymous else policy['principalId']) or row['authenticatedPrincipalId']!=(policy['principalId'] if success else None) or requested is None or finished is None or window is None or not window[0]<=requested<=finished<=window[1] or row['statusCode'] not in ((200,206) if success else (401,403)):
            errors.append(f'{label}: request identity/method/non-secret auth reference, actual HTTP outcome and UTC must match')
        origin_before=len(errors);origin=selected_observation(root,execution,prefix,row['originAccessRef'],defs,'localSourceOriginAccessObservation',label+'/origin access',errors,cache)
        origin_path=existing_ref(root,row['originAccessRef'],prefix)
        if origin is None or len(errors)!=origin_before:continue
        binding={key:value for key,value in expected.items() if key!='authMethod'}
        binding.update({key:row[key] for key in ('case','requestId','httpMethod','authRef','requestPrincipalId','authenticatedPrincipalId','requestedAt','finishedAt','statusCode')})
        if any(origin.get(key)!=value for key,value in binding.items()):errors.append(f'{label}: origin access must bind this exact request, source/object/version, authorization and UTC interval')
        if any(origin_path.samefile(path) for path in paths if path is not None):errors.append(f'{label}: origin access observations must be physically distinct from structured records, inputs and other requests')
        paths.append(origin_path)
        if not success and (origin['originRequestCount']!=0 or origin['objectReadCount']!=0):errors.append(f'{label}: denied authentication must precede all origin access and protected object reads')
        body=existing_ref(root,row['responseBodyRef'],prefix)
        records=[a for a in artifacts if isinstance(a,dict) and a.get('ref')==row['responseBodyRef']]
        if body is None or row['responseBodyRef'] not in (execution.get('rawOutputRefs') or []) or len(records)!=1 or records[0].get('artifactType')!='produced_media' or any(body.samefile(p) for p in paths if p is not None):
            errors.append(f'{label}: selected-slot independently retained actual response bytes required');continue
        paths.append(body)
        try:actual=inspect_artifact(body,cache)
        except OSError:errors.append(f'{label}: readable response bytes required');continue
        if actual['size']!=row['responseByteCount'] or actual['sha256']!=row['responseSha256'] or records[0].get('byteCount')!=actual['size'] or records[0].get('sha256')!=actual['sha256']:
            errors.append(f'{label}: observed response byte count/hash must match actual retained bytes')
        if success:
            if actual['size']<=0 or actual['sha256']!=policy['payloadSha256'] or row['returnedObjectId']!=policy['objectId'] or row['returnedObjectVersion']!=policy['objectVersion']:
                errors.append(f'{label}: successful protected read must return the exact approved immutable object bytes')
        else:
            safe=actual['size']==0
            if 0<actual['size']<=1024:
                def fields(pairs):
                    if len({k for k,_ in pairs})!=len(pairs):raise ValueError('duplicate public error fields')
                    return dict(pairs)
                try:
                    with body.open(encoding='utf8') as stream:safe=json.load(stream,object_pairs_hook=fields)=={'error':'access_denied'}
                except (OSError,ValueError,UnicodeError):safe=False
            if not safe or row['returnedObjectId'] is not None or row['returnedObjectVersion'] is not None:
                errors.append(f'{label}: anonymous/invalid authentication must expose no protected object bytes or identity')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if actual.get('auth_flow_supported') is not True:errors.append(f'{label}: true auth_flow_supported requires all parsed authentication outcomes')


def derive_local_source_listing_page(root,execution,prefix,report,policy,listing_run,number,claim,window,defs,label,errors,cache,paths,traces):
    """Derive an OpenList page from retained POST request and native HTTP bytes."""
    before=len(errors)
    run=selected_observation(root,execution,prefix,claim.get('transportExecutionRef'),defs,'localSourceListingTransportExecution',label,errors,cache)
    if run is None or len(errors)!=before:return
    common={k:report[k] for k in ('configurationRef','acceptanceProfile','subjectVersion','inputSamples','sourceId','sandboxId','endpointURL')}
    common.update(scope='GENERIC_OPENLIST_SANDBOX',runId=listing_run['runId'],pageNo=number+1,requestId=claim['requestId'],traceId=claim['traceId'])
    start,end=utc(run['startedAt']),utc(run['finishedAt'])
    if any(run.get(k)!=v for k,v in common.items()) or not recorded_text(run['traceId']) or run['traceId'] in traces or start is None or end is None or window is None or not window[0]<=start<end<=window[1]:
        errors.append(f'{label}: each executed page must bind distinct trace/request/run/page, approved versions/source and positive UTC interval');return
    traces.add(run['traceId'])
    def retained(ref,kind,maximum):
        return retained_local_source_transport_artifact(root,execution,prefix,ref,kind,maximum,label,errors,cache,paths)
    run_path=retained(claim['transportExecutionRef'],'measurement_output',262144)
    request_path=retained(run['requestRef'],'command_output',262144)
    response_path=retained(run['responseRef'],'produced_media',262144+65536)
    stderr_path=retained(run['stderrRef'],'command_output',65536)
    if any(path is None for path in (run_path,request_path,response_path,stderr_path)):return
    argv=policy['transportCommandArgs']+['--request',run['requestRef'],'--response',run['responseRef'],'--stderr',run['stderrRef']]
    if run['commandArgs']!=argv or run['toolBuild']!=policy['transportToolBuild'] or any(not recorded_text(v) for v in policy['transportCommandArgs']) or not recorded_text(policy['transportToolBuild']):
        errors.append(f'{label}: executed listing command/build must match the approved client and exact retained paths');return
    before=len(errors)
    request=bounded_evaluator_json(root,execution,prefix,run['requestRef'],'command_output',defs,'localSourceListingRequest',label,errors,cache)
    if request is None or len(errors)!=before:return
    span=policy['transportInputSpan'];sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==span['sampleId']),None)
    inputs=[i for i in (execution.get('environmentCaptured') or {}).get('inputSampleArtifacts') or [] if isinstance(i,dict) and i.get('sampleId')==span['sampleId']]
    source=existing_ref(root,inputs[0].get('inputArtifactRef'),prefix) if len(inputs)==1 else None
    try:
        if sample is None or source is None:raise ValueError('input binding')
        actual=inspect_artifact(source,cache);last=span['byteOffset']+span['byteCount']
        if last>actual['size'] or actual['sha256']!=sample['checksum'] or inputs[0].get('sha256')!=actual['sha256'] or inputs[0].get('byteCount')!=actual['size']:raise ValueError('input span')
    except (OSError,ValueError):
        errors.append(f'{label}: listing input span must bind separate actual approved immutable input bytes');return
    expected_request=dict(common,requestedAt=run['startedAt'],inputSpan={**span,'immutableId':sample['immutableId'],'sha256':sample['checksum']},httpMethod='POST',body=dict(path=policy['listingPath'],page=number+1,per_page=policy['pageSize'],refresh=False))
    if any(request.get(k)!=v for k,v in expected_request.items()):
        errors.append(f'{label}: native listing POST, path/page/size, input span and request timestamp must bind the exact executed page');return
    try:
        status,headers,body=parse_local_source_http_response(response_path.read_bytes())
        if run['exitCode']!=0 or stderr_path.read_bytes().strip() or status!=200 or headers.get('content-type','').split(';',1)[0].strip().lower()!='application/json':raise ValueError('listing HTTP outcome')
        if not 0<len(body)<=262144:raise ValueError('listing response bound')
        def pairs(items):
            if len({key for key,_ in items})!=len(items):raise ValueError('duplicate listing JSON keys')
            return dict(items)
        def constant(value):raise ValueError('nonfinite listing JSON')
        response=json.loads(body.decode('utf8'),object_pairs_hook=pairs,parse_constant=constant)
    except (OSError,UnicodeError,ValueError,TypeError,OverflowError):
        errors.append(f'{label}: successful listing must derive bounded retained native HTTP/JSON response and actual exit/diagnostic');return
    before=len(errors);validate_schema(response,defs.get('localSourceListingResponse',{}),label+'/native OpenList response',errors)
    if len(errors)!=before:return
    total=response['data']['total'];content=response['data']['content'];offset=number*policy['pageSize']
    if response['code']!=200 or total!=len(policy['objects']) or offset>=total or len(content)!=min(policy['pageSize'],total-offset):
        errors.append(f'{label}: OpenList success code, actual total and bounded page population must agree');return
    objects=[]
    for item in content:
        kind='directory' if item['is_dir'] else 'file'
        matches=[obj for obj in policy['objects'] if obj['name']==item['name'] and obj['kind']==kind]
        metadata={key:item[key] for key in ('modified','size','hashinfo')}
        if len(matches)!=1 or matches[0]['listingMetadata']!=metadata:
            errors.append(f'{label}: native listing identity and version metadata must match exactly one approved logical object/version');return
        objects.append({key:matches[0][key] for key in ('objectId','versionId','name','kind')})
    observed=dict(requestId=run['requestId'],traceId=run['traceId'],requestedAt=request['requestedAt'],finishedAt=run['finishedAt'],requestCursor=None if number==0 else str(number+1),nextCursor=str(number+2) if offset+len(content)<total else None,statusCode=status,objects=objects)
    if any(claim.get(key)!=value for key,value in observed.items()):
        errors.append(f'{label}: aggregate page claims must equal independently derived request/HTTP pagination, time and object/version outcomes');return
    return observed


def validate_qualified_local_source_listing(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-06' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('local-v1'):return
    label=f"qualified local source listing {plan['taskId']}";before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('sourceListingRef'),defs,'localSourceListingObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-OPENLIST-LOCAL'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:config=load(path).get('configuration',{}) if path else {};policy=config.get('localSourceListingPolicy');fault=config.get('localSourceFaultPolicy')
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=fault=None
    validate_schema(policy,defs.get('localSourceListingPolicy',{}),label+'/approved policy',errors)
    if report is None or len(errors)!=before:return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],**{k:policy[k] for k in ('sourceId','sandboxId','endpointURL')})
    if any(report[k]!=v for k,v in expected.items()) or policy['subjectVersion']!=expected['subjectVersion'] or not isinstance(fault,dict) or any(policy[k]!=fault.get(k) for k in ('sourceId','sandboxId','subjectVersion')) or not recorded_text(policy['endpointURL']):errors.append(f'{label}: exact approved OpenList/API versions, source/sandbox/input and listing endpoint required');return
    objects=policy['objects'];ids=[o['objectId'] for o in objects];criteria=policy['criteria'];criteria_ids={'api','sdk','versioning','support'}
    if len(ids)!=len(set(ids)) or len(report['runs'])<policy['minimumListingRuns'] or {c['criterionId'] for c in criteria}!=criteria_ids or {c['criterionId'] for c in report['assessment']}!=criteria_ids or not all(ai_finite(c['weight']) for c in criteria) or not all(ai_finite(v) for v in policy['gradeValues'].values()):errors.append(f'{label}: exact distinct approved population, repeated listing and finite rubric required');return
    try:
        endpoint=urllib.parse.urlsplit(policy['endpointURL']);origin=endpoint.scheme+'://'+endpoint.netloc
        if not valid_local_origin(origin,{'http','https'}) or endpoint.path!='/api/fs/list' or endpoint.query or endpoint.fragment or endpoint.username is not None or endpoint.password is not None:raise ValueError('listing endpoint')
    except (ValueError,TypeError):
        errors.append(f'{label}: approved listing endpoint must be the exact local OpenList list API');return
    listing_path=policy['listingPath']
    if not listing_path.startswith('/') or '\\' in listing_path or any(part in ('.','..') for part in listing_path.split('/')) or any(ord(char)<32 for char in listing_path):
        errors.append(f'{label}: approved listing root must be a canonical absolute sandbox path');return
    request_ids=set();run_ids=set();previous=None;traces=set()
    paths=[existing_ref(root,env.get('sourceListingRef'),prefix),path]
    for record in env.get('inputSampleArtifacts') or []:
        if isinstance(record,dict):
            input_path=existing_ref(root,record.get('inputArtifactRef'),prefix)
            if input_path is not None:paths.append(input_path)
    for run in report['runs']:
        if run['runId'] in run_ids:errors.append(f'{label}: unique repeated listing run identities required')
        run_ids.add(run['runId']);cursor=None;seen_cursors=set();listed=[]
        for number,claim in enumerate(run['pages']):
            page=derive_local_source_listing_page(root,execution,prefix,report,policy,run,number,claim,window,defs,label,errors,cache,paths,traces)
            if page is None:continue
            start,end=utc(page['requestedAt']),utc(page['finishedAt'])
            if start is None or end is None or window is None or not window[0]<=start<=end<=window[1] or previous is not None and start<previous:errors.append(f'{label}: listing request timestamps must be ordered inside execution')
            previous=end
            if page['requestId'] in request_ids or page['statusCode']!=200 or page['requestCursor']!=cursor or number+1<len(run['pages']) and (not recorded_text(page['nextCursor']) or page['nextCursor'] in seen_cursors) or number+1==len(run['pages']) and page['nextCursor'] is not None:errors.append(f'{label}: actual successful pagination must follow unique cursors and end completely')
            request_ids.add(page['requestId']);cursor=page['nextCursor'];seen_cursors.add(cursor);listed.extend(page['objects'])
        if len(listed)!=len(objects) or {o['objectId'] for o in listed}!=set(ids) or len({o['objectId'] for o in listed})!=len(listed) or any(o!={key:next(p for p in objects if p['objectId']==o['objectId'])[key] for key in ('objectId','versionId','name','kind')} for o in listed if o['objectId'] in ids):errors.append(f'{label}: every repeated listing must retain the exact complete approved object identities/versions/names')
    grades=[];basis_paths=[]
    for row in report['assessment']:
        before=len(errors);basis=selected_observation(root,execution,prefix,row['basisRef'],defs,'localSourceAssessmentBasis',label+'/assessment',errors,cache);basis_path=existing_ref(root,row['basisRef'],prefix)
        if basis is None or len(errors)!=before:continue
        at=utc(row['observedAt']);basis_at=utc(basis['observedAt'])
        if at is None or basis_at is None or window is None or not window[0]<=basis_at<=at<=window[1] or basis['criterionId']!=row['criterionId'] or basis['subjectVersion']!=expected['subjectVersion'] or inspect_artifact(basis_path,cache)['sha256']!=row['basisSha256'] or any(not recorded_text(basis[k]) for k in ('toolBuild','reference','details')) or not recorded_text(row['rationale']) or any(basis_path.samefile(p) for p in basis_paths):errors.append(f'{label}: distinct assessed API/SDK/versioning/support basis must bind captured versions and rubric')
        basis_paths.append(basis_path);criterion=next(c for c in criteria if c['criterionId']==row['criterionId']);grades.append((criterion['weight'],policy['gradeValues'][row['status']]))
    try:score=sum(w*g for w,g in grades)/sum(w for w,g in grades) if len(grades)==4 else None
    except (OverflowError,ZeroDivisionError):score=None
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if actual.get('listing_stability') is not True:errors.append(f'{label}: listing stability gate must agree with complete repeated page observations')
    if not ai_finite(score) or not ai_finite(actual.get('maintainability')) or not math.isclose(actual['maintainability'],score,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: maintainability must derive the independently approved weighted assessment rubric')


def valid_local_origin(value,schemes):
    try:
        if not isinstance(value,str) or not value or any(ord(char)<=32 or ord(char)>=127 for char in value) or any(char in value for char in ('\\','%','?','#')):return False
        origin=urllib.parse.urlsplit(value)
        host=origin.hostname;port=origin.port
        if origin.scheme not in schemes or not host or origin.username is not None or origin.password is not None or origin.path or origin.query or origin.fragment:return False
        if port is not None and not 1<=port<=65535 or re.fullmatch(r'(?:[A-Za-z0-9.-]+|\[[0-9a-fA-F:]+\])(?::[0-9]+)?',origin.netloc) is None:return False
        if ':' in host:
            address=ipaddress.IPv6Address(host)
            if host!=address.compressed:return False
            # Mapped literals inherit the IPv4 boundary; link-local and transition addresses never qualify.
            if address.ipv4_mapped is not None:address=address.ipv4_mapped
            else:return address==ipaddress.IPv6Address('::1') or address in ipaddress.IPv6Network('fc00::/7')
        elif re.fullmatch(r'[0-9]+(?:\.[0-9]+){3}',host):
            address=ipaddress.IPv4Address(host)
            if host!=str(address):return False
        else:
            name=host[:-1] if host.endswith('.') else host
            if len(name)>253 or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',label) for label in name.split('.')):return False
            return host=='localhost'
        return any(address in ipaddress.IPv4Network(network) for network in ('127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
    except (ValueError,TypeError):return False


def validate_qualified_inputs(root, plan, execution, defs, prefix, status, errors, cache, record_refs=None, configuration=None):
    if status != 'pass' or not plan.get('sampleIds'):return
    label=f"qualified input samples {plan['taskId']}"
    env=execution.get('environmentCaptured') or {}
    records=env.get('inputSampleArtifacts')
    samples={s.get('id'):s for s in execution.get('samples') or [] if isinstance(s,dict)}
    if not isinstance(records,list) or not records:
        errors.append(f'{label}: typed inputSampleArtifacts required');return
    ids=[r.get('sampleId') for r in records if isinstance(r,dict)]
    if len(ids)!=len(records) or len(ids)!=len(set(ids)) or set(ids)!=set(samples):
        errors.append(f'{label}: input artifact identities must exactly bind approved execution samples')
    forbidden=[env.get('acceptanceProfileConfigurationRef'),*(execution.get('rawOutputRefs') or [])]
    forbidden += list(record_refs or ())
    forbidden += [s.get('approvalRef') for s in samples.values()]
    forbidden += [r.get(k) for r in execution.get('resources') or [] if isinstance(r,dict) for k in ('configurationRef','bookingRef')]
    forbidden += [r.get('reviewRef') for r in execution.get('complianceReviews') or [] if isinstance(r,dict)]
    profile=(env.get('acceptanceProfile') or {}).get('id')
    if profile in PROFILE_SCOPES:
        forbidden.append(profile_index_ref(f"POC-{int(plan['pocId'].split('-')[-1]):03d}",profile))
    domains=configuration.get('numericDomainReviewRefs',{}) if isinstance(configuration,dict) else {}
    if isinstance(domains,dict):
        for ref in domains.values():
            forbidden.append(ref)
            path=existing_ref(root,ref,prefix)
            if path:
                try: forbidden.append(load(path).get('definitionRef'))
                except (OSError,ValueError,AttributeError,yaml.YAMLError): pass
    peers=[path for ref in forbidden if (path:=existing_ref(root,ref,prefix)) is not None]
    for record in records:
        validate_schema(record,defs.get('inputSampleArtifact',{}),label,errors)
        if not isinstance(record,dict):continue
        sample=samples.get(record.get('sampleId'))
        path=existing_ref(root,record.get('inputArtifactRef'),prefix)
        if sample is None or path is None or record.get('immutableId')!=sample.get('immutableId'):
            errors.append(f'{label}: input reference/immutable identity must bind the exact selected sample');continue
        if any(path.samefile(peer) for peer in peers):
            errors.append(f'{label}: binary input must be distinct from structured records and execution outputs');continue
        try:
            actual=inspect_artifact(path,cache)
            if actual['size']<=0 or record.get('byteCount')!=actual['size'] or record.get('sha256')!=actual['sha256'] or sample.get('checksum')!=actual['sha256']:
                errors.append(f'{label}: sample/approval checksum must bind actual nonempty input bytes')
        except OSError:
            errors.append(f'{label}: input bytes must be readable')


def qualified_lifecycle_archive_paths(owner,before_ref,after_ref,changed,git):
    allowed=set()
    prefix=f'evidence/{owner}/'
    def blob(ref,path,limit):
        if int(git('cat-file','-s',f'{ref}:{path}'))>limit:return None
        return git('show',f'{ref}:{path}')
    for manifest_path in changed:
        if not manifest_path.startswith(prefix) or not manifest_path.endswith(('/manifest.json','/raw-results.bundle.json')):continue
        text=blob(after_ref,manifest_path,1048576)
        if text is None:continue
        manifest=yaml.load(text,Loader=UniqueKeyLoader)
        if not isinstance(manifest,dict):continue
        source=manifest.get('actualSource',manifest.get('source'))
        if not isinstance(source,str) or not re.fullmatch('[a-f0-9]{40}',source):continue
        git('merge-base','--is-ancestor',source,before_ref)
        if 'tree' in manifest and manifest['tree']!=git('show','-s','--format=%T',source):continue
        if 'actualMain' in manifest:git('merge-base','--is-ancestor',manifest['actualMain'],before_ref)
        key='entries' if 'entries' in manifest else 'artifacts' if 'artifacts' in manifest else 'files'
        records=manifest.get(key)
        if not isinstance(records,list) or not records:continue
        try:
            text=blob(before_ref,manifest_path,1048576)
            if text is None:return set()
            previous=yaml.load(text,Loader=UniqueKeyLoader)
        except subprocess.CalledProcessError:previous=None
        if previous is not None:
            old=previous.get(key) or []
            expected=copy.deepcopy(previous);expected[key]=records
            if records[:len(old)]!=old or manifest!=expected:continue
        paths={manifest_path}
        for record in records:
            if not isinstance(record,dict):return set()
            if key in ('artifacts','files'):
                path=record.get('path')
                if key=='files':
                    if not isinstance(path,str) or Path(path).name!=path or path in ('.','..'):return set()
                    path=str(Path(manifest_path).parent/path).replace('\\','/')
                if not lexical_ref(path,prefix.rstrip('/')):return set()
                text=blob(after_ref,path,33554432)
                if text is None:return set()
                raw=text.encode('utf8')
                size=record.get('canonicalBytes') if key=='files' else record.get('canonicalByteCount')
                digest=record.get('canonicalLfSha256') if key=='files' else record.get('canonicalSha256')
                if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:return set()
                paths.add(path)
            else:
                if record.get('encoding')!='concatenated-zlib-base64-parts' or type(record.get('size')) is not int or not 0<=record['size']<=33554432:return set()
                encoded=[]
                for part in record.get('parts') or []:
                    name=part.get('path')
                    if not isinstance(name,str) or Path(name).name!=name or name in ('.','..'):return set()
                    path=str(Path(manifest_path).parent/name).replace('\\','/')
                    text=blob(after_ref,path,65536)
                    if text is None:return set()
                    raw=text.encode('ascii')
                    if hashlib.sha256(raw).hexdigest()!=part.get('sha256'):return set()
                    encoded.append(raw.strip());paths.add(path)
                decoder=zlib.decompressobj()
                raw=decoder.decompress(base64.b64decode(b''.join(encoded),validate=True),33554433)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(raw)!=record['size'] or hashlib.sha256(raw).hexdigest()!=record.get('sha256'):return set()
        allowed.update(paths)
    return allowed


def qualified_lifecycle_delta_paths(root,before_ref,after_ref,git):
    """Authenticate one committed metadata delivery; never exempt whole paths."""
    changed=set(git('diff','--name-only',before_ref,after_ref).splitlines())
    shared={'specs/coordination/program-plan.yaml','specs/coordination/active-work.yaml','specs/coordination/task-completions.yaml'}
    if not changed or not changed.intersection(shared):return set()
    if any(path not in shared and not path.startswith(('specs/tasks/','evidence/')) for path in changed):return set()
    def document(ref,path):return yaml.load(git('show',f'{ref}:{path}'),Loader=UniqueKeyLoader)
    before,after=(document(ref,'specs/coordination/program-plan.yaml') for ref in (before_ref,after_ref))
    if not isinstance(before,dict) or not isinstance(after,dict):return set()
    old_rows={row['taskId']:row for row in before.get('tasks') or []}
    new_rows={row['taskId']:row for row in after.get('tasks') or []}
    if len(old_rows)!=len(before.get('tasks') or []) or len(new_rows)!=len(after.get('tasks') or []):return set()
    owners=[task for task in old_rows if task in new_rows and old_rows[task]!=new_rows[task]]
    if len(owners)!=1:return set()
    owner=owners[0]
    if not re.fullmatch('[A-Z]+-[0-9]{3}',owner):return set()
    task_path=f'specs/tasks/{owner}.md'
    if any(path not in shared|{task_path} and not path.startswith(f'evidence/{owner}/') for path in changed):return set()
    # The existing history library reads immutable reservation/task snapshots.
    helper_path=Path(__file__).resolve().parents[2]/'scripts/check-program-plan-history.py'
    spec=importlib.util.spec_from_file_location('qualified_poc_lifecycle_history',helper_path)
    history=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)
    history.git=lambda repository,*args:subprocess.run(['git',*args],cwd=repository,capture_output=True,text=True,encoding='utf8')
    transitions=history.TRANSITIONS
    if not transitions.only_lifecycle_target_changed(before,after,'tasks',owner,{'status'}):return set()
    old_state,new_state=old_rows[owner].get('status'),new_rows[owner].get('status')
    if new_state!='completed' and (old_state,new_state) not in transitions.ALLOWED_ACTIVE_TRANSITIONS:return set()
    if old_state not in history.ACTIVE_STATES:return set()
    active_path='specs/coordination/active-work.yaml'
    old_active,new_active=(document(ref,active_path) for ref in (before_ref,after_ref))
    old_entries=[row for row in old_active.get('tasks') or [] if row.get('taskId')==owner]
    new_entries=[row for row in new_active.get('tasks') or [] if row.get('taskId')==owner]
    if len(old_entries)!=1:return set()
    entry=old_entries[0]
    old_spec,old_body=history.parse_front_matter(git('show',f'{before_ref}:{task_path}'))
    new_spec,new_body=history.parse_front_matter(git('show',f'{after_ref}:{task_path}'))
    checks=[]
    history.stable_spec_matches(owner,entry,old_spec,old_body,checks,reservation=False)
    history.stable_spec_matches(owner,entry,new_spec,new_body,checks,reservation=False)
    phase_fields={'status','agentRole','baseSha','workBranch'}
    if transitions.entry_without_fields(old_spec,phase_fields)!=transitions.entry_without_fields(new_spec,phase_fields):return set()
    if new_spec.get('status')!=new_state or new_spec.get('baseSha')!=before_ref:return set()
    def authority_sections(body):
        sections=re.split(r'(?m)^## ',body)
        result={}
        for section in sections:
            title,_,text=section.partition('\n')
            phase_titles={'当前 Review（以上实施/预留阶段描述为历史记录）','当前 Completion（实施阶段为历史记录）'}
            if title in {'必须执行的测试','Evidence','协作与交接','未解决问题'}|phase_titles:continue
            if title in result:return None
            result[title]=text.replace('[x]','[ ]').replace('[X]','[ ]')
        return result
    if authority_sections(old_body)!=authority_sections(new_body):return set()
    ledger_path='specs/coordination/task-completions.yaml'
    old_ledger,new_ledger=(document(ref,ledger_path) for ref in (before_ref,after_ref))
    if new_state=='completed':
        if not history.only_task_removed(old_active,new_active,owner):return set()
        old_records,new_records=old_ledger.get('records') or [],new_ledger.get('records') or []
        expected=copy.deepcopy(old_ledger)
        if len(new_records)!=len(old_records)+1 or new_records[:-1]!=old_records:return set()
        if any(old.get('taskId')==owner for old in old_records):return set()
        record=new_records[-1];expected['records']=new_records
        if expected!=new_ledger or record.get('taskId')!=owner:return set()
        if record.get('taskSpec')!=task_path or record.get('evidencePath')!=f'evidence/{owner}' or record.get('handoffPath')!=f'evidence/{owner}/handoff.md':return set()
        reservation,implementation=record.get('reservationCommit'),record.get('mergeCommit')
        if reservation==implementation or record.get('reservationRef')==record.get('completionRef'):return set()
        history.validate_commit(str(root),str(reservation),owner,record.get('reservationRef',''),'qualified reservation',checks)
        history.validate_commit(str(root),str(implementation),owner,record.get('completionRef',''),'qualified implementation',checks)
        history.validate_reservation_snapshot(str(root),record,checks)
        if checks:return set()
        if len(git('show','-s','--format=%P',implementation).split())<2:return set()
        git('merge-base','--is-ancestor',reservation,implementation)
        git('merge-base','--is-ancestor',implementation,before_ref)
        required={f'evidence/{owner}/{name}' for name in ('summary.md','handoff.md','commands.txt','test-results/README.md')}
        if not required.issubset(changed):return set()
        # Supply the actual node's four blobs to the established evidence parser.
        with tempfile.TemporaryDirectory() as directory:
            for path in required:
                target=Path(directory)/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(git('show',f'{after_ref}:{path}'),encoding='utf8')
            history.RECOVERY.validate_structured_completion_evidence(directory,owner,implementation,required,checks)
        if checks:return set()
    else:
        if old_ledger!=new_ledger or len(new_entries)!=1:return set()
        if transitions.registry_without_task(old_active,owner)!=transitions.registry_without_task(new_active,owner):return set()
        if transitions.entry_without_fields(entry,{'status','agentRole','baseSha'})!=transitions.entry_without_fields(new_entries[0],{'status','agentRole','baseSha'}):return set()
        if new_entries[0].get('status')!=new_state or new_entries[0].get('baseSha')!=before_ref:return set()
        history.stable_spec_matches(owner,new_entries[0],new_spec,new_body,checks,reservation=True)
        if checks:return set()
    conventional={'api-samples/README.md','assumptions.md','changed-files.md','commands.txt','follow-ups.md','handoff.md','migration-report/README.md','performance/README.md','risks.md','rollback-verification/README.md','scope.md','screenshots/README.md','security/README.md','summary.md','test-results/README.md'}
    allowed=shared|{task_path}|{f'evidence/{owner}/{name}' for name in conventional}
    allowed.update(qualified_lifecycle_archive_paths(owner,before_ref,after_ref,changed,git))
    if any(path not in allowed for path in changed):return set()
    message=git('show','-s','--format=%B',after_ref)
    if not history.exact_token(message,owner):return set()
    return changed


def validate_qualified_source(root, plan, execution, configuration, defs, prefix, errors, record_refs=None):
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
        ignored = set(git('ls-files','--others','--ignored','--exclude-standard').splitlines())
        referenced = set(record_refs or ())
        identity = (execution.get('environmentCaptured') or {}).get('acceptanceProfile')
        profile = identity.get('id') if isinstance(identity,dict) else None
        if profile in PROFILE_SCOPES:
            poc_task = f"POC-{int(plan['pocId'].split('-')[-1]):03d}"
            referenced.add(profile_index_ref(poc_task,profile))
        def collect(value):
            if isinstance(value,dict):
                for item in value.values(): collect(item)
            elif isinstance(value,list):
                for item in value: collect(item)
            elif isinstance(value,str) and lexical_ref(value,prefix):
                referenced.add(value)
        collect(execution)
        collect(configuration)
        domains = configuration.get('numericDomainReviewRefs',{}) if isinstance(configuration,dict) else {}
        if isinstance(domains,dict):
            for ref in domains.values():
                path = existing_ref(root,ref,prefix)
                if path is not None: collect(load(path))
        for ref in list(referenced):
            path = existing_ref(root,ref,prefix)
            if path is not None:
                referenced.add(path.relative_to(root.resolve()).as_posix())
        if referenced & ignored:
            raise ValueError('referenced qualified evidence must not be ignored and untracked: '+', '.join(sorted(referenced & ignored)))
        if referenced & set(untracked):
            raise ValueError('referenced qualified evidence must be tracked: '+', '.join(sorted(referenced & set(untracked))))
        poc_task = f"POC-{int(plan['pocId'].split('-')[-1]):03d}"
        own_prefixes = tuple(str(Path(profile_index_ref(task,profile)).parent).replace('\\','/')+'/'
                             for task in sorted(TASKS) for profile in PROFILE_SCOPES)
        phase_paths = {f'specs/tasks/{owner}.md' for owner in (poc_task,'GZ-020')}
        def phase_only(before, after):
            # Authenticate the existing document, permitting only the terminal status transition.
            pattern = r'\A(---\r?\n(?:(?!^---).)*?^status: )in_progress(\r?\n(?:(?!^---).)*?^---(?:\r?\n|\Z).*)\Z'
            match = re.fullmatch(pattern,before,re.MULTILINE|re.DOTALL)
            header = before.split('---',2)[1] if before.startswith('---') else ''
            return (match is not None and len(re.findall(r'^status:',header,re.MULTILINE)) == 1
                    and after == match[1]+'completed'+match[2])
        cursor=commit
        deliveries=[]
        for node in git('rev-list','--first-parent','--reverse',f'{commit}..{context}').splitlines():
            paths=git('diff','--name-only',cursor,node).splitlines()
            deliveries.append((paths,cursor,node))
            cursor=node
        if cursor!=context:deliveries.append((changed,commit,context))
        deliveries.append((dirty,context,None))
        for paths, before_ref, after_ref in deliveries:
            authenticated=qualified_lifecycle_delta_paths(root,before_ref,after_ref,git) if after_ref else set()
            for path in paths:
                # Existing tested-byte semantics permit restored implementation bytes.
                # Lifecycle metadata must still authenticate every historical edge.
                if after_ref and path not in changed and not path.startswith(('specs/coordination/','specs/tasks/','evidence/')):
                    continue
                if path in authenticated:
                    continue
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
    except (subprocess.CalledProcessError,ValueError,OSError,yaml.YAMLError,KeyError,TypeError,AttributeError,zlib.error) as exc:
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


def safe_generator_relative_path(value):
    if not isinstance(value,str) or not value or value.strip()!=value or value.startswith('/') or any(ord(char)<32 or ord(char)==127 or char in '\\:<>"|?*' for char in value):
        return False
    reserved={'CON','PRN','AUX','NUL'}|{f'{prefix}{number}' for prefix in ('COM','LPT') for number in range(1,10)}
    return all(part and part not in ('.','..') and not part.endswith((' ','.')) and part.split('.')[0].upper() not in reserved for part in value.split('/'))


def validate_qualified_hierarchy_sandbox(root, plan, execution, defs, prefix, status, errors):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-05' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('local-v1'):
        return
    label=f"qualified local hierarchy sandbox {plan['taskId']}"
    capture=env.get('syntheticHierarchySandbox')
    validate_schema(capture,defs.get('localHierarchySandboxCapture',{}),label,errors)
    manifest=env.get('synthetic_hierarchy_manifest')
    generator=manifest.get('generator') if isinstance(manifest,dict) else None
    root_path=generator.get('rootPath') if isinstance(generator,dict) else None
    if not safe_generator_relative_path(root_path):
        errors.append(f'{label}: generator rootPath must be a normalized safe relative sandbox path')
    if not isinstance(capture,dict):return
    boundary=capture.get('boundary')
    resources=[r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-METADATA-SCALE']
    ref=capture.get('configurationRef')
    if len(resources)!=1 or ref!=resources[0].get('configurationRef'):
        errors.append(f'{label}: selected independently approved RES-METADATA-SCALE configuration required');return
    path=existing_ref(root,ref,prefix)
    if path is None:
        errors.append(f'{label}: selected-slot controlled mount configuration must exist');return
    try:record=load(path)
    except (OSError,yaml.YAMLError,ValueError):
        errors.append(f'{label}: controlled mount configuration must be readable');return
    config=record.get('configuration') if isinstance(record,dict) else None
    approved=config.get('syntheticHierarchySandbox') if isinstance(config,dict) else None
    validate_schema(approved,defs.get('localHierarchySandboxBoundary',{}),label+'/approved boundary',errors)
    if not isinstance(boundary,dict) or boundary!=approved or boundary.get('rootPath')!=root_path or any(not recorded_text(boundary.get(key)) for key in ('sandboxId','mountId','physicalHostId')):
        errors.append(f'{label}: exact generator root and concrete controlled disposable mount identity must match approved resource boundary')


def retained_metadata_chunks(path, consume_physical, decode_gzip=False):
    """Bound decoded output while hashing the exact retained bytes in the same read."""
    decoder=zlib.decompressobj(31) if decode_gzip else None
    try:
        with path.open('rb') as stream:
            for physical in iter(lambda: stream.read(ARTIFACT_CHUNK_BYTES),b''):
                consume_physical(physical)
                if decoder is None:
                    yield physical;continue
                pending=physical
                while pending:
                    decoded=decoder.decompress(pending,ARTIFACT_CHUNK_BYTES)
                    pending=decoder.unconsumed_tail
                    if decoder.unused_data:raise OSError('metadata gzip must contain exactly one member without trailing bytes')
                    if decoded:yield decoded
        if decoder is not None and not decoder.eof:raise OSError('metadata gzip is incomplete')
    except zlib.error as exc:
        raise OSError('metadata gzip is malformed or has an invalid checksum') from exc


def streamed_metadata_records(path,schema):
    """Read projected JSONL metadata with bounded line memory; never materialize the manifest."""
    validator=jsonschema.Draft202012Validator(schema);digest=hashlib.sha256();count=0
    def fields(pairs):
        if len({key for key,_ in pairs})!=len(pairs):raise ValueError('duplicate metadata fields')
        return dict(pairs)
    if path.name.endswith('.jsonl.gz'):
        line=bytearray()
        for chunk in retained_metadata_chunks(path,digest.update,path.name.endswith('.jsonl.gz')):
            offset=0
            while offset<len(chunk):
                end=chunk.find(b'\n',offset);end=len(chunk) if end<0 else end+1
                if len(line)+end-offset>ARTIFACT_CHUNK_BYTES:raise ValueError('metadata record exceeds bounded line representation')
                line.extend(chunk[offset:end]);offset=end
                if line[-1:]==b'\n':
                    record=json.loads(line,object_pairs_hook=fields);validator.validate(record);count+=1;line.clear()
                    yield record
        if line:
            record=json.loads(line,object_pairs_hook=fields);validator.validate(record);count+=1
            yield record
        return count,'sha256:'+digest.hexdigest()

    with path.open('rb') as stream:
        while True:
            line=stream.readline(ARTIFACT_CHUNK_BYTES+1)
            if not line:break
            if len(line)>ARTIFACT_CHUNK_BYTES:raise ValueError('metadata record exceeds bounded line representation')
            digest.update(line);record=json.loads(line,object_pairs_hook=fields);validator.validate(record);count+=1
            yield record
    return count,'sha256:'+digest.hexdigest()


def derive_metadata_memory_counter(root,execution,prefix,report,policy,row,defs,label,errors,cache,paths):
    """Derive a counter from retained native OS bytes, never from the aggregate claim."""
    before=len(errors)
    capture=selected_observation(root,execution,prefix,row.get('counterCaptureRef'),defs,'metadataMemoryCounterCapture',label,errors,cache)
    if capture is None or len(errors)!=before:return
    expected={k:report[k] for k in ('configurationRef','acceptanceProfile','subjectVersion','inputSamples','manifestId','scannerBuild','scanId','processId','collectorBuild','nativeProcessId','counterFormat')}
    expected.update(observedAt=row['observedAt'],toolBuild=policy['collectorBuild'])
    if any(capture.get(k)!=v for k,v in expected.items()) or capture['exitCode']!=0 or capture['collectorProcessId']==policy['nativeProcessId'] or not recorded_text(policy['collectorBuild']) or any(not recorded_text(a) for a in policy['collectorCommandArgs']):
        errors.append(f'{label}: native counter capture must bind exact scanner PID, collector build/process, scope, sample time and successful native exit');return
    if capture['commandArgs']!=policy['collectorCommandArgs']+['--pid',str(policy['nativeProcessId']),'--output',capture['counterRef']]:
        errors.append(f'{label}: executed collector argv must equal approved collector and exact native PID/output');return
    env=execution.get('environmentCaptured') or {};retained=[]
    for ref,kind in ((row['counterCaptureRef'],'measurement_output'),(capture['counterRef'],'command_output')):
        path=existing_ref(root,ref,prefix);records=[r for r in env.get('rawExecutionArtifacts') or [] if isinstance(r,dict) and r.get('ref')==ref]
        if path is None or ref not in (execution.get('rawOutputRefs') or []) or len(records)!=1 or records[0].get('artifactType')!=kind:
            errors.append(f'{label}: selected typed native counter capture and OS output required');return
        facts=inspect_artifact(path,cache)
        if not 0<facts['size']<=65536 or records[0].get('byteCount')!=facts['size'] or records[0].get('sha256')!=facts['sha256'] or any(path.samefile(peer) for peer in paths):
            errors.append(f'{label}: independent bounded counter bytes must match their retained physical hash/size');return
        paths.append(path);retained.append(path)
    try:
        if policy['counterFormat']=='linux_proc_status':
            text=retained[1].read_text(encoding='utf8');values={}
            for key in ('Pid','VmHWM','VmRSS'):
                lines=re.findall(r'^'+key+r':[^\r\n]*$',text,re.MULTILINE)
                if len(lines)!=1:raise ValueError('missing/duplicate OS counter')
                match=re.fullmatch(key+r':[ \t]*([0-9]{1,16})'+(r'[ \t]+kB' if key!='Pid' else '')+r'[ \t]*',lines[0])
                if match is None:raise ValueError('malformed OS counter')
                values[key]=int(match.group(1))
            pid,peak,resident=values['Pid'],values['VmHWM']*1024,values['VmRSS']*1024
        else:
            value=bounded_evaluator_json(root,execution,prefix,capture['counterRef'],'command_output',defs,'metadataWindowsMemoryCounter',label,errors,cache,65536)
            if value is None:return
            pid,peak,resident=value['ProcessId'],value['PeakWorkingSetSize'],value['WorkingSetSize']
        if pid!=policy['nativeProcessId'] or not 0<=resident<=peak<=2**60 or row['peakResidentBytes']!=peak:raise ValueError('OS/aggregate counter mismatch')
    except (OSError,UnicodeError,ValueError,OverflowError,KeyError):
        errors.append(f'{label}: process peak bytes must derive unique retained native Pid/VmHWM/VmRSS or Windows process counters');return
    return peak


def validate_qualified_metadata_resources(root,plan,execution,prefix,window,defs,errors,cache,resource,scan_policy,intervals):
    label=f"qualified metadata scan resources {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('metadataResourceRef'),defs,'metadataResourceObservation',label,errors,cache)
    path=existing_ref(root,resource['configurationRef'],prefix)
    try:policy=load(path).get('configuration',{}).get('metadataResourcePolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('metadataResourcePolicy',{}),label+'/approved resource policy',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    bound=('scannerBuild','scanId','manifestId','processId','collectorBuild','nativeProcessId','counterFormat','collectorCommandArgs','sourceIdentity','quotaDocumentRef','quotaDocumentSha256')
    if any(report[k]!=v for k,v in expected.items()) or any(report[k]!=policy[k] for k in bound) or any(policy[k]!=scan_policy[k] for k in ('scannerBuild','scanId','manifestId')):
        errors.append(f'{label}: exact approved source adapter/version, scan, process, collector, input and profile identities required');return
    quota_path=existing_ref(root,policy['quotaDocumentRef'],prefix)
    if quota_path is None:
        errors.append(f'{label}: approved selected-slot quota documentation required');return
    try:
        if inspect_artifact(quota_path,cache,textual=True)['sha256']!=policy['quotaDocumentSha256']:raise ValueError('quota documentation hash mismatch')
    except (OSError,ValueError,UnicodeError,yaml.YAMLError):
        errors.append(f'{label}: readable immutable approved quota documentation required');return
    quota=qualified_observation_report(quota_path,defs,'metadataQuotaDocument',label+'/quota documentation',errors,cache)
    if len(errors)!=before or not isinstance(quota,dict):return
    if quota['sourceIdentity']!=policy['sourceIdentity'] or not all(recorded_text(quota[k]) for k in ('resetSemantics','backoffStrategy','documentationRevision')) or not ai_finite(quota['requestLimit']) or not ai_finite(quota['periodSeconds']) or quota['periodSeconds']<=0 or not ai_finite(quota['maximumBackoffSeconds']):
        errors.append(f'{label}: documented adapter quota must retain exact source/version and finite reset/backoff semantics');return
    rows=report['memorySamples'];times=[utc(r['observedAt']) for r in rows]
    if any(t is None for t in times) or window is None or times!=sorted(times) or not window[0]<=times[0]<=intervals[0][0] or not intervals[-1][1]<=times[-1]<=window[1] or times[0]>=times[-1] or any(any(row[k]!=policy[k] for k in ('processId','scanId','scannerBuild')) for row in rows):
        errors.append(f'{label}: the same scanner process peak-resident counter must bracket the complete scan workload within its UTC execution');return
    counter_paths=[existing_ref(root,env['metadataResourceRef'],prefix)];counters=[]
    for row in rows:
        value=derive_metadata_memory_counter(root,execution,prefix,report,policy,row,defs,label,errors,cache,counter_paths)
        if value is None:return
        counters.append(value)
    if counters!=sorted(counters) or counters[-1]<=0 or not all(ai_finite(c) for c in counters):
        errors.append(f'{label}: cumulative OS process peak memory must be positive and never reset inside the measured scan');return
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    try:derived=(('source_api_quota',quota['requestLimit']*60/quota['periodSeconds']),('memory_peak',counters[-1]/(1024*1024)))
    except (OverflowError,ZeroDivisionError):
        errors.append(f'{label}: resource metrics must have a representable finite derived value');return
    if any(not ai_finite(value) for _,value in derived):
        errors.append(f'{label}: resource metrics must have a representable finite derived value');return
    for metric,value in derived:
        if not ai_finite(actual.get(metric)) or not math.isclose(actual[metric],value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive the retained approved quota or observed process peak counter in its declared unit')


def validate_qualified_metadata_scan(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-05' or status!='pass':return
    label=f"qualified metadata scan {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('metadataScanRef'),defs,'metadataScanObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-METADATA-SCALE'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('metadataScanPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('metadataScanPolicy',{}),label+'/approved scan',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    sample=next((s for s in execution.get('samples') or [] if s.get('id')==policy['baselineInputSampleId']),None);input_record=next((r for r in env.get('inputSampleArtifacts') or [] if isinstance(r,dict) and r.get('sampleId')==policy['baselineInputSampleId']),None)
    if any(report[k]!=v for k,v in expected.items()) or policy['scannerBuild']!=expected['subjectVersion'] or any(report[k]!=policy[k] for k in ('manifestId','scannerBuild')) or sample is None or input_record is None or policy['manifestId']!=sample['immutableId'] or policy['baseline']['ref']!=input_record.get('inputArtifactRef') or policy['baseline']['sha256']!=sample['checksum']:
        errors.append(f'{label}: exact approved immutable metadata input/resource/scanner/profile identities required');return
    if env.get('acceptanceProfile')==profile_identity('local-v1'):
        captured=env.get('synthetic_hierarchy_manifest');generator=captured.get('generator') if isinstance(captured,dict) else None
        if policy.get('hierarchyGenerator')!=generator:errors.append(f'{label}: approved complete hierarchy generator must bind the retained baseline manifest')
    phases=(report['enumeration'],report['changeStream'],report['incremental']);intervals=[]
    for phase in phases:
        first,last=utc(phase['startedAt']),utc(phase['finishedAt'])
        if first is None or last is None or window is None or not window[0]<=first<last<=window[1]:errors.append(f'{label}: positive measured UTC enumeration/change/traversal intervals within execution required');return
        intervals.append((first,last,(last-first).total_seconds()))
    if intervals[0][1]>intervals[1][0] or intervals[1][1]>intervals[2][0] or phases[0]['scanId']!=policy['scanId'] or any(p['changeSetId']!=policy['changeSetId'] for p in phases[1:]):errors.append(f'{label}: baseline enumeration, controlled change set and incremental traversal must bind ordered approved runs')
    validate_qualified_metadata_resources(root,plan,execution,prefix,window,defs,errors,cache,resource,policy,intervals)
    handle=tempfile.NamedTemporaryFile(prefix='guize-metadata-',suffix='.sqlite',delete=False);database=Path(handle.name);handle.close();connection=None
    try:
        connection=sqlite3.connect(str(database));connection.execute('PRAGMA journal_mode=OFF');connection.execute('PRAGMA temp_store=FILE');connection.execute('PRAGMA cache_size=-8192')
        connection.executescript('CREATE TABLE baseline(objectId TEXT PRIMARY KEY,kind TEXT,versionId TEXT,depth INTEGER,fileSizeBytes INTEGER);CREATE TABLE enumerated(objectId TEXT PRIMARY KEY,kind TEXT,versionId TEXT,depth INTEGER,fileSizeBytes INTEGER);CREATE TABLE expected(eventId TEXT PRIMARY KEY,sequence INTEGER UNIQUE,objectId TEXT,operation TEXT,beforeVersion TEXT,afterVersion TEXT);CREATE TABLE observed(eventId TEXT PRIMARY KEY,sequence INTEGER UNIQUE,objectId TEXT,operation TEXT,beforeVersion TEXT,afterVersion TEXT);CREATE TABLE applied(eventId TEXT PRIMARY KEY);CREATE TABLE traversed(objectId TEXT PRIMARY KEY);CREATE TABLE current(objectId TEXT PRIMARY KEY,versionId TEXT);CREATE TABLE post_scan(objectId TEXT PRIMARY KEY,versionId TEXT);')
        def ingest(table,descriptor,schema_name,columns,input_manifest=False):
            path=existing_ref(root,descriptor['ref'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==descriptor['ref']]
            if path is None or not input_manifest and (len(records)!=1 or records[0].get('artifactType')!='command_output' or descriptor['ref'] not in (execution.get('rawOutputRefs') or [])):raise ValueError('selected-slot typed retained metadata record stream required')
            inspected=inspect_artifact(path,cache,textual=True)
            if inspected['sha256']!=descriptor['sha256']:raise ValueError('metadata stream must bind exact approved/observed immutable bytes')
            iterator=streamed_metadata_records(path,defs[schema_name]);observed_count=0;previous=None
            while True:
                try:record=next(iterator)
                except StopIteration as terminal:
                    count,digest=terminal.value;break
                if schema_name=='metadataObservedChangeRecord':
                    at=utc(record['observedAt'])
                    if record['sequence']!=observed_count+1 or at is None or not intervals[1][0]<=at<=intervals[1][1] or at>intervals[2][0] or previous is not None and at<previous:raise ValueError('retained controlled changes need the approved actual sequence and ordered observed timestamps before replay')
                    previous=at
                connection.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in columns)+')',tuple(record[k] for k in columns));observed_count+=1
            if count!=descriptor['count'] or count!=observed_count or digest!=descriptor['sha256']:raise ValueError('actual streamed record count/hash must match the retained observation')
            return count
        object_columns=('objectId','kind','versionId','depth','fileSizeBytes');event_columns=('eventId','sequence','objectId','operation','beforeVersion','afterVersion')
        baseline_count=ingest('baseline',policy['baseline'],'metadataObjectRecord',object_columns,True);enumerated_count=ingest('enumerated',phases[0]['objects'],'metadataObjectRecord',object_columns);expected_count=ingest('expected',policy['expectedChanges'],'metadataChangeRecord',event_columns);event_count=ingest('observed',phases[1]['events'],'metadataObservedChangeRecord',event_columns);ingest('applied',phases[2]['appliedEvents'],'metadataAppliedEventRecord',('eventId',));ingest('traversed',phases[2]['traversedObjects'],'metadataTraversedObjectRecord',('objectId',))
        post_scan=phases[2]['postScanObjects'];post_path=existing_ref(root,post_scan['ref'],prefix);post_at=utc(post_scan['observedAt'])
        if post_path is None or post_at is None or not intervals[2][1]<=post_at<=window[1]:raise ValueError('complete post-scan catalogue must be independently observed after incremental traversal within execution')
        other_streams=(policy['baseline'],policy['expectedChanges'],phases[0]['objects'],phases[1]['events'],phases[2]['appliedEvents'],phases[2]['traversedObjects'])
        if any(post_path.samefile(existing_ref(root,descriptor['ref'],prefix)) for descriptor in other_streams):raise ValueError('post-scan object/version catalogue must retain a separate independently observed physical file')
        ingest('post_scan',post_scan,'metadataObjectVersionRecord',('objectId','versionId'))
        def mismatch(first,second,columns='*'):
            return connection.execute('SELECT '+columns+' FROM '+first+' EXCEPT SELECT '+columns+' FROM '+second+' LIMIT 1').fetchone() is not None or connection.execute('SELECT '+columns+' FROM '+second+' EXCEPT SELECT '+columns+' FROM '+first+' LIMIT 1').fetchone() is not None
        if baseline_count==0 or mismatch('baseline','enumerated') or mismatch('expected','observed') or mismatch('expected','applied','eventId'):raise ValueError('enumeration and replay must cover the complete approved object/change manifests exactly once')
        if connection.execute('SELECT min(sequence),max(sequence),count(*) FROM expected').fetchone()!=(1,expected_count,expected_count) or {r[0] for r in connection.execute('SELECT DISTINCT operation FROM expected')}!={'create','update','delete'}:raise ValueError('approved deterministic create/update/delete stream requires a complete ordered sequence')
        connection.execute('INSERT INTO current SELECT objectId,versionId FROM baseline')
        for object_id,operation,before_version,after_version in connection.execute('SELECT objectId,operation,beforeVersion,afterVersion FROM expected ORDER BY sequence'):
            existing=connection.execute('SELECT versionId FROM current WHERE objectId=?',(object_id,)).fetchone();version=existing[0] if existing else 'absent'
            if version!=before_version or not (before_version=='absent' and after_version!='absent' if operation=='create' else before_version!='absent' and after_version=='absent' if operation=='delete' else before_version!='absent' and after_version!='absent' and before_version!=after_version):raise ValueError('controlled changes must bind valid actual object-version transitions')
            connection.execute('DELETE FROM current WHERE objectId=?',(object_id,))
            if after_version!='absent':connection.execute('INSERT INTO current VALUES (?,?)',(object_id,after_version))
        if mismatch('current','post_scan'):raise ValueError('complete independently observed post-scan object/version state must exactly equal the baseline plus controlled create/update/delete transitions')
        if connection.execute("SELECT objectId FROM traversed WHERE objectId NOT IN (SELECT objectId FROM baseline UNION SELECT objectId FROM expected WHERE operation='create') LIMIT 1").fetchone():raise ValueError('incremental traversal may only visit governed baseline/created object identities')
        counts=connection.execute("SELECT sum(kind='file'),sum(kind='directory'),max(depth),sum(CASE WHEN kind='file' THEN fileSizeBytes ELSE 0 END) FROM baseline").fetchone();actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
        if not counts[0]:raise ValueError('average file size requires a nonempty approved file population')
        derived=dict(enumeration_rate=enumerated_count/intervals[0][2],source_change_frequency=event_count*3600/intervals[1][2],incremental_scan_cost=intervals[2][2],file_count=counts[0],directory_count=counts[1],directory_depth_max=counts[2],average_file_size=counts[3]/counts[0])
        for metric,value in derived.items():
            if not ai_finite(actual.get(metric)) or not math.isclose(actual[metric],value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive actual complete streamed object/event counts and measured traversal timestamps')
        validate_qualified_metadata_profiles(root,plan,execution,prefix,window,defs,errors,cache,resource,policy,connection)
    except (OSError,ValueError,UnicodeError,OverflowError,sqlite3.Error,jsonschema.ValidationError) as failure:errors.append(f'{label}: invalid retained metadata observations ({type(failure).__name__})')
    finally:
        if connection is not None:connection.close()
        database.unlink(missing_ok=True)


def validate_qualified_metadata_profiles(root,plan,execution,prefix,window,defs,errors,cache,resource,scan_policy,connection):
    label=f"qualified metadata profiling {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('metadataProfilingRef'),defs,'metadataProfilingObservation',label,errors,cache)
    path=existing_ref(root,resource['configurationRef'],prefix)
    try:config=load(path).get('configuration',{}) if path else {};policy=config.get('metadataProfilingPolicy');resources=config.get('metadataResourcePolicy')
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=resources=None
    validate_schema(policy,defs.get('metadataProfilingPolicy',{}),label+'/approved policy',errors)
    if report is None or len(errors)!=before:return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],manifestId=scan_policy['manifestId'],scannerBuild=scan_policy['scannerBuild'],sourceIdentity=policy['sourceIdentity'])
    if any(report[k]!=v for k,v in expected.items()) or any(policy[k]!=scan_policy[k] for k in ('manifestId','scannerBuild')) or not isinstance(resources,dict) or policy['sourceIdentity']!=resources.get('sourceIdentity') or report['rangeDisposition']!=policy['rangeDisposition'] or report['validatorKind']!=policy['validatorKind']:errors.append(f'{label}: exact approved source/adapter/build/immutable population/profile required');return
    columns=('objectId','kind','versionId','depth','fileSizeBytes','name','path','modifiedAt');basic=columns[:5]
    connection.executescript('CREATE TABLE profile_approved(objectId TEXT PRIMARY KEY,kind TEXT,versionId TEXT,depth INTEGER,fileSizeBytes INTEGER,name TEXT,path TEXT,modifiedAt TEXT);CREATE TABLE profile_observed AS SELECT * FROM profile_approved;CREATE UNIQUE INDEX profile_observed_id ON profile_observed(objectId);CREATE TABLE profile_page AS SELECT * FROM profile_approved;CREATE UNIQUE INDEX profile_page_id ON profile_page(objectId);')
    def records(descriptor,schema_name):
        path=existing_ref(root,descriptor['ref'],prefix);matches=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==descriptor['ref']]
        if path is None or len(matches)!=1 or matches[0].get('artifactType')!='command_output' or descriptor['ref'] not in (execution.get('rawOutputRefs') or []):raise ValueError('exact selected-slot typed record stream required')
        iterator=streamed_metadata_records(path,defs[schema_name]);count=0
        while True:
            try:row=next(iterator)
            except StopIteration as terminal:
                total,digest=terminal.value;break
            count+=1;yield row
        if total!=descriptor['count'] or total!=count or digest!=descriptor['sha256']:raise ValueError('complete retained record stream must bind count/hash')
    def ingest(table,descriptor):
        for row in records(descriptor,'metadataProfiledObjectRecord'):
            parts=row['path'].split('/')
            if any(not p or p in ('.','..') for p in parts) or parts[-1]!=row['name'] or '/' in row['name'] or '\x00' in row['name'] or len(parts)!=row['depth'] or utc(row['modifiedAt']) is None:raise ValueError('actual filename/path/depth/UTC semantics required')
            connection.execute('INSERT INTO '+table+' VALUES (?,?,?,?,?,?,?,?)',tuple(row[k] for k in columns))
    def differs(a,b,cols=columns):
        selection=','.join(cols)
        return connection.execute('SELECT '+selection+' FROM '+a+' EXCEPT SELECT '+selection+' FROM '+b+' LIMIT 1').fetchone() is not None or connection.execute('SELECT '+selection+' FROM '+b+' EXCEPT SELECT '+selection+' FROM '+a+' LIMIT 1').fetchone() is not None
    ingest('profile_approved',policy['filenameInput']);ingest('profile_observed',report['filenameObjects'])
    if differs('profile_approved','baseline',basic) or differs('profile_observed','profile_approved') or connection.execute('SELECT count(*) FROM profile_approved').fetchone()[0]==0:raise ValueError('filename observation must cover the complete exact immutable baseline population')
    approved_path=existing_ref(root,policy['filenameInput']['ref'],prefix);observed_path=existing_ref(root,report['filenameObjects']['ref'],prefix)
    if approved_path.samefile(observed_path):raise ValueError('filename output must retain independently observed bytes')
    categories=policy['extensionCategories']
    if len(categories)!=len(set(categories)) or any(c!=c.lower() or not recorded_text(c) or c in ('none','other') for c in categories):raise ValueError('distinct approved extension categories required')
    distributions={k:{} for k in ('nameLength','characterSet','extension','pathDepth')}
    for kind,name,depth in connection.execute('SELECT kind,name,depth FROM profile_observed'):
        suffix=name.rsplit('.',1)[1].lower() if '.' in name and not name.startswith('.') else '';extension=suffix if suffix in categories else 'other' if suffix else 'none'
        values=dict(nameLength=str(len(name)),characterSet='ascii' if name.isascii() else 'non_ascii',pathDepth=str(depth))
        if kind=='file':values['extension']=extension
        for k,v in values.items():distributions[k][v]=distributions[k].get(v,0)+1
    if report['filenameDistributions']!=distributions:raise ValueError('name-length/character-set/approved-extension/path-depth distributions must derive the complete filename stream')
    run_id=None;run_ids=set();request_ids=set();cursor=None;cursors=set();last=None
    def finish_run():
        if cursor is not None or differs('profile_page','profile_approved'):raise ValueError('every repeated provider listing must terminate and cover exact identities/versions/names/timestamps')
        connection.execute('DELETE FROM profile_page')
    for row in records(report['providerPages'],'metadataProviderPageRecord'):
        if row['runId']!=run_id:
            if run_id is not None:finish_run()
            if row['runId'] in run_ids:raise ValueError('listing runs must be distinct contiguous observations')
            run_id=row['runId'];run_ids.add(run_id);cursor=None;cursors=set()
        first,end,provider_at=(utc(row[k]) for k in ('requestedAt','finishedAt','providerTimestamp'))
        if any(t is None for t in (first,end,provider_at)) or window is None or not window[0]<=first<=end<=window[1] or last is not None and first<last or row['sourceIdentity']!=policy['sourceIdentity'] or row['endpointURL']!=policy['endpointURL'] or row['statusCode']!=200 or row['requestId'] in request_ids or row['requestCursor']!=cursor or row['nextCursor'] is not None and (not recorded_text(row['nextCursor']) or row['nextCursor'] in cursors):raise ValueError('provider pagination must bind unique actual requests/cursors, source endpoint and UTC behavior')
        last=end;request_ids.add(row['requestId']);cursor=row['nextCursor'];cursors.add(cursor);ingest('profile_page',row['objects'])
    if run_id is None or len(run_ids)<policy['minimumListingRuns']:raise ValueError('at least the approved number of complete repeated provider listings required')
    finish_run();identity=connection.execute('SELECT kind,versionId,fileSizeBytes FROM baseline WHERE objectId=?',(policy['probeObjectId'],)).fetchone()
    updates=list(connection.execute("SELECT beforeVersion,afterVersion FROM expected WHERE objectId=? AND operation='update'",(policy['probeObjectId'],)))
    if identity is None or identity[:2]!=('file',policy['baselineVersion']) or (policy['baselineVersion'],policy['updatedVersion']) not in updates:raise ValueError('Range/validator probe must bind governed baseline and actual controlled object update')
    payloads=[]
    for key in ('baselinePayload','updatedPayload'):
        descriptor=policy[key];path=existing_ref(root,descriptor['ref'],prefix);matches=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==descriptor['ref']]
        if path is None or len(matches)!=1 or matches[0].get('artifactType')!='produced_media' or not 1<=path.stat().st_size<=65536 or inspect_artifact(path,cache)['sha256']!=descriptor['sha256']:raise ValueError('bounded approved object-version probe bytes required')
        payloads.append(path.read_bytes())
    if len(payloads[0])!=identity[2]:raise ValueError('baseline Range probe bytes must bind actual complete approved object metadata size')
    if payloads[0]==payloads[1]:raise ValueError('controlled update must exercise changed probe content')
    rows=report['probes'];names={'unchanged_first','unchanged_second','bounded','unsatisfiable','changed'}
    if {r['case'] for r in rows}!=names or len({r['requestId'] for r in rows})!=5:raise ValueError('exact unique before/repeat/Range/unsupported/update probes required')
    for row in rows:
        changed=row['case']=='changed';content=payloads[int(changed)];version=policy['updatedVersion'] if changed else policy['baselineVersion'];at=utc(row['observedAt']);ref=row['responseRef'];path=existing_ref(root,ref,prefix);matches=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==ref]
        if row['objectId']!=policy['probeObjectId'] or row['objectVersion']!=version or at is None or window is None or not window[0]<=at<=window[1] or path is None or len(matches)!=1 or matches[0].get('artifactType')!='produced_media' or path.stat().st_size>65536:raise ValueError('actual source/version/time/response bytes required')
        info=inspect_artifact(path,cache)
        if info['sha256']!=row['responseSha256'] or info['size']!=row['responseByteCount']:raise ValueError('response body byte count/hash mismatch')
        body=path.read_bytes();case=row['case'];expected_range='bytes=0-1' if case=='bounded' else 'bytes='+str(len(content))+'-' if case=='unsatisfiable' else ''
        if row['requestRange']!=expected_range:raise ValueError('actual bounded/unsatisfiable/full Range request required')
        if case in ('bounded','unsatisfiable'):
            disposition=policy['rangeDisposition']
            expected_status=206 if case=='bounded' else 416
            expected_body=content[:2] if case=='bounded' else b'';expected_header=f'bytes 0-{min(1,len(content)-1)}/{len(content)}' if case=='bounded' else f'bytes */{len(content)}'
            good=(row['statusCode']==expected_status and body==expected_body and row['contentRange']==expected_header) if disposition=='supported' else (row['statusCode']==200 and body==content and row['contentRange']=='') if disposition=='ignored' else (row['statusCode'] in (400,405,501) and body==b'' and row['contentRange']=='')
        else:good=row['statusCode']==200 and body==content and row['contentRange']==''
        if not good:raise ValueError('Range disposition must derive actual status/header/body behavior, including truthful unsupported support')
        if policy['validatorKind']=='etag' and (not recorded_text(row['etag']) or row['versionValidator']) or policy['validatorKind']=='version_token' and (row['etag'] or row['versionValidator']!=version) or policy['validatorKind']=='none' and (row['etag'] or row['versionValidator']):raise ValueError('validator kind must match retained HTTP ETag/equivalent version/absence observations')
    first,second,changed=(next(r for r in rows if r['case']==k) for k in ('unchanged_first','unchanged_second','changed'));key='etag' if policy['validatorKind']=='etag' else 'versionValidator';available=policy['validatorKind']!='none'
    if not utc(first['observedAt'])<utc(second['observedAt'])<utc(changed['observedAt']) or report['validatorStableOnUnchanged'] is not (available and first[key]==second[key]) or report['validatorChangedOnUpdate'] is not (available and second[key]!=changed[key]):raise ValueError('validator stability/change results must derive before/repeat/update response observations')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if any(actual.get(k) is not True for k in ('filename_characteristics_profiled','provider_characteristics_profiled','range_support_profiled','etag_behavior_profiled')):raise ValueError('four profiling gates must agree with retained derived observations')


def validate_qualified_passthrough_identity(root, plan, execution, defs, prefix, status, errors):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-01' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('production'):
        return
    label=f"qualified production passthrough identity {plan['taskId']}"
    capture=env.get('productionPassthroughIdentity')
    validate_schema(capture,defs.get('productionPassthroughCapture',{}),label,errors)
    if not isinstance(capture,dict):return
    resources=[r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-A380-ESXI67']
    ref=capture.get('configurationRef')
    if len(resources)!=1 or ref!=resources[0].get('configurationRef'):
        errors.append(f'{label}: exact selected RES-A380-ESXI67 configuration required');return
    path=existing_ref(root,ref,prefix)
    if path is None:
        errors.append(f'{label}: approved selected-slot configuration must exist');return
    try:record=load(path)
    except (OSError,yaml.YAMLError,ValueError):
        errors.append(f'{label}: approved configuration must be readable');return
    config=record.get('configuration') if isinstance(record,dict) else None
    approved=config.get('productionPassthroughIdentity') if isinstance(config,dict) else None
    validate_schema(approved,defs.get('productionPassthroughIdentity',{}),label+'/approved identity',errors)
    identity=capture.get('identity')
    if not isinstance(identity,dict):return
    if identity!=approved or any(not recorded_text(identity.get(key)) for key in ('nodeId','physicalHostId','guestId','hypervisorBuild','gpuDeviceId','driverBuild','runtimeBuild','encoderBuild')):
        errors.append(f'{label}: concrete host/guest/GPU/build identity must exactly match approved resource configuration')
    inventory=env.get('worker_node_inventory')
    nodes=[node for node in inventory if isinstance(node,dict) and node.get('nodeId')==identity.get('nodeId')] if isinstance(inventory,list) else []
    if len(nodes)!=1 or any(nodes[0].get(key)!=value for key,value in identity.items() if key not in ('schemaVersion','resourceId')):
        errors.append(f'{label}: one exact captured A380 passthrough node must match approved hypervisor/GPU/build identity')


def validate_qualified_passthrough_firmware(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-01' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('production'):return
    label=f"qualified production passthrough firmware {plan['taskId']}";capture=env.get('productionPassthroughIdentity')
    if not isinstance(capture,dict) or not isinstance(capture.get('identity'),dict):return
    before=len(errors);report=selected_observation(root,execution,prefix,env.get('productionFirmwareRef'),defs,'passthroughFirmwareObservation',label,errors,cache)
    path=existing_ref(root,capture.get('configurationRef'),prefix)
    try:config=load(path).get('configuration',{}) if path else {};policy=config.get('passthroughFirmwarePolicy')
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('passthroughFirmwarePolicy',{}),label+'/approved firmware',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    identity=capture['identity'];device=identity.get('gpuDeviceId')
    if report['configurationRef']!=capture.get('configurationRef') or report['identity']!=identity or any(report[key]!=policy[key] for key in ('firmwareBuild','biosConfigurationId','iommuGroupId')):
        errors.append(f'{label}: exact approved host/device/build/firmware/configuration/group identities required')
    times=[utc(report[key]) for key in ('settingsCapturedAt','guestEnumeratedAt','runtimeInitializedAt')]
    if any(t is None for t in times) or window is None or not window[0]<=times[0]<=times[1]<=times[2]<=window[1]:
        errors.append(f'{label}: captured firmware must precede guest enumeration and runtime initialization within execution')
    members=report['iommuMembers'];ids=[member['deviceId'] for member in members]
    isolated=len(ids)==len(set(ids)) and set(ids)==set(policy['approvedGroupDeviceIds']) and device in ids and all(member['requiredHostDevice'] is False and member['assignedToGuest'] is True for member in members)
    allocated=report['allocatedDeviceId']==device and report['addressSpaceAllocatedBytes']>0 and report['allocationSucceeded'] is True
    initialized=device in report['enumeratedDeviceIds'] and report['runtimeReady'] is True
    derived=dict(bios_iommu_configuration_verified=report['iommuEnabled'] is True,iommu_group_isolation_verified=isolated,above_4g_enabled=report['above4gEnabled'] is True and allocated,resizable_bar_enabled=report['resizableBarEnabled'] is True and initialized)
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    for gate,observed in derived.items():
        if observed is not True or actual.get(gate) is not observed:errors.append(f'{label}: {gate} must derive selected firmware/group/allocation/enumeration observations')


def validate_qualified_passthrough_transitions(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-01' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('production'):return
    label=f"qualified passthrough transitions {plan['taskId']}";capture=env.get('productionPassthroughIdentity')
    if not isinstance(capture,dict) or not isinstance(capture.get('identity'),dict):return
    before=len(errors);validate_schema(capture,defs.get('productionPassthroughCapture',{}),label+'/selected identity',errors)
    if len(errors)!=before:return
    report=selected_observation(root,execution,prefix,env.get('passthroughTransitionRef'),defs,'passthroughTransitions',label,errors,cache)
    if report is None or len(errors)!=before:return
    identity=capture['identity'];device=identity['gpuDeviceId'];config=capture['configurationRef'];inputs={s.get('checksum') for s in execution.get('samples') or []}
    if report['identity']!=identity or report['configurationRef']!=config:errors.append(f'{label}: exact approved selected host/guest/GPU/driver/runtime/encoder configuration required')
    if {c['case'] for c in report['cases']}!={'guest_reboot','host_reboot','device_reset'}:errors.append(f'{label}: exact unique guest reboot, host reboot and device reset outcomes required');return
    seen_probes={};intervals=[]
    for row in report['cases']:
        start,end=utc(row['startedAt']),utc(row['finishedAt']);old,new=row['before'],row['after'];old_at,new_at=utc(old['observedAt']),utc(new['observedAt'])
        if any(t is None for t in (start,end,old_at,new_at)) or window is None or not window[0]<=old_at<=start<end<=new_at<=window[1] or row['manualRebuildCount']!=0:errors.append(f'{label}: retained before/transition/after UTC observations without manual rebuild required')
        else:intervals.append((start,end,row))
        kind=row['case']
        changed=(old['guestBootId']!=new['guestBootId'] and old['hostBootId']==new['hostBootId']) if kind=='guest_reboot' else old['hostBootId']!=new['hostBootId'] if kind=='host_reboot' else old['deviceGenerationId']!=new['deviceGenerationId'] and old['hostBootId']==new['hostBootId'] and old['guestBootId']==new['guestBootId']
        if not changed:errors.append(f'{label}: each exercised reboot/reset must change its corresponding boot or device generation identity')
        for state in (old,new):
            if device not in state['enumeratedDeviceIds'] or device not in state['assignedDeviceIds'] or state['runtimeReady'] is not True:errors.append(f'{label}: actual device enumeration, guest reassignment and initialized runtime required before and after transition')
            ref=state['probeRef'];count=len(errors);observed=selected_observation(root,execution,prefix,ref,defs,'passthroughRuntimeProbe',label,errors,cache)
            if observed is None or len(errors)!=count:continue
            times=[utc(observed[k]) for k in ('startedAt','finishedAt')];at=utc(state['observedAt'])
            if observed['configurationRef']!=config or observed['identity']!=identity or any(observed[k]!=state[k] for k in ('hostBootId','guestBootId','deviceGenerationId')) or any(t is None for t in times) or at is None or window is None or not window[0]<=times[0]<times[1]<=at<=window[1] or observed['inputSha256'] not in inputs or observed['runtimeReady'] is not True or observed['decodeErrorCount']!=0:errors.append(f'{label}: successful recovered AV1 probe must bind exact approved input/device/build and observed boot/reset generation')
            payload=existing_ref(root,observed['outputRef'],prefix);matches=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==observed['outputRef']]
            if payload is None or len(matches)!=1 or matches[0].get('artifactType')!='produced_media' or matches[0].get('nodeId')!=identity['nodeId'] or observed['outputRef'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: runtime probe requires retained node-bound actual produced output');continue
            try:actual=inspect_artifact(payload,cache)
            except OSError:errors.append(f'{label}: produced runtime probe output must be readable');continue
            if actual['size']==0 or actual['sha256']!=observed['outputSha256']:errors.append(f'{label}: recovered runtime probe must bind nonempty exact output bytes')
            seen_probes[ref]=observed
        if old['probeRef']==new['probeRef'] or old['probeRef'] in seen_probes and new['probeRef'] in seen_probes and seen_probes[old['probeRef']]['outputRef']==seen_probes[new['probeRef']]['outputRef']:errors.append(f'{label}: recovery must execute a distinct probe and retain its own produced output')
        after_probe=seen_probes.get(new['probeRef']);after_started=utc(after_probe['startedAt']) if after_probe else None
        if after_started is None or end is None or after_started<end:errors.append(f'{label}: recovered runtime probe must start after the exercised transition finishes')
    ordered=sorted(intervals,key=lambda item:item[0])
    for previous,current in zip(ordered,ordered[1:]):
        prior=previous[2]['after'];following=current[2]['before']
        if previous[1]>current[0] or utc(prior['observedAt'])>current[0] or any(prior[k]!=following[k] for k in ('hostBootId','guestBootId','deviceGenerationId')):errors.append(f'{label}: repeated transitions must retain consistent chronological device/boot state')
    before=len(errors)
    firmware=selected_observation(root,execution,prefix,env.get('productionFirmwareRef'),defs,'passthroughFirmwareObservation',label,errors,cache)
    if firmware is None or len(errors)!=before:return
    if firmware and ordered and (ordered[0][2]['before']['hostBootId']!=firmware['hostBootId'] or utc(firmware['runtimeInitializedAt']) is None or utc(ordered[0][2]['before']['observedAt'])<utc(firmware['runtimeInitializedAt'])):errors.append(f'{label}: first transition must bind captured initialized host boot')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if any(actual.get(g) is not True for g in ('vm_reboot_recovery','esxi_host_reboot_reenumeration','device_reset_recovery')):errors.append(f'{label}: true recovery gates require corresponding observed transitions and runtime probes')


def validate_qualified_production_soak(root, plan, execution, defs, prefix, status, window, errors):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-01' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('production'):
        return
    label=f"qualified production soak {plan['taskId']}"
    capture=env.get('productionPassthroughSoak')
    validate_schema(capture,defs.get('productionPassthroughSoakCapture',{}),label,errors)
    if not isinstance(capture,dict):return
    ref=capture.get('configurationRef')
    if not isinstance(ref,str) or ref not in {r.get('configurationRef') for r in execution.get('resources') or [] if isinstance(r,dict) and isinstance(r.get('configurationRef'),str)}:
        errors.append(f'{label}: soak floor must bind a selected independently approved resource configuration')
        return
    path=existing_ref(root,ref,prefix)
    if path is None:return
    try:record=load(path)
    except (OSError,yaml.YAMLError,ValueError) as exc:
        errors.append(f'{label}: cannot read approved soak floor: {exc}')
        return
    settings=record.get('configuration') if isinstance(record,dict) else None
    floor=settings.get('productionPassthroughSoak') if isinstance(settings,dict) else None
    validate_schema(floor,defs.get('productionPassthroughSoakConfiguration',{}),label+'/approved floor',errors)
    if not isinstance(floor,dict):return
    days=floor.get('minimumContinuousDays')
    if type(days) is not int or days<2 or capture.get('minimumContinuousDays')!=days:
        errors.append(f'{label}: exact approved minimumContinuousDays must represent at least two complete days')
        return
    start,end=utc(capture.get('observedStartedAt')),utc(capture.get('observedFinishedAt'))
    if start is None or end is None or window is None or not window[0]<=start<end<=window[1]:
        errors.append(f'{label}: continuous observed interval must be within executionWindow')
        return
    raw=capture.get('rawOutputRef')
    records=[r for r in env.get('rawExecutionArtifacts') or [] if isinstance(r,dict) and r.get('ref')==raw]
    raw_path=existing_ref(root,raw,prefix)
    passthrough=env.get('productionPassthroughIdentity')
    identity=passthrough.get('identity') if isinstance(passthrough,dict) else None
    if len(records)!=1 or records[0].get('artifactType')!='scope_observation' or raw not in (execution.get('rawOutputRefs') or []) or raw_path is None:
        errors.append(f'{label}: observed soak must bind selected-slot typed scope_observation bytes')
    elif not isinstance(identity,dict) or records[0].get('nodeId')!=identity.get('nodeId') or ref!=passthrough.get('configurationRef'):
        errors.append(f'{label}: dedicated observation must bind the selected approved A380 node/configuration')
    else:
        phone=env.get('android_thermal_background_observation')
        scope=env.get('android_validation_scope')
        other_refs=[value.get('rawOutputRef') for value in (phone,scope) if isinstance(value,dict)]+[env.get('androidMediaProbeRef')]
        aliases=any(raw==other or ((other_path:=existing_ref(root,other,prefix)) is not None and raw_path.samefile(other_path)) for other in other_refs)
        if aliases:
            errors.append(f'{label}: dedicated A380 soak observation must be physically distinct from phone/media/probe artifacts')
        else:
            report=qualified_observation_report(raw_path,defs,'productionPassthroughSoakObservation',label,errors,{})
            expected=dict(configurationRef=ref,identity=identity,observedStartedAt=capture.get('observedStartedAt'),observedFinishedAt=capture.get('observedFinishedAt'),continuous=True)
            if report is not None and any(report.get(key)!=value for key,value in expected.items()):
                errors.append(f'{label}: dedicated observation contents must bind exact approved A380 identity and continuous captured interval')
    observed_hours=(end-start).total_seconds()/3600
    actual=next((m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict) and m.get('id')=='multi_day_stability_duration'),None)
    if observed_hours<days*24 or not good_actual('hours',actual) or not math.isclose(actual,observed_hours,rel_tol=1e-9,abs_tol=1e-9):
        errors.append(f'{label}: multi_day_stability_duration must match observed hours and reach the approved continuous multi-day floor')


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


ARTIFACT_CHUNK_BYTES = 1024 * 1024
RAW_ASSIGNMENT = re.compile(r'''(?:["'](?P<quoted>[^\r\n"']{1,128})["']|(?P<plain>[A-Za-z][A-Za-z0-9_.:/-]{0,127}))\s*[:=](?=(?P<value>[^\r\n]{0,128}))''')
RAW_AUTHORIZATION = re.compile(r'''(?i)\b(?:authorization|proxy-authorization)["']?\s*[:=]\s*["']?(?:Bearer|Basic)\s+\S+''')


def inspect_artifact(path, cache, textual=False, byte_range=None):
    """One bounded read per artifact type within this validation invocation."""
    cached = cache.get(path)
    if cached is not None and (not textual or cached['textScanned']) and (byte_range is None or byte_range in cached.get('rangeHashes',{})):
        return cached
    digest = hashlib.sha256()
    size = path.stat().st_size
    valid_range=byte_range is not None and len(byte_range)==2 and all(type(value) is int for value in byte_range) and 0<=byte_range[0]<=byte_range[1]<size
    complete_range=valid_range and byte_range==(0,size-1)
    range_digest=hashlib.sha256() if valid_range and not complete_range else None
    offset=0
    decoder = codecs.getincrementaldecoder('utf8')('strict') if textual else None
    scan_decoder = codecs.getincrementaldecoder('utf8')('replace') if textual else None
    tail, credential, invalid_utf8 = '', False, False
    def scan(text):
        nonlocal tail, credential
        window = tail+text
        findings = []
        secret_scan(window,'raw textual artifact',findings)
        for match in RAW_ASSIGNMENT.finditer(window):
            key = match['quoted'] or match['plain']
            value = False if re.match(r'(?i)^false(?:\s*$|\s*[,}])',match['value'].strip()) else match['value']
            if secret_key(key,value): findings.append('credential-bearing assignment')
        credential = credential or bool(findings) or RAW_AUTHORIZATION.search(window) is not None
        tail = window[-4096:]
    def consume_physical(chunk):
        nonlocal offset
        digest.update(chunk)
        if range_digest is not None:
            first,last=byte_range
            low,high=max(0,first-offset),min(len(chunk),last+1-offset)
            if low<high:range_digest.update(chunk[low:high])
        offset+=len(chunk)
    for chunk in retained_metadata_chunks(path,consume_physical,textual and path.name.endswith('.jsonl.gz')):
        if scan_decoder is not None:scan(scan_decoder.decode(chunk))
        if decoder is not None:
            try: decoder.decode(chunk)
            except UnicodeDecodeError:
                invalid_utf8 = True
                decoder = None
    if scan_decoder is not None:scan(scan_decoder.decode(b'',final=True))
    if decoder is not None:
        try: decoder.decode(b'',final=True)
        except UnicodeDecodeError: invalid_utf8 = True
    cached = dict(size=size,sha256='sha256:'+digest.hexdigest(),textScanned=textual,credential=credential,invalidUtf8=invalid_utf8)
    if valid_range:
        cached['rangeHashes']={byte_range:cached['sha256'] if complete_range else 'sha256:'+range_digest.hexdigest() if offset>byte_range[1] else None}
    cache[path] = cached
    return cached


def validate_qualified_raw(root, plan, execution, configuration, defs, prefix, status, record_refs, errors, artifact_cache=None):
    artifact_cache = {} if artifact_cache is None else artifact_cache
    label = f"qualified raw artifacts {plan['taskId']}"
    if isinstance(configuration,dict) and 'approvedAt' in configuration:
        approved = utc(configuration['approvedAt'])
        if approved is None or approved > datetime.now(timezone.utc):
            errors.append(f'{label}: profile configuration approval must have occurred by validation time')
    refs = execution.get('rawOutputRefs') or []
    records = (execution.get('environmentCaptured') or {}).get('rawExecutionArtifacts')
    if not isinstance(records,list) or not records:
        errors.append(f'{label}: typed rawExecutionArtifacts are required')
        return
    structured = {ref for ref in record_refs if isinstance(ref,str)}
    def reserve(ref):
        if isinstance(ref,str): structured.add(ref)
    for resource in execution.get('resources') or []:
        if isinstance(resource,dict):
            for key in ('configurationRef','bookingRef'): reserve(resource.get(key))
    for sample in execution.get('samples') or []:
        if isinstance(sample,dict): reserve(sample.get('approvalRef'))
    for review in execution.get('complianceReviews') or []:
        if isinstance(review,dict): reserve(review.get('reviewRef'))
    reserve((execution.get('environmentCaptured') or {}).get('acceptanceProfileConfigurationRef'))
    poc_task = f"POC-{int(plan['pocId'].split('-')[-1]):03d}"
    profile = ((execution.get('environmentCaptured') or {}).get('acceptanceProfile') or {}).get('id')
    if profile in PROFILE_SCOPES: structured.add(profile_index_ref(poc_task,profile))
    domains = configuration.get('numericDomainReviewRefs',{}) if isinstance(configuration,dict) else {}
    if isinstance(domains,dict):
        for ref in domains.values():
            reserve(ref)
            path = existing_ref(root,ref,prefix)
            if path:
                try: reserve(load(path).get('definitionRef'))
                except (OSError,ValueError,AttributeError,yaml.YAMLError): pass
    structured_paths = [path for ref in structured if (path := existing_ref(root,ref,prefix)) is not None]
    seen, kinds, total_bytes = [], {}, 0
    for record in records:
        validate_schema(record,defs.get('recoveryRawExecutionArtifact' if plan['pocId']=='POC-10' else 'rawExecutionArtifact',{}),label,errors)
        if not isinstance(record,dict): continue
        ref = record.get('ref')
        seen.append(ref)
        if isinstance(ref,str): kinds[ref] = record.get('artifactType')
        path = existing_ref(root,ref,prefix)
        if path is None:
            errors.append(f'{label}: artifact must exist in selected slot')
            continue
        if ref in structured or any(path.samefile(peer) for peer in structured_paths):
            errors.append(f'{label}: raw outputs must be disjoint from structured records and approvals')
        try:
            actual = inspect_artifact(path,artifact_cache,textual=record.get('artifactType') != 'produced_media')
        except OSError as exc:
            artifact_cache[path] = dict(size=0,sha256=None,textScanned=True,credential=False,invalidUtf8=False,readError=True)
            errors.append(f'{label}: cannot read raw artifact: {exc}')
            continue
        total_bytes += actual['size']
        if actual['credential']:
            errors.append(f'{label}: credentials forbidden in raw textual artifacts')
        if actual['invalidUtf8'] and not (plan['pocId']=='POC-10' and record.get('artifactType')=='recovery_output'):
            errors.append(f'{label}: raw textual artifacts must decode as UTF-8')
        if type(record.get('byteCount')) is not int or record['byteCount'] != actual['size']:
            errors.append(f'{label}: byteCount must bind actual raw bytes')
        if record.get('sha256') != actual['sha256']:
            errors.append(f'{label}: checksum must bind actual raw bytes')
    if any(not isinstance(ref,str) for ref in seen+refs) or len(seen) != len(set(ref for ref in seen if isinstance(ref,str))) or set(ref for ref in seen if isinstance(ref,str)) != set(ref for ref in refs if isinstance(ref,str)):
        errors.append(f'{label}: exact unique rawOutputRefs mapping is required')
    for command in execution.get('commands') or []:
        if isinstance(command,dict) and kinds.get(command.get('outputRef')) != 'command_output':
            errors.append(f'{label}: command output must identify a command_output artifact')
    if status == 'pass' and total_bytes == 0:
        errors.append(f'{label}: PASS requires nonempty dedicated raw output')
    if plan['pocId'] == 'POC-02' and status == 'pass':
        ref = (execution.get('environmentCaptured') or {}).get('producedMediaArtifactRef')
        media = existing_ref(root,ref,prefix)
        if not isinstance(ref,str) or kinds.get(ref) != 'produced_media' or media is None or media.stat().st_size == 0:
            errors.append(f'{label}: POC-002 PASS requires a designated nonempty produced_media artifact')
        elif (execution.get('provenance') or {}).get('output_sha256') != inspect_artifact(media,artifact_cache)['sha256']:
            errors.append(f'{label}: POC-002 output_sha256 must match produced media bytes')




def validate_qualified_media_scheduling(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-02' or status!='pass':return
    label=f"qualified playback scheduling {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('mediaSchedulingRef'),defs,'mediaSchedulingObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None)
    path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:configuration=load(path).get('configuration',{}) if path else {};policy=configuration.get('mediaSchedulingPolicy');security=configuration.get('mediaNegativePolicy')
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=security=None
    validate_schema(policy,defs.get('mediaSchedulingPolicy',{}),label+'/approved policy',errors)
    validate_schema(security,defs.get('mediaNegativePolicy',{}),label+'/existing approved permissions',errors)
    if report is None or len(errors)!=before:return
    context_keys=('assetId','assetVersion','authorizedUserId','deniedUserId','currentGrantId','expiredGrantId','revokedGrantId','aclVersion','grantValidFrom','grantValidUntil','revokedAt')
    context={k:security[k] for k in context_keys}
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],context=context,schedulerBuild=policy['schedulerBuild'],demandEpoch=policy['demandEpoch'])
    if policy['context']!=context or any(report[k]!=v for k,v in expected.items()) or not all(ai_finite(policy[k]) for k in ('agingStepSeconds','maximumAdmissionSeconds','maximumFirstReadySeconds')):
        errors.append(f'{label}: exact approved resource/profile/input and existing asset/user/ACL/grant context required');return
    inventory=env.get('worker_node_inventory');nodes={n['nodeId']:n for n in inventory if isinstance(n,dict) and isinstance(n.get('nodeId'),str)} if isinstance(inventory,list) else {}
    assembly=env.get('parallelMediaAssembly');assembly=assembly if isinstance(assembly,dict) else {}
    sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==policy['inputSampleId']),None)
    total,per_node,reserved=policy['totalCapacity'],policy['perNodeCapacity'],policy['reservedPlaybackSlots']
    if not nodes or sample is None or sample['checksum']!=policy['inputSha256'] or sample['immutableId']!=context['assetVersion'] or policy['sourceFrameCount']!=assembly.get('sourceFrameCount') or not 0<reserved<total<=len(nodes)*per_node:
        errors.append(f'{label}: controlled inventory, source and positive bounded reserved capacity required');return
    if env.get('acceptanceProfile')==profile_identity('local-v1'):
        caps=env.get('scheduler_configuration');caps=caps if isinstance(caps,dict) else {}
        if caps.get('maxConcurrentSegments')!=total or caps.get('perNodeConcurrency')!=per_node or type(caps.get('maxConcurrentSegments')) is not int or type(caps.get('perNodeConcurrency')) is not int:errors.append(f'{label}: scheduling caps must equal the approved local capture');return
    grant_from,grant_until=utc(context['grantValidFrom']),utc(context['grantValidUntil'])
    if grant_from is None or grant_until is None or grant_from>=grant_until or window is None:errors.append(f'{label}: approved grant and execution UTC window required');return
    approved={j['jobId']:j for j in policy['jobs']};jobs={j['jobId']:j for j in report['jobs']}
    if len(approved)!=len(policy['jobs']) or len(jobs)!=len(report['jobs']) or set(jobs)!=set(approved):errors.append(f'{label}: unique complete approved job matrix required');return
    if any(policy[k] not in jobs for k in ('playbackJobId','prewarmJobId','agingJobId')) or not policy['saturationJobIds'] or len(set(policy['saturationJobIds']))!=len(policy['saturationJobIds']) or any(j not in jobs for j in policy['saturationJobIds']):errors.append(f'{label}: exact playback/prewarm/aging and background saturation subjects required');return
    clocks={};allowed={};outputs=[];priorities={'playback':0,'prewarm':3,'background':6}
    for job_id,row in jobs.items():
        spec=approved[job_id];node=nodes.get(spec['nodeId'])
        if any(row[k]!=v for k,v in spec.items()) or node is None or spec['encoderBuild']!=node.get('encoderBuild') or not 0<=spec['sourceStartFrame']<spec['sourceEndFrame']<=policy['sourceFrameCount']:
            errors.append(f'{label}: each job must bind approved node/build/purpose/input span');continue
        stamps={k:utc(row[k]) if row[k] is not None else None for k in ('queuedAt','admittedAt','startedAt','finishedAt','readyAt')};queued=stamps['queuedAt']
        if queued is None or not window[0]<=queued<=window[1]:errors.append(f'{label}: actual queue timestamp required');continue
        valid=spec['userId']==context['authorizedUserId'] and spec['grantId']==context['currentGrantId'] and spec['aclVersion']==context['aclVersion'] and spec['demandEpoch']==policy['demandEpoch'] and grant_from<=queued<=grant_until
        allowed[job_id]=valid;clocks[job_id]=stamps
        if not valid:
            file=existing_ref(root,row['denialBodyRef'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==row['denialBodyRef']]
            if any(stamps[k] is not None for k in ('admittedAt','startedAt','finishedAt','readyAt')) or any(row[k] is not None for k in ('outputArtifactRef','outputSha256','decodeRef')) or file is None or len(records)!=1 or records[0].get('artifactType')!='produced_media' or row['denialBodyRef'] not in (execution.get('rawOutputRefs') or []) or inspect_artifact(file,cache)['size']!=0 or inspect_artifact(file,cache)['sha256']!=row['denialBodySha256']:
                errors.append(f'{label}: unauthorized/expired/revoked/stale demand cannot consume slots or return media bytes')
            continue
        admitted,start,end,ready=(stamps[k] for k in ('admittedAt','startedAt','finishedAt','readyAt'))
        if any(t is None for t in (admitted,start,end,ready)) or not queued<=admitted<=start<end<=ready<=window[1] or admitted>grant_until or row['denialBodyRef'] is not None:
            errors.append(f'{label}: authorized job queue/admission/run/completion/READY clocks required');continue
        file=existing_ref(root,row['outputArtifactRef'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==row['outputArtifactRef']]
        if file is None or len(records)!=1 or records[0].get('artifactType')!='produced_media' or records[0].get('nodeId')!=spec['nodeId'] or row['outputArtifactRef'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: exact node-produced output bytes required');continue
        info=inspect_artifact(file,cache);other_refs=[a.get('ref') for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')!=row['outputArtifactRef']]+[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]
        other_refs += [j.get('outputArtifactRef') for j in report['jobs'] if j['jobId']!=job_id]+[r.get('outputArtifactRef') for r in env.get('workerEncodeExecutions') or [] if isinstance(r,dict)]
        if info['size']<=0 or info['sha256']!=row['outputSha256'] or any(file.samefile(p) for ref in other_refs if (p:=existing_ref(root,ref,prefix)) is not None):errors.append(f'{label}: scheduling outputs must have actual distinct nonempty bytes/hash');continue
        decode_before=len(errors);probe=selected_observation(root,execution,prefix,row['decodeRef'],defs,'mediaSchedulingDecode',label+'/decode',errors,cache)
        if probe is None or len(errors)!=decode_before:continue
        decoded=utc(probe['observedAt']);identity=dict(jobId=job_id,demandEpoch=policy['demandEpoch'],nodeId=spec['nodeId'],encoderBuild=spec['encoderBuild'],decoderBuild=policy['decoderBuild'],inputSampleId=policy['inputSampleId'],inputSha256=policy['inputSha256'],sourceStartFrame=spec['sourceStartFrame'],sourceEndFrame=spec['sourceEndFrame'],outputArtifactRef=row['outputArtifactRef'],outputSha256=row['outputSha256'])
        if any(probe[k]!=v for k,v in identity.items()) or decoded is None or not end<=decoded<=ready or probe['decodedFrameCount']!=spec['sourceEndFrame']-spec['sourceStartFrame'] or probe['decodeErrorCount']!=0 or probe['decodable'] is not True:errors.append(f'{label}: first READY and completion must bind exact AV1 decoder/input/build/span/output')
        outputs.append(file)
    if len(clocks)!=len(jobs) or len(errors)!=before:return
    if any(not ai_finite(max(0,(window[1]-times['queuedAt']).total_seconds())/policy['agingStepSeconds']) for times in clocks.values()):
        errors.append(f'{label}: finite representable approved aging interval required');return
    def priority(job_id,at):
        waited=max(0,(at-clocks[job_id]['queuedAt']).total_seconds())
        return max(policy['agingFloorPriority'],priorities[jobs[job_id]['purpose']]-math.floor(waited/policy['agingStepSeconds'])) if jobs[job_id]['purpose']!='playback' else 0
    def active(at,strict=False):return [j for j in jobs if allowed[j] and clocks[j]['admittedAt'] is not None and (clocks[j]['admittedAt']<at if strict else clocks[j]['admittedAt']<=at) and at<clocks[j]['finishedAt']]
    # State snapshots and admission intervals describe cooperative capacity;
    # no running encoder is stopped to grant the playback reservation.
    snapshots=report['snapshots'];observed=[]
    for snapshot in snapshots:
        at=utc(snapshot['observedAt']);observed.append(at)
        if at is None or not window[0]<=at<=window[1] or len(snapshot['jobs'])!=len(jobs) or {r['jobId'] for r in snapshot['jobs']}!=set(jobs):errors.append(f'{label}: bounded complete UTC queue-state snapshots required');continue
        for state in snapshot['jobs']:
            j=state['jobId'];t=clocks[j]
            wanted='not_queued' if at<t['queuedAt'] else 'denied' if not allowed[j] else 'queued' if at<t['admittedAt'] else 'admitted' if at<t['startedAt'] else 'running' if at<t['finishedAt'] else 'completed' if at<t['readyAt'] else 'ready'
            aging_at=min(at,t['admittedAt']) if allowed[j] and t['admittedAt'] is not None else at
            if state['state']!=wanted or state['basePriority']!=priorities[jobs[j]['purpose']] or state['effectivePriority']!=priority(j,aging_at):errors.append(f'{label}: P0/P3/P6 queue state and aging priority must derive actual timestamps')
        running=active(at)
        if len(running)>total or sum(jobs[j]['purpose']!='playback' for j in running)>total-reserved or any(sum(jobs[j]['nodeId']==n for j in running)>per_node for n in nodes):errors.append(f'{label}: reserved playback/total/per-node capacity cannot be oversubscribed')
    if any(t is None for t in observed) or observed!=sorted(observed) or len(set(observed))!=len(observed):errors.append(f'{label}: ordered distinct state snapshots required')
    admissions=[(j,clocks[j]['admittedAt'],clocks[j]['finishedAt']) for j in jobs if allowed[j]]
    if encode_interval_capacity(admissions)[0]>total or encode_interval_capacity([interval for interval in admissions if jobs[interval[0]]['purpose']!='playback'])[0]>total-reserved or any(encode_interval_capacity([interval for interval in admissions if jobs[interval[0]]['nodeId']==node])[0]>per_node for node in nodes):
        errors.append(f'{label}: admission intervals exceed total/per-node/non-playback reserved capacity')
    for j in jobs:
        if not allowed[j]:continue
        at=clocks[j]['admittedAt'];running=active(at,True);n=jobs[j]['nodeId'];eligible=[]
        for q in jobs:
            t=clocks[q]
            if not allowed[q] or t['queuedAt']>at or q!=j and t['admittedAt']<=at:continue
            if len(running)>=total or sum(jobs[a]['nodeId']==jobs[q]['nodeId'] for a in running)>=per_node or jobs[q]['purpose']!='playback' and sum(jobs[a]['purpose']!='playback' for a in running)>=total-reserved:continue
            eligible.append(q)
        if j not in eligible or any(priority(q,at)<priority(j,at) for q in eligible):errors.append(f'{label}: admission must honor effective queue priority and reserved capacity')
    playback=policy['playbackJobId'];prewarm=policy['prewarmJobId'];aged=policy['agingJobId'];p=clocks[playback]
    if not all(allowed[j] for j in (playback,prewarm,aged)) or jobs[playback]['purpose']!='playback' or jobs[prewarm]['purpose']!='prewarm' or jobs[aged]['purpose']!='background' or priority(aged,clocks[aged]['admittedAt'])>=6:errors.append(f'{label}: exercised P0 playback, P3 prewarm and aged P6 background required')
    saturated=policy['saturationJobIds'];queued=p['queuedAt'];admitted=p['admittedAt']
    if len(saturated)!=total-reserved or any(not allowed[j] or jobs[j]['purpose']!='background' or not clocks[j]['startedAt']<=queued<admitted<clocks[j]['finishedAt'] for j in saturated) or queued not in observed or admitted not in observed or report['preemptedRunningProcessIds']:
        errors.append(f'{label}: actual background saturation must persist across reserved playback admission without FFmpeg preemption')
    admission=(admitted-queued).total_seconds();ready_latency=(p['readyAt']-queued).total_seconds()
    if not ai_finite(report['admissionLatencySeconds']) or not ai_finite(report['firstReadyLatencySeconds']) or not math.isclose(report['admissionLatencySeconds'],admission,rel_tol=1e-9,abs_tol=1e-9) or not math.isclose(report['firstReadyLatencySeconds'],ready_latency,rel_tol=1e-9,abs_tol=1e-9) or admission>policy['maximumAdmissionSeconds'] or ready_latency>policy['maximumFirstReadySeconds'] or p['readyAt'] not in observed:errors.append(f'{label}: admission and decoded first READY latency must derive complete observed playback clocks')
    fallback=report['fallback'];at=utc(fallback['observedAt']);fallback_before=len(errors);h264=selected_observation(root,execution,prefix,env.get('h264FallbackRef'),defs,'mediaFallbackObservation',label+'/fallback',errors,cache)
    if h264 is not None and len(errors)==fallback_before:
        expected_fallback=dict(jobId=playback,userId=context['authorizedUserId'],grantId=context['currentGrantId'],aclVersion=context['aclVersion'],assetId=context['assetId'],assetVersion=context['assetVersion'],demandEpoch=policy['demandEpoch'],outputArtifactRef=h264['outputArtifactRef'],outputSha256=h264['outputSha256'],decodeRef=h264['decodeRef'])
        file=existing_ref(root,fallback['outputArtifactRef'],prefix);decode=selected_observation(root,execution,prefix,fallback['decodeRef'],defs,'mediaFallbackDecodeObservation',label+'/fallback decode',errors,cache)
        decoded=utc(decode.get('observedAt')) if isinstance(decode,dict) else None
        decode_identity={k:h264[k] for k in ('runId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame')}
        if any(fallback[k]!=v for k,v in expected_fallback.items()) or at is None or not max(queued,grant_from)<=at<=min(p['readyAt'],grant_until) or file is None or inspect_artifact(file,cache)['size']<=0 or inspect_artifact(file,cache)['sha256']!=fallback['outputSha256'] or decode is None or decoded is None or at is None or decoded>at or any(decode.get(k)!=v for k,v in decode_identity.items()) or decode.get('decodedFrameCount')!=h264['encodedFrameCount'] or decode.get('codec')!='h264' or decode.get('outputArtifactRef')!=fallback['outputArtifactRef'] or decode.get('outputSha256')!=fallback['outputSha256'] or decode.get('decodable') is not True or decode.get('decodeErrorCount')!=0:errors.append(f'{label}: authorized source/H264 fallback must retain exact independent decoder and actual bytes before first AV1 READY')
    if next((m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict) and m.get('id')=='playback_priority_reserved_capacity'),None) is not True:errors.append(f'{label}: scheduling gate must agree with observed priority/reserved capacity outcomes')


def complete_decoder_timeline(raw,params,frame_count,frames_per_second):
    """The existing whole-sequence frame/packet check, shared with codec probes."""
    try:
        stream=raw['streams'][0];items=raw['packets_and_frames'];frames=[row for row in items if row['type']=='frame'];packets=[row for row in items if row['type']=='packet']
        numerator,denominator=(int(v) for v in params['time_base'].split('/'));step=denominator/(numerator*frames_per_second)
        fps_n,fps_d=(int(v) for v in params['r_frame_rate'].split('/'));fps=fps_n/fps_d
        valid=ai_finite(step) and step>=1 and math.isclose(step,round(step),rel_tol=1e-9,abs_tol=1e-9) and ai_finite(fps) and math.isclose(fps,frames_per_second,rel_tol=1e-9,abs_tol=1e-9)
        ticks=round(step) if valid else 0;pts=[row['pts'] for row in frames];duration=lambda row:row.get('duration',row.get('pkt_duration'))
        return valid and all(stream.get(k)==v for k,v in params.items()) and len(frames)==frame_count and pts==[pts[0]+i*ticks for i in range(len(frames))] and all(duration(row)==ticks and all(row[k]==params[k] for k in ('width','height','pix_fmt')) for row in frames) and bool(packets) and {row['pts'] for row in packets}==set(pts) and all(a['dts']+a['duration']==b['dts'] for a,b in zip(packets,packets[1:])) and sum(row['duration'] for row in packets)==len(frames)*ticks
    except (KeyError,TypeError,ValueError,ZeroDivisionError,OverflowError,IndexError):return False


def worker_media_packet_bytes(media,raw,codec):
    """Bind original MP4 probe packets to bounded native container and payload bytes."""
    entries={'av1':(b'av01',),'h264':(b'avc1',b'avc3'),'hevc':(b'hvc1',b'hev1'),'vp9':(b'vp09',),'mpeg4':(b'mp4v',)}
    try:
        declared=raw['streams'][0]['codec_tag_string'].encode('ascii');accepted=entries.get(codec,(declared,))
        if len(declared)!=4 or declared not in accepted:return False
        size=media.stat().st_size;boxes=[];offset=0
        with media.open('rb') as stream:
            while offset<size:
                if len(boxes)>=10000 or size-offset<8:return False
                stream.seek(offset);header=stream.read(16);length=int.from_bytes(header[:4],'big');kind=header[4:8];head=8
                if length==1:length=int.from_bytes(header[8:16],'big');head=16
                elif length==0:length=size-offset
                if length<head or offset+length>size:return False
                boxes.append((kind,offset+head,offset+length));offset+=length
            ftyp=[(a,b) for k,a,b in boxes if k==b'ftyp'];moov=[(a,b) for k,a,b in boxes if k==b'moov'];mdat=[(a,b) for k,a,b in boxes if k==b'mdat']
            if len(ftyp)!=1 or len(moov)!=1 or not mdat or ftyp[0][1]-ftyp[0][0]<8 or (ftyp[0][1]-ftyp[0][0])%4 or ftyp[0][1]-ftyp[0][0]>4096 or moov[0][1]-moov[0][0]>1048576:return False
            stream.seek(ftyp[0][0]);brands=stream.read(ftyp[0][1]-ftyp[0][0]);brands=brands[:4]+brands[8:]
            if not any(brands[i:i+4] in (b'isom',b'iso2',b'iso5',b'iso6',b'mp41',b'mp42',b'av01',b'avc1',b'dash') for i in range(0,len(brands),4)):return False
            stream.seek(moov[0][0]);metadata=stream.read(moov[0][1]-moov[0][0]);pending=[(0,len(metadata),0)];sample_entries=[]
            while pending:
                first,last,depth=pending.pop();cursor=first
                while cursor<last:
                    if last-cursor<8:return False
                    length=int.from_bytes(metadata[cursor:cursor+4],'big');kind=metadata[cursor+4:cursor+8]
                    if length<8 or cursor+length>last:return False
                    if kind in (b'trak',b'mdia',b'minf',b'stbl'):
                        if depth>=4 or kind!=(b'trak',b'mdia',b'minf',b'stbl')[depth]:return False
                        pending.append((cursor+8,cursor+length,depth+1))
                    elif kind==b'stsd':
                        if depth!=4 or length<24 or int.from_bytes(metadata[cursor+12:cursor+16],'big')!=1:return False
                        entry_size=int.from_bytes(metadata[cursor+16:cursor+20],'big')
                        if entry_size<8 or entry_size!=length-16:return False
                        if metadata[cursor+20:cursor+24]==declared:
                            if entry_size<86:return False
                            sample_entries.append(metadata[cursor+20:cursor+24])
                    cursor+=length
            if len(sample_entries)!=1:return False
            ranges=[]
            for packet in (row for row in raw['packets_and_frames'] if row['type']=='packet'):
                start,count=int(packet['pos']),int(packet['size']);end=start+count
                if not any(a<=start<end<=b for a,b in mdat):return False
                stream.seek(start);digest=hashlib.sha256();remaining=count
                while remaining:
                    block=stream.read(min(1048576,remaining))
                    if not block:return False
                    digest.update(block);remaining-=len(block)
                if 'SHA256:'+digest.hexdigest()!=packet['data_hash']:return False
                ranges.append((start,end))
            ranges.sort()
            return bool(ranges) and all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:])) and raw['format']['format_name']=='mov,mp4,m4a,3gp,3g2,mj2' and int(raw['format']['size'])==size
    except (OSError,UnicodeError,ValueError,KeyError,OverflowError):return False


def validate_qualified_worker_capabilities(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-01' or status!='pass':return
    label=f"qualified worker capabilities {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('workerCapabilitiesRef'),defs,'workerCapabilityObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('workerCapabilityPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('workerCapabilityPolicy',{}),label+'/approved policy',errors)
    if report is None or len(errors)!=before:return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    inventory=env.get('worker_node_inventory');nodes={n['nodeId']:n for n in inventory if isinstance(n,dict) and isinstance(n.get('nodeId'),str)} if isinstance(inventory,list) else {}
    if any(report[k]!=v for k,v in expected.items()) or not nodes or len(nodes)!=len(inventory) or env.get('encoder_capability_matrix')!=policy['claims'] or not ai_finite(policy['framesPerSecond']):errors.append(f'{label}: exact approved inventory/codec matrix, input/profile and build required');return
    scope=env.get('physical_host_scope');host_values=[n.get('physicalHostId') for n in nodes.values()];scope_hosts=scope.get('physicalHostIds') if isinstance(scope,dict) else None
    if any(not recorded_text(h) for h in host_values):errors.append(f'{label}: every inventory node needs a concrete physical host identity');return
    hosts=set(host_values)
    if not all(recorded_text(h) for h in hosts) or not isinstance(scope_hosts,list) or not scope_hosts or any(not recorded_text(h) for h in scope_hosts) or len(scope_hosts)!=len(set(scope_hosts)) or set(scope_hosts)!=hosts or scope.get('physicalMultiHostValidated') is not (len(hosts)>1):
        errors.append(f'{label}: physical host scope must cover every exact inventory node and disclose same-host limits');return
    if next((m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict) and m.get('id')=='worker_physical_scope_recorded'),None) is not True:
        errors.append(f'{label}: physical scope gate must derive the complete node-to-host comparison');return
    try:duration=policy['sourceFrameCount']/policy['framesPerSecond']
    except (OverflowError,ZeroDivisionError):duration=None
    if not ai_finite(duration) or duration<=0:errors.append(f'{label}: finite positive approved source duration required');return
    claims=policy['claims'];ids=[c['caseId'] for c in claims];pairs=[(c['nodeId'],c['codec']) for c in claims]
    scope=env.get('vm_validation_scope') if env.get('acceptanceProfile')==profile_identity('local-v1') else env.get('android_validation_scope');android=scope.get('nodeId') if isinstance(scope,dict) else None
    if len(ids)!=len(set(ids)) or len({c['runId'] for c in claims})!=len(claims) or len(pairs)!=len(set(pairs)) or {n for n,c in pairs}!=set(nodes) or any(not {'av1','h264'}.issubset({codec for node,codec in pairs if node==n}) for n in nodes) or any(c['status']=='untested' and c['codec'] in ('av1','h264') for c in claims) or not any(c['nodeId']==android and c['codec']=='av1' and c['status']=='supported' for c in claims) or len(report['claims'])!=len(claims) or {r['caseId'] for r in report['claims']}!=set(ids):
        errors.append(f'{label}: every exact node needs AV1/H264 probe disposition and every advertised codec claim needs a unique retained observation');return
    media_paths=[];decoder_paths=[]
    for row in report['claims']:
        claim=next(c for c in claims if c['caseId']==row['caseId']);node=nodes[claim['nodeId']];sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==claim['inputSampleId']),None)
        if any(row[k]!=v for k,v in claim.items()) or any(claim[k]!=node.get(k) for k in ('nodeId','physicalHostId','platform','osBuild','architecture','encoderBuild','compatibilityGroupId','nodeConfiguration')) or sample is None or claim['inputSha256']!=sample['checksum'] or claim['sourceStartFrame']!=0 or claim['sourceEndFrame']!=policy['sourceFrameCount'] or any(not recorded_text(claim[k]) for k in ('osBuild','architecture','encoderBuild','decoderBuild')) or claim['encoderParameters'].get('codec')!=claim['codec']:
            errors.append(f'{label}: codec probe must bind exact approved node OS/architecture/build/config/command/input');continue
        before=len(errors)
        if claim['status']!='supported':
            diagnostic=selected_observation(root,execution,prefix,row['diagnosticRef'],defs,'workerCapabilityDiagnostic',label+'/diagnostic',errors,cache)
            if diagnostic is None or len(errors)!=before:continue
            observed=utc(diagnostic['observedAt']);raw=existing_ref(root,diagnostic['rawProbeRef'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==diagnostic['rawProbeRef']]
            if any(diagnostic[k]!=v for k,v in claim.items()) or not recorded_text(diagnostic['reason']) or not recorded_text(diagnostic['probeToolBuild']) or observed is None or window is None or not window[0]<=observed<=window[1] or raw is None or len(records)!=1 or records[0].get('artifactType')!='command_output' or records[0].get('nodeId')!=claim['nodeId'] or not 0<raw.stat().st_size<=65536 or inspect_artifact(raw,cache)['sha256']!=diagnostic['rawProbeSha256']:
                errors.append(f'{label}: unsupported/untested claims require exact node-bound bounded diagnostic probe bytes')
            continue
        start,end=utc(row['startedAt']),utc(row['finishedAt'])
        if start is None or end is None or window is None or not window[0]<=start<end<=window[1] or row['exitCode']!=0 or row['encodedFrameCount']!=policy['sourceFrameCount']:errors.append(f'{label}: supported claim needs successful full input encode inside UTC execution');continue
        probe=selected_observation(root,execution,prefix,row['decodeRef'],defs,'workerCapabilityDecode',label+'/decode',errors,cache)
        if probe is None or len(errors)!=before:continue
        identity={k:claim[k] for k in ('runId','caseId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame','codec')};identity.update(outputArtifactRef=row['outputArtifactRef'],outputSha256=row['outputSha256']);decoded=utc(probe['observedAt'])
        if any(probe[k]!=v for k,v in identity.items()) or decoded is None or not end<=decoded<=window[1] or probe['decodable'] is not True or probe['decodedFrameCount']!=policy['sourceFrameCount'] or probe['decodeErrorCount']!=0 or not ai_finite(probe['durationSeconds']) or not math.isclose(probe['durationSeconds'],duration,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: every supported codec needs exact complete zero-error node/output decoder result');continue
        media=existing_ref(root,row['outputArtifactRef'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==row['outputArtifactRef']]
        if media is None or len(records)!=1 or records[0].get('artifactType')!='produced_media' or records[0].get('nodeId')!=claim['nodeId'] or row['outputArtifactRef'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: exact per-node codec produced output required');continue
        info=inspect_artifact(media,cache);other_refs=[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]+[row['decodeRef'],env.get('workerCapabilitiesRef')]+[a.get('ref') for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('artifactType')=='produced_media' and a.get('ref')!=row['outputArtifactRef']]
        if info['size']<=0 or info['size']!=row['outputByteCount'] or info['sha256']!=row['outputSha256'] or any(media.samefile(p) for p in media_paths) or any(media.samefile(p) for ref in other_refs if (p:=existing_ref(root,ref,prefix)) is not None):errors.append(f'{label}: each supported codec must retain physically distinct nonempty output bytes/hash');continue
        media_paths.append(media)
        decode_start,decode_end=utc(probe['startedAt']),utc(probe['finishedAt'])
        args=['-v','error','-protocol_whitelist','file,pipe','-select_streams','v:0','-show_streams','-show_packets','-show_frames','-show_format','-show_program_version','-show_data_hash','sha256','-of','json','-i',row['outputArtifactRef']]
        if decode_start is None or decode_end is None or not end<=decode_start<=decode_end<=decoded or probe['exitCode']!=0 or re.split(r'[\\/]',probe['command'][0])[-1] not in ('ffprobe','ffprobe.exe') or probe['command'][1:]!=args:
            errors.append(f'{label}: exact file-only decoder tool/parameters and ordered current encode/decode clocks required');continue
        raw=bounded_evaluator_json(root,execution,prefix,probe['rawProbeRef'],'command_output',defs,'workerCapabilityProbeOutput',label+'/raw decoder',errors,cache,8388608)
        protected=[media,existing_ref(root,row['decodeRef'],prefix),existing_ref(root,env.get('workerCapabilitiesRef'),prefix),path]+decoder_paths+[existing_ref(root,a.get('inputArtifactRef'),prefix) for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]+[existing_ref(root,a.get('ref'),prefix) for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('artifactType')=='produced_media']
        for key in ('rawProbe','stderr','processExit'):
            file=existing_ref(root,probe[key+'Ref'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==probe[key+'Ref']]
            if file is None or len(records)!=1 or records[0].get('artifactType')!='command_output' or records[0].get('nodeId')!=claim['nodeId'] or probe[key+'Ref'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: distinct node-bound retained decoder stdout/stderr required');continue
            artifact=inspect_artifact(file,cache)
            if artifact['sha256']!=probe[key+'Sha256'] or records[0].get('sha256')!=artifact['sha256'] or records[0].get('byteCount')!=artifact['size'] or key=='stderr' and artifact['size']!=0 or any(file.samefile(p) for p in protected if p is not None):errors.append(f'{label}: actual decoder stdout/stderr bytes/hash must be distinct and zero-error')
            protected.append(file);decoder_paths.append(file)
        if raw is None or len(errors)!=before:continue
        exit=bounded_evaluator_json(root,execution,prefix,probe['processExitRef'],'command_output',defs,'workerCapabilityDecoderExit',label+'/decoder exit',errors,cache)
        exit_binding=dict(runId=claim['runId'],caseId=claim['caseId'],nodeId=claim['nodeId'],decoderBuild=claim['decoderBuild'],outputArtifactRef=row['outputArtifactRef'],outputSha256=row['outputSha256'],command=probe['command'],startedAt=probe['startedAt'],finishedAt=probe['finishedAt'],exitCode=probe['exitCode'],stdoutRef=probe['rawProbeRef'],stdoutSha256=probe['rawProbeSha256'],stderrRef=probe['stderrRef'],stderrSha256=probe['stderrSha256'])
        if exit is None or not 1<=int(exit['processId'])<=4294967295 or any(exit[k]!=v for k,v in exit_binding.items()):errors.append(f'{label}: independent native decoder process exit must bind native PID, this tool/argv/time/output and original stdout/stderr');continue
        params=raw['streams'][0]
        if raw['program_version']['version']!=claim['decoderBuild'] or params['codec_name']!=claim['codec'] or not complete_decoder_timeline(raw,params,policy['sourceFrameCount'],policy['framesPerSecond']):errors.append(f'{label}: retained decoder frames/packets must derive the exact codec, complete span, duration and approved tool build');continue
        if not worker_media_packet_bytes(media,raw,claim['codec']):errors.append(f'{label}: original decoder packets must match native MP4 codec/container structure and exact retained media payload bytes')
    if next((m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict) and m.get('id')=='worker_capabilities_reproducible'),None) is not True:errors.append(f'{label}: capability gate must agree with complete per-node codec observations')


def validate_qualified_hls_ready(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-02' or status!='pass':return
    label=f"qualified HLS READY {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('hlsReadyRef'),defs,'hlsReadyObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('hlsReadyPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('hlsReadyPolicy',{}),label+'/approved policy',errors)
    if report is None or len(errors)!=before:return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],**{k:policy[k] for k in ('jobId','attemptEpoch','inputSampleId','inputSha256','initNodeId','initUri')})
    sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==policy['inputSampleId']),None)
    inventory=env.get('worker_node_inventory');nodes={n['nodeId']:n for n in inventory if isinstance(n,dict) and isinstance(n.get('nodeId'),str)} if isinstance(inventory,list) else {}
    assembly=env.get('parallelMediaAssembly');assembly=assembly if isinstance(assembly,dict) else {}
    if any(report[k]!=v for k,v in expected.items()) or sample is None or sample['checksum']!=policy['inputSha256'] or not ai_finite(policy['framesPerSecond']) or policy['sourceFrameCount']!=assembly.get('sourceFrameCount') or policy['initNodeId'] not in nodes or policy['encoderParameters']!=(execution.get('provenance') or {}).get('encoder_parameters'):
        errors.append(f'{label}: exact approved job/attempt/input/profile/build and finite frame rate required');return
    segments=policy['segments'];ids=[s['segmentId'] for s in segments];count=len(segments)
    if len(ids)!=len(set(ids)) or len({s['uri'] for s in segments})!=count or [s['index'] for s in segments]!=list(range(count)) or segments[0]['sourceStartFrame']!=0 or segments[-1]['sourceEndFrame']!=policy['sourceFrameCount'] or any(s['sourceStartFrame']>=s['sourceEndFrame'] for s in segments) or any(a['sourceEndFrame']!=b['sourceStartFrame'] for a,b in zip(segments,segments[1:])) or len(report['segments'])!=count or {s['segmentId'] for s in report['segments']}!=set(ids):
        errors.append(f'{label}: exact unique ordered segment identities must cover the entire approved source');return
    try:durations=[(s['sourceEndFrame']-s['sourceStartFrame'])/policy['framesPerSecond'] for s in segments]
    except (OverflowError,ZeroDivisionError):durations=[]
    if len(durations)!=count or not all(ai_finite(d) and d>0 for d in durations):errors.append(f'{label}: finite positive derived segment durations required');return
    init=existing_ref(root,report['initArtifactRef'],prefix);init_at=utc(report['initReadyAt']);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==report['initArtifactRef']]
    if init is None or len(records)!=1 or records[0].get('artifactType')!='produced_media' or records[0].get('nodeId')!=policy['initNodeId'] or init_at is None or window is None or not window[0]<=init_at<=window[1]:
        errors.append(f'{label}: identified nonempty initialization artifact and UTC readiness required');return
    init_info=inspect_artifact(init,cache);other_refs=[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]+[env.get('hlsReadyRef')]+[a.get('ref') for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')!=report['initArtifactRef']]
    if init_info['size']<=0 or init_info['sha256']!=report['initSha256'] or any(init.samefile(p) for ref in other_refs if (p:=existing_ref(root,ref,prefix)) is not None):
        errors.append(f'{label}: initialization bytes/hash must be distinct from sources, segments and observations');return
    times={};starts={};media_paths=[init];intervals=[]
    for row in report['segments']:
        segment=next(s for s in segments if s['segmentId']==row['segmentId']);node=nodes.get(segment['nodeId']);start,end,ready=(utc(row[k]) for k in ('startedAt','finishedAt','readyAt'));frames=segment['sourceEndFrame']-segment['sourceStartFrame']
        if any(row[k]!=v for k,v in segment.items()) or node is None or any(segment[k]!=node.get(k) for k in ('physicalHostId','encoderBuild','compatibilityGroupId')) or any(v is None for v in (start,end,ready)) or window is None or not window[0]<=start<end<=ready<=window[1] or row['exitCode']!=0 or row['encodedFrameCount']!=frames:
            errors.append(f'{label}: READY segment must bind successful identified encode and ordered UTC times');continue
        before=len(errors);probe=selected_observation(root,execution,prefix,row['decodeRef'],defs,'hlsSegmentDecode',label+'/decode',errors,cache)
        if probe is None or len(errors)!=before:continue
        identity=dict(jobId=policy['jobId'],attemptEpoch=policy['attemptEpoch'],segmentId=segment['segmentId'],nodeId=segment['nodeId'],encoderBuild=segment['encoderBuild'],decoderBuild=policy['decoderBuild'],inputSha256=policy['inputSha256'],outputArtifactRef=row['outputArtifactRef'],outputSha256=row['outputSha256'],initArtifactRef=report['initArtifactRef'],initSha256=report['initSha256'])
        decoded=utc(probe['observedAt'])
        if any(probe[k]!=v for k,v in identity.items()) or decoded is None or not end<=decoded<=ready or not init_at<=decoded or probe['decodable'] is not True or probe['decodedFrameCount']!=frames or probe['decodeErrorCount']!=0 or row['encoderParameters']!=policy['encoderParameters'] or probe['encoderParameters']!=row['encoderParameters'] or probe['streamParameters']!=policy['streamParameters']:
            errors.append(f'{label}: READY requires matching complete zero-error decoder probe');continue
        media=existing_ref(root,row['outputArtifactRef'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==row['outputArtifactRef']]
        if media is None or len(records)!=1 or records[0].get('artifactType')!='produced_media' or records[0].get('nodeId')!=segment['nodeId']:
            errors.append(f'{label}: exact node-produced segment artifact required');continue
        info=inspect_artifact(media,cache)
        other_refs=[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]+[row['decodeRef'],env.get('hlsReadyRef')]+[a.get('ref') for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('artifactType')=='produced_media' and a.get('ref')!=row['outputArtifactRef']]
        if info['size']<=0 or info['size']!=row['outputByteCount'] or info['sha256']!=row['outputSha256'] or any(media.samefile(p) for p in media_paths) or any(media.samefile(p) for ref in other_refs if (p:=existing_ref(root,ref,prefix)) is not None):
            errors.append(f'{label}: segment bytes/hash must be nonempty and physically distinct');continue
        times[segment['segmentId']]=ready;starts[segment['segmentId']]=start;media_paths.append(media);intervals.append((segment['segmentId'],start,end,segment['nodeId']))
    if len(times)!=count:return
    # A playlist and independently decodable fragments do not prove one compatible,
    # continuous presentation. Retain the actual init+ordered-media bytes and probe.
    sequence_before=len(errors);sequence=selected_observation(root,execution,prefix,report['sequenceDecodeRef'],defs,'hlsSequenceDecodeObservation',label+'/complete sequence',errors,cache)
    if sequence is not None and len(errors)==sequence_before:
        ordered=[next(row for row in report['segments'] if row['segmentId']==s['segmentId']) for s in segments]
        parts=[{k:row[k] for k in ('segmentId','nodeId','encoderBuild','sourceStartFrame','sourceEndFrame','outputArtifactRef','outputSha256','encoderParameters')} for row in ordered]
        identity={k:report[k] for k in ('configurationRef','acceptanceProfile','subjectVersion','inputSamples','jobId','attemptEpoch','inputSampleId','inputSha256','initArtifactRef','initSha256')}
        identity.update(parts=parts,decoderBuild=policy['decoderBuild'],encoderParameters=policy['encoderParameters'],streamParameters=policy['streamParameters'])
        start,end=utc(sequence['startedAt']),utc(sequence['finishedAt'])
        if any(sequence[k]!=v for k,v in identity.items()) or start is None or end is None or not max(times.values())<=start<=end<=window[1] or sequence['exitCode']!=0 or sequence['decodeErrorCount']!=0 or sequence['decodedFrameCount']!=policy['sourceFrameCount']:
            errors.append(f'{label}: whole-sequence decode must bind approved ordered segments, parameters, builds and actual successful interval')
        output=existing_ref(root,sequence['outputArtifactRef'],prefix);record=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==sequence['outputArtifactRef']]
        protected=[existing_ref(root,ref,prefix) for ref in [resource['configurationRef'],env.get('hlsReadyRef'),report['sequenceDecodeRef']]+[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]]+media_paths
        sequence_ok=output is not None and len(record)==1 and record[0].get('artifactType')=='produced_media' and sequence['outputArtifactRef'] in (execution.get('rawOutputRefs') or []) and not any(output.samefile(p) for p in protected if p is not None)
        if sequence_ok:
            info=inspect_artifact(output,cache)
            sequence_ok=info['size']==sequence['outputByteCount'] and info['sha256']==sequence['outputSha256'] and record[0].get('byteCount')==info['size'] and record[0].get('sha256')==info['sha256']
            try:
                with output.open('rb') as joined:
                    for part in [init]+[existing_ref(root,row['outputArtifactRef'],prefix) for row in ordered]:
                        with part.open('rb') as stream:
                            while block:=stream.read(1048576):
                                if joined.read(len(block))!=block:sequence_ok=False;break
                    if joined.read(1):sequence_ok=False
            except OSError:sequence_ok=False
        if not sequence_ok:errors.append(f'{label}: distinct retained whole-sequence bytes must equal init plus every media artifact in approved order')
        raw_path=existing_ref(root,sequence['rawProbeRef'],prefix);stderr=existing_ref(root,sequence['stderrRef'],prefix)
        raw=bounded_evaluator_json(root,execution,prefix,sequence['rawProbeRef'],'command_output',defs,'hlsWholeProbeOutput',label+'/whole-sequence probe',errors,cache,8388608)
        stderr_rows=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==sequence['stderrRef']]
        other_paths=protected+[output,existing_ref(root,sequence['rawProbeRef'],prefix)]
        if raw_path is None or inspect_artifact(raw_path,cache)['sha256']!=sequence['rawProbeSha256'] or any(raw_path.samefile(p) for p in protected+[output] if p is not None) or stderr is None or len(stderr_rows)!=1 or stderr_rows[0].get('artifactType')!='command_output' or sequence['stderrRef'] not in (execution.get('rawOutputRefs') or []) or inspect_artifact(stderr,cache)['size']!=0 or inspect_artifact(stderr,cache)['sha256']!=sequence['stderrSha256'] or any(stderr.samefile(p) for p in other_paths if p is not None) or sequence['command'][1:]!=['-v','error','-select_streams','v:0','-show_streams','-show_packets','-show_frames','-of','json',sequence['outputArtifactRef']]:
            errors.append(f'{label}: retained whole-sequence ffprobe stdout, zero-error stderr and exact input command must be distinct and bound')
        if raw is not None:
            if not complete_decoder_timeline(raw,policy['streamParameters'],policy['sourceFrameCount'],policy['framesPerSecond']):errors.append(f'{label}: actual complete decoder frames and packet PTS/DTS must have approved compatible stream parameters and one continuous full timeline')
    if not any(times[a['segmentId']]>times[b['segmentId']] for a,b in zip(segments,segments[1:])):
        errors.append(f'{label}: retained scenario must exercise out-of-order READY completion')
    if env.get('acceptanceProfile')==profile_identity('local-v1'):
        caps=env.get('scheduler_configuration');caps=caps if isinstance(caps,dict) else {};total,per_node=caps.get('maxConcurrentSegments'),caps.get('perNodeConcurrency')
        if type(total) is not int or type(per_node) is not int or total<1 or per_node<1 or encode_interval_capacity([(sid,a,b) for sid,a,b,n in intervals])[0]>total or any(encode_interval_capacity([(sid,a,b) for sid,a,b,n in intervals if n==node])[0]>per_node for node in nodes):errors.append(f'{label}: observed segment encodes must respect total and per-node caps')
    clocks=[];prefixes=[];playlist_paths=[];hole_observed=False
    for snapshot in report['snapshots']:
        clock=utc(snapshot['observedAt']);clocks.append(clock)
        if clock is None or window is None or not window[0]<=init_at<=clock<=window[1]:errors.append(f'{label}: manifest snapshot UTC must lie in execution window after initialization');continue
        ready_ids={sid for sid,at in times.items() if at<=clock};states=snapshot['segmentStates']
        if len(states)!=count or {s['segmentId'] for s in states}!=set(ids) or any(s['state']!=('ready' if s['segmentId'] in ready_ids else 'queued' if clock<starts[s['segmentId']] else 'encoding') for s in states):errors.append(f'{label}: intermediate state must derive from each completed encode/decode time')
        contiguous=[]
        for s in segments:
            if s['segmentId'] not in ready_ids:break
            contiguous.append(s)
        prefixes.append(len(contiguous));hole_observed=hole_observed or len(ready_ids)>len(contiguous)
        playlist=existing_ref(root,snapshot['playlistRef'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==snapshot['playlistRef']]
        if playlist is None or len(records)!=1 or records[0].get('artifactType')!='command_output' or playlist.stat().st_size>65536 or any(playlist.samefile(p) for p in playlist_paths+media_paths):errors.append(f'{label}: bounded distinct retained manifest bytes required');continue
        playlist_paths.append(playlist)
        try:body=playlist.read_text(encoding='utf8');info=inspect_artifact(playlist,cache)
        except (OSError,UnicodeError):errors.append(f'{label}: UTF8 manifest bytes required');continue
        if info['sha256']!=snapshot['playlistSha256']:errors.append(f'{label}: retained playlist hash mismatch')
        lines=body.splitlines();expected_lines=['#EXTM3U','#EXT-X-VERSION:7','#EXT-X-TARGETDURATION:'+str(math.ceil(max(durations))),'#EXT-X-MEDIA-SEQUENCE:0','#EXT-X-MAP:URI="'+policy['initUri']+'"']
        for s in contiguous:expected_lines.extend(['#EXTINF:'+format(durations[s['index']],'.6f')+',',s['uri']])
        if len(contiguous)==count:expected_lines.append('#EXT-X-ENDLIST')
        if lines!=expected_lines:errors.append(f'{label}: manifest must advertise exactly the contiguous READY prefix and ENDLIST only at full completion')
    if any(t is None for t in clocks) or any(a>=b for a,b in zip(clocks,clocks[1:])) or not hole_observed or not any(0<p<count for p in prefixes) or not prefixes or prefixes[-1]!=count:
        errors.append(f'{label}: retain ordered hole, intermediate prefix and complete manifest snapshots')
    if next((m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict) and m.get('id')=='hls_ready_only_contiguous'),None) is not True:errors.append(f'{label}: boolean gate must agree with observed contiguous READY manifests')


def validate_qualified_media_soak(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-02' or status!='pass':return
    label=f"qualified media soak {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('mediaSoakRef'),defs,'mediaSoakObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None)
    path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('mediaSoakPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('mediaSoakPolicy',{}),label+'/approved soak',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    limits=('minimumDurationMinutes','maximumProgressGapSeconds','maximumRecoverySeconds','maximumResidentBytes','maximumResidentGrowthBytes','maximumTemporaryBytes','maximumCpuSeconds')
    if any(report[k]!=v for k,v in expected.items()) or not all(ai_finite(policy[k]) for k in limits):
        errors.append(f'{label}: approved finite soak budgets and exact selected input/profile/build context required');return
    inventory=env.get('worker_node_inventory');nodes={n['nodeId']:n for n in inventory if isinstance(n,dict) and isinstance(n.get('nodeId'),str)} if isinstance(inventory,list) else {}
    cases=policy['cases'];ids=[c['caseId'] for c in cases];runs=[c['runId'] for c in cases];pairs=[(c['nodeId'],c['codec']) for c in cases]
    if not nodes or len(ids)!=len(set(ids)) or len(runs)!=len(set(runs)) or len(pairs)!=len(set(pairs)) or {n for n,codec in pairs if codec=='av1'}!=set(nodes) or not any(codec=='h264' for _,codec in pairs) or any(n not in nodes for n,_ in pairs) or len(report['cases'])!=len(cases) or {r['caseId'] for r in report['cases']}!=set(ids):
        errors.append(f'{label}: approved complete AV1 inventory coverage and distinct H264 soak workload required');return
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if not ai_finite(actual.get('sustained_encode_duration')) or actual['sustained_encode_duration']+1e-9<policy['minimumDurationMinutes']:
        errors.append(f'{label}: continuous measured duration must cover the independently approved minimum');return
    event_ids=set();media_paths=[];trace_intervals=[]
    for row in report['cases']:
        approved=next(c for c in cases if c['caseId']==row['caseId']);node=nodes[approved['nodeId']];sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==approved['inputSampleId']),None)
        total=(env.get('parallelMediaAssembly') or {}).get('sourceFrameCount') if isinstance(env.get('parallelMediaAssembly'),dict) else None
        if any(row[k]!=v for k,v in approved.items()) or any(approved[k]!=node.get(k) for k in ('encoderBuild','physicalHostId','compatibilityGroupId')) or sample is None or approved['inputSha256']!=sample['checksum'] or type(total) is not int or not 0<=approved['sourceStartFrame']<approved['sourceEndFrame']<=total:
            errors.append(f'{label}: each exercised codec must bind approved node/build/config/command and input span');continue
        first,last=utc(row['startedAt']),utc(row['finishedAt'])
        if first is None or last is None or window is None or not window[0]<=first<last<=window[1] or (last-first).total_seconds()/60+1e-9<policy['minimumDurationMinutes']:
            errors.append(f'{label}: each continuous codec workload must cover the approved minimum within UTC execution');continue
        trace_intervals.append((approved['runId'],first,last,approved['nodeId']))
        if row['processExitCode']!=0 or row['terminalStatus']!='completed' or row['processTerminationReason']!='approved_window_completed':
            errors.append(f'{label}: the complete controlled workload must finish normally with a successful final process exit')
        samples=row['progress'];times=[utc(r['observedAt']) for r in samples]
        if any(t is None for t in times) or times[0]!=first or times[-1]!=last or times!=sorted(times) or any((b-a).total_seconds()>policy['maximumProgressGapSeconds'] for a,b in zip(times,times[1:])):
            errors.append(f'{label}: bounded ordered progress must cover the complete continuous soak without an unobserved gap');continue
        frames=approved['sourceEndFrame']-approved['sourceStartFrame']
        iterations=[s['completedIterations'] for s in samples];cpu=[s['cpuSeconds'] for s in samples];resident=[s['residentBytes'] for s in samples]
        progress_times=[first]+[times[i] for i in range(1,len(samples)) if iterations[i]>iterations[i-1]]+[last]
        if iterations[0]!=0 or iterations[-1]<=0 or iterations!=sorted(iterations) or any((b-a).total_seconds()>policy['maximumProgressGapSeconds'] for a,b in zip(progress_times,progress_times[1:])) or any(s['completedFrames']!=s['completedIterations']*frames for s in samples) or not all(ai_finite(s[k]) for s in samples for k in ('completedIterations','completedFrames','residentBytes','temporaryBytes','cpuSeconds')) or cpu!=sorted(cpu) or cpu[-1]>policy['maximumCpuSeconds'] or max(resident)>policy['maximumResidentBytes'] or max(resident)-resident[0]>policy['maximumResidentGrowthBytes'] or any(s['temporaryBytes']>policy['maximumTemporaryBytes'] for s in samples) or samples[-1]['temporaryBytes']!=0:
            errors.append(f'{label}: actual completed iterations/frames and CPU/memory/temp observations must remain within approved stability budgets')
        for event in row['failureEvents']:
            occurred,recovered=utc(event['occurredAt']),utc(event['recoveredAt']) if event['recoveredAt'] is not None else None
            if event['eventId'] in event_ids or event['kind'] in ('gpu_hang','corrupt_segment') or occurred is None or recovered is None or not first<=occurred<=recovered<=last or (recovered-occurred).total_seconds()>policy['maximumRecoverySeconds']:
                errors.append(f'{label}: no GPU hang, corrupt segment or unrecovered/out-of-bound encoder/runtime failure may qualify')
            event_ids.add(event['eventId'])
        ref=row['outputArtifactRef'];media=existing_ref(root,ref,prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==ref]
        if media is None or ref not in (execution.get('rawOutputRefs') or []) or len(records)!=1 or records[0].get('artifactType')!='produced_media' or records[0].get('nodeId')!=approved['nodeId']:
            errors.append(f'{label}: codec soak must retain its exact node-bound produced output');continue
        try:
            info=inspect_artifact(media,cache)
            separate=[env.get('mediaSoakRef'),row['decodeRef']]+[a.get('ref') for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('artifactType')=='produced_media' and a.get('ref')!=ref]+[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]
            if info['size']<=0 or info['size']!=row['outputByteCount'] or info['sha256']!=row['outputSha256'] or any(media.samefile(p) for p in media_paths) or any(media.samefile(p) for other in separate if (p:=existing_ref(root,other,prefix)) is not None):raise ValueError()
            media_paths.append(media)
        except (OSError,ValueError):errors.append(f'{label}: distinct retained codec outputs must bind actual nonempty bytes/hash');continue
        decode_before=len(errors);probe=selected_observation(root,execution,prefix,row['decodeRef'],defs,'mediaSoakDecodeObservation',label+'/decode',errors,cache)
        if probe is None or len(errors)!=decode_before:continue
        keys=('runId','caseId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame','codec')
        decoded=utc(probe['observedAt'])
        if any(probe[k]!=approved[k] for k in keys) or probe['outputArtifactRef']!=ref or probe['outputSha256']!=row['outputSha256'] or probe['decodable'] is not True or probe['decodedFrameCount']!=frames or probe['decodeErrorCount']!=0 or not ai_finite(probe['durationSeconds']) or probe['durationSeconds']<=0 or decoded is None or not last<=decoded<=window[1]:
            errors.append(f'{label}: each sustained codec output must decode its approved span without errors after the measured workload')
    if env.get('acceptanceProfile')==profile_identity('local-v1'):
        caps=env.get('scheduler_configuration');caps=caps if isinstance(caps,dict) else {}
        if type(caps.get('maxConcurrentSegments')) is not int or type(caps.get('perNodeConcurrency')) is not int or encode_interval_capacity([(r,a,b) for r,a,b,_ in trace_intervals])[0]>caps.get('maxConcurrentSegments',0) or any(encode_interval_capacity([(r,a,b) for r,a,b,n in trace_intervals if n==node])[0]>caps.get('perNodeConcurrency',0) for node in nodes):errors.append(f'{label}: controlled soak must respect approved total and per-node concurrency')
    if actual.get('sustained_encode_stability') is not (len(errors)==before):errors.append(f'{label}: stability gate must derive complete continuous workload and failure/resource/decode observations')


def validate_qualified_h264_fallback(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-02' or status!='pass':return
    label=f"qualified H264 fallback {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report_ref=env.get('h264FallbackRef')
    report=selected_observation(root,execution,prefix,report_ref,defs,'mediaFallbackObservation',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None)
    path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('mediaFallbackPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('mediaFallbackPolicy',{}),label+'/approved fallback',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    sample=next((s for s in execution.get('samples') or [] if isinstance(s,dict) and s.get('id')==policy['inputSampleId']),None)
    inventory=env.get('worker_node_inventory');nodes=[n for n in inventory if isinstance(n,dict) and n.get('nodeId')==policy['nodeId']] if isinstance(inventory,list) else []
    assembly=env.get('parallelMediaAssembly');total=assembly.get('sourceFrameCount') if isinstance(assembly,dict) else None
    if any(report[k]!=v for k,v in expected.items()) or any(report[k]!=v for k,v in policy.items()) or sample is None or policy['inputSha256']!=sample['checksum'] or len(nodes)!=1 or any(policy[k]!=nodes[0].get(k) for k in ('physicalHostId','encoderBuild','compatibilityGroupId')) or type(total) is not int or not 0<=policy['sourceStartFrame']<policy['sourceEndFrame']<=total:
        errors.append(f'{label}: exact approved input, participating node/build/profile and fallback parameters/span required');return
    start,end=utc(report['startedAt']),utc(report['finishedAt'])
    if start is None or end is None or window is None or not window[0]<=start<end<=window[1] or report['exitCode']!=0 or report['encodedFrameCount']!=policy['sourceEndFrame']-policy['sourceStartFrame']:
        errors.append(f'{label}: successful ordered H264 encode must cover its approved frame span inside execution');return
    probe=selected_observation(root,execution,prefix,report['decodeRef'],defs,'mediaFallbackDecodeObservation',label+'/decode',errors,cache)
    if probe is None or len(errors)!=before:return
    identity={k:policy[k] for k in ('runId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame','codec')}
    decoded=utc(probe['observedAt'])
    if any(probe[k]!=v for k,v in identity.items()) or probe['outputArtifactRef']!=report['outputArtifactRef'] or probe['outputSha256']!=report['outputSha256'] or probe['decodable'] is not True or probe['decodedFrameCount']!=report['encodedFrameCount'] or probe['decodeErrorCount']!=0 or not ai_finite(probe['durationSeconds']) or probe['durationSeconds']<=0 or decoded is None or not end<=decoded<=window[1]:
        errors.append(f'{label}: exact retained H264 output must decode its complete span with approved decoder and zero errors');return
    ref=report['outputArtifactRef'];records=[r for r in env.get('rawExecutionArtifacts') or [] if isinstance(r,dict) and r.get('ref')==ref];media=existing_ref(root,ref,prefix)
    if media is None or ref not in (execution.get('rawOutputRefs') or []) or len(records)!=1 or records[0].get('artifactType')!='produced_media' or records[0].get('nodeId')!=policy['nodeId']:
        errors.append(f'{label}: exact node-bound nonempty produced H264 bytes required');return
    distinct=[report_ref,report['decodeRef']]+[r.get('ref') for r in env.get('rawExecutionArtifacts') or [] if isinstance(r,dict) and r.get('artifactType')=='produced_media' and r.get('ref')!=ref]+[r.get('inputArtifactRef') for r in env.get('inputSampleArtifacts') or [] if isinstance(r,dict)]
    try:
        actual=inspect_artifact(media,cache)
        if actual['size']<=0 or actual['size']!=report['outputByteCount'] or actual['sha256']!=report['outputSha256'] or any(media.samefile(other) for other_ref in distinct if (other:=existing_ref(root,other_ref,prefix)) is not None):raise ValueError('invalid fallback output binding')
    except (OSError,ValueError):errors.append(f'{label}: H264 output bytes/hash must be distinct from AV1 outputs, source input and observation artifacts')


def validate_qualified_encode_workers(root, plan, execution, prefix, status, window, errors, artifact_cache=None, defs=None):
    artifact_cache = {} if artifact_cache is None else artifact_cache
    if plan['pocId'] != 'POC-02' or status != 'pass':
        return
    label = f"qualified encode workers {plan['taskId']}"
    env = execution.get('environmentCaptured') or {}
    inventory = env.get('worker_node_inventory')
    required = {'nodeId','platform','physicalHostId','encoderBuild','compatibilityGroupId'}
    if not isinstance(inventory,list) or len(inventory) < 2 or any(not isinstance(node,dict) or not required.issubset(node) or any(not recorded_text(node[key]) for key in required) for node in inventory):
        errors.append(f'{label}: typed worker inventory requires at least two identified tested nodes')
        return
    nodes = {node['nodeId']:node for node in inventory}
    if len(nodes) != len(inventory) or not {'windows','linux'}.issubset({node['platform'] for node in inventory}):
        errors.append(f'{label}: distinct Windows and Linux workers are required')
    if len({node['compatibilityGroupId'] for node in inventory}) != 1:
        errors.append(f'{label}: parallel encode workers must bind the same admitted compatibility group')
    scope = env.get('physical_host_scope')
    hosts = {node['physicalHostId'] for node in inventory}
    if not isinstance(scope,dict) or not isinstance(scope.get('physicalHostIds'),list) or any(not recorded_text(host) for host in scope['physicalHostIds']) or set(scope['physicalHostIds']) != hosts or scope.get('physicalMultiHostValidated') is not (len(hosts) > 1):
        errors.append(f'{label}: physical host scope must bind inventory and disclose same-host limits')
    capabilities = env.get('encoder_capability_matrix')
    if not isinstance(capabilities,list) or len(capabilities) != len(nodes):
        errors.append(f'{label}: typed AV1 capability matrix must cover exact inventory')
        return
    seen = set()
    for capability in capabilities:
        if not isinstance(capability,dict) or not isinstance(capability.get('nodeId'),str) or capability['nodeId'] not in nodes:
            errors.append(f'{label}: capability must bind an inventory node')
            continue
        node = nodes[capability['nodeId']]
        if capability['nodeId'] in seen or capability.get('encoderBuild') != node['encoderBuild'] or capability.get('compatibilityGroupId') != node['compatibilityGroupId'] or capability.get('codec') != 'av1' or capability.get('supported') is not True:
            errors.append(f'{label}: tested AV1 capability must bind exact node/build')
        seen.add(capability['nodeId'])
    runs = env.get('workerEncodeExecutions')
    if not isinstance(runs,list) or len(runs) < 2:
        errors.append(f'{label}: identified parallel worker encode executions are required')
        return
    artifacts = {record.get('ref'):record for record in env.get('rawExecutionArtifacts') or [] if isinstance(record,dict) and isinstance(record.get('ref'),str)}
    inputs = {sample.get('checksum') for sample in execution.get('samples') or []}
    intervals = []
    stream_intervals = []
    run_paths = []
    run_refs = set()
    completed = set()
    for run in runs:
        if not isinstance(run,dict) or not isinstance(run.get('nodeId'),str) or run['nodeId'] not in nodes:
            errors.append(f'{label}: encode execution must bind an inventory node')
            continue
        node = nodes[run['nodeId']]
        start,end = utc(run.get('startedAt')),utc(run.get('finishedAt'))
        if start is None or end is None or not start < end or window is None or not window[0] <= start < end <= window[1]:
            errors.append(f'{label}: worker encode interval must be positive and within executionWindow')
        else:
            intervals.append((run['nodeId'],start,end))
        if run.get('encoderBuild') != node['encoderBuild'] or run.get('compatibilityGroupId') != node['compatibilityGroupId'] or not isinstance(run.get('inputSha256'),str) or run['inputSha256'] not in inputs:
            errors.append(f'{label}: worker encode must bind tested build and approved input')
        for key,kind in (('rawOutputRef','command_output'),('outputArtifactRef','produced_media')):
            artifact = artifacts.get(run[key]) if isinstance(run.get(key),str) else None
            if artifact is None or artifact.get('artifactType') != kind or artifact.get('nodeId') != node['nodeId']:
                errors.append(f'{label}: worker artifacts must bind exact node and artifact type')
        output = existing_ref(root,run.get('outputArtifactRef'),prefix)
        if output is None or output.stat().st_size == 0 or run.get('outputSha256') != inspect_artifact(output,artifact_cache)['sha256']:
            errors.append(f'{label}: worker output hash must bind nonempty produced bytes')
        trace=existing_ref(root,run.get('rawOutputRef'),prefix)
        pair=(run.get('rawOutputRef'),run.get('outputArtifactRef'))
        if any(not isinstance(ref,str) for ref in pair) or any(ref in run_refs for ref in pair) or (trace and output and trace.samefile(output)) or any(path.samefile(prior) for path in (trace,output) if path for prior in run_paths):
            errors.append(f'{label}: each stream requires unique physically distinct trace and output identities')
        else:
            run_refs.update(pair)
            run_paths.extend(path for path in (trace,output) if path)
            if start is not None and end is not None and start<end:
                stream_intervals.append((pair,start,end,node['nodeId']))
        completed.add(node['nodeId'])
    if completed != set(nodes) or not any(a[0] != b[0] and max(a[1],b[1]) < min(a[2],b[2]) for i,a in enumerate(intervals) for b in intervals[i+1:]):
        errors.append(f'{label}: all inventory nodes must execute, with overlapping work on distinct nodes')
    _,minutes=encode_interval_capacity(intervals)
    peak,_=encode_interval_capacity([(identity,start,end) for identity,start,end,_ in stream_intervals])
    if (env.get('acceptanceProfile') or {}).get('id')=='local-v1':
        caps=env.get('scheduler_configuration')
        caps=caps if isinstance(caps,dict) else {}
        total_cap,per_node=caps.get('maxConcurrentSegments'),caps.get('perNodeConcurrency')
        if type(total_cap) is not int or total_cap<1 or type(per_node) is not int or per_node<1:
            errors.append(f'{label}: positive integer local concurrency caps required')
        elif peak>total_cap or any(encode_interval_capacity([(identity,start,end) for identity,start,end,owner in stream_intervals if owner==node])[0]>per_node for node in nodes):
            errors.append(f'{label}: captured stream concurrency exceeds approved total/per-node caps')
    measurements={item.get('id'):item.get('actual') for item in execution.get('measurements') or [] if isinstance(item,dict)}
    for metric,observed in (('encode_throughput',peak),('sustained_encode_duration',minutes)):
        actual=measurements.get(metric)
        if metric=='sustained_encode_duration' and (not ai_finite(actual) or not math.isclose(actual,observed,rel_tol=1e-9,abs_tol=1e-9)):
            errors.append(f'{label}: sustained_encode_duration must equal captured continuous worker interval capacity in minutes')
        elif metric=='encode_throughput' and (not ai_finite(actual) or actual!=observed):
            errors.append(f'{label}: {metric} must equal captured continuous worker interval capacity')
    validate_qualified_media_assembly(root,execution,prefix,runs,artifacts,defs or {},errors,artifact_cache)


def validate_qualified_a380_encode(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-02' or status!='pass' or (env.get('acceptanceProfile') or {}).get('id')!='production':return
    label=f"qualified A380 encode {plan['taskId']}";capture=env.get('productionA380Encode');before=len(errors)
    validate_schema(capture,defs.get('productionA380Encode',{}),label,errors)
    if not isinstance(capture,dict) or len(errors)!=before:return
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-A380-ENCODE'),None)
    if resource is None or capture['configurationRef']!=resource.get('configurationRef'):
        errors.append(f'{label}: exact approved RES-A380-ENCODE configuration required');return
    config_path=existing_ref(root,capture['configurationRef'],prefix)
    try:approved=load(config_path).get('configuration',{}).get('productionA380Encode') if config_path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):approved=None
    if not isinstance(approved,dict) or approved.get('identity')!=capture['identity']:
        errors.append(f'{label}: exact previously approved A380 device/host/driver/runtime/encoder identity required');return
    identity=capture['identity'];nodes=env.get('worker_node_inventory') or [];runs=env.get('workerEncodeExecutions') or []
    if not isinstance(nodes,list) or not isinstance(runs,list):
        errors.append(f'{label}: typed inventory and encode-run lists required');return
    if any(not recorded_text(value) for key,value in identity.items() if key!='schemaVersion'):
        errors.append(f'{label}: concrete A380 identity values required');return
    selected_nodes=[n for n in nodes if isinstance(n,dict) and n.get('nodeId')==identity['nodeId']]
    selected_runs=[r for r in runs if isinstance(r,dict) and r.get('nodeId')==identity['nodeId'] and r.get('outputArtifactRef')==capture['outputArtifactRef']]
    keys=('nodeId','physicalHostId','platform','gpuVendor','gpuModel','gpuDeviceId','driverBuild','runtimeBuild','encoderBuild','encoderBackend')
    if len(selected_nodes)!=1 or any(selected_nodes[0].get(k)!=identity[k] for k in keys) or len(selected_runs)!=1:
        errors.append(f'{label}: approved physical A380 must bind one inventory node and designated encode run/output');return
    run=selected_runs[0]
    if any(run.get(k)!=identity[k] for k in ('encoderBuild','gpuDeviceId','driverBuild','runtimeBuild','encoderBackend')):
        errors.append(f'{label}: designated encode must use the approved hardware device and builds');return
    start,end=utc(run.get('startedAt')),utc(run.get('finishedAt'))
    if start is None or end is None or window is None or not window[0]<=start<end<=window[1]:
        errors.append(f'{label}: valid designated A380 encode interval required');return
    before=len(errors)
    telemetry=selected_observation(root,execution,prefix,capture['telemetryRef'],defs,'a380TelemetryObservation',label,errors,cache)
    request=selected_observation(root,execution,prefix,capture['rangeRef'],defs,'a380RangeObservation',label,errors,cache)
    if len(errors)!=before or telemetry is None or request is None:return
    expected=dict(identity=identity,configurationRef=capture['configurationRef'],inputSampleId=run.get('inputSampleId'),inputSha256=run.get('inputSha256'),outputArtifactRef=run.get('outputArtifactRef'),outputSha256=run.get('outputSha256'))
    if any(report.get(k)!=v for report in (telemetry,request) for k,v in expected.items()):
        errors.append(f'{label}: observations must bind the exact approved device, input and produced output')
    sampling=approved.get('telemetrySampling')
    before=len(errors);validate_schema(sampling,defs.get('a380TelemetrySampling',{}),label,errors)
    if len(errors)!=before:return
    if telemetry['sampling']!=sampling:errors.append(f'{label}: telemetry must bind approved sampling tool/build/interval/scope/phases')
    step=sampling['intervalSeconds'];phases=sampling['phases'];phase_windows=[]
    if isinstance(step,bool) or not math.isfinite(step) or step<=0 or not recorded_text(sampling['toolBuild']):
        errors.append(f'{label}: concrete sampling tool and finite positive interval required');return
    for phase in phases:
        first,last=utc(phase['startedAt']),utc(phase['finishedAt'])
        if first is None or last is None or not start<=first<last<=end:
            errors.append(f'{label}: each approved workload phase needs valid UTC encode endpoints');return
        phase_windows.append((phase['phase'],first,last))
    if [p[0] for p in phase_windows]!=['warmup','concurrency','soak'] or phase_windows[0][1]!=start or phase_windows[-1][2]!=end or any(a[2]!=b[1] for a,b in zip(phase_windows,phase_windows[1:])):
        errors.append(f'{label}: approved warmup/concurrency/soak phases must cover the designated workload');return
    stamps=[];observed_phases=set();power=[];temperature=[]
    for row in telemetry['samples']:
        at=utc(row['observedAt']);watts=row['powerWatts'];celsius=row['temperatureCelsius']
        if at is None or not any(row['phase']==name and first<=at<=last for name,first,last in phase_windows) or isinstance(watts,bool) or not isinstance(watts,(int,float)) or not math.isfinite(watts) or watts<0 or isinstance(celsius,bool) or not isinstance(celsius,(int,float)) or not math.isfinite(celsius):
            errors.append(f'{label}: retained telemetry samples require finite readings and exact UTC workload phase');return
        stamps.append(at);observed_phases.add(row['phase']);power.append(watts);temperature.append(celsius)
    if observed_phases!={'warmup','concurrency','soak'} or stamps[0]!=start or stamps[-1]!=end or any(not math.isclose((b-a).total_seconds(),step,rel_tol=1e-9,abs_tol=1e-9) for a,b in zip(stamps,stamps[1:])):
        errors.append(f'{label}: actual sampling timestamps must cover all phases at the approved interval')
    if not recorded_text(approved.get('outputServingPath')) or request['mediaPath']!=approved['outputServingPath']:
        errors.append(f'{label}: first-byte request must use the approved produced-media serving path')
    output=existing_ref(root,capture['outputArtifactRef'],prefix);body=existing_ref(root,request['responseBodyRef'],prefix)
    artifacts=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==request['responseBodyRef']]
    if output is None or body is None or len(artifacts)!=1 or artifacts[0].get('artifactType')!='produced_media' or artifacts[0].get('nodeId')!=identity['nodeId'] or request['responseBodyRef'] not in (execution.get('rawOutputRefs') or []):
        errors.append(f'{label}: retained response bytes must bind the A380 node in this selected slot');return
    paths=[existing_ref(root,capture[key],prefix) for key in ('telemetryRef','rangeRef','outputArtifactRef')]+[body]
    if any(a.samefile(b) for i,a in enumerate(paths) if a for b in paths[i+1:] if b):errors.append(f'{label}: telemetry, request, media and returned bytes must be physically distinct')
    first,last=request['rangeStart'],request['rangeEnd'];began,received=utc(request['requestStartedAt']),utc(request['firstByteAt'])
    try:
        source=inspect_artifact(output,cache,byte_range=(first,last));response=inspect_artifact(body,cache)
    except OSError as exc:
        errors.append(f'{label}: cannot read actual produced/returned Range bytes: {exc}');return
    if request['statusCode']!=206 or request['contentRange']!=f'bytes {first}-{last}/{source["size"]}' or request['requestRange']!=f'bytes={first}-{last}' or not 0<=first<=last<source['size'] or response['size']!=last-first+1 or response['sha256']!=request['responseSha256']:
        errors.append(f'{label}: retained Range status/headers/body hash must match the produced byte interval');return
    range_hash=source.get('rangeHashes',{}).get((first,last))
    if response['sha256']!=range_hash:errors.append(f'{label}: actual Range response must equal exact A380-produced media bytes')
    if began is None or received is None or not end<=began<=received<=window[1]:
        errors.append(f'{label}: first-byte request must follow the designated encode inside executionWindow');return
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    for metric,value in (('encoder_power_peak_watts',max(power)),('encoder_temperature_peak_celsius',max(temperature)),('a380_range_first_byte_latency',(received-began).total_seconds()*1000)):
        claimed=actual.get(metric)
        if isinstance(claimed,bool) or not isinstance(claimed,(int,float)) or not math.isfinite(claimed) or not math.isclose(claimed,value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must equal actual retained telemetry/request observation')



MEDIA_NEGATIVE_GATES={'disallowed_input_targets_denied','resource_limits_enforced','worker_interruption_idempotent_recovery','cancellation_cleanup_complete','attempt_fencing_single_publish','seek_epoch_rejects_stale_demand','hls_acl_and_revocation'}


LOCAL_STORAGE_OBSERVED_GATES={'local_authenticated_reads','local_range_correctness','local_read_hash_verified','openlist_disconnect_recovery','local_backup_restore_verified','incomplete_replica_rejected','hash_mismatch_replica_rejected','cache_eviction_preserves_authoritative_state','replica_migration_preserves_old_valid_copy','local_capacity_reservations_preserved','watermark_behavior','concurrent_workload_stability','failure_recovery'}


def validate_qualified_local_storage(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-04' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('local-v1'):return
    label=f"qualified local storage {plan['taskId']}";before=len(errors);report=selected_observation(root,execution,prefix,env.get('localStorageRef'),defs,'localStorageOutcomes',label,errors,cache);resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-OPENLIST-LOCAL'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('localStoragePolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('localStoragePolicy',{}),label+'/approved sandbox controls',errors)
    if report is None or len(errors)!=before:return
    samples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []];expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=compliance_subject_version(plan,execution),inputSamples=samples)
    if any(report[k]!=v for k,v in expected.items()) or policy['subjectVersion']!=expected['subjectVersion'] or policy['sandboxRoot']!=env.get('sandbox_root_boundary') or policy['openlistBuild']!=env.get('openlist_version') or policy['authorizedAuthRef']==policy['invalidAuthRef']:
        errors.append(f'{label}: exact approved OpenList build/root/profile/input and distinct credential references required');return
    objects=policy['objects'];sample_map={s['id']:s for s in samples};inputs={r['sampleId']:r for r in env.get('inputSampleArtifacts') or [] if isinstance(r,dict)};artifacts={a.get('ref'):a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and isinstance(a.get('ref'),str)}
    if len(objects)!=len(samples) or {r['sampleId'] for r in objects}!=set(sample_map) or len({r['assetId'] for r in objects})!=len(objects):errors.append(f'{label}: every approved immutable input needs one distinct governed sandbox object');return
    request_ids=set();state_times={}
    observation_refs={r.get('originAccessRef') for row in report['objects'] for r in row['requests']}|{row.get('concurrentWorkloadRef') for row in report['objects']}
    observation_paths=[path,existing_ref(root,env.get('localStorageRef'),prefix)]+[existing_ref(root,r.get('inputArtifactRef'),prefix) for r in inputs.values()]+[existing_ref(root,ref,prefix) for ref in artifacts if ref not in observation_refs]
    def independent_observation(ref,schema):
        count=len(errors);result=selected_observation(root,execution,prefix,ref,defs,schema,label,errors,cache);location=existing_ref(root,ref,prefix)
        if result is None or len(errors)!=count:return None
        if any(location.samefile(other) for other in observation_paths if other is not None):errors.append(f'{label}: request/workload observations must be physically distinct from inputs, structured state, returned bytes and other observations')
        observation_paths.append(location)
        if any(result.get(key)!=value for key,value in expected.items()):errors.append(f'{label}: independent observation must bind the same approved configuration/profile/subject/input')
        return result
    def interval(first,last):
        start,end=utc(first),utc(last)
        if start is None or end is None or window is None or not window[0]<=start<=end<=window[1]:errors.append(f'{label}: ordered actual sandbox operation timestamps inside execution required');return None
        return start,end
    def bytes_info(ref,digest):
        file=existing_ref(root,ref,prefix)
        if file is None or artifacts.get(ref,{}).get('artifactType')!='produced_media' or ref not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: actual selected-slot storage/returned bytes required');return None
        info=inspect_artifact(file,cache)
        if info['sha256']!=digest:errors.append(f'{label}: actual retained storage byte digest mismatch')
        return info
    def state(ref):
        count=len(errors);result=selected_observation(root,execution,prefix,ref,defs,'localStorageState',label,errors,cache)
        if result is None or len(errors)!=count:return None
        captured=utc(result['observedAt'])
        if captured is None or window is None or not window[0]<=captured<=window[1]:errors.append(f'{label}: actual state snapshot timestamp inside execution required');return None
        state_times[ref]=captured
        if any(result[k]!=expected[k] for k in expected):errors.append(f'{label}: every before/after snapshot must bind the same approved sandbox subjects')
        for field,key in (('assets','assetId'),('sourceMappings','objectId'),('retention','assetId'),('replicas','replicaId'),('caches','cacheId')):
            if len({r[key] for r in result[field]})!=len(result[field]):errors.append(f'{label}: state identities must be unique')
        return result['states'] if 'states' in result else {k:result[k] for k in ('assets','sourceMappings','retention','replicas','caches')}
    def semantic(value):
        if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if k!='payloadRef'}
        if isinstance(value,list):return [semantic(v) for v in value]
        return value
    baseline=state(report['baselineStateRef'])
    if baseline is None:return
    if semantic(baseline)!=semantic(policy['baselineState']):errors.append(f'{label}: baseline must match independently approved governed state')
    known={r['assetId']:r for r in objects}
    if {r['assetId'] for r in baseline['assets']}!=set(known) or {r['assetId'] for r in baseline['retention']}!=set(known):errors.append(f'{label}: baseline must represent all approved assets and retention')
    for obj in objects:
        if not any(r['assetId']==obj['assetId'] and r['versionId']==obj['versionId'] for r in baseline['assets']) or not any(r['sourceId']==obj['sourceId'] and r['objectId']==obj['objectId'] and r['assetId']==obj['assetId'] and r['versionId']==obj['versionId'] for r in baseline['sourceMappings']):errors.append(f'{label}: approved object/asset/version/source mapping relationships must be represented in baseline')
    for field in ('replicas','caches'):
        for entry in baseline[field]:
            obj=known.get(entry['assetId']);info=bytes_info(entry['payloadRef'],entry['sha256'])
            if obj is None or entry['versionId']!=obj['versionId'] or info is None or info['sha256']!=sample_map[obj['sampleId']]['checksum'] or entry['state']!=('VERIFIED' if field=='replicas' else 'COMPLETE'):errors.append(f'{label}: baseline copies must bind verified approved asset-version bytes')
    rows=report['objects']
    if len(rows)!=len(objects) or {r['sampleId'] for r in rows}!={r['sampleId'] for r in objects}:errors.append(f'{label}: complete per-input storage outcome matrix required');return
    measured_full=[];concurrent=[]
    for row in rows:
        obj=next(r for r in objects if r['sampleId']==row['sampleId']);sample=sample_map[row['sampleId']];source_record=inputs.get(sample['id']);source=existing_ref(root,source_record.get('inputArtifactRef'),prefix) if source_record else None
        if source is None or obj['versionId']!=sample['immutableId']:errors.append(f'{label}: exact approved immutable source object required');continue
        source_info=inspect_artifact(source,cache)
        if source_info['size']<8 or source_info['sha256']!=sample['checksum']:errors.append(f'{label}: independently approved nonempty source bytes required');continue
        total=source_info['size'];requests=row['requests'];required={'full','bounded','suffix','unsatisfiable','missing_auth','invalid_auth','concurrent_a','concurrent_b'}
        if len(requests)!=8 or {r['case'] for r in requests}!=required:errors.append(f'{label}: full/auth/Range/concurrent read controls required')
        object_concurrent=[]
        for request in requests:
            kind=request['case'];info=bytes_info(request['responseRef'],request['responseSha256']);timing=interval(request['startedAt'],request['finishedAt']);authorized=kind not in ('missing_auth','invalid_auth');credential=policy['authorizedAuthRef'] if authorized else policy['invalidAuthRef'] if kind=='invalid_auth' else None
            if request['requestId'] in request_ids or request['objectURL']!=obj['objectURL'] or request['assetId']!=obj['assetId'] or request['versionId']!=obj['versionId'] or request['authRef']!=credential or info is None or source.samefile(existing_ref(root,request['responseRef'],prefix)) or timing and state_times[report['baselineStateRef']]>timing[0]:errors.append(f'{label}: actual authenticated response must bind approved object/version/path, prior baseline and distinct returned bytes');continue
            request_ids.add(request['requestId'])
            origin=independent_observation(request['originAccessRef'],'localStorageOriginAccessObservation')
            if origin is not None:
                binding={key:request[key] for key in ('case','requestId','objectURL','assetId','versionId','authRef','requestRange','statusCode','startedAt','finishedAt')};binding.update(sourceId=obj['sourceId'],objectId=obj['objectId'])
                if any(origin.get(key)!=value for key,value in binding.items()):errors.append(f'{label}: origin observation must bind the exact request, credential, source/object/version and UTC interval')
                if not authorized and (origin['originRequestCount']!=0 or origin['objectReadCount']!=0):errors.append(f'{label}: denied authentication must precede all origin requests and protected object reads')
            if not authorized:
                if request['statusCode'] not in (401,403) or request['originByteCount']!=0 or info['size']!=0:errors.append(f'{label}: missing or invalid credentials must expose no object bytes')
                continue
            if kind=='unsatisfiable':
                if request['requestRange']!=f'bytes={total}-' or request['statusCode']!=416 or request['contentRange']!=f'bytes */{total}' or info['size']!=0:errors.append(f'{label}: unsatisfiable Range status/header/body mismatch')
                continue
            first,last=(0,7) if kind=='bounded' else (total-4,total-1) if kind=='suffix' else (0,total-1);request_range='bytes=0-7' if kind=='bounded' else 'bytes=-4' if kind=='suffix' else None;partial=kind in ('bounded','suffix');expected_range=f'bytes {first}-{last}/{total}' if partial else None
            observed=inspect_artifact(source,cache,byte_range=(first,last));digest=observed['rangeHashes'].get((first,last))
            if request['requestRange']!=request_range or request['statusCode']!=(206 if partial else 200) or request['contentRange']!=expected_range or info['size']!=last-first+1 or info['sha256']!=digest or request['originByteCount']!=info['size']:errors.append(f'{label}: actual full/bounded/suffix bytes and HTTP headers must match approved source')
            if kind=='full' and timing and timing[1]>timing[0]:measured_full.append((info['size'],(timing[1]-timing[0]).total_seconds()))
            if kind.startswith('concurrent_') and timing:object_concurrent.append(timing)
        if len(object_concurrent)!=2 or max(r[0] for r in object_concurrent)>=min(r[1] for r in object_concurrent):errors.append(f'{label}: actual concurrent successful reads must overlap')
        concurrent.extend(object_concurrent)
        copies=row['copyRejections']
        if len(copies)!=2 or {c['case'] for c in copies}!={'incomplete','hash_mismatch'}:errors.append(f'{label}: incomplete and hash-mismatch promotion attempts required')
        for copy in copies:
            info=bytes_info(copy['payloadRef'],copy['sha256']);after=state(copy['afterStateRef']);timing=interval(copy['startedAt'],copy['finishedAt'])
            invalid=info is not None and (0<info['size']<total if copy['case']=='incomplete' else info['size']==total and info['sha256']!=sample['checksum'])
            if not invalid or copy['assetId']!=obj['assetId'] or copy['versionId']!=obj['versionId'] or copy['expectedSha256']!=sample['checksum'] or copy['promotionDecision']!='rejected' or after is None or semantic(after)!=semantic(baseline) or timing and state_times.get(copy['afterStateRef'],timing[0])<timing[1]:errors.append(f'{label}: actual invalid copy must be rejected without authoritative-state promotion or mutation')
        disconnect=row['disconnect'];attempts=disconnect['attempts'];after=state(disconnect['afterStateRef'])
        if not 2<=len(attempts)<=policy['maximumRetries']+1 or after is None or semantic(after)!=semantic(baseline):errors.append(f'{label}: bounded disconnect/restart recovery must preserve governed state')
        last=None
        for index,attempt in enumerate(attempts):
            timing=interval(attempt['startedAt'],attempt['finishedAt']);info=bytes_info(attempt['responseRef'],attempt['responseSha256']);complete=index==len(attempts)-1
            if timing is None or info is None or attempt['attemptNo']!=index+1 or timing and last is not None and timing[0]<last or attempt['transport']!=('success' if complete else 'disconnected') or complete and (info['sha256']!=sample['checksum'] or info['size']!=total) or not complete and not info['size']<total or attempt['partialPromotedCount']!=0:errors.append(f'{label}: disconnect recovery must retain ordered failed partial reads and final verified full bytes without promotion')
            if timing:last=timing[1]
        restart=utc(disconnect['serviceRestartedAt'])
        interrupted=utc(attempts[0]['finishedAt']) if attempts else None;recovered=utc(attempts[-1]['startedAt']) if attempts else None
        if restart is None or interrupted is None or recovered is None or len(attempts)<2 or not interrupted<=restart<=recovered:errors.append(f'{label}: observed OpenList restart must precede successful recovery')
        recovery_finished=utc(attempts[-1]['finishedAt']) if attempts else None
        if after is not None and (recovery_finished is None or state_times[disconnect['afterStateRef']]<recovery_finished):errors.append(f'{label}: recovered state snapshot must follow the final verified retry')
        backup=row['backupRestore'];backup_info=bytes_info(backup['backupDataRef'],backup['backupSha256']);restore_info=bytes_info(backup['restoredDataRef'],backup['restoredSha256']);backup_state=state(backup['backupStateRef']);restored_state=state(backup['restoredStateRef']);interval(backup['startedAt'],backup['finishedAt'])
        backup_path=existing_ref(root,backup['backupDataRef'],prefix);restored_path=existing_ref(root,backup['restoredDataRef'],prefix)
        if backup_path is not None and restored_path is not None and backup_path.samefile(restored_path):errors.append(f'{label}: backup and post-restore readback must be physically distinct phase artifacts')
        if backup_info is None or restore_info is None or backup_info['sha256']!=sample['checksum'] or restore_info['sha256']!=sample['checksum'] or backup_state is None or restored_state is None or semantic(backup_state)!=semantic(baseline) or semantic(restored_state)!=semantic(baseline):errors.append(f'{label}: actual backup and restored data hashes plus governed metadata state must match baseline')
        if backup_state is not None and restored_state is not None:
            for captured,ref,digest in ((backup_state,backup['backupDataRef'],backup['backupSha256']),(restored_state,backup['restoredDataRef'],backup['restoredSha256'])):
                if not any(r['replicaId']==obj['oldReplicaId'] and r['payloadRef']==ref and r['sha256']==digest for r in captured['replicas']):errors.append(f'{label}: captured backup/restored replica state must point to its actually compared data bytes')
        if backup_state is not None and restored_state is not None and (utc(backup['startedAt']) is None or utc(backup['finishedAt']) is None or not utc(backup['startedAt'])<=state_times[backup['backupStateRef']]<=utc(backup['finishedAt'])<=state_times[backup['restoredStateRef']]):errors.append(f'{label}: captured backup/restore state clocks must bind the actual backup operation')
        eviction=state(row['evictionAfterStateRef']);expected_evicted={**baseline,'caches':[r for r in baseline['caches'] if r['assetId']!=obj['assetId']]}
        evicted_at=utc(row['evictedAt'])
        if eviction is None or semantic(eviction)!=semantic(expected_evicted) or evicted_at is None or not state_times[report['baselineStateRef']]<=evicted_at<=state_times[row['evictionAfterStateRef']]:errors.append(f'{label}: cache eviction must remove only this cache while preserving authoritative assets/links/retention/formal replicas')
        migration=row['migration'];during=state(migration['copyingStateRef']);after=state(migration['verifiedStateRef']);candidate=migration['newReplicaId'];old=[r for r in baseline['replicas'] if r['replicaId']==obj['oldReplicaId']];new=[r for r in after['replicas'] if r['replicaId']==candidate] if after else [];interval(migration['startedAt'],migration['verifiedAt'])
        if len(old)!=1 or candidate!=obj['newReplicaId'] or candidate==obj['oldReplicaId'] or during is None or not any(r==old[0] for r in during['replicas']) or after is None or len(new)!=1 or new[0]['state']!='VERIFIED' or new[0]['assetId']!=obj['assetId'] or new[0]['versionId']!=obj['versionId'] or new[0]['sha256']!=sample['checksum']:errors.append(f'{label}: old verified replica must remain available throughout new-copy verification');continue
        new_info=bytes_info(new[0]['payloadRef'],new[0]['sha256']);pending=[r for r in during['replicas'] if r['replicaId']==candidate];pending_info=bytes_info(pending[0]['payloadRef'],pending[0]['sha256']) if len(pending)==1 else None
        stripped={**after,'replicas':[r for r in after['replicas'] if r['replicaId']!=candidate]};during_stripped={**during,'replicas':[r for r in during['replicas'] if r['replicaId']!=candidate]}
        if new_info is None or new_info['size']!=total or pending_info is None or not 0<pending_info['size']<total or pending[0]['state']!='COPYING' or pending[0]['assetId']!=obj['assetId'] or pending[0]['versionId']!=obj['versionId'] or semantic(stripped)!=semantic(baseline) or semantic(during_stripped)!=semantic(baseline):errors.append(f'{label}: migration must observe incomplete COPYING then exact-byte VERIFIED transition without losing old valid copy')
        migration_start,migration_finish=utc(migration['startedAt']),utc(migration['verifiedAt'])
        if migration_start is None or migration_finish is None or not migration_start<=state_times[migration['copyingStateRef']]<=migration_finish<=state_times[migration['verifiedStateRef']]:errors.append(f'{label}: actual copying and verified state snapshots must follow the recorded migration phases')
        # Reuse the retained, byte-verified migration write and backup/restore lifecycle;
        # a declared concurrency status alone cannot grant the workload gate.
        workload=independent_observation(row['concurrentWorkloadRef'],'localStorageConcurrentWorkloadObservation')
        if workload is not None:
            binding={key:obj[key] for key in ('sampleId','sourceId','objectId','assetId','versionId','newReplicaId')}
            binding.update(writeStartedAt=migration['startedAt'],writeFinishedAt=migration['verifiedAt'],copyingStateRef=migration['copyingStateRef'],verifiedStateRef=migration['verifiedStateRef'],lifecycleStartedAt=backup['startedAt'],lifecycleFinishedAt=backup['finishedAt'],backupDataRef=backup['backupDataRef'],restoredDataRef=backup['restoredDataRef'],backupStateRef=backup['backupStateRef'],restoredStateRef=backup['restoredStateRef'])
            if any(workload.get(key)!=value for key,value in binding.items()):errors.append(f'{label}: independent concurrent workload must bind the actual migration write and backup/restore bytes/state/intervals')
            write_window=interval(workload['writeStartedAt'],workload['writeFinishedAt']);lifecycle_window=interval(workload['lifecycleStartedAt'],workload['lifecycleFinishedAt'])
            windows=object_concurrent+[r for r in (write_window,lifecycle_window) if r is not None]
            if len(windows)!=4 or max(r[0] for r in windows)>=min(r[1] for r in windows):errors.append(f'{label}: both reads, byte-verified migration write and observed lifecycle must have one positive-duration common overlap')
    capacity=env.get('capacity_watermark_configuration') or {};observations=report['capacityObservations'];minimum=min(r['freeBytes'] for r in observations);reserved=max(r['reservedBytes'] for r in observations);phases={r['phase'] for r in observations};previous=None;cycle=('fill','pause','evict','resume');cycle_position=0
    if not {'fill','pause','evict','resume'}<=phases:errors.append(f'{label}: actual fill/pause/eviction/resume capacity observations required')
    for row in observations:
        at=utc(row['observedAt']);free=row['freeBytes'];reservation=row['reservedBytes']
        if at is None or window is None or not window[0]<=at<=window[1] or previous is not None and at<previous or free>capacity.get('capacityBytes',-1) or reservation>capacity.get('maxReservedBytes',-1) or free-reservation<capacity.get('safetyFloorBytes',float('inf')) or row['phase']=='pause' and (free>capacity.get('pauseFreeBytes',-1) or row['admission']!='paused') or row['phase']=='resume' and (free<capacity.get('resumeFreeBytes',float('inf')) or row['admission']!='admitted'):errors.append(f'{label}: actual capacity decisions must preserve floor/reservations and approved watermarks')
        if cycle_position<len(cycle) and row['phase']==cycle[cycle_position]:cycle_position+=1
        previous=at
    if cycle_position!=len(cycle):errors.append(f'{label}: actual capacity recovery must include an ordered fill/pause/evict/resume cycle')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)};derived=dict(local_minimum_free_bytes=minimum,local_maximum_reserved_bytes=reserved)
    if len(measured_full)==len(objects):derived.update(sequential_throughput=sum(size for size,elapsed in measured_full)/sum(elapsed for size,elapsed in measured_full)/1000000,io_latency=sum(elapsed for size,elapsed in measured_full)*1000/len(measured_full))
    else:errors.append(f'{label}: positive observed complete-read intervals required for actual throughput and latency')
    for metric,value in derived.items():
        if not ai_finite(actual.get(metric)) or not math.isclose(actual[metric],value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive observed byte counts and operation intervals')
    accepted=len(errors)==before
    for gate in LOCAL_STORAGE_OBSERVED_GATES:
        if actual.get(gate) is not accepted or not accepted:errors.append(f'{label}: {gate} must derive actual returned bytes and governed state transitions')


def validate_qualified_media_negative(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-02' or status!='pass':return
    label=f"qualified media negative matrix {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('mediaNegativeRef'),defs,'mediaNegativeOutcomes',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('mediaNegativePolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('mediaNegativePolicy',{}),label+'/approved controls',errors)
    if report is None or len(errors)!=before:return
    samples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []];nodes=[{k:n.get(k) for k in ('nodeId','physicalHostId','encoderBuild')} for n in env.get('worker_node_inventory') or [] if isinstance(n,dict)];assembly=env.get('parallelMediaAssembly') or {};quality=selected_observation(root,execution,prefix,env.get('mediaQualityTimingRef'),defs,'mediaQualityTimingReport',label,errors,cache)
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=samples,jobId=policy['jobId'],assetId=policy['assetId'],assetVersion=policy['assetVersion'],inputSampleId=assembly.get('inputSampleId'),inputSha256=assembly.get('inputSha256'))
    if any(report[k]!=v for k,v in expected.items()) or policy['subjectVersion']!=expected['subjectVersion'] or policy['nodes']!=nodes or quality is None or policy['jobId']!=quality['jobId'] or policy['assetVersion']!=next((r['immutableId'] for r in samples if r['id']==assembly.get('inputSampleId')),None):
        errors.append(f'{label}: exact admitted job/asset/version/input/build/profile and approved node controls required');return
    limits=policy['limits'];limit_ids={'cpuSeconds','memoryBytes','elapsedSeconds','temporaryBytes','outputBytes'};targets={r['case']:r['target'] for r in policy['deniedTargets']};required_targets={'protocol','path','proxy'}
    if set(limits)!=limit_ids or any(not ai_finite(v) or v<=0 for v in limits.values()) or len(policy['deniedTargets'])!=3 or set(targets)!=required_targets or policy['authorizedUserId']==policy['deniedUserId'] or len(set(policy[k] for k in ('currentGrantId','revokedGrantId','expiredGrantId')))!=3 or policy['cancelJobId']==policy['jobId']:
        errors.append(f'{label}: finite independent limits, three denied target classes and distinct authorization controls required');return
    first,last,expired=utc(policy['grantValidFrom']),utc(policy['grantValidUntil']),utc(policy['expiredAt']);revoked=utc(policy['revokedAt'])
    if any(t is None for t in (first,last,expired,revoked)) or not first<last:
        errors.append(f'{label}: valid approved grant validity and revocation clocks required');return
    artifacts={a.get('ref'):a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and isinstance(a.get('ref'),str)};request_ids=set()
    def instant(value):
        at=utc(value)
        if at is None or window is None or not window[0]<=at<=window[1]:errors.append(f'{label}: actual negative observations must be inside the execution window')
        return at
    def payload(ref,digest,node=None):
        file=existing_ref(root,ref,prefix);record=artifacts.get(ref,{})
        if file is None or record.get('artifactType')!='produced_media' or ref not in (execution.get('rawOutputRefs') or []) or node is not None and record.get('nodeId')!=node:errors.append(f'{label}: actual selected-slot node-bound bytes required');return None
        info=inspect_artifact(file,cache)
        if info['sha256']!=digest:errors.append(f'{label}: actual observed byte hash mismatch')
        return info
    rows=report['nodes']
    if len(rows)!=len(nodes) or [r['identity'] for r in rows]!=nodes:errors.append(f'{label}: all admitted node identities must be exercised exactly once');return
    for row in rows:
        node=row['identity']['nodeId'];denials=row['deniedTargets'];checks=row['limitCases']
        if len(denials)!=3 or {r['case'] for r in denials}!=required_targets or len(checks)!=5 or {r['case'] for r in checks}!=limit_ids:errors.append(f'{label}: complete per-node denied target and independently exceeded limit matrix required')
        for case in denials:
            at=instant(case['observedAt']);info=payload(case['outboundRef'],case['outboundSha256'],node)
            if case['requestId'] in request_ids or case['target']!=targets.get(case['case']) or case['status']!='denied' or case['inputBytesRead']!=0 or case['outputBytesWritten']!=0 or case['publicationCount']!=0 or info is None or info['size']!=0:errors.append(f'{label}: denied target must be rejected before input/output/network access')
            request_ids.add(case['requestId'])
        for case in checks:
            start,end=instant(case['startedAt']),instant(case['finishedAt']);kind=case['case'];observed=case['observed']
            if case['requestId'] in request_ids or start is None or end is None or start>end or any(not ai_finite(v) or v<0 for v in observed.values()) or observed[kind]<=limits[kind] or any(observed[k]>limits[k] for k in limit_ids-{kind}) or kind=='elapsedSeconds' and not math.isclose(observed[kind],(end-start).total_seconds(),rel_tol=1e-9,abs_tol=1e-9) or case['terminationReason']!=kind or case['processStatus']!='terminated' or case['remainingTemporaryBytes']!=0 or case['remainingOutputBytes']!=0 or case['publicationCount']!=0:errors.append(f'{label}: each actual exceeded limit requires matching termination and bounded cleanup without publication')
            request_ids.add(case['requestId'])
        lifecycle=row['lifecycle'];parts=[r for r in env.get('workerEncodeExecutions') or [] if isinstance(r,dict) and r.get('nodeId')==node and r.get('sourceStartFrame')==lifecycle['retrySourceStartFrame'] and r.get('sourceEndFrame')==lifecycle['retrySourceEndFrame']];partial=payload(lifecycle['partialRef'],lifecycle['partialSha256'],node);times=[instant(lifecycle[k]) for k in ('partialCreatedAt','interruptedAt','oldAttemptExpiresAt','retriedAt','retryFinishedAt','cancelledAt','cleanupFinishedAt')]
        if any(t is None for t in times) or times!=sorted(times) or partial is None or partial['size']<=0 or lifecycle['oldAttemptEpoch']>=lifecycle['currentAttemptEpoch'] or lifecycle['retryJobId']!=policy['jobId'] or lifecycle['terminalResultCount']!=1 or lifecycle['remainingTemporaryBytes']!=0 or lifecycle['remainingOutputBytes']!=0 or lifecycle['activeProcessCount']!=0 or lifecycle['cancelledAttemptPublicationCount']!=0 or lifecycle['cancelledPartialDisposition'] not in ('removed','quarantined') or lifecycle['cancelledPartialPublishable'] is not False or len(parts)!=1:
            errors.append(f'{label}: interrupted partial retry must preserve job identity, terminate cancellation and clean or quarantine without duplicate results');continue
        result=payload(lifecycle['publishedRef'],lifecycle['publishedSha256'],node)
        if result is None or result['size']==0 or lifecycle['publishedRef']==lifecycle['partialRef'] or lifecycle['publishedRef']==parts[0]['outputArtifactRef'] or lifecycle['retryEncoderBuild']!=row['identity']['encoderBuild'] or lifecycle['retryInputSha256']!=report['inputSha256'] or lifecycle['retrySourceStartFrame']!=parts[0]['sourceStartFrame'] or lifecycle['retrySourceEndFrame']!=parts[0]['sourceEndFrame'] or lifecycle['retryDecodedFrameCount']!=lifecycle['retrySourceEndFrame']-lifecycle['retrySourceStartFrame'] or lifecycle['retryDecodeErrorCount']!=0:errors.append(f'{label}: fresh retry output must decode the admitted input span with the same actual encoder/input and no errors')
        retry_before=len(errors);probe=selected_observation(root,execution,prefix,lifecycle['retryProbeRef'],defs,'mediaRetryDecodeObservation',label,errors,cache)
        paths=[existing_ref(root,ref,prefix) for ref in (lifecycle['partialRef'],lifecycle['publishedRef'],parts[0]['outputArtifactRef'],lifecycle['retryProbeRef'],lifecycle['cancelledPartialRef'])]
        if any(a.samefile(b) for i,a in enumerate(paths) if a for b in paths[i+1:] if b):errors.append(f'{label}: interrupted partial, fresh retry output, original output and retry probe must be physically distinct')
        if probe is not None and len(errors)==retry_before:
            expected_probe=dict(jobId=policy['jobId'],attemptEpoch=lifecycle['currentAttemptEpoch'],nodeId=node,encoderBuild=lifecycle['retryEncoderBuild'],inputSha256=report['inputSha256'],outputArtifactRef=lifecycle['publishedRef'],outputSha256=lifecycle['publishedSha256'],decoderBuild=policy['retryDecoderBuild'],sourceStartFrame=lifecycle['retrySourceStartFrame'],sourceEndFrame=lifecycle['retrySourceEndFrame'],decodedFrameCount=lifecycle['retryDecodedFrameCount'],decodeErrorCount=lifecycle['retryDecodeErrorCount'],codec='av1',decodable=True)
            probe_start,probe_finish=instant(probe['startedAt']),instant(probe['finishedAt'])
            if any(probe[k]!=v for k,v in expected_probe.items()) or not recorded_text(policy['retryDecoderBuild']) or not ai_finite(probe['durationSeconds']) or probe['durationSeconds']<=0 or probe_start is None or probe_finish is None or not times[3]<=probe_start<=probe_finish<=times[4]:errors.append(f'{label}: actual retry AV1 probe must bind current job/attempt/node/input/output/span/build and ordered decode before completion')
        cancel_partial=payload(lifecycle['cancelledPartialRef'],lifecycle['cancelledPartialSha256'],node);cancel_start=instant(lifecycle['cancelledStartedAt']);cancel_created=instant(lifecycle['cancelledPartialCreatedAt'])
        if lifecycle['cancelJobId']!=policy['cancelJobId'] or lifecycle['cancelledAttemptEpoch']<=lifecycle['currentAttemptEpoch'] or lifecycle['cancelledProcessStatusBefore']!='running' or lifecycle['cancelledProcessStatusAfter']!='terminated' or cancel_partial is None or cancel_partial['size']==0 or lifecycle['cancelledPartialRef'] in (lifecycle['partialRef'],lifecycle['publishedRef']) or cancel_start is None or cancel_created is None or not cancel_start<=cancel_created<=times[5]<=times[6]:errors.append(f'{label}: cancellation must exercise a distinct active job and real partial output before termination/cleanup')
        submissions=lifecycle['submissions'];required={'current','duplicate','late','cancelled'}
        if len(submissions)!=4 or {r['case'] for r in submissions}!=required:errors.append(f'{label}: complete current/duplicate/late/cancelled completion fencing matrix required')
        for submission in submissions:
            at=instant(submission['observedAt']);kind=submission['case'];epoch=lifecycle['oldAttemptEpoch'] if kind=='late' else lifecycle['cancelledAttemptEpoch'] if kind=='cancelled' else lifecycle['currentAttemptEpoch']
            if submission['attemptEpoch']!=epoch or submission['jobId']!=(policy['cancelJobId'] if kind=='cancelled' else policy['jobId']) or submission['decision']!=('published' if kind=='current' else 'rejected') or submission['publicationDelta']!=(1 if kind=='current' else 0) or submission['terminalResultDelta']!=(1 if kind=='current' else 0) or at is None or at<times[4] or kind=='cancelled' and at<times[5]:errors.append(f'{label}: only the current live completion may publish READY and a terminal result once')
        seek=row['seekCases']
        if len(seek)!=3 or {r['case'] for r in seek}!={'current','stale_seek','revoked'}:errors.append(f'{label}: current, stale-seek and revoked demand controls required')
        for case in seek:
            at=instant(case['observedAt']);info=payload(case['responseRef'],case['responseSha256'],node);allowed=case['case']=='current'
            if case['currentSeekEpoch']<=case['previousSeekEpoch'] or case['requestedSeekEpoch']!=(case['currentSeekEpoch'] if case['case']!='stale_seek' else case['previousSeekEpoch']) or case['grantId']!=(policy['revokedGrantId'] if case['case']=='revoked' else policy['currentGrantId']) or case['decision']!=('admitted' if allowed else 'denied') or case['newReservedSlots']!=(1 if allowed else 0) or info is None or (info['size']==0 if allowed else info['size']!=0) or case['case']=='revoked' and (at is None or at<revoked):errors.append(f'{label}: stale/revoked demand must consume no reserved capacity or protected bytes')
            if allowed and (at is None or not first<=at<last):errors.append(f'{label}: current seek admission must occur during the approved grant validity interval')
    surfaces={r['surface']:r for r in policy['protectedOutputs']};surface_ids={'manifest','init','segment','cache_hit'}
    if len(policy['protectedOutputs'])!=4 or set(surfaces)!=surface_ids:errors.append(f'{label}: approved manifest/init/segment/cache-hit outputs required');return
    if surfaces['segment']['ref']!=quality['firstSegment']['segmentRef'] or surfaces['segment']['sha256']!=quality['firstSegment']['segmentSha256'] or surfaces['cache_hit']['ref']!=surfaces['segment']['ref'] or surfaces['cache_hit']['sha256']!=surfaces['segment']['sha256']:errors.append(f'{label}: segment and cache-hit baselines must bind the actual first playable output')
    access=report['accessCases'];cases={'authorized','cross_user','expired','revoked','direct_origin'}
    if len(access)!=20 or {(r['surface'],r['case']) for r in access}!={(s,c) for s in surface_ids for c in cases}:errors.append(f'{label}: complete HLS authorization matrix required')
    origin_paths=[]
    protected_paths=[existing_ref(root,ref,prefix) for ref in [resource['configurationRef'],env.get('mediaNegativeRef')]+[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]+[r.get('responseRef') for r in access]+[r['ref'] for r in surfaces.values()]]
    for row in access:
        at=instant(row['observedAt']);kind=row['case'];surface=surfaces.get(row['surface']);info=payload(row['responseRef'],row['responseSha256']);baseline=payload(surface['ref'],surface['sha256']) if surface else None;allowed=kind=='authorized';grant=policy['expiredGrantId'] if kind=='expired' else policy['revokedGrantId'] if kind=='revoked' else policy['currentGrantId'];user=policy['deniedUserId'] if kind=='cross_user' else policy['authorizedUserId']
        if row['requestId'] in request_ids or row['assetId']!=policy['assetId'] or row['assetVersion']!=policy['assetVersion'] or row['aclVersion']!=policy['aclVersion'] or row['userId']!=user or row['grantId']!=grant or row['route']!=('origin' if kind=='direct_origin' else 'entry') or info is None or baseline is None or baseline['size']==0 or row['decision']!=('allowed' if allowed else 'denied') or row['originContactCount']!=(1 if allowed and row['surface']!='cache_hit' else 0) or allowed and (row['statusCode']!=200 or info['sha256']!=baseline['sha256'] or at is None or not first<=at<last) or not allowed and (row['statusCode'] not in (401,403) or info['size']!=0) or kind=='expired' and (at is None or at<expired) or kind=='revoked' and (at is None or at<revoked):errors.append(f'{label}: HLS access must bind protected bytes/user/version/ACL/grant and deny unauthorized or origin bypass reads')
        if not allowed:
            origin_before=len(errors);origin=selected_observation(root,execution,prefix,row['originAccessRef'],defs,'hlsOriginAccessObservation',label+'/HLS origin access',errors,cache);origin_path=existing_ref(root,row['originAccessRef'],prefix)
            if origin is not None and len(errors)==origin_before:
                binding={k:report[k] for k in ('configurationRef','acceptanceProfile','subjectVersion','inputSamples','jobId','inputSampleId','inputSha256')};binding.update({k:row[k] for k in ('surface','case','requestId','observedAt','assetId','assetVersion','aclVersion','userId','grantId','route','decision','statusCode','responseRef','responseSha256')})
                if any(origin[k]!=v for k,v in binding.items()) or origin['originRequestCount']!=0 or origin['objectReadCount']!=0 or any(origin_path.samefile(p) for p in protected_paths+origin_paths if p is not None):errors.append(f'{label}: denied HLS request needs a distinct exact request-bound zero-origin/object-read observation')
                origin_paths.append(origin_path)
        elif row['originAccessRef'] is not None:errors.append(f'{label}: denied-origin witness must not be borrowed by authorized HLS requests')
        request_ids.add(row['requestId'])
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    derived=len(errors)==before
    for gate in MEDIA_NEGATIVE_GATES:
        if actual.get(gate) is not derived or not derived:errors.append(f'{label}: {gate} must derive complete actual negative outcomes rather than asserted booleans')



def bounded_evaluator_json(root,execution,prefix,ref,kind,defs,schema,label,errors,cache,maximum=262144):
    """Parse only selected retained evaluator bytes; never invokes the evaluator."""
    env=execution.get('environmentCaptured') or {};rows=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==ref]
    path=existing_ref(root,ref,prefix)
    if path is None or ref not in (execution.get('rawOutputRefs') or []) or len(rows)!=1 or rows[0].get('artifactType')!=kind:
        errors.append(f'{label}: selected typed evaluator evidence required');return None
    def pairs(items):
        if len({k for k,_ in items})!=len(items):raise ValueError('duplicate evaluator JSON keys')
        return dict(items)
    def constant(value):raise ValueError('nonfinite evaluator JSON')
    try:
        if not 0<inspect_artifact(path,cache)['size']<=maximum:raise ValueError('evaluator byte bound')
        with path.open('rb') as stream:raw=stream.read(maximum+1)
        if len(raw)>maximum:raise ValueError('evaluator byte bound')
        result=json.loads(raw.decode('utf8'),object_pairs_hook=pairs,parse_constant=constant)
    except (OSError,UnicodeError,ValueError):
        errors.append(f'{label}: bounded unique-key finite evaluator JSON required');return None
    before=len(errors);validate_schema(result,defs.get(schema,{}),label,errors)
    return result if isinstance(result,dict) and len(errors)==before else None


AI_COUNT_RULES={'asr_wer':'whitespace_word_edit','asr_cer':'unicode_codepoint_edit','speaker_der':'speaker_seconds',
                'factual_consistency':'unit_exact_accuracy','multimodal_correction_accuracy':'unit_exact_accuracy',
                'ocr_accuracy':'unit_exact_accuracy','thumbnail_human_selection_rate':'unit_exact_accuracy','tag_f1':'label_set_f1'}


def derive_ai_count_evidence(root,execution,prefix,row,item,identity,method,expected,window,defs,label,errors,cache,payload):
    """Verify retained evaluator comparisons against complete actual inputs, not claimed totals."""
    before=len(errors)
    evidence=bounded_evaluator_json(root,execution,prefix,row.get('countComparisonRef'),'command_output',defs,'aiCountComparison',label,errors,cache)
    reference=bounded_evaluator_json(root,execution,prefix,identity['referenceRef'],'produced_media',defs,'aiCountPayload',label,errors,cache)
    output=bounded_evaluator_json(root,execution,prefix,item['outputRef'],'produced_media',defs,'aiCountPayload',label,errors,cache)
    payload(identity['referenceRef'],identity['referenceSha256'])
    if any(value is None for value in (evidence,reference,output)) or len(errors)!=before:return None
    paths=[existing_ref(root,ref,prefix) for ref in (row['countComparisonRef'],identity['referenceRef'],item['outputRef'])]
    if any(a.samefile(b) for i,a in enumerate(paths) for b in paths[i+1:]):
        errors.append(f'{label}: evaluator, approved reference and actual output must be physically distinct');return None
    rule=AI_COUNT_RULES[row['metricId']]
    binding=dict(expected,metricId=row['metricId'],itemId=row['itemId'],sampleId=row['sampleId'],
                 inputSha256=item['inputSha256'],outputRef=item['outputRef'],outputSha256=item['outputSha256'],
                 referenceRef=identity['referenceRef'],referenceSha256=identity['referenceSha256'],
                 methodId=method['methodId'],evaluatorBuild=method['evaluatorBuild'],rubricVersion=method['rubricVersion'],
                 observedAt=row['observedAt'],comparisonRule=rule)
    started,finished,completed=utc(evidence['startedAt']),utc(evidence['finishedAt']),utc(item['finishedAt'])
    if method.get('comparisonRule')!=rule or any(evidence.get(k)!=v for k,v in binding.items()) or evidence['argv']!=method['evaluatorArgv']+['--output',item['outputRef'],'--reference',identity['referenceRef']] or evidence['exitCode']!=0 or any(t is None for t in (started,finished,completed)) or window is None or not window[0]<=completed<=started<=finished<=window[1] or finished!=utc(row['observedAt']):
        errors.append(f'{label}: comparison must bind approved rule/build/argv, actual input/output/reference and completed evaluator UTC');return None
    if reference['kind']!='ai_count_reference' or output['kind']!='ai_count_output' or output['itemId']!=item['itemId']:
        errors.append(f'{label}: actual reference/output count payload identities required');return None
    def metric_value(document):
        rows=document['metrics'];mapping={value['metricId']:value for value in rows}
        if len(mapping)!=len(rows) or set(mapping)!=set(AI_COUNT_RULES):return None
        for metric,value in mapping.items():
            content='text' if AI_COUNT_RULES[metric] in ('whitespace_word_edit','unicode_codepoint_edit') else 'segments' if AI_COUNT_RULES[metric]=='speaker_seconds' else 'labels' if AI_COUNT_RULES[metric]=='label_set_f1' else 'units'
            if set(value)!={'metricId',content}:return None
        return mapping[row['metricId']]
    ref,out=metric_value(reference),metric_value(output)
    if ref is None or out is None:
        errors.append(f'{label}: complete unique count-metric payload required');return None
    events=evidence['comparisons'];numerator=0;denominator=0;valid=True
    if rule in ('whitespace_word_edit','unicode_codepoint_edit'):
        if 'text' not in ref or 'text' not in out:valid=False
        else:
            left=ref['text'].split() if rule=='whitespace_word_edit' else list(ref['text'])
            right=out['text'].split() if rule=='whitespace_word_edit' else list(out['text'])
            ri=oi=0;denominator=len(left)
            for event in events:
                op=event.get('operation');rindex=event.get('referenceIndex');oindex=event.get('outputIndex')
                if set(event)!={'operation','referenceIndex','outputIndex'} or op not in ('equal','substitution','deletion','insertion'):valid=False;break
                if op!='insertion':
                    if type(rindex) is not int or rindex!=ri or ri>=len(left):valid=False;break
                elif rindex is not None:valid=False;break
                if op!='deletion':
                    if type(oindex) is not int or oindex!=oi or oi>=len(right):valid=False;break
                elif oindex is not None:valid=False;break
                if op in ('equal','substitution') and (left[ri]==right[oi])!=(op=='equal'):valid=False;break
                numerator+=op!='equal';ri+=op!='insertion';oi+=op!='deletion'
            valid=valid and ri==len(left) and oi==len(right)
    elif rule=='label_set_f1':
        if 'labels' not in ref or 'labels' not in out:valid=False
        else:
            left=set(ref['labels']);right=set(out['labels']);seen=set()
            valid=len(events)==len(left|right)
            for event in events:
                key=event.get('labelId')
                if set(event)!={'labelId','inReference','inOutput'} or key not in left|right or key in seen or event['inReference'] is not (key in left) or event['inOutput'] is not (key in right):valid=False;break
                seen.add(key)
            tp=len(left&right);fp=len(right-left);fn=len(left-right)
            valid=valid and seen==left|right and row['truePositive']==tp and row['falsePositive']==fp and row['falseNegative']==fn
            numerator=2*tp;denominator=2*tp+fp+fn
    elif rule=='unit_exact_accuracy':
        if 'units' not in ref or 'units' not in out:valid=False
        else:
            left={v['unitId']:v['value'] for v in ref['units']};right={v['unitId']:v['value'] for v in out['units']}
            valid=len(left)==len(ref['units']) and len(right)==len(out['units']) and set(left)==set(right) and len(events)==len(left)
            seen=set();denominator=len(left)
            for event in events:
                key=event.get('unitId')
                if set(event)!={'unitId','matched'} or key not in left or key in seen or key not in right:valid=False;break
                seen.add(key)
                try:matched=json.dumps(left[key],sort_keys=True,allow_nan=False)==json.dumps(right[key],sort_keys=True,allow_nan=False)
                except (ValueError,OverflowError):valid=False;break
                if event['matched'] is not matched:valid=False;break
                numerator+=matched
            valid=valid and seen==set(left)
    else:
        if 'segments' not in ref or 'segments' not in out:valid=False
        else:
            segments=ref['segments']+out['segments']
            if any(not ai_finite(s[k]) or s[k]<0 for s in segments for k in ('startedSeconds','finishedSeconds')) or any(s['startedSeconds']>=s['finishedSeconds'] for s in segments):valid=False
            if valid:
                boundaries=sorted({s[k] for s in segments for k in ('startedSeconds','finishedSeconds')});spans=list(zip(boundaries,boundaries[1:]))
                valid=len(events)==len(spans)
                for event,(start,end) in zip(events,spans):
                    left=[s['speakerId'] for s in ref['segments'] if s['startedSeconds']<=start and s['finishedSeconds']>=end]
                    right=[s['speakerId'] for s in out['segments'] if s['startedSeconds']<=start and s['finishedSeconds']>=end]
                    if len(left)!=len(set(left)) or len(right)!=len(set(right)) or set(event)!={'startedSeconds','finishedSeconds','referenceSpeakers','outputSpeakers'} or type(event.get('startedSeconds')) is bool or type(event.get('finishedSeconds')) is bool or event.get('startedSeconds')!=start or event.get('finishedSeconds')!=end or event.get('referenceSpeakers')!=sorted(left) or event.get('outputSpeakers')!=sorted(right):valid=False;break
                    denominator+=(end-start)*len(left);numerator+=(end-start)*(max(len(left),len(right))-len(set(left)&set(right)))
    if not valid or not ai_finite(numerator) or not ai_finite(denominator) or denominator<=0:
        errors.append(f'{label}: complete evaluator unit/alignment/time comparisons must match actual reference/output contents');return None
    value=numerator/denominator
    claimed_counts_match=rule=='label_set_f1' or math.isclose(row['numerator'],numerator,rel_tol=1e-9,abs_tol=1e-9) and math.isclose(row['denominator'],denominator,rel_tol=1e-9,abs_tol=1e-9)
    if not ai_finite(value) or not claimed_counts_match or not ai_finite(row['score']) or not math.isclose(row['score'],value,rel_tol=1e-9,abs_tol=1e-9):
        errors.append(f'{label}: count ratio claims must derive complete actual evaluator comparisons');return None
    return value


def derive_ai_score_evidence(root,execution,prefix,row,item,identity,method,expected,window,defs,label,errors,cache,payload):
    mode=method['mode'];kind='command_output' if mode=='tool_score' else 'measurement_output'
    evidence=bounded_evaluator_json(root,execution,prefix,row.get('scoreEvidenceRef'),kind,defs,'aiScoreEvidence',label,errors,cache)
    if evidence is None:return None
    binding=dict(expected,metricId=row['metricId'],itemId=row['itemId'],sampleId=row['sampleId'],
                 inputSha256=item['inputSha256'],outputRef=row['outputRef'],outputSha256=row['outputSha256'],
                 referenceRef=identity['referenceRef'],referenceSha256=identity['referenceSha256'],
                 methodId=method['methodId'],evaluatorBuild=method['evaluatorBuild'],rubricVersion=method['rubricVersion'],
                 observedAt=row['observedAt'],mode=mode)
    if any(evidence.get(k)!=v for k,v in binding.items()):
        errors.append(f'{label}: evaluator bytes must bind actual model output, approved reference and method/build/rubric');return None
    reference=payload(identity['referenceRef'],identity['referenceSha256'])
    if reference is None or identity['referenceRef']==item['outputRef']:
        errors.append(f'{label}: independently approved actual reference bytes required');return None
    if mode=='tool_score':
        values=evidence['toolScores']
        if any(not ai_finite(value) for value in values):
            errors.append(f'{label}: finite actual tool score observations required');return None
    else:
        judgments=evidence['judgments'];criteria=method['criterionIds']
        if evidence['reviewerId']!=method['reviewerId'] or len(criteria)!=len(set(criteria)) or len(judgments)!=len(criteria) or {j['criterionId'] for j in judgments}!=set(criteria):
            errors.append(f'{label}: approved reviewer and exact rubric criteria required');return None
        values=[j['grade'] for j in judgments]
        if any(not ai_finite(value) or value not in method['gradeValues'] for value in values) or any(not recorded_text(j['basis']) for j in judgments):
            errors.append(f'{label}: actual rubric judgments require approved finite grades and concrete basis');return None
    value=math.fsum(v/len(values) for v in values)
    if not ai_finite(row['score']) or not math.isclose(row['score'],value,rel_tol=1e-9,abs_tol=1e-9):
        errors.append(f'{label}: claimed score must derive actual retained evaluator observations');return None
    return value


def derive_vmaf_frame_result(root,execution,prefix,quality,defs,label,errors,cache):
    invocation=bounded_evaluator_json(root,execution,prefix,quality['evaluatorCommandRef'],'command_output',defs,'vmafEvaluatorInvocation',label,errors,cache)
    if invocation is None:return None
    keys=('configurationRef','subjectVersion','acceptanceProfile','jobId','inputSampleId','inputSha256',
          'outputArtifactRef','outputSha256','encoderBuild','encoderParameters','evaluatorBuild','modelId','modelSha256','evaluatedAt')
    if any(invocation.get(key)!=quality[key] for key in keys):
        errors.append(f'{label}: actual evaluator invocation must bind approved model/build and exact evaluated input/output');return None
    path=existing_ref(root,invocation['resultRef'],prefix)
    if path is None or inspect_artifact(path,cache)['sha256']!=invocation['resultSha256']:
        errors.append(f'{label}: evaluator invocation must bind actual frame-result bytes');return None
    result=bounded_evaluator_json(root,execution,prefix,invocation['resultRef'],'command_output',defs,'vmafFrameResults',label,errors,cache,8388608)
    if result is None:return None
    frames=result['frames']
    if len(frames)!=quality['evaluatedFrameCount'] or [f['frameNum'] for f in frames]!=list(range(len(frames))) or any(not ai_finite(f['metrics']['vmaf']) for f in frames):
        errors.append(f'{label}: complete ordered unique finite VMAF frame observations required');return None
    value=math.fsum(f['metrics']['vmaf']/len(frames) for f in frames)
    if not ai_finite(quality['vmafMean']) or not math.isclose(quality['vmafMean'],value,rel_tol=1e-9,abs_tol=1e-9):
        errors.append(f'{label}: vmafMean must derive actual complete frame observations');return None
    return value


def validate_qualified_media_quality_timing(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-02' or status!='pass':return
    label=f"qualified media quality/timing {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('mediaQualityTimingRef'),defs,'mediaQualityTimingReport',label,errors,cache)
    if report is None or len(errors)!=before:return
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None)
    if resource is None or report['configurationRef']!=resource.get('configurationRef'):
        errors.append(f'{label}: exact approved worker/encoder configuration required');return
    path=existing_ref(root,report['configurationRef'],prefix)
    try:policy=load(path).get('configuration',{}).get('mediaEvaluationPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    before=len(errors);validate_schema(policy,defs.get('mediaEvaluationPolicy',{}),label+'/approved evaluator',errors)
    if len(errors)!=before or not isinstance(policy,dict):return
    assembly=env.get('parallelMediaAssembly');runs=env.get('workerEncodeExecutions');provenance=execution.get('provenance') or {}
    if not isinstance(assembly,dict) or not isinstance(runs,list):return
    samples=[{k:sample.get(k) for k in ('id','immutableId','checksum')} for sample in execution.get('samples') or []]
    expected=dict(configurationRef=resource['configurationRef'],subjectVersion=compliance_subject_version(plan,execution),acceptanceProfile=env.get('acceptanceProfile'),jobId=policy['jobId'],inputSampleId=assembly.get('inputSampleId'),inputSha256=assembly.get('inputSha256'),outputArtifactRef=assembly.get('outputArtifactRef'),outputSha256=assembly.get('outputSha256'),encoderBuild=policy['encoderBuild'],encoderParameters=provenance.get('encoder_parameters'))
    if policy['inputSamples']!=samples or policy['encoderParameters']!=expected['encoderParameters'] or any(report.get(k)!=v for k,v in expected.items()) or any(not recorded_text(policy[k]) for k in ('jobId','evaluatorBuild','modelId','encoderBuild')):
        errors.append(f'{label}: exact approved inputs/assembly/encoder parameters and evaluator model/build required')
    if any(not isinstance(run,dict) or run.get('encoderBuild')!=policy['encoderBuild'] for run in runs):errors.append(f'{label}: evaluated output must bind the admitted encode builds')
    output=existing_ref(root,report['outputArtifactRef'],prefix)
    if output is None or inspect_artifact(output,cache)['sha256']!=report['outputSha256']:errors.append(f'{label}: evaluated assembly must bind actual produced media bytes')
    before=len(errors);quality=selected_observation(root,execution,prefix,report['qualityRef'],defs,'vmafEvaluatorOutput',label,errors,cache)
    segment=report['firstSegment'];probe=selected_observation(root,execution,prefix,segment['decodeRef'],defs,'firstPlayableSegmentProbe',label,errors,cache)
    job=selected_observation(root,execution,prefix,report['jobEventRef'],defs,'mediaJobStartObservation',label,errors,cache)
    if len(errors)!=before or quality is None or probe is None or job is None:return
    if any(quality.get(k)!=v for k,v in expected.items()) or any(quality[k]!=policy[k] for k in ('evaluatorBuild','modelId','modelSha256')) or quality['evaluatedFrameCount']!=assembly.get('sourceFrameCount'):
        errors.append(f'{label}: VMAF output must bind exact input/output frames and approved evaluator/model')
    at=utc(quality['evaluatedAt']);finished=[utc(run.get('finishedAt')) for run in runs if isinstance(run,dict)]
    if at is None or window is None or not window[0]<=at<=window[1] or len(finished)!=len(runs) or not finished or any(t is None or t>at for t in finished):errors.append(f'{label}: full-output quality evaluation must follow completed encoding within execution')
    artifacts={a.get('ref'):a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and isinstance(a.get('ref'),str)}
    command=quality['evaluatorCommandRef']
    if command not in (execution.get('rawOutputRefs') or []) or artifacts.get(command,{}).get('artifactType')!='command_output' or existing_ref(root,command,prefix) is None:errors.append(f'{label}: evaluated model invocation must retain selected command output')
    controls=[run for run in runs if isinstance(run,dict) and run.get('rawOutputRef')==segment['encodeRunRef'] and run.get('nodeId')==segment['nodeId'] and run.get('sourceStartFrame')==0]
    first,produced,ready,decoded=(utc(value) for value in (segment['jobStartedAt'],segment['segmentProducedAt'],segment['firstPlayableAt'],probe['observedAt']))
    if len(controls)!=1 or type(controls[0].get('sourceEndFrame')) is not int or segment['sourceStartFrame']!=0 or not 0<segment['sourceEndFrame']<=controls[0].get('sourceEndFrame',0):
        errors.append(f'{label}: first segment must bind the identified initial input span and real job start')
    expected_job={k:expected[k] for k in ('configurationRef','subjectVersion','acceptanceProfile','jobId','inputSampleId','inputSha256','encoderBuild','encoderParameters')}
    expected_job.update(encodeRunRef=segment['encodeRunRef'],nodeId=segment['nodeId'],jobStartedAt=segment['jobStartedAt'])
    worker=utc(controls[0].get('startedAt')) if len(controls)==1 else None
    if any(job.get(k)!=v for k,v in expected_job.items()) or len(controls)!=1 or job['workerStartedAt']!=controls[0].get('startedAt'):
        errors.append(f'{label}: retained job-start event must bind exact approved job/input/encoder and selected worker execution')
    if any(t is None for t in (first,worker,produced,decoded,ready)) or window is None or not window[0]<=first<=worker<=produced<=decoded<=ready<=window[1]:errors.append(f'{label}: ordered job/worker/produced/decode/first-playable UTC timestamps must retain queue delay')
    media=existing_ref(root,segment['segmentRef'],prefix)
    if media is None or segment['segmentRef'] not in (execution.get('rawOutputRefs') or []) or artifacts.get(segment['segmentRef'],{}).get('artifactType')!='produced_media' or artifacts.get(segment['segmentRef'],{}).get('nodeId')!=segment['nodeId']:
        errors.append(f'{label}: first playable segment requires exact node-bound produced bytes')
    elif inspect_artifact(media,cache)['size']==0 or inspect_artifact(media,cache)['sha256']!=segment['segmentSha256']:errors.append(f'{label}: first playable segment digest must match actual nonempty bytes')
    if media is not None and output is not None and media.samefile(output):errors.append(f'{label}: first partial segment must be distinct from the whole multi-worker assembly')
    expected_probe=dict(jobId=policy['jobId'],nodeId=segment['nodeId'],segmentRef=segment['segmentRef'],segmentSha256=segment['segmentSha256'],inputSha256=report['inputSha256'],sourceStartFrame=segment['sourceStartFrame'],sourceEndFrame=segment['sourceEndFrame'],decoderBuild=assembly.get('decoderBuild'))
    if any(probe.get(k)!=v for k,v in expected_probe.items()) or probe['decodedFrameCount']!=segment['sourceEndFrame']-segment['sourceStartFrame'] or probe['decodeErrorCount']!=0 or probe['decodable'] is not True:
        errors.append(f'{label}: first-playable probe must decode the exact retained AV1 input span without errors')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    vmaf=derive_vmaf_frame_result(root,execution,prefix,quality,defs,label,errors,cache)
    derived={} if vmaf is None else {'av1_quality':vmaf}
    if first is not None and ready is not None:derived['first_segment_latency']=(ready-first).total_seconds()*1000
    for metric,value in derived.items():
        if not ai_finite(value) or not ai_finite(actual.get(metric)) or not math.isclose(actual[metric],value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive retained evaluator results and first-playable timestamps')


def encode_interval_capacity(intervals):
    """Bound distinct-node streams and the longest continuous active component."""
    instants=sorted({instant for _,start,end in intervals for instant in (start,end)})
    peak=max((len({node for node,start,end in intervals if start<=instant<end}) for instant in instants),default=0)
    longest=0.0
    component_start=component_end=None
    for _,start,end in sorted(intervals,key=lambda item:(item[1],item[2])):
        if component_end is None or start>component_end:
            component_start,component_end=start,end
        else:
            component_end=max(component_end,end)
        longest=max(longest,(component_end-component_start).total_seconds()/60)
    return peak,longest


def validate_qualified_media_assembly(root,execution,prefix,runs,artifacts,defs,errors,cache):
    label=f"qualified media assembly {execution['taskId']}"
    env=execution.get('environmentCaptured') or {}
    assembly=env.get('parallelMediaAssembly')
    validate_schema(assembly,defs.get('parallelMediaAssembly',{}),label,errors)
    if not isinstance(assembly,dict):
        errors.append(f'{label}: typed parallelMediaAssembly is required');return
    samples={s['id']:s for s in execution.get('samples') or []}
    sample=samples.get(assembly.get('inputSampleId'))
    total=assembly.get('sourceFrameCount')
    if sample is None or assembly.get('inputSha256')!=sample['checksum'] or type(total) is not int or total<=0:
        errors.append(f'{label}: exact approved input and positive source frame count are required');return
    if not recorded_text(assembly.get('decoderBuild')):
        errors.append(f'{label}: decoder build must identify the exercised validation tool')
    parts=[]
    for run in runs:
        if not isinstance(run,dict):continue
        start,end=run.get('sourceStartFrame'),run.get('sourceEndFrame')
        if run.get('inputSampleId')!=sample['id'] or run.get('inputSha256')!=sample['checksum'] or type(start) is not int or type(end) is not int or not 0<=start<end<=total:
            errors.append(f'{label}: each worker must bind an exact positive source-frame span');continue
        parts.append({key:run.get(key) for key in ('nodeId','outputArtifactRef','outputSha256','sourceStartFrame','sourceEndFrame')})
    parts.sort(key=lambda part:part['sourceStartFrame'])
    cursor=0
    for part in parts:
        if part['sourceStartFrame']!=cursor:
            errors.append(f'{label}: source spans must be contiguous and non-overlapping')
        cursor=part['sourceEndFrame']
    if len(parts)!=len(runs) or cursor!=total or assembly.get('parts')!=parts:
        errors.append(f'{label}: ordered parts must cover the entire approved input exactly once')
    output_ref=assembly.get('outputArtifactRef')
    output=artifacts.get(output_ref) if isinstance(output_ref,str) else None
    if output_ref!=env.get('producedMediaArtifactRef') or output is None or output.get('artifactType')!='produced_media' or assembly.get('outputSha256')!=(execution.get('provenance') or {}).get('output_sha256'):
        errors.append(f'{label}: assembly must bind the designated produced output and actual digest')
    output_path=existing_ref(root,output_ref,prefix)
    part_paths=[path for part in parts if (path:=existing_ref(root,part.get('outputArtifactRef'),prefix)) is not None]
    if any(part.get('outputArtifactRef')==output_ref for part in parts) or (output_path and any(output_path.samefile(path) for path in part_paths)):
        errors.append(f'{label}: assembled output must be distinct from worker parts')
    validation_ref=assembly.get('validationRef')
    artifact=artifacts.get(validation_ref) if isinstance(validation_ref,str) else None
    path=existing_ref(root,validation_ref,prefix)
    if artifact is None or artifact.get('artifactType')!='measurement_output' or validation_ref not in (execution.get('rawOutputRefs') or []) or path is None:
        errors.append(f'{label}: assembled decode/timeline validation must retain typed selected-slot raw output');return
    if (output_path and path.samefile(output_path)) or any(path.samefile(part_path) for part_path in part_paths):
        errors.append(f'{label}: decode/timeline report must be distinct from encoded media');return
    if inspect_artifact(path,cache)['size']>262144:
        errors.append(f'{label}: decode/timeline report exceeds bounded structured-report size');return
    try:
        with path.open(encoding='utf8') as stream:
            report=yaml.load(stream.read(262145),Loader=UniqueKeyLoader)
    except (OSError,UnicodeError,yaml.YAMLError):
        errors.append(f'{label}: decode/timeline report must be readable structured output');return
    validate_schema(report,defs.get('assembledDecodeReport',{}),label,errors)
    if not isinstance(report,dict):return
    expected={key:assembly.get(key) for key in ('inputSampleId','inputSha256','sourceFrameCount','outputSha256','parts','decoderBuild')}
    if any(report.get(key)!=value for key,value in expected.items()) or type(report.get('decodedFrameCount')) is not int or report['decodedFrameCount']!=total or type(report.get('decodeErrorCount')) is not int or report['decodeErrorCount']!=0 or type(report.get('timelineDiscontinuityCount')) is not int or report['timelineDiscontinuityCount']!=0:
        errors.append(f'{label}: decoded output and continuous timeline must bind the complete ordered assembly')


def qualified_observation_report(path, defs, schema, label, errors, cache):
    try:
        size=inspect_artifact(path,cache)['size']
        if not 0<size<=262144:
            errors.append(f'{label}: structured observation must be nonempty and at most 262144 bytes')
            return None
        with path.open(encoding='utf8') as stream:
            report=yaml.load(stream.read(262145),Loader=UniqueKeyLoader)
    except (OSError,UnicodeError,yaml.YAMLError):
        errors.append(f'{label}: readable structured observation required')
        return None
    validate_schema(report,defs.get(schema,{}),label,errors)
    return report if isinstance(report,dict) else None



def selected_observation(root, execution, prefix, ref, defs, schema, label, errors, cache):
    env = execution.get('environmentCaptured') or {}
    matches = [item for item in env.get('rawExecutionArtifacts') or [] if isinstance(item,dict) and item.get('ref') == ref]
    path = existing_ref(root,ref,prefix)
    if len(matches) != 1 or matches[0].get('artifactType') != 'measurement_output' or ref not in (execution.get('rawOutputRefs') or []) or path is None:
        errors.append(f'{label}: selected-slot typed measurement output required')
        return None
    return qualified_observation_report(path,defs,schema,label,errors,cache)


def observation_interval(report, execution, label, errors):
    start,end = utc(report.get('observedStartedAt')),utc(report.get('observedFinishedAt'))
    window = (execution.get('environmentCaptured') or {}).get('executionWindow') or {}
    first,last = utc(window.get('startedAt')),utc(window.get('finishedAt'))
    if start is None or end is None or first is None or last is None or not first <= start < end <= last:
        errors.append(f'{label}: positive observed interval must be inside executionWindow')
        return None
    return (end-start).total_seconds()


def validate_qualified_phone_observation(root, execution, prefix, scope, observation, path, defs, errors, cache):
    label = f"qualified physical phone observation {execution['taskId']}"
    report = qualified_observation_report(path,defs,'physicalPhoneObservation',label,errors,cache)
    if report is None:
        return
    expected = {key:scope.get(key) for key in ('nodeId','deviceId','physicalHostId','encoderBuild')}
    expected.update({key:observation.get(key) for key in ('temperaturePeakCelsius','powerPeakWatts','testDurationSeconds','backgroundSurvivedSeconds')})
    if any(report.get(key) != value for key,value in expected.items()):
        errors.append(f'{label}: retained report must match exact device/node/host/build and measured temperature/power/background values')
    duration = observation_interval(report,execution,label,errors)
    if duration is not None and report.get('testDurationSeconds') != duration:
        errors.append(f'{label}: completed test duration must equal observed interval')


def validate_qualified_inference_observation(root, plan, execution, prefix, status, window, defs, errors, cache):
    if plan['pocId'] != 'POC-09' or status != 'pass':
        return
    label = f"qualified inference observation {plan['taskId']}"
    env = execution.get('environmentCaptured') or {}
    report = selected_observation(root,execution,prefix,env.get('inferenceObservationRef'),defs,'inferenceObservation',label,errors,cache)
    if report is None:
        return
    expected_inputs = [{key:sample.get(key) for key in ('id','immutableId','checksum')} for sample in execution.get('samples') or []]
    if report.get('subjectVersion') != compliance_subject_version(plan,execution) or report.get('inputSamples') != expected_inputs:
        errors.append(f'{label}: report must bind exact model/prompt/parameters/runtime/tools and approved input identities')
    count = report.get('completedItemCount')
    elapsed = observation_interval(report,execution,label,errors)
    actual = next((item.get('actual') for item in execution.get('measurements') or [] if item.get('id') == 'throughput'),None)
    if type(count) is not int or count <= 0:
        errors.append(f'{label}: positive integer completed item count required')
    elif elapsed is not None and (isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isfinite(actual) or not math.isclose(actual,count/elapsed,rel_tol=1e-9,abs_tol=1e-9)):
        errors.append(f'{label}: throughput must equal retained completed count divided by elapsed seconds')


RECOVERY_GATE_DOMAINS = {
    'db_restore':('database',), 'users_permissions_restore':('permissions',),
    'assets_restore':('assets',), 'source_mappings_restore':('sourceMappings',),
    'formal_replicas_restore':('replicas',), 'retention_restore':('retention',),
    'audit_restore':('audit',), 'outbox_restore':('delivery',), 'tasks_restore':('tasks',),
    'authoritative_relationships_restore':('permissions','assets','sourceMappings','replicas','retention','audit','delivery','tasks'),
    'secret_store_restore':('openbao',), 'secret_value_roundtrip':('valueComparisons',),
    'secret_unreadable_failure_detected':('unreadableFixture',), 'file_restore':('files',),
    'playback_restore':('playback',), 'ai_manual_revisions_restore':('revisions',),
    'search_index_consistency_restore':('indexEntries',), 'image_signature_restore':('deployment',),
}


def recovery_domain_digest(value):
    """Hash parsed state; transport references may differ after a legitimate restore."""
    def semantic(item):
        if isinstance(item,dict):
            # Phase-bound value artifacts have different transport hashes; actual parsed
            # comparison digests are reconciled separately before granting PASS.
            value_comparison={'referenceId','method','comparisonContextId','artifactRef'}.issubset(item)
            return {key:semantic(value) for key,value in item.items() if key not in ('artifactRef','imageArtifactRef','signatureArtifactRef','verificationRef','configurationRef','controlBackupRef') and not (value_comparison and key=='sha256')}
        if isinstance(item,list):return [semantic(value) for value in item]
        return item
    return 'sha256:'+hashlib.sha256(json.dumps(semantic(value),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')).hexdigest()


def decode_recovery_control_backup(data):
    """Fixed bounded non-secret lab codec, never an OpenBao secret decryptor."""
    if not 0 < len(data) <= 262144:raise ValueError('backup fixture size')
    decoder=zlib.decompressobj(31)
    decoded=decoder.decompress(data,262145)
    if len(decoded)>262144 or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:raise ValueError('backup fixture decoding')
    def nonfinite(value):raise ValueError('nonfinite configuration')
    value=json.loads(decoded.decode('utf8'),parse_constant=nonfinite)
    if not isinstance(value,dict):raise ValueError('backup configuration object')
    return value


def verify_recovery_signature(image, signature, public_key, build, label, errors, cache):
    """Verify retained bytes with a fixed existing tool and approved public key."""
    try:
        if 'recovery-openssl-build' not in cache:
            result=subprocess.run(['openssl','version'],capture_output=True,timeout=10)
            if result.returncode:raise ValueError('signature verifier version unavailable')
            cache['recovery-openssl-build']=result.stdout.decode('utf8').strip()
        if cache['recovery-openssl-build']!=build:raise ValueError('signature verifier build differs from approved build')
        key=subprocess.run(['openssl','pkey','-pubin','-in',str(public_key),'-text','-noout'],capture_output=True,timeout=10)
        if key.returncode or not key.stdout.startswith(b'ED25519 Public-Key:'):raise ValueError('approved key must be Ed25519 public key')
        result=subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',str(public_key),'-sigfile',str(signature),'-rawin','-in',str(image)],capture_output=True,timeout=10)
        if result.returncode:raise ValueError('actual Ed25519 signature verification failed')
    except (OSError,ValueError,UnicodeError,subprocess.TimeoutExpired) as exc:
        errors.append(f'{label}: signature verification failed: {exc}')


def recovery_playback_allowed(state, playback):
    """Join the retained playback subject to its restored allow grant."""
    asset=next((a for a in state['assets'] if a['assetId']==playback['assetId']),None)
    user=next((u for u in state['permissions'] if u['userId']==playback['authorizedUserId']),None)
    if asset is None or user is None or 'asset:read' not in user['permissionIds']:return False
    matching=[grant for grant in user['scopedGrants'] if grant['assetId']==asset['assetId']
        and grant['aclVersion']==asset['aclVersion'] and grant['permissionId']=='asset:read']
    return any(grant['disposition']=='allow' for grant in matching) and not any(grant['disposition']=='deny' for grant in matching)


def recovery_exact_json(value):
    """Canonical comparison retains JSON scalar types (true is not integer 1)."""
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def validate_recovery_index_readback(root,execution,prefix,report,defs,label,errors,cache,retained):
    descriptor=report['indexReadback'];ref=descriptor['artifactRef']
    actual=retained(ref,descriptor['sha256'],size=descriptor['byteCount'])
    path=existing_ref(root,ref,prefix)
    if actual is None or path is None:return
    assets={row['assetId']:row for row in report['states']['assets']}
    expected={row['entryId']:{**row,'version':assets.get(row['assetId'],{}).get('version')} for row in report['states']['indexEntries']}
    seen=set()
    try:
        for row in streamed_metadata_records(path,defs['recoveryIndexExportEntry']):
            # This is a complete bounded-row export, not a declaration of a count.
            if len(seen)>=len(expected) or row['entryId'] in seen or recovery_exact_json(row)!=recovery_exact_json(expected.get(row['entryId'])):
                errors.append(f'{label}: actual index export must exactly bind every approved entry, version and indexed field');return
            seen.add(row['entryId'])
    except (OSError,ValueError,TypeError,UnicodeError,jsonschema.ValidationError,yaml.YAMLError):
        errors.append(f'{label}: actual index export must be finite typed JSONL');return
    if seen!=set(expected):errors.append(f'{label}: actual index export must not omit or retain stale entries')


def validate_recovery_readiness(root,execution,prefix,capture,config,baseline,restored,subjects,events,times,window,defs,label,errors,cache,paths):
    """Validate retained command readbacks and the actual authorized playback request."""
    policy=config.get('configuration',{}).get('recoveryReadiness')
    refs={row['event']:row['witnessRef'] for row in events}
    witnesses={}
    for event in ('services_ready','vm_set_ready','authorized_playback_succeeded','recovery_completed'):
        before=len(errors)
        witness=selected_observation(root,execution,prefix,refs[event],defs,'recoveryBusinessEvent',label,errors,cache)
        if witness is None or len(errors)!=before:return
        witnesses[event]=witness
    artifacts={a['ref']:a for a in execution['environmentCaptured']['rawExecutionArtifacts'] if isinstance(a,dict) and isinstance(a.get('ref'),str)}
    def state_payloads(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.endswith('Ref') and isinstance(item,str):
                    path=existing_ref(root,item,prefix)
                    if path is not None and not any(path.samefile(peer) for peer in paths):paths.append(path)
                elif isinstance(item,(dict,list)):state_payloads(item)
        elif isinstance(value,list):
            for item in value:state_payloads(item)
    state_payloads(baseline);state_payloads(restored)
    def payload(descriptor):
        path=existing_ref(root,descriptor['artifactRef'],prefix);artifact=artifacts.get(descriptor['artifactRef'])
        if path is None or artifact is None or artifact.get('artifactType')!='recovery_output' or descriptor['artifactRef'] not in execution['rawOutputRefs']:
            errors.append(f'{label}: readiness must bind selected-slot typed actual returned bytes');return
        actual=inspect_artifact(path,cache)
        if actual['sha256']!=descriptor['sha256'] or actual['size']!=descriptor['byteCount'] or actual['size']<=0:
            errors.append(f'{label}: readiness output hash/size must equal actual bytes');return
        if any(path.samefile(peer) for peer in paths):errors.append(f'{label}: readiness readbacks must be physically independent');return
        paths.append(path)
        return path,actual
    manifest_path=existing_ref(root,capture['restoredRef'],prefix)
    if manifest_path is None:return
    manifest_sha=inspect_artifact(manifest_path,cache)['sha256']
    if not isinstance(policy,dict):errors.append(f'{label}: approved readiness command/member policy required');return
    for event in ('services_ready','vm_set_ready','recovery_completed'):
        approved=policy.get(event);witness=witnesses[event];before=len(errors)
        run=selected_observation(root,execution,prefix,witness.get('executionRef'),defs,'recoveryReadinessExecution',label,errors,cache)
        if run is None or len(errors)!=before:continue
        run_path=existing_ref(root,witness.get('executionRef'),prefix)
        if run_path and any(run_path.samefile(peer) for peer in paths):errors.append(f'{label}: readiness executions must be physically independent')
        if run_path:paths.append(run_path)
        if not isinstance(approved,dict) or not isinstance(approved.get('commandArgs'),list) or not approved['commandArgs'] or any(not recorded_text(v) for v in approved['commandArgs']) or not recorded_text(approved.get('toolBuild')):
            errors.append(f'{label}: approved readiness argv/build required');continue
        expected={k:witness[k] for k in ('resourceId','acceptanceProfile','subjectVersion','inputSamples','subjects')}
        expected.update(event=event,configurationRef=capture['configurationRef'],recoveryRunId=subjects['recoveryRunId'],restoredRef=capture['restoredRef'],commandArgs=approved['commandArgs'],toolBuild=approved['toolBuild'])
        start,end=utc(run['startedAt']),utc(run['finishedAt'])
        if any(recovery_exact_json(run.get(k))!=recovery_exact_json(v) for k,v in expected.items()) or start is None or end is None or not window[0]<=start<=end==times[event]<=window[1]:
            errors.append(f'{label}: readiness execution must bind approved command/build/subjects and actual finish instant')
        retained=payload(run['outputArtifact'])
        if retained is None:continue
        path,actual=retained
        if actual['size']>262144:errors.append(f'{label}: readiness JSON output exceeds bounded capture');continue
        try:
            def unique(pairs):
                result={}
                for key,value in pairs:
                    if key in result:raise ValueError('duplicate JSON field')
                    result[key]=value
                return result
            def invalid_constant(value):raise ValueError('non-finite JSON constant')
            result=json.loads(path.read_text(encoding='utf8'),object_pairs_hook=unique,parse_constant=invalid_constant)
            before=len(errors);validate_schema(result,defs['recoveryReadinessResult'],label,errors)
            if len(errors)!=before:continue
        except (OSError,ValueError,UnicodeError):errors.append(f'{label}: readiness must retain finite typed execution output JSON');continue
        expected_result=dict(event=event,recoveryRunId=subjects['recoveryRunId'],physicalHostId=subjects['physicalHostId'],setId=subjects['serviceSetId'] if event=='services_ready' else subjects['vmSetId'] if event=='vm_set_ready' else subjects['recoveryRunId'],restoredRef=capture['restoredRef'],restoredSha256=manifest_sha)
        if any(result.get(k)!=v for k,v in expected_result.items()):errors.append(f'{label}: readiness output must bind current restored manifest and approved run/host/set')
        if event=='recovery_completed':
            expected_checks=[dict(checkId=name,status='succeeded',evidenceRef=refs[name]) for name in ('services_ready','vm_set_ready','authenticated_browsing_succeeded','authorized_playback_succeeded')]
        else:
            members=approved.get('memberIds')
            if not isinstance(members,list) or not members or any(not recorded_text(v) for v in members) or len(set(members))!=len(members):
                errors.append(f'{label}: complete unique approved service/VM member set required');continue
            expected_checks=[dict(checkId=name,status='healthy',**({'state':'running'} if event=='vm_set_ready' else {})) for name in members]
        if sorted(map(recovery_exact_json,result['checks']))!=sorted(map(recovery_exact_json,expected_checks)):
            errors.append(f'{label}: readiness output must contain all exact healthy members or verified completion checks')
    witness=witnesses['authorized_playback_succeeded'];request=witness.get('playbackRequest');before=len(errors)
    validate_schema(request,defs['recoveryBusinessEvent']['properties']['playbackRequest'],label,errors)
    baseline=config.get('configuration',{}).get('recoveryBaseline',{}).get('playbackRequest')
    if len(errors)!=before or not isinstance(baseline,dict):
        errors.append(f'{label}: approved actual playback request required');return
    assets={a['assetId']:a for a in restored['states']['assets']};asset=assets.get(subjects['assetId'])
    first,last=request['rangeStart'],request['rangeEnd'];start,end=utc(request['requestedAt']),utc(request['finishedAt'])
    if asset is None or request['assetId']!=subjects['assetId'] or request['assetVersion']!=asset['version'] or request['aclVersion']!=asset['aclVersion'] or request['userId']!=subjects['authorizedUserId'] or any(request.get(k)!=baseline.get(k) for k in ('requestURL','authRef','rangeStart','rangeEnd')) or start is None or end is None or not window[0]<=start<=end==times['authorized_playback_succeeded']<=window[1] or last<first or not recovery_playback_allowed(restored['states'],dict(assetId=request['assetId'],authorizedUserId=request['userId'])):
        errors.append(f'{label}: actual playback request must bind approved URL/auth/range and current restored ACL/finish time');return
    retained=payload(dict(artifactRef=request['responseArtifactRef'],sha256=request['responseSha256'],byteCount=request['responseByteCount']))
    primary=[a for a in restored['states']['replicas'] if a['assetId']==request['assetId'] and a['primary'] is True and a['state']=='verified']
    if retained is None or len(primary)!=1:return
    source=existing_ref(root,primary[0]['artifactRef'],prefix)
    if source is None:return
    if retained[0].samefile(source) or last>=primary[0]['byteCount'] or retained[1]['size']!=last-first+1:
        errors.append(f'{label}: actual playback body must be a distinct bounded primary-replica range');return
    try:digest=primary[0]['sha256'] if first==0 and last+1==primary[0]['byteCount'] else range_slice_hash(source,first,last-first+1)
    except OSError:digest=None
    if retained[1]['sha256']!=digest:errors.append(f'{label}: readiness playback returned bytes must equal actual verified primary slice')


def validate_recovery_state(root, execution, prefix, report, defs, label, errors, cache, all_paths, approved, comparison_run_id):
    state=report['states']
    env=execution['environmentCaptured']
    artifacts={item['ref']:item for item in env['rawExecutionArtifacts'] if isinstance(item,dict) and isinstance(item.get('ref'),str)}
    def retained(ref,digest,kind='recovery_output',size=None):
        path=existing_ref(root,ref,prefix)
        artifact=artifacts.get(ref)
        if path is None or artifact is None or artifact.get('artifactType')!=kind or ref not in execution['rawOutputRefs']:
            errors.append(f'{label}: state must bind selected-slot typed retained bytes');return
        actual=inspect_artifact(path,cache)
        if actual['sha256']!=digest or actual['size']<=0 or (size is not None and actual['size']!=size):
            errors.append(f'{label}: state digest/size must match actual retained bytes')
        if any(path.samefile(prior) for prior in all_paths):
            errors.append(f'{label}: recovery states, comparisons and retained outputs must be physically distinct')
        all_paths.append(path)
        return actual
    database=state['database']
    for name in ('schema','data'):
        readback=database[name+'Readback'];retained(readback['artifactRef'],database[name+'Sha256'],size=readback['byteCount'])
    for revision in state['revisions']:
        for name in ('aiResult','manualEdit'):
            payload=revision[name];retained(payload['artifactRef'],payload['sha256'],size=payload['byteCount'])
    validate_recovery_index_readback(root,execution,prefix,report,defs,label,errors,cache,retained)
    assets={item['assetId']:item for item in state['assets']}
    users={item['userId'] for item in state['permissions']}
    for domain,key in (('assets','assetId'),('permissions','userId'),('sourceMappings','sourceId'),('replicas','replicaId'),('retention','assetId'),('tasks','taskId'),('revisions','revisionId'),('indexEntries','entryId'),('deployment','imageId'),('delivery','eventId')):
        if len({item[key] for item in state[domain]})!=len(state[domain]):
            errors.append(f'{label}: {domain} identities must be unique')
    for domain in ('sourceMappings','replicas','retention','tasks','playback','revisions','indexEntries'):
        if any(item['assetId'] not in assets for item in state[domain]):errors.append(f'{label}: {domain} must reference restored authoritative assets')
    if any(item['ownerId'] not in users for item in state['tasks']) or any(item['authorUserId'] not in users for item in state['revisions']):
        errors.append(f'{label}: tasks/revisions must reference restored users')
    if any(item['authorizedUserId'] not in users or not recovery_playback_allowed(state,item) for item in state['playback']):errors.append(f'{label}: playback must bind its restored subject allow grant and current asset ACL')
    grants=[grant for user in state['permissions'] for grant in user['scopedGrants']]
    if len({g['grantId'] for g in grants})!=len(grants) or {g['assetId'] for g in grants}!=set(assets) or any(g['assetId'] not in assets or g['aclVersion']!=assets[g['assetId']]['aclVersion'] for g in grants):
        errors.append(f'{label}: scoped ACL grants must uniquely bind every restored asset and its ACL version')
    if any(item['anonymousAccess'] and item['visibility']!='PUBLIC' for item in state['assets']):
        errors.append(f'{label}: anonymous publication must retain the authoritative public visibility')
    if any(item['metadataSha256']!=assets.get(item['assetId'],{}).get('metadataSha256') for item in state['indexEntries']) or {item['assetId'] for item in state['indexEntries']}!=set(assets):
        errors.append(f'{label}: index entries must exactly reconcile restored authoritative metadata')
    if any(sum(item['primary'] is True for item in state['replicas'] if item['assetId']==asset)!=1 for asset in assets):
        errors.append(f'{label}: each asset requires exactly one verified authoritative primary replica')
    for item in state['replicas']:
        retained(item['artifactRef'],item['sha256'],size=item['byteCount'])
    if any(utc(item['scheduledAt']) is None for item in state['retention']):
        errors.append(f'{label}: retained retention scheduledAt must be a valid UTC date-time')
    previous='sha256:'+'0'*64
    for sequence,item in enumerate(state['audit']):
        payload={key:item[key] for key in ('entryId','sequence','entityId','previousSha256','event')}
        actual='sha256:'+hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()
        if item['sequence']!=sequence or item['previousSha256']!=previous or item['sha256']!=actual or item['entityId'] not in assets:
            errors.append(f'{label}: audit ordering and computed integrity chain must bind authoritative entities')
        previous=item['sha256']
        event=item['event']
        if event['actorId'] not in users or utc(event['occurredAt']) is None or event['taskId'] is not None and event['taskId'] not in {task['taskId'] for task in state['tasks']}:
            errors.append(f'{label}: canonical audit event must bind valid actor/time/task relationships')
    if len({item['dedupId'] for item in state['delivery']})!=len(state['delivery']) or any(item['aggregateId'] not in assets or item['publicationCount']!=(1 if item['status']=='processed' else 0) or item['inboxProcessedCount']!=(1 if item['status']=='processed' else 0) for item in state['delivery']):
        errors.append(f'{label}: delivery state must bind unique dedup/event identities and publication/inbox counts')
    if {item['referenceId'] for item in state['valueComparisons']}!=set(state['openbao']['referenceIds']):
        errors.append(f'{label}: actual value comparisons must cover exact restored OpenBao references')
    store=state['openbao'];retained(store['configurationRef'],store['configurationSha256'],'measurement_output')
    before=len(errors);configuration=selected_observation(root,execution,prefix,store['configurationRef'],defs,'recoveryOpenBaoConfiguration',label,errors,cache)
    if configuration is not None and len(errors)==before:
        if configuration['subjectVersion']!=report['subjectVersion'] or configuration['acceptanceProfile']!=report['acceptanceProfile'] or {m['mountId'] for m in configuration['mounts']}!=set(store['mountIds']) or {p['policyId'] for p in configuration['policies']}!=set(store['policyIds']) or len({m['mountId'] for m in configuration['mounts']})!=len(configuration['mounts']) or len({p['policyId'] for p in configuration['policies']})!=len(configuration['policies']) or len({a['authId'] for a in configuration['authMethods']})!=len(configuration['authMethods']):
            errors.append(f'{label}: non-secret OpenBao configuration must bind unique exact mounts/policies/auth settings and captured runtime/profile')
    value_observations=[]
    for item in state['valueComparisons']:
        retained(item['artifactRef'],item['sha256'],'measurement_output')
        before=len(errors)
        value=selected_observation(root,execution,prefix,item['artifactRef'],defs,'recoveryValuePhaseObservation',label,errors,cache)
        if value is None or len(errors)!=before:continue
        expected={key:report[key] for key in ('resourceId','acceptanceProfile','subjectVersion','inputSamples')}
        expected.update({key:item[key] for key in ('referenceId','method','comparisonContextId')})
        expected.update(recoveryRunId=comparison_run_id,phase='before_backup' if report['kind']=='recovery_baseline' else 'after_restore',readbackOutcome='succeeded')
        at,start,end=(utc(value.get('observedAt')),utc(report.get('observedStartedAt')),utc(report.get('observedFinishedAt')))
        if not recorded_text(comparison_run_id) or any(value.get(key)!=v for key,v in expected.items()) or at is None or start is None or end is None or not start<=at<=end:
            errors.append(f'{label}: value readback must bind exact pre/post phase, approved recovery run, subject and captured time')
        value_observations.append({key:value[key] for key in ('referenceId','method','comparisonContextId','comparisonDigest')})
    if len({item['logicalPath'] for item in state['files']})!=len(state['files']):errors.append(f'{label}: restored logical file paths must be unique')
    for item in state['files']:
        if not safe_generator_relative_path(item['logicalPath']):errors.append(f'{label}: logical file path must be safe and relative')
        retained(item['artifactRef'],item['sha256'],size=item['byteCount'])
    for item in state['playback']:
        first,last=item['rangeStart'],item['rangeEnd']
        if last<first:errors.append(f'{label}: playback range must be ordered');continue
        actual=retained(item['artifactRef'],item['sha256'],size=last-first+1)
        primary=[row for row in state['replicas'] if row['assetId']==item['assetId'] and row['primary'] is True and row['state']=='verified']
        if len(primary)!=1:continue  # The replica relationship check above reports this.
        replica=primary[0];source=existing_ref(root,replica['artifactRef'],prefix)
        if actual is None or source is None:continue
        if last>=replica['byteCount']:errors.append(f'{label}: playback range must be inside its verified primary replica');continue
        try:expected=replica['sha256'] if first==0 and last+1==replica['byteCount'] else range_slice_hash(source,first,last-first+1)
        except OSError:expected=None
        if actual['sha256']!=expected:errors.append(f'{label}: playback response bytes must equal the requested verified primary replica slice')
    for item in state['deployment']:
        retained(item['imageArtifactRef'],item['imageSha256'])
        retained(item['signatureArtifactRef'],item['signatureSha256'])
        before=len(errors);verification=selected_observation(root,execution,prefix,item['verificationRef'],defs,'recoveryDeploymentVerification',label,errors,cache)
        path=existing_ref(root,item['verificationRef'],prefix)
        if path:
            if any(path.samefile(prior) for prior in all_paths):errors.append(f'{label}: signature verification must be distinct from retained payloads')
            all_paths.append(path)
        if verification is None or any(verification.get(key)!=item[key] for key in ('imageSha256','signatureSha256','signerIdentity')):
            errors.append(f'{label}: signature verification must bind actual image/signature digests and approved signer')
        approvals=approved.get('approvedSigners')
        selected=[a for a in approvals if isinstance(a,dict) and a.get('signerIdentity')==item['signerIdentity']] if isinstance(approvals,list) else []
        if len(selected)!=1:
            errors.append(f'{label}: signature requires one independently approved public trust identity');continue
        trust=selected[0];validate_schema(trust,defs.get('recoverySignerApproval',{}),label+'/approved signer',errors)
        if verification is None or len(errors)!=before:continue
        key=existing_ref(root,trust['publicKeyRef'],prefix);image=existing_ref(root,item['imageArtifactRef'],prefix);signature=existing_ref(root,item['signatureArtifactRef'],prefix)
        if key is None or image is None or signature is None or trust['publicKeyRef'] not in execution['rawOutputRefs'] or artifacts.get(trust['publicKeyRef'],{}).get('artifactType')!='recovery_output' or not 0<inspect_artifact(key,cache)['size']<=16384 or inspect_artifact(key,cache)['sha256']!=trust['publicKeySha256'] or inspect_artifact(signature,cache)['size']!=64 or any(verification[k]!=trust[k] for k in ('algorithm','publicKeySha256','verifierBuild')):
            errors.append(f'{label}: signature verification must bind retained public key bytes and approved algorithm/build');continue
        verify_recovery_signature(image,signature,key,trust['verifierBuild'],label,errors,cache)
    return sorted(value_observations,key=lambda value:(value['referenceId'],value['method'],value['comparisonContextId']))


def validate_recovery_browse_request(root,execution,prefix,witness,states,approved,subjects,at,window,defs,label,errors,cache,paths):
    request=witness.get('request');before=len(errors)
    validate_schema(request,defs['recoveryBusinessEvent']['properties']['request'],label+'/browse request',errors)
    policy=approved.get('browseRequest') if isinstance(approved,dict) else None
    if len(errors)!=before:return
    if not isinstance(policy,dict) or not all(recorded_text(policy.get(k)) for k in ('requestURL','authRef')) or not isinstance(policy.get('requestedAssetIds'),list) or not policy['requestedAssetIds'] or not all(isinstance(k,str) and k for k in policy['requestedAssetIds']) or len(set(policy['requestedAssetIds']))!=len(policy['requestedAssetIds']):
        errors.append(f'{label}: browse request must bind the existing approved resource URL/auth reference and asset scope');return
    began,finished=utc(request['requestedAt']),utc(request['finishedAt'])
    if request['httpMethod']!='GET' or request['requestURL']!=policy['requestURL'] or request['authRef']!=policy['authRef'] or request['userId']!=subjects['authorizedUserId'] or request['authorizationDecision']!='allow' or request['statusCode']!=200 or began is None or finished is None or at!=finished or not window[0]<=began<=finished<=window[1]:
        errors.append(f'{label}: actual authenticated browse request identity, authorization and response completion must bind the readiness event')
    ref=request['responseArtifactRef'];path=existing_ref(root,ref,prefix);records=[r for r in execution['environmentCaptured']['rawExecutionArtifacts'] if r.get('ref')==ref]
    if path is None or ref not in execution['rawOutputRefs'] or len(records)!=1 or records[0].get('artifactType')!='recovery_output':errors.append(f'{label}: browse must retain selected-slot actual response bytes');return
    if any(path.samefile(peer) for peer in paths):errors.append(f'{label}: browse response must be physically distinct from state and event reports')
    paths.append(path);actual=inspect_artifact(path,cache)
    if not 0<actual['size']<=262144 or actual['size']!=request['responseByteCount'] or actual['sha256']!=request['responseSha256']:errors.append(f'{label}: browse response byte count/hash must match bounded actual response');return
    try:
        def fields(items):
            if len({k for k,_ in items})!=len(items):raise ValueError('duplicate browse fields')
            return dict(items)
        with path.open(encoding='utf8') as stream:body=json.load(stream,object_pairs_hook=fields)
        route=policy.get('responseItemsPath')
        if not isinstance(route,list) or len(route)>8 or any(not isinstance(k,str) or not k for k in route):raise ValueError('approved response projection required')
        for key in route:body=body[key]
        if not isinstance(body,list) or not body or len(body)>10000 or any(not isinstance(row,dict) or not isinstance(row.get('assetId'),str) or not row['assetId'] or not isinstance(row.get('version'),str) or not row['version'] or type(row.get('aclVersion')) is not int or row['aclVersion']<1 for row in body):raise ValueError('typed browse asset/version and positive integer ACL identities required')
        ids=[row['assetId'] for row in body]
        if any(not isinstance(k,str) for k in ids) or len(ids)!=len(set(ids)) or set(ids)!=set(policy['requestedAssetIds']) or subjects['assetId'] not in ids:raise ValueError('exact requested asset identities required')
        assets={row['assetId']:row for row in states['assets']}
        if any(row['assetId'] not in assets or any(row[k]!=assets[row['assetId']][k] for k in ('version','aclVersion')) or not recovery_playback_allowed(states,dict(assetId=row['assetId'],authorizedUserId=request['userId'])) for row in body):raise ValueError('returned identities must match restored versions and subject allow grants without matching deny')
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):errors.append(f'{label}: retained browse response must reconcile actual returned identities with the restored ACL state')


def validate_recovery_replay_readback(root,execution,prefix,capture,restored,comparison,approved,run_id,window,defs,label,errors,cache,paths):
    before=len(errors);report=selected_observation(root,execution,prefix,comparison['replayExecutionRef'],defs,'recoveryReplayExecution',label+'/replay execution',errors,cache);post=selected_observation(root,execution,prefix,comparison['postReplayStateRef'],defs,'recoveryDeliveryReadback',label+'/post replay',errors,cache)
    if report is None or post is None or len(errors)!=before:return
    for ref in (comparison['replayExecutionRef'],comparison['postReplayStateRef']):
        path=existing_ref(root,ref,prefix)
        if any(path.samefile(peer) for peer in paths):errors.append(f'{label}: replay execution and independently captured post-state must be physically distinct')
        paths.append(path)
    common={key:comparison[key] for key in ('resourceId','subjectVersion','acceptanceProfile','inputSamples')};common.update(configurationRef=capture['configurationRef'],recoveryRunId=run_id)
    policy=approved.get('replayCommand')
    if not isinstance(policy,dict) or not isinstance(policy.get('commandArgs'),list) or not policy['commandArgs'] or any(not recorded_text(v) for v in policy['commandArgs']) or not all(recorded_text(policy.get(k)) for k in ('toolBuild','consumerId')):
        errors.append(f'{label}: replay must bind existing resource-approved command/tool/consumer');return
    if any(row.get(k)!=v for row in (report,post) for k,v in common.items()) or report['restoredRef']!=capture['restoredRef'] or post['replayExecutionRef']!=comparison['replayExecutionRef'] or report['commandArgs']!=policy['commandArgs'] or report['toolBuild']!=policy['toolBuild'] or report['exitCode']!=0:
        errors.append(f'{label}: replay execution must bind actual command/tool/run/input/profile and restored state')
    start,end,post_at,compare_end=(utc(x) for x in (report['startedAt'],report['finishedAt'],post['observedAt'],comparison['observedFinishedAt']))
    compare_start=utc(comparison['observedStartedAt'])
    if None in (start,end,post_at,compare_end,compare_start) or window is None or not window[0]<=compare_start<=start<=end<=post_at<=compare_end<=window[1]:errors.append(f'{label}: replay command and independent post-state must be ordered within the comparison execution interval')
    output=report['outputArtifact'];path=existing_ref(root,output['artifactRef'],prefix);records=[r for r in execution['environmentCaptured']['rawExecutionArtifacts'] if r.get('ref')==output['artifactRef']]
    if path is None or output['artifactRef'] not in execution['rawOutputRefs'] or len(records)!=1 or records[0].get('artifactType')!='recovery_output':errors.append(f'{label}: replay must retain actual selected-slot command output');return
    if any(path.samefile(peer) for peer in paths):errors.append(f'{label}: command output must be physically distinct from independently captured delivery state')
    paths.append(path);actual=inspect_artifact(path,cache)
    if actual['size']<=0 or actual['size']!=output['byteCount'] or actual['sha256']!=output['sha256']:errors.append(f'{label}: actual replay command output must match its byte count/hash');return
    before_rows={row['eventId']:row for row in restored['states']['delivery']};observed={};publications=set()
    try:
        for row in streamed_metadata_records(path,defs['recoveryReplayEvent']):
            event=row['eventId'];prior=before_rows.get(event)
            if event in observed or event not in comparison['replayedEventIds'] or prior is None or any(row[k]!=prior[k] for k in ('dedupId','aggregateId')) or row['publicationId'] in publications or row['consumerId']!=policy['consumerId'] or row['publicationCount']!=1 or row['inboxProcessedCount']!=1 or row['outcome']!='processed':raise ValueError('replay command output must bind each selected event/dedup/aggregate to one actual publication and consumer result')
            observed[event]=row;publications.add(row['publicationId'])
            if len(observed)>10000:raise ValueError('replay output exceeds selected manifest bound')
        if set(observed)!=set(comparison['replayedEventIds']):raise ValueError('actual command output must cover exact selected replay events')
    except (OSError,ValueError,UnicodeError,jsonschema.ValidationError):errors.append(f'{label}: parsed actual replay command output must prove the selected once-only publication/consumer outcomes')
    if post['delivery']!=comparison['postReplayDelivery']:errors.append(f'{label}: comparison delivery claims must equal independently captured actual post-replay state')


def validate_qualified_recovery_observation(root, plan, execution, prefix, status, window, defs, errors, cache):
    if plan['pocId']!='POC-10' or status!='pass':return
    label=f"qualified recovery observation {plan['taskId']}"
    env=execution.get('environmentCaptured') or {}
    capture=env.get('recoveryEvidence')
    resources=[item for item in execution.get('resources') or [] if isinstance(item,dict) and item.get('id')=='RES-RECOVERY-SANDBOX']
    if not isinstance(capture,dict) or len(resources)!=1 or capture.get('configurationRef')!=resources[0].get('configurationRef'):
        errors.append(f'{label}: recovery evidence must bind approved recovery resource configuration');return
    config_path=existing_ref(root,capture['configurationRef'],prefix)
    try:approved=load(config_path).get('configuration',{}).get('recoveryBaseline') if config_path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):approved=None
    if not isinstance(approved,dict) or approved.get('baselineRef')!=capture.get('baselineRef'):
        errors.append(f'{label}: approved baseline reference required');return
    reports={};paths=[];before=len(errors)
    for key,schema in (('baselineRef','recoveryStateManifest'),('restoredRef','recoveryStateManifest'),('comparisonRef','recoveryComparisonReport')):
        report=selected_observation(root,execution,prefix,capture.get(key),defs,schema,label,errors,cache)
        path=existing_ref(root,capture.get(key),prefix)
        if path:
            if any(path.samefile(prior) for prior in paths):errors.append(f'{label}: baseline/restored/comparison reports must be physically distinct')
            paths.append(path)
        reports[key]=report
    if len(errors)!=before or any(report is None for report in reports.values()):return
    baseline,restored,comparison=(reports[key] for key in ('baselineRef','restoredRef','comparisonRef'))
    baseline_sha=inspect_artifact(paths[0],cache)['sha256'];restored_sha=inspect_artifact(paths[1],cache)['sha256']
    if approved.get('baselineSha256')!=baseline_sha or comparison.get('baselineRef')!=capture['baselineRef'] or comparison.get('baselineSha256')!=baseline_sha or comparison.get('restoredRef')!=capture['restoredRef'] or comparison.get('restoredSha256')!=restored_sha:
        errors.append(f'{label}: approved baseline and comparison must bind actual manifest bytes')
    inputs=[{key:sample.get(key) for key in ('id','immutableId','checksum')} for sample in execution.get('samples') or []]
    subject=compliance_subject_version(plan,execution)
    for report in (baseline,restored,comparison):
        if report.get('inputSamples')!=inputs or report.get('subjectVersion')!=subject or report.get('acceptanceProfile')!=env.get('acceptanceProfile'):
            errors.append(f'{label}: manifests/comparison must bind exact approved inputs, tool build and profile')
    begin,end=utc(baseline['observedStartedAt']),utc(baseline['observedFinishedAt'])
    config=load(config_path);approval=utc(config.get('approvedAt'))
    if begin is None or end is None or approval is None or window is None or not begin<end<=approval<=window[0]:
        errors.append(f'{label}: baseline capture and independent approval must precede restore execution')
    if baseline['kind']!='recovery_baseline' or restored['kind']!='recovery_restored':errors.append(f'{label}: exact baseline/restored report roles required')
    observation_interval(restored,execution,label,errors);observation_interval(comparison,execution,label,errors)
    if utc(restored['observedFinishedAt']) and utc(comparison['observedStartedAt']) and utc(restored['observedFinishedAt'])>utc(comparison['observedStartedAt']):errors.append(f'{label}: comparison must follow restored-state capture')
    timing_subjects=config.get('configuration',{}).get('recoveryTimingSubjects')
    comparison_run_id=timing_subjects.get('recoveryRunId') if isinstance(timing_subjects,dict) else None
    value_observations=[validate_recovery_state(root,execution,prefix,report,defs,label,errors,cache,paths,approved,comparison_run_id) for report in (baseline,restored)]
    if value_observations[0]!=value_observations[1]:errors.append(f'{label}: actual pre/post secret comparison digests must match')
    expected_gates={item['id'] for item in plan['protocol']['measurements'] if item['unit']=='boolean'}
    rows=comparison['rows']
    if set(RECOVERY_GATE_DOMAINS)!=expected_gates or len(rows)!=len(expected_gates) or {row['gate'] for row in rows}!=expected_gates:
        errors.append(f'{label}: comparison must cover exact frozen boolean recovery gates')
    for row in rows:
        domains=RECOVERY_GATE_DOMAINS.get(row['gate'])
        if domains is None:continue
        left={domain:recovery_domain_digest(baseline['states'][domain]) for domain in domains}
        right={domain:recovery_domain_digest(restored['states'][domain]) for domain in domains}
        if row['before']!=left or row['after']!=right or left!=right:
            errors.append(f'{label}: {row["gate"]} must be supported by computed parsed-state comparisons')
    contexts=[{key:item[key] for key in ('referenceId','method','comparisonContextId')} for item in baseline['states']['valueComparisons']]
    if approved.get('approvedComparisonContexts')!=contexts:errors.append(f'{label}: one-way/HMAC comparison context requires explicit prior resource approval')
    negative=baseline['states']['unreadableFixture'];witness=comparison['unreadableWitness']
    if any(witness.get(key)!=negative[key] for key in ('fixtureId','backupSha256')) or witness.get('errorCode')!=negative['expectedErrorCode']:
        errors.append(f'{label}: unreadable backup witness must identify exact approved negative fixture and expected failure')
    before=len(errors);observation=selected_observation(root,execution,prefix,witness.get('observationRef'),defs,'recoveryBackupDecodeObservation',label,errors,cache)
    approved_negative=approved.get('approvedUnreadableFixture')
    identity_keys=('fixtureId','backupSha256','controlBackupSha256','codec','corruptionOffset','corruptionXor')
    if not isinstance(approved_negative,dict) or any(approved_negative.get(k)!=negative[k] for k in identity_keys):
        errors.append(f'{label}: corrupted backup must bind exact independently approved readable control and mutation')
    for report in (baseline,restored):
        fixture=report['states']['unreadableFixture'];store=report['states']['openbao']
        control=existing_ref(root,fixture['controlBackupRef'],prefix);corrupt=existing_ref(root,fixture['artifactRef'],prefix)
        if control is None or corrupt is None or any(a.get('ref') not in execution['rawOutputRefs'] for a in ({'ref':fixture['controlBackupRef']},{'ref':fixture['artifactRef']})) or any(next((a.get('artifactType') for a in env['rawExecutionArtifacts'] if a.get('ref')==ref),None)!='recovery_output' for ref in (fixture['controlBackupRef'],fixture['artifactRef'])):
            errors.append(f'{label}: unreadable backup requires retained selected-slot control and corrupted bytes');continue
        control_info,corrupt_info=inspect_artifact(control,cache),inspect_artifact(corrupt,cache)
        if not 0<control_info['size']<=262144 or corrupt_info['size']!=fixture['byteCount'] or corrupt_info['sha256']!=fixture['backupSha256'] or control_info['sha256']!=fixture['controlBackupSha256'] or control.samefile(corrupt):
            errors.append(f'{label}: backup fixture must bind bounded distinct actual control/corrupt bytes');continue
        try:
            original=control.read_bytes();damaged=corrupt.read_bytes();offset=fixture['corruptionOffset']
            if offset>=len(original) or damaged!=original[:offset]+bytes([original[offset]^fixture['corruptionXor']])+original[offset+1:]:raise ValueError('corruption is not the approved control mutation')
            decoded=decode_recovery_control_backup(original)
            config_path=existing_ref(root,store['configurationRef'],prefix)
            config=qualified_observation_report(config_path,defs,'recoveryOpenBaoConfiguration',label,errors,cache) if config_path else None
            if config is None or decoded!=config:raise ValueError('readable control must restore the captured non-secret configuration')
            digest='sha256:'+hashlib.sha256(json.dumps(decoded,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')).hexdigest()
            try:decode_recovery_control_backup(damaged)
            except (ValueError,zlib.error,UnicodeError):pass
            else:raise ValueError('corrupted backup decoded successfully')
            if observation is None or any(observation.get(k)!=fixture[k] for k in ('fixtureId','backupSha256','controlBackupSha256','codec')) or observation.get('controlDecodedSha256')!=digest:
                raise ValueError('decoder observation must reconcile actual readable-control output and corrupted-input failure')
        except (OSError,ValueError,zlib.error,UnicodeError) as exc:
            errors.append(f'{label}: actual controlled backup decoding failed admission: {exc}')
    before_delivery={item['eventId']:item for item in restored['states']['delivery']};after_delivery={item['eventId']:item for item in comparison['postReplayDelivery']}
    if len(after_delivery)!=len(comparison['postReplayDelivery']) or set(before_delivery)!=set(after_delivery):
        errors.append(f'{label}: replay must preserve exact event identities without duplicates')
    selected=comparison['replayedEventIds']
    approved_events=approved.get('approvedReplayEventIds')
    if selected!=approved_events or not set(selected).issubset(before_delivery):
        errors.append(f'{label}: replay must bind exact previously approved event identities')
    transitioned=False
    for event,item in before_delivery.items():
        target=after_delivery.get(event) or {}
        expected={**item,'status':'processed','publicationCount':1,'inboxProcessedCount':1} if event in selected else item
        if target!=expected:
            errors.append(f'{label}: replay must process each exact dedup identity only once')
        transitioned=transitioned or event in selected and item['status']=='pending' and target.get('status')=='processed'
    if not transitioned:errors.append(f'{label}: an approved pending fixture must actually undergo replay')
    validate_recovery_replay_readback(root,execution,prefix,capture,restored,comparison,approved,comparison_run_id,window,defs,label,errors,cache,paths)


RECOVERY_TIME_ENDPOINTS = {
    'rpo_observed':('backup_checkpoint','recoverable_data_boundary'),
    'rto_observed':('recovery_started','recovery_completed'),
    'service_recovery_time':('recovery_started','services_ready'),
    'vm_recovery_time':('recovery_started','vm_set_ready'),
    'core_browsing_recovery_time':('recovery_started','authenticated_browsing_succeeded'),
    'playback_recovery_time':('recovery_started','authorized_playback_succeeded'),
}


def validate_qualified_recovery_timing(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-10' or status!='pass':return
    label=f"qualified recovery timing {plan['taskId']}"
    env=execution.get('environmentCaptured') or {};capture=env.get('recoveryEvidence')
    if not isinstance(capture,dict):return  # The recovery-state validator reports the missing capture.
    before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('recoveryTimingRef'),defs,'recoveryTimingReport',label,errors,cache)
    if report is None or len(errors)!=before:return
    config_path=existing_ref(root,capture.get('configurationRef'),prefix)
    try:config=load(config_path) if config_path else {};approved=config.get('configuration',{}).get('recoveryTimingSubjects')
    except (OSError,ValueError,AttributeError,yaml.YAMLError):approved=None
    if not isinstance(approved,dict) or report['subjects']!=approved or any(not recorded_text(approved.get(key)) for key in ('recoveryRunId','physicalHostId','serviceSetId','vmSetId','authorizedUserId','assetId')):
        errors.append(f'{label}: exact previously approved recovery run/host/service/VM/access subjects required');return
    expected=dict(configurationRef=capture.get('configurationRef'),baselineRef=capture.get('baselineRef'),restoredRef=capture.get('restoredRef'),comparisonRef=capture.get('comparisonRef'),resourceId='RES-RECOVERY-SANDBOX',subjectVersion=compliance_subject_version(plan,execution),acceptanceProfile=env.get('acceptanceProfile'),inputSamples=[{key:s.get(key) for key in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    if any(report.get(key)!=value for key,value in expected.items()):errors.append(f'{label}: timing must bind exact baseline/restored/comparison/resource/tool/input/profile identities')
    names={event for pair in RECOVERY_TIME_ENDPOINTS.values() for event in pair};rows=report['events']
    if len(rows)!=len(names) or {row['event'] for row in rows}!=names:
        errors.append(f'{label}: exact unique recovery business events required');return
    times={};paths=[]
    for key in ('baselineRef','restoredRef','comparisonRef'):
        path=existing_ref(root,capture.get(key),prefix)
        if path:paths.append(path)
    timing_path=existing_ref(root,env.get('recoveryTimingRef'),prefix)
    if timing_path:paths.append(timing_path)
    for row in rows:
        name=row['event'];at=utc(row['observedAt']);path=existing_ref(root,row['witnessRef'],prefix)
        before=len(errors)
        witness=selected_observation(root,execution,prefix,row['witnessRef'],defs,'recoveryBusinessEvent',label,errors,cache)
        if witness is None or len(errors)!=before:continue
        if path and any(path.samefile(peer) for peer in paths):errors.append(f'{label}: business event witnesses must be physically distinct from reports and other events')
        if path:paths.append(path)
        identity=dict(event=name,observedAt=row['observedAt'],subjects=approved,resourceId='RES-RECOVERY-SANDBOX',subjectVersion=expected['subjectVersion'],acceptanceProfile=expected['acceptanceProfile'],inputSamples=expected['inputSamples'],outcome='succeeded')
        if any(witness.get(key)!=value for key,value in identity.items()):errors.append(f'{label}: retained event must bind its exact timestamp and approved execution subjects')
        if at is None:errors.append(f'{label}: each business event requires a valid UTC timestamp')
        else:times[name]=at
    if set(times)!=names or window is None:return
    checkpoint=utc(approved.get('backupCheckpointAt'))
    before=len(errors)
    baseline=selected_observation(root,execution,prefix,capture.get('baselineRef'),defs,'recoveryStateManifest',label,errors,cache)
    restored=selected_observation(root,execution,prefix,capture.get('restoredRef'),defs,'recoveryStateManifest',label,errors,cache)
    comparison=selected_observation(root,execution,prefix,capture.get('comparisonRef'),defs,'recoveryComparisonReport',label,errors,cache)
    if len(errors)!=before or any(report is None for report in (baseline,restored,comparison)):return
    baseline_end=utc(baseline.get('observedFinishedAt')) if isinstance(baseline,dict) else None
    comparison_end=utc(comparison.get('observedFinishedAt')) if isinstance(comparison,dict) else None
    if checkpoint is None or checkpoint!=times['backup_checkpoint'] or baseline_end is None or checkpoint>baseline_end:
        errors.append(f'{label}: backup checkpoint must bind approved baseline recoverable data boundary')
    for name,at in times.items():
        if name!='backup_checkpoint' and not window[0]<=at<=window[1]:errors.append(f'{label}: recovery business event must occur inside executionWindow')
    start=times['recovery_started'];complete=times['recovery_completed'];boundary=times['recoverable_data_boundary']
    ready=('services_ready','vm_set_ready','authenticated_browsing_succeeded','authorized_playback_succeeded')
    if not times['backup_checkpoint']<=boundary<=start<=complete or any(not start<=times[key]<=complete for key in ready) or comparison_end is None or complete>comparison_end:
        errors.append(f'{label}: checkpoint/disruption/recovery/readiness/completion events must be ordered')
    try:states=restored['states'];users={item['userId'] for item in states['permissions']};assets={item['assetId'] for item in states['assets']};playback=states['playback']
    except (TypeError,KeyError,AttributeError):return
    if approved['authorizedUserId'] not in users or approved['assetId'] not in assets or not any(item['assetId']==approved['assetId'] and item['authorizedUserId']==approved['authorizedUserId'] and item['statusCode']==206 and recovery_playback_allowed(states,item) for item in playback):
        errors.append(f'{label}: browsing/playback ready events must bind restored authorized subjects')
    browse_event=next(row for row in rows if row['event']=='authenticated_browsing_succeeded')
    before=len(errors);browse_witness=selected_observation(root,execution,prefix,browse_event['witnessRef'],defs,'recoveryBusinessEvent',label,errors,cache)
    if browse_witness is not None and len(errors)==before:
        baseline_policy=config.get('configuration',{}).get('recoveryBaseline')
        validate_recovery_browse_request(root,execution,prefix,browse_witness,states,baseline_policy,approved,times['authenticated_browsing_succeeded'],window,defs,label,errors,cache,paths)
    validate_recovery_readiness(root,execution,prefix,capture,config,baseline,restored,approved,rows,times,window,defs,label,errors,cache,paths)
    actual={item.get('id'):item.get('actual') for item in execution.get('measurements') or []}
    for metric,(first,last) in RECOVERY_TIME_ENDPOINTS.items():
        measured=(times[last]-times[first]).total_seconds();claimed=actual.get(metric)
        if isinstance(claimed,bool) or not isinstance(claimed,(int,float)) or not math.isfinite(claimed) or measured<0 or not math.isclose(claimed,measured,rel_tol=1e-9,abs_tol=1e-9):
            errors.append(f'{label}: {metric} must equal retained business-event elapsed seconds')


ACCESS_DENIAL_GATES={'unauthorized':'unauthorized_identity_denied','expired':'expired_authorization_denied','cross_user':'cross_user_cache_isolation','rate_limit':'rate_limit_enforced','direct_source':'local_direct_origin_denied','direct_admin':'local_direct_origin_denied','direct_worker':'local_direct_origin_denied'}


def validate_qualified_access_outcomes(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-07' or status!='pass':return
    label=f"qualified access outcomes {plan['taskId']}";env=execution.get('environmentCaptured') or {};profile=(env.get('acceptanceProfile') or {}).get('id');local=profile=='local-v1';before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('accessOutcomeRef'),defs,'accessOutcomeReport',label,errors,cache)
    if report is None or len(errors)!=before:return
    resource_id='RES-LOCAL-ACCESS-PATH' if local else 'RES-PUBLIC-NETWORK'
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')==resource_id),None)
    if resource is None or report['configurationRef']!=resource.get('configurationRef') or report['pathConfigurationRef']!=env.get('acceptanceProfileConfigurationRef'):
        errors.append(f'{label}: exact selected profile/resource/path configuration required');return
    config_path=existing_ref(root,report['configurationRef'],prefix)
    try:policy=load(config_path).get('configuration',{}).get('accessPolicy') if config_path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    before=len(errors);validate_schema(policy,defs.get('accessOutcomePolicy',{}),label,errors)
    if len(errors)!=before or policy is None:return
    if not math.isfinite(policy['rateLimit']['windowSeconds']):
        errors.append(f'{label}: finite approved rate window required');return
    inputs=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []]
    expected=dict(resourceId=resource_id,acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=inputs,assetId=policy['assetId'],sourceVersion=policy['sourceVersion'],aclVersion=policy['aclVersion'])
    if any(report.get(k)!=v for k,v in expected.items()):errors.append(f'{label}: report must bind approved subjects, ACL/source versions, input/tool/profile')
    if policy['authorizedUserId']==policy['deniedUserId'] or policy['authorizedGrantId']==policy['expiredGrantId'] or any(not recorded_text(policy[k]) for k in ('assetId','sourceVersion','aclVersion','authorizedUserId','deniedUserId','authorizedGrantId','expiredGrantId')):
        errors.append(f'{label}: concrete distinct authorized/denied subjects and grants required')
    valid_from,valid_until,expired=map(utc,(policy['grantValidFrom'],policy['grantValidUntil'],policy['expiredAt']))
    if valid_from is None or valid_until is None or expired is None or valid_from>=valid_until or window is None:
        errors.append(f'{label}: valid UTC approved grant lifetime required');return
    source_rows=env.get('inputSampleArtifacts') or []
    if not isinstance(source_rows,list):
        errors.append(f'{label}: typed actual input sample artifacts required');return
    selected=[r for r in source_rows if isinstance(r,dict) and r.get('sampleId')==report['inputSampleId']]
    sample=next((s for s in execution.get('samples') or [] if s.get('id')==report['inputSampleId']),None)
    source=existing_ref(root,selected[0].get('inputArtifactRef'),prefix) if len(selected)==1 else None
    if sample is None or source is None or selected[0].get('immutableId')!=sample.get('immutableId') or inspect_artifact(source,cache)['sha256']!=sample.get('checksum'):
        errors.append(f'{label}: actual approved source bytes required');return
    source_info=inspect_artifact(source,cache);etag='"'+sample['checksum'].removeprefix('sha256:')+'"'
    required={'authorized_range','authorized_if_range','authorized_stream','unauthorized','expired','cross_user','rate_limit'}
    if local:required|={'direct_source','direct_admin','direct_worker'}
    rows=report['cases']
    if len(rows)!=len(required) or {r['case'] for r in rows}!=required:
        errors.append(f'{label}: exact unique authorized, denial, cache, rate and route cases required');return
    if local:
        tls=env.get('local_tls_path_configuration')
        try:
            parsed={key:urllib.parse.urlsplit(policy['paths'][key]) for key in ('range','stream','source')}
        except ValueError:
            errors.append(f'{label}: valid approved local access URLs required');return
        if not isinstance(tls,dict) or any(parsed[key].scheme+'://'+parsed[key].netloc!=tls.get('entryOrigin') for key in ('range','stream')) or parsed['source'].scheme+'://'+parsed['source'].netloc!=tls.get('openlistOrigin'):
            errors.append(f'{label}: access policy must bind the captured local TLS/OpenList origins')
    artifacts={a.get('ref'):a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and isinstance(a.get('ref'),str)};paths=[source];passed={};primed_at=None;primed_range=None;denied_ranges=[];rate_case=None
    def public_denial(body,actual,case):
        if actual['size']==0:return True
        if actual['size']>1024:return False
        def public_fields(pairs):
            if len({key for key,_ in pairs})!=len(pairs):raise ValueError('duplicate public error fields')
            return dict(pairs)
        try:
            with body.open(encoding='utf8') as stream:document=json.load(stream,object_pairs_hook=public_fields)
        except (OSError,ValueError,UnicodeError):return False
        return document=={'error':'rate_limited' if case=='rate_limit' else 'access_denied'}
    for row in rows:
        case=row['case'];before=len(errors);witness=selected_observation(root,execution,prefix,row['witnessRef'],defs,'accessRequestOutcome',label,errors,cache)
        if witness is None or len(errors)!=before:continue
        common={k:report[k] for k in ('configurationRef','pathConfigurationRef','resourceId','acceptanceProfile','subjectVersion','inputSamples','assetId','sourceVersion','aclVersion','inputSampleId')}
        if any(witness.get(k)!=v for k,v in common.items()) or witness['case']!=case:errors.append(f'{label}: retained request must bind exact case/subject/ACL/source/configuration')
        at=utc(witness['observedAt']);body=existing_ref(root,witness['responseBodyRef'],prefix);trace=existing_ref(root,row['witnessRef'],prefix)
        if at is None or not window[0]<=at<=window[1] or body is None or artifacts.get(witness['responseBodyRef'],{}).get('artifactType')!='produced_media' or witness['responseBodyRef'] not in (execution.get('rawOutputRefs') or []):
            errors.append(f'{label}: selected-slot actual returned bytes and valid UTC request time required');continue
        for path in (trace,body):
            if path and any(path.samefile(peer) for peer in paths):errors.append(f'{label}: each request and response artifact must be physically distinct')
            if path:paths.append(path)
        actual=inspect_artifact(body,cache)
        if actual['sha256']!=witness['responseSha256'] or actual['size']!=witness['responseByteCount']:errors.append(f'{label}: response hash/count must bind actual returned bytes')
        role='stream' if case=='authorized_stream' else case.removeprefix('direct_') if case.startswith('direct_') else 'range'
        if witness['requestURL']!=policy['paths'][role]:errors.append(f'{label}: exact approved entry/origin/admin/worker path required')
        if case.startswith('authorized_'):
            if witness['userId']!=policy['authorizedUserId'] or witness['grantId']!=policy['authorizedGrantId'] or not valid_from<=at<valid_until:errors.append(f'{label}: authorized request must use the approved currently valid subject/grant')
            first,last=witness['rangeStart'],witness['rangeEnd'];is_stream=case=='authorized_stream'
            if witness['statusCode']!=(200 if is_stream else 206) or witness['etag']!=etag or witness['requestRange']!=('' if is_stream else f'bytes={first}-{last}') or witness['ifRange']!=(etag if case=='authorized_if_range' else '') or not 0<=first<=last<source_info['size'] or (is_stream and (first!=0 or last!=source_info['size']-1)) or witness['contentRange']!=('' if is_stream else f'bytes {first}-{last}/{source_info["size"]}') or actual['size']!=last-first+1:
                errors.append(f'{label}: authorized Range/If-Range/stream status and headers must match exact approved source')
            else:
                digest=hashlib.sha256();remaining=last-first+1
                with source.open('rb') as stream:
                    stream.seek(first)
                    while remaining:
                        block=stream.read(min(remaining,ARTIFACT_CHUNK_BYTES))
                        if not block:break
                        digest.update(block);remaining-=len(block)
                if remaining or actual['sha256']!='sha256:'+digest.hexdigest():errors.append(f'{label}: authorized response bytes must equal the actual approved source interval')
            if case=='authorized_stream':
                if witness['maximumBufferedBytes']>policy['maximumBufferedBytes']:errors.append(f'{label}: streaming buffer exceeds approved bound')
            if case=='authorized_range':primed_at=at;primed_range=(witness['rangeStart'],witness['rangeEnd'],witness['requestRange'])
        else:
            denied_ranges.append((witness['rangeStart'],witness['rangeEnd'],witness['requestRange']))
            if case!='rate_limit' and witness['originRequestCount']!=0:
                errors.append(f'{label}: denied requests must not contact the origin')
            if case=='expired':
                if witness['userId']!=policy['authorizedUserId'] or witness['grantId']!=policy['expiredGrantId'] or at<expired:errors.append(f'{label}: expired denial must exercise the approved expired grant')
            elif case=='cross_user':
                if witness['userId']!=policy['deniedUserId'] or witness['grantId']!=policy['deniedGrantId'] or not valid_from<=at<valid_until or witness['cacheKey']!=policy['protectedCacheKey']:errors.append(f'{label}: cross-user request must exercise the same protected cached object with the denied subject/grant')
            elif case=='rate_limit':
                rate_case=witness
                if witness['userId']!=policy['authorizedUserId'] or witness['grantId']!=policy['authorizedGrantId'] or not valid_from<=at<valid_until or witness['statusCode']!=429 or witness['requestCount']<=policy['rateLimit']['maximumRequests'] or witness['originRequestCount']>policy['rateLimit']['maximumRequests'] or witness['rateWindowSeconds']!=policy['rateLimit']['windowSeconds']:errors.append(f'{label}: rate outcome must exceed approved limit with bounded origin requests and 429')
                attempts=witness['rateAttempts'];limit=policy['rateLimit']['maximumRequests'];times=[utc(a['observedAt']) for a in attempts]
                if len(attempts)!=witness['requestCount'] or [a['sequence'] for a in attempts]!=list(range(1,len(attempts)+1)) or any(t is None for t in times) or not times or times[-1]!=at or any(not window[0]<=t<=at for t in times) or any(a>b for a,b in zip(times,times[1:])) or (times[-1]-times[0]).total_seconds()>policy['rateLimit']['windowSeconds'] or sum(a['originContacted'] for a in attempts)!=witness['originRequestCount'] or any(a['statusCode']!=206 if a['sequence']<=limit else a['statusCode']!=429 or a['originContacted'] for a in attempts):
                    errors.append(f'{label}: rate counts/statuses/timestamps must derive from retained consecutive request attempts')
                elif any(not valid_from<=t<valid_until for t in times):errors.append(f'{label}: each rate attempt must use a currently valid grant')
                for attempt in attempts:
                    returned=existing_ref(root,attempt['responseBodyRef'],prefix)
                    if returned is None or artifacts.get(attempt['responseBodyRef'],{}).get('artifactType')!='produced_media' or attempt['responseBodyRef'] not in (execution.get('rawOutputRefs') or []):
                        errors.append(f'{label}: each rate attempt requires actual selected-slot returned bytes');continue
                    observed=inspect_artifact(returned,cache)
                    if observed['sha256']!=attempt['responseSha256'] or observed['size']!=attempt['responseByteCount']:errors.append(f'{label}: rate attempt response count/hash must bind actual bytes')
                    if attempt['sequence']>limit:
                        if not public_denial(returned,observed,'rate_limit'):errors.append(f'{label}: excess rate attempt leaked protected payload')
                    else:
                        first,last=witness['rangeStart'],witness['rangeEnd'];digest=hashlib.sha256();remaining=last-first+1
                        if not 0<=first<=last<source_info['size']:errors.append(f'{label}: rate warmup request needs valid approved source interval');continue
                        with source.open('rb') as stream:
                            stream.seek(first)
                            while remaining:
                                block=stream.read(min(remaining,ARTIFACT_CHUNK_BYTES))
                                if not block:break
                                digest.update(block);remaining-=len(block)
                        if remaining or observed['size']!=last-first+1 or observed['sha256']!='sha256:'+digest.hexdigest():errors.append(f'{label}: allowed rate warmup bytes must equal the approved protected interval')
                if attempts and attempts[-1]['responseBodyRef']!=witness['responseBodyRef']:errors.append(f'{label}: final throttled response must bind the actual last request attempt')
            elif witness['userId']!='anonymous' or witness['grantId'] is not None:errors.append(f'{label}: unauthorized/direct-origin denial must lack valid subject/grant')
            if witness['statusCode'] not in ([429] if case=='rate_limit' else [401,403]):errors.append(f'{label}: denied requests require fail-closed HTTP status')
            if not public_denial(body,actual,case):errors.append(f'{label}: denial body must be empty or an exact public error document without protected bytes')
        passed[case]=len(errors)==before
        if case in ('authorized_range','cross_user') and witness['cacheKey']!=policy['protectedCacheKey']:errors.append(f'{label}: authorized/cache-isolation cases must use exact shared cache identity')
    if primed_range is None or any(value!=primed_range for value in denied_ranges):errors.append(f'{label}: denied cases must exercise the same protected Range as authorized cache priming')
    cross=next((r for r in rows if r['case']=='cross_user'),None)
    if cross:
        before=len(errors);witness=selected_observation(root,execution,prefix,cross['witnessRef'],defs,'accessRequestOutcome',label,errors,cache)
        if witness is not None and len(errors)==before and (primed_at is None or utc(witness['observedAt']) is None or utc(witness['observedAt'])<=primed_at):errors.append(f'{label}: cross-user denial must follow authorized cache priming')
    if rate_case is None:errors.append(f'{label}: approved rate-limit exercise required')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    for case,gate in ACCESS_DENIAL_GATES.items():
        if case in required and (not passed.get(case) or actual.get(gate) is not True):errors.append(f'{label}: {gate} must be supported by the corresponding observed denial')
    for gate,case in (('local_range_through_path' if local else 'range_through_path','authorized_range'),('local_large_file_streaming' if local else 'public_large_file_streaming','authorized_stream')):
        if actual.get(gate) is not True or not passed.get(case) or not passed.get('authorized_if_range'):errors.append(f'{label}: authorized Range/If-Range and streaming gate must bind observed bytes')



RANGE_MATRIX_CASES={'range_start','range_middle','range_end','suffix','unsatisfiable','if_match','if_stale','miss','fill','hit','updated','interrupted','partial_read','recovered','stream','other_user','denied_user','latency_hot','latency_cold','latency_slow','latency_multi'}


def range_slice_hash(path,first,count):
    digest=hashlib.sha256();remaining=count
    with path.open('rb') as stream:
        stream.seek(first)
        while remaining:
            block=stream.read(min(ARTIFACT_CHUNK_BYTES,remaining))
            if not block:break
            digest.update(block);remaining-=len(block)
    return None if remaining else 'sha256:'+digest.hexdigest()


def validate_qualified_public_network(root,plan,execution,prefix,status,window,defs,errors,cache):
    env=execution.get('environmentCaptured') or {}
    if plan['pocId']!='POC-07' or status!='pass' or env.get('acceptanceProfile')!=profile_identity('production'):return
    errors.append(f"deferred production qualification {plan['pocId']}: production TLS outcome validation is not implemented; PASS unavailable")
    label=f"qualified public network {plan['taskId']}";before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('publicNetworkRef'),defs,'publicNetworkObservations',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-PUBLIC-NETWORK'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:config=load(path).get('configuration',{}) if path else {};policy=config.get('publicNetworkPolicy');access_policy=config.get('accessPolicy')
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None;access_policy=None
    validate_schema(policy,defs.get('publicNetworkPolicy',{}),label+'/approved network',errors);validate_schema(access_policy,defs.get('accessOutcomePolicy',{}),label+'/approved access',errors)
    access=selected_observation(root,execution,prefix,env.get('accessOutcomeRef'),defs,'accessOutcomeReport',label,errors,cache)
    if len(errors)!=before or report is None or access is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],accessOutcomeRef=env.get('accessOutcomeRef'),acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    if any(report[k]!=v for k,v in expected.items()) or access['configurationRef']!=report['configurationRef'] or any(access[k]!=expected[k] for k in ('acceptanceProfile','subjectVersion','inputSamples')):errors.append(f'{label}: exact approved endpoint/access/resource/profile/tool/input observations required')
    try:
        endpoint=urllib.parse.urlsplit(policy['endpointURL']);unintended=urllib.parse.urlsplit(policy['unintendedURL']);bypass=urllib.parse.urlsplit(policy['bypassURL']);source=urllib.parse.urlsplit(access_policy['paths']['source']);high_port=endpoint.port or 443
        new_address=ipaddress.IPv6Address(policy['newAddress']);old_address=ipaddress.IPv6Address(policy['oldAddress']);ipaddress.ip_address(policy['originAddress'])
        if endpoint.scheme!='https' or not endpoint.hostname or endpoint.username is not None or not 1024<high_port<=65535 or policy['endpointURL']!=access_policy['paths']['range'] or policy['ddnsName']!=endpoint.hostname or new_address==old_address or unintended.hostname!=endpoint.hostname or unintended.port is None or unintended.port==high_port or unintended.username is not None or bypass.hostname!=policy['originHost'] or (bypass.port or (443 if bypass.scheme=='https' else 80))!=policy['originPort'] or bypass.username is not None or source.hostname!=policy['originHost'] or (source.port or (443 if source.scheme=='https' else 80))!=policy['originPort']:raise ValueError()
    except (ValueError,TypeError):errors.append(f'{label}: distinct approved IPv6 DDNS addresses and exact HTTPS high-port/proxy origin and denial targets required');return
    changed=utc(policy['ddnsUpdatedAt']);old_dns,new_dns=report['dnsBefore'],report['dnsAfter'];old_at,new_at=utc(old_dns['observedAt']),utc(new_dns['observedAt']);maximum=policy['maximumPropagationSeconds']
    if any(t is None for t in (changed,old_at,new_at)) or window is None or not window[0]<=changed<=new_at<=window[1] or old_at>changed or not ai_finite(maximum) or (new_at-changed).total_seconds()>maximum or old_dns['addresses']!=[policy['oldAddress']] or new_dns['addresses']!=[policy['newAddress']] or any(d['name']!=policy['ddnsName'] or d['resolverBuild']!=policy['resolverBuild'] for d in (old_dns,new_dns)):
        errors.append(f'{label}: measured DDNS update must replace the prior mapping within the approved propagation window');return
    controls=report['controls'];points=policy['testPointIds'];request_ids=set()
    if len(controls)!=len(points) or {r['testPointId'] for r in controls}!=set(points):errors.append(f'{label}: every approved external test point requires a distinct actual TLS/IPv6/routed access probe')
    permitted={r['witnessRef'] for r in access['cases'] if r['case']=='authorized_range'}
    if len(permitted)!=1:errors.append(f'{label}: one validated baseline protected Range request required');return
    baseline_ref=next(iter(permitted));count=len(errors);baseline=selected_observation(root,execution,prefix,baseline_ref,defs,'accessRequestOutcome',label,errors,cache)
    if baseline is None or len(errors)!=count:return
    grant_start,grant_end=utc(access_policy['grantValidFrom']),utc(access_policy['grantValidUntil'])
    if grant_start is None or grant_end is None or grant_start>=grant_end:errors.append(f'{label}: approved live access grant UTC interval required');return
    witness_paths=[];response_paths=[]
    def actual_body(row):
        matches=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==row['responseBodyRef']];payload=existing_ref(root,row['responseBodyRef'],prefix)
        if payload is None or len(matches)!=1 or matches[0].get('artifactType')!='produced_media' or row['responseBodyRef'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: selected actual response bytes required');return None
        try:info=inspect_artifact(payload,cache)
        except OSError:errors.append(f'{label}: response body must be readable');return None
        if info['sha256']!=row['responseSha256'] or info['size']!=row['responseByteCount']:errors.append(f'{label}: response observation must bind retained actual byte count/hash')
        return payload,info
    for row in controls:
        if row['requestId'] in request_ids:errors.append(f'{label}: distinct actual public requests required')
        request_ids.add(row['requestId']);tls=row['tls'];times=[utc(row['connectedAt']),utc(tls['startedAt']),utc(tls['finishedAt']),utc(row['requestStartedAt']),utc(row['requestFinishedAt'])]
        if any(t is None for t in times) or not new_at<=times[0]<=times[1]<=times[2]<=times[3]<=times[4]<=window[1] or row['requestURL']!=policy['endpointURL'] or row['connectedAddress']!=policy['newAddress'] or row['remotePort']!=high_port or any(row[k]!=policy[k] for k in ('routeId','proxyBuild','originHost','originPort')):errors.append(f'{label}: actual IPv6 transport and high-port route must bind the updated intended endpoint/proxy/origin')
        if tls['sni']!=endpoint.hostname or tls['protocol'] not in policy['approvedProtocols'] or tls['cipher'] not in policy['approvedCiphers'] or tls['trustStoreBuild']!=policy['trustStoreBuild'] or tls['certificateSha256']!=policy['certificateSha256'] or tls['chainFingerprints'][0]!=policy['certificateSha256'] or tls['chainFingerprints'][-1]!=policy['trustAnchorSha256'] or tls['chainValidated'] is not True or tls['hostnameValidated'] is not True:errors.append(f'{label}: captured validated TLS chain/SNI/trust store/protocol/cipher must bind the approved certificate and endpoint')
        count=len(errors);witness=selected_observation(root,execution,prefix,row['accessWitnessRef'],defs,'publicNetworkRequest',label,errors,cache)
        if witness is not None and len(errors)==count:
            if witness['baselineAccessWitnessRef']!=baseline_ref or witness['requestId']!=row['requestId'] or witness['testPointId']!=row['testPointId'] or witness['case']!='authorized_range' or any(witness[k]!=access[k] for k in ('configurationRef','pathConfigurationRef','resourceId','acceptanceProfile','subjectVersion','inputSamples','assetId','sourceVersion','aclVersion','inputSampleId')) or witness['requestURL']!=row['requestURL'] or utc(witness['observedAt'])!=times[-1] or witness['statusCode']!=206 or any(witness[k]!=row[k] for k in ('responseBodyRef','responseSha256','responseByteCount')):errors.append(f'{label}: transport and TLS observations must bind the same actual authorized protected Range request/response')
            if witness['userId']!=access_policy['authorizedUserId'] or witness['grantId']!=access_policy['authorizedGrantId'] or times[-1] is None or not grant_start<=times[-1]<grant_end or any(witness[k]!=baseline[k] for k in ('rangeStart','rangeEnd','requestRange','ifRange','etag','contentRange','cacheKey','responseSha256','responseByteCount')) or witness['maximumBufferedBytes']>access_policy['maximumBufferedBytes'] or witness['originRequestCount']>1:
                errors.append(f'{label}: each actual point request must use the approved live subject/grant and exact baseline protected Range bytes/headers')
            witness_path=existing_ref(root,row['accessWitnessRef'],prefix)
            if witness_path is not None:
                if any(witness_path.samefile(peer) for peer in witness_paths):errors.append(f'{label}: each external point must retain a physically distinct actual request witness')
                witness_paths.append(witness_path)
        body=actual_body(row)
        if body is not None:
            body_path,_=body
            if any(body_path.samefile(peer) for peer in response_paths):errors.append(f'{label}: each external point must retain its own actual response bytes')
            response_paths.append(body_path)
    denials=report['denials'];required={(point,case) for point in points for case in ('unintended_listener','direct_bypass','stale_address')}
    if len(denials)!=len(required) or {(r['testPointId'],r['case']) for r in denials}!=required:errors.append(f'{label}: every test point must exercise unintended listener, direct bypass and stale-address denial')
    for row in denials:
        at=utc(row['observedAt']);case=row['case'];target=policy['unintendedURL'] if case=='unintended_listener' else policy['bypassURL'] if case=='direct_bypass' else policy['endpointURL'];address=policy['originAddress'] if case=='direct_bypass' else policy['oldAddress'] if case=='stale_address' else policy['newAddress'];target_port=unintended.port if case=='unintended_listener' else policy['originPort'] if case=='direct_bypass' else high_port
        if row['requestId'] in request_ids or at is None or not window[0]<=at<=window[1] or case=='stale_address' and (at-changed).total_seconds()<=maximum or row['requestURL']!=target or row['connectedAddress']!=address or row['remotePort']!=target_port or row['originRequestCount']!=0 or row['outcome']!=('connection_refused' if row['statusCode']==0 else 'denied'):errors.append(f'{label}: actual disallowed/bypass/stale probes must not route to the protected origin beyond the approved DDNS window')
        request_ids.add(row['requestId']);body=actual_body(row)
        if body is not None:
            path,info=body;safe=info['size']==0
            if not safe and row['statusCode']==403 and info['size']<=1024:
                def fields(pairs):
                    if len({k for k,_ in pairs})!=len(pairs):raise ValueError('duplicate public error fields')
                    return dict(pairs)
                try:
                    with path.open(encoding='utf8') as stream:safe=json.load(stream,object_pairs_hook=fields)=={'error':'access_denied'}
                except (OSError,ValueError,UnicodeError):safe=False
            if not safe:errors.append(f'{label}: denied routing must not disclose protected response bytes')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if any(actual.get(g) is not True for g in ('tls_valid','ipv6_reachability','high_port_route','ddns_propagation')):errors.append(f'{label}: true public network gates require these corresponding observed outcomes')


def validate_qualified_range_matrix(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-03' or status!='pass':return
    label=f"qualified Range matrix {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('rangeMatrixRef'),defs,'rangeMatrixReport',label,errors,cache)
    if report is None or len(errors)!=before:return
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-ATS-SANDBOX'),None)
    if resource is None or report['configurationRef']!=resource.get('configurationRef'):
        errors.append(f'{label}: exact approved ATS sandbox configuration required');return
    path=existing_ref(root,report['configurationRef'],prefix)
    try:policy=load(path).get('configuration',{}).get('rangeMatrixPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    before=len(errors);validate_schema(policy,defs.get('rangeMatrixPolicy',{}),label,errors)
    if policy is None or len(errors)!=before:return
    if policy['baseVersion']==policy['updatedVersion'] or policy['baseETag']==policy['updatedETag'] or len(set(policy['authorizedUsers']))!=len(policy['authorizedUsers']) or policy['deniedUser'] in policy['authorizedUsers'] or any(not math.isfinite(policy[k]) for k in ('slowOriginDelayMs','slowOriginBandwidthBytesPerSecond')):
        errors.append(f'{label}: distinct governed versions/users and finite controlled origin profile required');return
    inputs=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []]
    common=dict(configurationRef=report['configurationRef'],inputSamples=inputs,inputSampleId=report['inputSampleId'],subjectVersion=compliance_subject_version(plan,execution),acceptanceProfile=env.get('acceptanceProfile'),assetId=policy['assetId'],aclVersion=policy['aclVersion'])
    if any(report.get(k)!=v for k,v in common.items()):errors.append(f'{label}: exact approved input/tool/profile/asset/ACL binding required')
    rows=env.get('inputSampleArtifacts') or [];rows=rows if isinstance(rows,list) else []
    selected=[r for r in rows if isinstance(r,dict) and r.get('sampleId')==report['inputSampleId']]
    sample=next((s for s in execution.get('samples') or [] if s.get('id')==report['inputSampleId']),None)
    source=existing_ref(root,selected[0].get('inputArtifactRef'),prefix) if len(selected)==1 else None
    updated=existing_ref(root,policy['updatedInputRef'],prefix)
    if sample is None or source is None or updated is None or selected[0].get('immutableId')!=sample.get('immutableId') or inspect_artifact(source,cache)['sha256']!=sample.get('checksum') or inspect_artifact(updated,cache)['sha256']!=policy['updatedInputSha256'] or policy['updatedInputSha256']==sample.get('checksum'):
        errors.append(f'{label}: actual immutable base and independently approved changed source bytes required');return
    sources={policy['baseVersion']:source,policy['updatedVersion']:updated};sizes={version:inspect_artifact(file,cache)['size'] for version,file in sources.items()};hashes={version:inspect_artifact(file,cache)['sha256'] for version,file in sources.items()}
    if policy['minimumInputBytes']<=max(policy['sliceBytes'],policy['maximumBufferedBytes']) or any(size<max(16,policy['minimumInputBytes']) for size in sizes.values()):
        errors.append(f'{label}: actual base/changed inputs must meet the independently approved representative minimum beyond one Slice and the buffering bound');return
    artifacts={a.get('ref'):a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and isinstance(a.get('ref'),str)};retained_paths=[source,updated]
    def retained(ref):
        file=existing_ref(root,ref,prefix)
        if file is None or ref not in (execution.get('rawOutputRefs') or []) or artifacts.get(ref,{}).get('artifactType')!='produced_media':
            errors.append(f'{label}: actual selected-slot response/cache bytes required');return None
        return file
    before=len(errors);update=selected_observation(root,execution,prefix,report['sourceUpdateRef'],defs,'rangeSourceUpdate',label,errors,cache)
    lifecycle=selected_observation(root,execution,prefix,report['cacheLifecycleRef'],defs,'rangeCacheLifecycle',label,errors,cache)
    if len(errors)!=before or update is None or lifecycle is None:return
    for observation in (update,lifecycle):
        if any(observation.get(k)!=v for k,v in common.items()):errors.append(f'{label}: source/cache journal must bind exact configured subjects')
    changed=utc(update['observedAt'])
    if changed is None or window is None or not window[0]<=changed<=window[1] or update['baseVersion']!=policy['baseVersion'] or update['updatedVersion']!=policy['updatedVersion'] or update['baseSha256']!=hashes[policy['baseVersion']] or update['updatedSha256']!=hashes[policy['updatedVersion']]:
        errors.append(f'{label}: source update needs exact versions, actual byte hashes and UTC event');return
    cases=report['cases']
    if len(cases)!=len(RANGE_MATRIX_CASES) or {r['case'] for r in cases}!=RANGE_MATRIX_CASES:
        errors.append(f'{label}: complete unique approved Range/cache/recovery/latency case matrix required');return
    valid={};latencies={};version_cache_users={};recovery_times={};range_results=[];request_ids=set()
    for row in cases:
        name=row['case'];before=len(errors);observation=selected_observation(root,execution,prefix,row['witnessRef'],defs,'rangeRequestObservation',label,errors,cache)
        if observation is None or len(errors)!=before:continue
        if observation['case']!=name or any(observation.get(k)!=v for k,v in common.items()):errors.append(f'{label}: typed request must bind exact case/input/tool/configuration/ACL')
        requests=observation['requests'];expected_count=policy['latencySampleCount'] if name.startswith('latency_') else 1
        if len(requests)!=expected_count:errors.append(f'{label}: exact approved latency/request sample count required')
        version=policy['updatedVersion'] if name=='updated' else policy['baseVersion'];file=sources[version];size=sizes[version];etag=policy['updatedETag'] if name=='updated' else policy['baseETag'];times=[];users=set();load_intervals=[]
        for request in requests:
            began,first_byte,finished=(utc(request[k]) for k in ('startedAt','firstByteAt','finishedAt'));body=retained(request['responseBodyRef'])
            if began is None or first_byte is None or finished is None or not window[0]<=began<=first_byte<=finished<=window[1] or body is None:
                errors.append(f'{label}: valid UTC request/first-byte/completion and actual returned bytes required');continue
            if (began<changed if name=='updated' else finished>changed):errors.append(f'{label}: requests must bind the observed source version before/after update')
            if request['sourceVersion']!=version or request['sourceSha256']!=hashes[version] or request['requestURL']!=policy['entryURL'] or request['aclVersion']!=policy['aclVersion']:
                errors.append(f'{label}: current source/version/ACL and approved path required')
            if request['requestId'] in request_ids:errors.append(f'{label}: each retained request needs a unique request identity')
            request_ids.add(request['requestId'])
            origin_before=len(errors);origin=selected_observation(root,execution,prefix,request['originAccessRef'],defs,'rangeOriginAccessObservation',label,errors,cache)
            if origin is None or len(errors)!=origin_before:continue
            binding=dict(configurationRef=report['configurationRef'],case=name,assetId=policy['assetId'],aclVersion=policy['aclVersion'],**{key:request[key] for key in ('requestId','userId','requestURL','requestRange','ifRange','sourceVersion','sourceSha256','startedAt','finishedAt')})
            if any(origin.get(key)!=value for key,value in binding.items()):errors.append(f'{label}: origin/object-read counts must bind this exact request, source, authorization and observation interval')
            users.add(request['userId']);actual=inspect_artifact(body,cache)
            load_intervals.append((request['userId'],began,finished))
            if actual['sha256']!=request['responseSha256'] or actual['size']!=request['responseByteCount']:errors.append(f'{label}: returned-byte count/hash must match actual artifact')
            if any(body.samefile(peer) for peer in retained_paths):errors.append(f'{label}: response bodies must be physically distinct from sources and other requests')
            retained_paths.append(body)
            expected_range='bytes=0-7'
            if name=='range_middle':expected_range='bytes=8-15'
            elif name=='range_end':expected_range=f'bytes={size-8}-{size-1}'
            elif name=='suffix':expected_range='bytes=-8'
            elif name=='unsatisfiable':expected_range=f'bytes={size}-{size+7}'
            elif name=='stream':expected_range=''
            if request['requestRange']!=expected_range or request['ifRange']!=(etag if name=='if_match' else '"stale-version"' if name=='if_stale' else ''):errors.append(f'{label}: exact deterministic Range/If-Range request required')
            if name=='denied_user':
                if request['userId']!=policy['deniedUser'] or request['statusCode'] not in (401,403) or actual['size']!=0 or request['cacheComplete'] or request['cacheVisible']:errors.append(f'{label}: denied cache context must expose no protected payload')
                if origin['originRequestCount']!=0 or origin['objectReadCount']!=0:errors.append(f'{label}: denied requests must precede all origin access and protected object reads')
            elif name=='partial_read':
                if request['statusCode']!=503 or actual['size']!=0 or request['cacheComplete'] or request['cacheVisible'] or request['transferCompleted']:errors.append(f'{label}: interrupted partial cache must not be published/read as complete')
            else:
                if request['userId'] not in policy['authorizedUsers']:errors.append(f'{label}: valid approved authorization context required')
                if name=='other_user' and request['userId']==policy['authorizedUsers'][0]:errors.append(f'{label}: other-user cache case must exercise a distinct approved authorization context')
                first,last=(0,size-1) if name in ('stream','if_stale') else (8,15) if name=='range_middle' else (size-8,size-1) if name in ('range_end','suffix') else (0,7)
                status_code=416 if name=='unsatisfiable' else 200 if name in ('stream','if_stale') else 206
                content_range=f'bytes */{size}' if name=='unsatisfiable' else '' if status_code==200 else f'bytes {first}-{last}/{size}'
                if request['statusCode']!=status_code or request['etag']!=etag or request['contentRange']!=content_range:errors.append(f'{label}: actual status/ETag/Content-Range must implement partial/full/unsatisfiable semantics')
                if name=='unsatisfiable':
                    if actual['size']:errors.append(f'{label}: unsatisfiable request must not return protected bytes')
                elif name=='interrupted':
                    if not 0<actual['size']<last-first+1 or request['transferCompleted'] or request['cacheComplete'] or request['cacheVisible'] or actual['sha256']!=range_slice_hash(file,first,actual['size']):errors.append(f'{label}: interrupted bytes must remain a correct unpublished partial prefix')
                elif actual['size']!=last-first+1 or actual['sha256']!=range_slice_hash(file,first,last-first+1) or not request['transferCompleted'] or not request['cacheComplete'] or not request['cacheVisible']:
                    errors.append(f'{label}: response must equal the exact current source interval with complete transfer')
                if request['maximumBufferedBytes']>policy['maximumBufferedBytes'] or request['retryCount']>policy['maximumRetries']:errors.append(f'{label}: approved memory/retry bounds exceeded')
                if name in ('stream','if_stale') and not 0<request['maximumBufferedBytes']<size:errors.append(f'{label}: full streaming must observe positive bounded buffering below the source size')
            expected_cache={'miss':'MISS','fill':'FILL','hit':'HIT','updated':'INVALIDATED','interrupted':'PARTIAL','partial_read':'PARTIAL','recovered':'FILL','latency_hot':'HIT','latency_cold':'MISS','latency_slow':'MISS','latency_multi':'HIT'}.get(name)
            if expected_cache and request['cacheStatus']!=expected_cache:errors.append(f'{label}: retained cache status must distinguish miss/fill/hit/invalidation/partial recovery')
            if name=='latency_cold' and not request['cachePurged']:errors.append(f'{label}: cold measurement requires observed sandbox purge')
            if name=='latency_slow' and (request['originDelayMs']!=policy['slowOriginDelayMs'] or request['originBandwidthBytesPerSecond']!=policy['slowOriginBandwidthBytesPerSecond']):errors.append(f'{label}: slow-origin request must bind the approved controlled delay/bandwidth')
            if name=='latency_multi' and request['concurrentUsers']!=policy['concurrentUsers']:errors.append(f'{label}: multi-user measurement must bind approved concurrency')
            key=(version,request['userId']);previous=version_cache_users.get(key)
            if previous is not None and previous!=request['cacheKey'] or any(peer_version==version and peer_user!=request['userId'] and peer_key==request['cacheKey'] for (peer_version,peer_user),peer_key in version_cache_users.items()):errors.append(f'{label}: each version needs stable distinct cache keys for every authorization context')
            version_cache_users[key]=request['cacheKey']
            times.append((first_byte-began).total_seconds()*1000)
            if name in ('interrupted','partial_read','recovered'):recovery_times[name]=began
        if name=='latency_multi':
            instants={instant for _,start,end in load_intervals for instant in (start,end)}
            peak=max((len({user for user,start,end in load_intervals if start<=instant<end}) for instant in instants),default=0)
            if len(users)<2 or not users.issubset(set(policy['authorizedUsers'])) or peak<policy['concurrentUsers']:errors.append(f'{label}: multi-user latency requires overlapping requests at approved distinct-user concurrency')
        if name.startswith('latency_') and times:
            latencies[name]=sum(times)/len(times) if policy['percentileMethod']=='mean' else sorted(times)[max(0,math.ceil(.95*len(times))-1)]
        valid[name]=len(errors)==before
        if name in ('range_start','range_middle','range_end','suffix','unsatisfiable','if_match','if_stale'):range_results.append(valid[name])
    for version in sources:
        contexts={user:key for (observed_version,user),key in version_cache_users.items() if observed_version==version}
        if version==policy['baseVersion'] and not set(policy['authorizedUsers']+[policy['deniedUser']]).issubset(contexts) or len(set(contexts.values()))!=len(contexts):errors.append(f'{label}: each version needs covered distinct ACL cache identities')
    if set(recovery_times)!={'interrupted','partial_read','recovered'} or not recovery_times.get('interrupted',changed)<recovery_times.get('partial_read',changed)<recovery_times.get('recovered',changed):errors.append(f'{label}: interruption, unpublished read and bounded recovery must be ordered')
    # Slice files are actual returned fragments; their union must cover the immutable source exactly.
    cursor=0
    for segment in report['slices']:
        body=retained(segment['artifactRef']);count=segment['end']-segment['start']+1
        if body is None or segment['start']!=cursor or not 0<count<=policy['sliceBytes'] or count!=min(policy['sliceBytes'],sizes[policy['baseVersion']]-cursor) or inspect_artifact(body,cache)['size']!=count or inspect_artifact(body,cache)['sha256']!=segment['sha256'] or segment['sha256']!=range_slice_hash(source,cursor,count):errors.append(f'{label}: actual ATS Slice fragments must be contiguous and byte-correct at approved boundaries')
        cursor=segment['end']+1
    if cursor!=sizes[policy['baseVersion']]:errors.append(f'{label}: Slice reassembly must cover the whole immutable source')
    stages=lifecycle['stages'];expected_stages=['before','filled','interrupted','recovered','updated','cleanup'];stage_times=[]
    if [s['stage'] for s in stages]!=expected_stages:errors.append(f'{label}: exact cache allocation/partial/recovery/update/cleanup lifecycle required')
    for stage in stages:
        at=utc(stage['observedAt']);stage_times.append(at);total=0;objects=stage['objects'];stage_name=stage['stage'];stage_paths=[]
        if at is None or not window[0]<=at<=window[1]:errors.append(f'{label}: valid UTC cache lifecycle observation required')
        elif stage_name=='updated' and at<changed or stage_name in ('before','filled','interrupted','recovered') and at>changed:errors.append(f'{label}: cache lifecycle must bind version transition at the observed update')
        if stage_name in ('before','cleanup') and objects:errors.append(f'{label}: cache baseline/cleanup must have no retained test objects')
        if stage_name in ('filled','recovered','updated') and not objects:errors.append(f'{label}: actual completed cache objects required')
        for item in objects:
            body=retained(item['artifactRef']);version=policy['updatedVersion'] if stage_name=='updated' else policy['baseVersion']
            if body is None:continue
            if any(body.samefile(peer) for peer in stage_paths):
                errors.append(f'{label}: a cache stage must not count duplicate references or physical aliases');continue
            stage_paths.append(body)
            if any(body.samefile(file) for file in sources.values()):errors.append(f'{label}: cache snapshots must be physically distinct from immutable source files')
            info=inspect_artifact(body,cache);total+=info['size']
            if item['sourceVersion']!=version or item['sha256']!=info['sha256'] or item['byteCount']!=info['size']:errors.append(f'{label}: cache object identity/count/hash must bind actual retained bytes')
            if stage_name=='interrupted':
                if item['complete'] or item['visible'] or not 0<info['size']<sizes[version] or info['sha256']!=range_slice_hash(sources[version],0,info['size']):errors.append(f'{label}: interrupted cache content must remain quarantined partial bytes')
            elif not item['complete'] or not item['visible'] or info['sha256']!=hashes[version]:errors.append(f'{label}: complete cache object must equal the actual current source version')
        if total!=stage['allocatedBytes']:errors.append(f'{label}: observed cache allocation must derive actual retained object byte counts')
    if any(t is None for t in stage_times) or any(a>b for a,b in zip(stage_times,stage_times[1:])):errors.append(f'{label}: cache lifecycle must be ordered')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    correctness=100*sum(range_results)/len(range_results) if range_results else 0
    if actual.get('range_correctness')!=correctness:errors.append(f'{label}: Range correctness must derive actual compared request cases')
    for metric,scenario in (('range_hot_cache_latency','latency_hot'),('range_cold_cache_latency','latency_cold'),('range_slow_origin_latency','latency_slow'),('range_multi_user_latency','latency_multi')):
        claimed=actual.get(metric);observed=latencies.get(scenario)
        if observed is None or isinstance(claimed,bool) or not isinstance(claimed,(int,float)) or not math.isfinite(claimed) or not math.isclose(claimed,observed,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive approved percentile/method and retained request timestamps')
    gates={m['id'] for m in plan['protocol']['measurements'] if m['unit']=='boolean'}
    if any(actual.get(gate) is not True for gate in gates) or not all(valid.values()):errors.append(f'{label}: true cache/Range gates require complete observed successful cases')



AI_EVALUATED_METRICS={'quality_score','asr_wer','asr_cer','speaker_der','translation_comet','translation_bleu','ocr_accuracy','factual_consistency','tag_f1','thumbnail_human_selection_rate','multimodal_correction_accuracy'}
AI_POLICY_GATES={'permission_denied':'caller_permission_gate','acl_revoked':'asset_acl_gate','budget_exhausted':'hard_budget_gate','request_rate_exceeded':'request_quota_gate','concurrency_exceeded':'concurrency_quota_gate'}


def ai_finite(value):
    try:return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
    except OverflowError:return False


FRONTEND_SCENARIO_ACTIONS={
    'million_row_virtual_list_equivalent':('scroll_begin','scroll_middle','scroll_end','select_row'),
    'dynamic_form_equivalent':('conditional_fields','validation','schema_update'),
    'flowchart_equivalent':('nodes','edges','edit','state_sync'),
    'decision_table_equivalent':('edit_rules','validate_rules'),
    'monitoring_view_equivalent':('metrics','filter','refresh','failure_state'),
    'sse_websocket_equivalent':('sse_update','websocket_update','reconnect','error_state'),
    'player_integration_equivalent':('embed_player','web_component_contract','player_events'),
    'mobile_experience_equivalent':('responsive_breakpoints','touch_interaction'),
    'permission_model_equivalent':('route_visibility','field_visibility','action_visibility','server_authorization'),
    'design_token_equivalent':('apply_tokens','switch_theme')}


def validate_qualified_frontend_comparison(root,plan,execution,prefix,status,window,defs,errors,cache):
    import os
    if plan['pocId']!='POC-08' or status!='pass':return
    label=f"qualified frontend comparison {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('frontendComparisonRef'),defs,'frontendComparisonReport',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-FRONTEND-COMPARE'),None);path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('frontendComparisonPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('frontendComparisonPolicy',{}),label+'/approved matrix',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []]);sample=next((s for s in execution.get('samples') or [] if s.get('id')==policy['inputSampleId']),None);inputs=env.get('inputSampleArtifacts') or [];input_record=next((r for r in inputs if isinstance(r,dict) and r.get('sampleId')==policy['inputSampleId']),None)
    if any(report[k]!=v for k,v in expected.items()) or sample is None or input_record is None or report['inputFixtureRef']!=input_record.get('inputArtifactRef') or report['inputFixtureSha256']!=sample['checksum']:
        errors.append(f'{label}: exact independently approved input/resource/profile/tool and immutable fixed matrix required');return
    input_path=existing_ref(root,report['inputFixtureRef'],prefix);before=len(errors);fixture=qualified_observation_report(input_path,defs,'frontendScenarioFixture',label,errors,cache) if input_path else None
    if fixture is None or len(errors)!=before:return
    scenarios=fixture['scenarios'];required=set(FRONTEND_SCENARIO_ACTIONS)
    if len(scenarios)!=10 or {r['scenarioId'] for r in scenarios}!=required or any(set(r['expectedResults'])!=set(FRONTEND_SCENARIO_ACTIONS[r['scenarioId']]) for r in scenarios):errors.append(f'{label}: exact frozen ten-scenario identity and interaction matrix required');return
    matrix={r['scenarioId']:r for r in scenarios};million=matrix['million_row_virtual_list_equivalent']
    arguments=million['arguments'];row_count=arguments.get('rowCount');viewport=arguments.get('viewportRows');overscan=arguments.get('overscanRows')
    if type(row_count) is not int or row_count!=1000000 or type(viewport) is not int or viewport<=0 or type(overscan) is not int or overscan<0 or viewport+2*overscan>=row_count:
        errors.append(f'{label}: virtualization requires approved million-row input and a bounded integer viewport/overscan window');return
    dom_bound=viewport+2*overscan
    identities=policy['candidates'];rows=report['candidates'];criteria=policy['criteria'];criterion_ids={'ecosystem_team_fit','component_reuse','long_term_maintenance'}
    if len(identities)!=2 or {r['candidateId'] for r in identities}!={'vue','react'} or len(rows)!=2 or {r['candidateId'] for r in rows}!={'vue','react'} or len(criteria)!=3 or {r['criterionId'] for r in criteria}!=criterion_ids or any(not ai_finite(r['weight']) or r['weight']<=0 for r in criteria) or any(not ai_finite(v) for v in policy['gradeValues']):errors.append(f'{label}: both locked candidates and exact fixed weighted maintainability rubric required');return
    total_weight=sum(r['weight'] for r in criteria)
    if not ai_finite(total_weight) or total_weight<=0:errors.append(f'{label}: finite approved rubric weight sum required');return
    weights={r['criterionId']:r['weight'] for r in criteria};identities={r['candidateId']:r for r in identities};coverage=0;bundle_sizes={};scores={};observed={};artifact_paths=[];build_ids=set()
    def interval(first,last):
        start,end=utc(first),utc(last)
        if start is None or end is None or window is None or not window[0]<=start<=end<=window[1]:errors.append(f'{label}: observed build/action/assessment times must be ordered inside execution');return None
        return start,end
    def distinct(path):
        if path is not None:
            if any(path.samefile(peer) for peer in artifact_paths):errors.append(f'{label}: each build, output, scenario and score needs physically distinct retained artifacts')
            artifact_paths.append(path)
    for row in rows:
        candidate=row['candidateId'];identity=identities[candidate];before=len(errors);build=selected_observation(root,execution,prefix,row['buildRef'],defs,'frontendBuildObservation',label,errors,cache)
        if build is None or len(errors)!=before:continue
        distinct(existing_ref(root,row['buildRef'],prefix));build_window=interval(build['startedAt'],build['finishedAt']);build_id=build['buildId']
        if build['identity']!=identity or build_id in build_ids or build['exitCode']!=0:errors.append(f'{label}: successful builds must bind distinct runs and exact approved framework/source/compiler/command/lock identities')
        build_ids.add(build_id);lock=existing_ref(root,identity['lockRef'],prefix)
        if lock is None or inspect_artifact(lock,cache,textual=True)['sha256']!=identity['lockSha256']:errors.append(f'{label}: actual retained dependency lock bytes must match the approved locked candidate')
        before=len(errors);manifest=selected_observation(root,execution,prefix,build['compilerManifestRef'],defs,'frontendCompilerManifest',label,errors,cache)
        if manifest is None or len(errors)!=before:continue
        manifest_path=existing_ref(root,build['compilerManifestRef'],prefix);distinct(manifest_path)
        manifest_at=utc(manifest['observedAt']);output_ref=identity['outputDirectory']
        if manifest['identity']!=identity or manifest['buildId']!=build_id or manifest_at is None or build_window is None or not build_window[1]<=manifest_at<=window[1] or inspect_artifact(manifest_path,cache,textual=True)['sha256']!=build['compilerManifestSha256']:
            errors.append(f'{label}: complete compiler manifest must bind the same approved identity, build, output directory, completion time and retained bytes');continue
        try:
            if not lexical_ref(output_ref,prefix):raise ValueError('output directory outside selected slot')
            directory=root/output_ref;component=root
            for part in output_ref.split('/'):
                component=component/part
                if component.is_symlink():raise ValueError('linked output directory')
            if not directory.is_dir() or not directory.resolve().is_relative_to((root/prefix).resolve()) or manifest_path.resolve().is_relative_to(directory.resolve()):raise ValueError('controlled directory and external manifest required')
            emitted_paths=set();pending=[directory];visited=0
            while pending:
                with os.scandir(pending.pop()) as entries:
                    for entry in entries:
                        visited+=1
                        if visited>4096 or entry.is_symlink():raise ValueError('bounded regular emitted files required')
                        path=Path(entry.path)
                        if entry.is_dir(follow_symlinks=False):pending.append(path)
                        elif entry.is_file(follow_symlinks=False):emitted_paths.add(path.relative_to(directory).as_posix())
                        else:raise ValueError('special emitted file')
        except (OSError,ValueError):
            errors.append(f'{label}: complete retained output directory must be selected-slot, bounded, regular and free of symlinks');continue
        files=manifest['emittedFiles'];paths=[blob['path'] for blob in files];refs=[blob['ref'] for blob in files]
        if len(set(paths))!=len(files) or len(set(refs))!=len(files) or set(paths)!=emitted_paths or any(blob['ref']!=output_ref+'/'+blob['path'] or not lexical_ref(blob['ref'],prefix) for blob in files):
            errors.append(f'{label}: complete compiler manifest must match every actual emitted file exactly once');continue
        manifest_bundles=[{k:blob[k] for k in ('ref','sha256','byteCount')} for blob in files]
        key=lambda blob:(blob['ref'],blob['sha256'],blob['byteCount'])
        if sorted(map(key,build['bundles']))!=sorted(map(key,manifest_bundles)):
            errors.append(f'{label}: bundles must be the exact complete compiler-emitted file set');continue
        size=0;binary_scan_cache={}
        for blob in files:
            payload=existing_ref(root,blob['ref'],prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==blob['ref']]
            if payload is None or len(records)!=1 or records[0].get('artifactType') not in ('command_output','produced_media') or blob['ref'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: actual retained build bundle output required');continue
            binary=records[0]['artifactType']=='produced_media'
            distinct(payload);info=inspect_artifact(payload,binary_scan_cache if binary else cache,textual=True);size+=info['size']
            if info['credential'] or info['invalidUtf8']!=binary:errors.append(f'{label}: emitted text must retain strict UTF8/secret checks and only actual binary assets may use produced_media')
            if info['size']==0 or info['size']!=blob['byteCount'] or info['sha256']!=blob['sha256']:errors.append(f'{label}: bundle byte count/hash must bind nonempty actual controlled build output')
        bundle_sizes[candidate]=size/1024;case_rows=row['scenarios']
        if len(case_rows)!=10 or {c['scenarioId'] for c in case_rows}!=required:errors.append(f'{label}: every candidate must actually exercise each frozen scenario once');continue
        trace_refs=[];observed[candidate]={};trace_finished=[]
        for case in case_rows:
            scenario_id=case['scenarioId'];expected_case=matrix[scenario_id];before=len(errors);trace=selected_observation(root,execution,prefix,case['observationRef'],defs,'frontendScenarioObservation',label,errors,cache)
            if trace is None or len(errors)!=before:continue
            distinct(existing_ref(root,case['observationRef'],prefix));trace_refs.append(case['observationRef']);trace_window=interval(trace['startedAt'],trace['finishedAt']);actions=trace['actions'];action_ids=FRONTEND_SCENARIO_ACTIONS[scenario_id]
            valid=trace['candidateId']==candidate and trace['buildId']==build_id and trace['scenarioId']==scenario_id and trace['fixtureId']==expected_case['fixtureId'] and trace['inputSha256']==sample['checksum'] and trace['scenarioDriverBuild']==policy['scenarioDriverBuild'] and trace['status']=='completed' and len(actions)==len(action_ids) and tuple(a['actionId'] for a in actions)==action_ids
            if trace_window is None or build_window is None or trace_window[0]<build_window[1]:valid=False
            last=None;results={}
            for action in actions:
                action_window=interval(action['startedAt'],action['finishedAt'])
                if action_window is None or trace_window is None or not trace_window[0]<=action_window[0]<=action_window[1]<=trace_window[1] or last is not None and action_window[0]<last:valid=False
                if action_window is not None:last=action_window[1]
                results[action['actionId']]=action['result']
            if results!=expected_case['expectedResults']:valid=False
            measurements=trace['measurements'];duration=(trace_window[1]-trace_window[0]).total_seconds()*1000 if trace_window else None
            measurement_map={m['measurementId']:m for m in measurements};required_measurements={'interaction_duration'}
            if scenario_id=='million_row_virtual_list_equivalent':required_measurements|={'measured_input_rows','rendered_dom_rows_peak'}
            if len(measurements)!=len(required_measurements) or set(measurement_map)!=required_measurements:valid=False
            duration_measurement=measurement_map.get('interaction_duration',{})
            if duration_measurement.get('unit')!='ms' or not ai_finite(duration_measurement.get('value')) or duration is None or not math.isclose(duration_measurement['value'],duration,rel_tol=1e-9,abs_tol=1e-9):valid=False
            if scenario_id=='million_row_virtual_list_equivalent':
                input_count=measurement_map.get('measured_input_rows',{});dom_count=measurement_map.get('rendered_dom_rows_peak',{})
                if input_count.get('unit')!='rows' or type(input_count.get('value')) is not int or input_count['value']!=row_count or dom_count.get('unit')!='rows' or type(dom_count.get('value')) is not int or not 0<dom_count['value']<=dom_bound:valid=False
            if not valid:errors.append(f'{label}: scenario outcome must bind its actual locked build/approved fixture/actions/result values and reproducible measurements')
            else:coverage+=1;observed[candidate][scenario_id]=results
            if trace_window:trace_finished.append(trace_window[1])
        score_rows=row['scores']
        if len(score_rows)!=3 or {r['criterionId'] for r in score_rows}!=criterion_ids:errors.append(f'{label}: exact rubric criterion rows for both actual builds required');continue
        weighted=0;scored=0
        for score_row in score_rows:
            before=len(errors);score=selected_observation(root,execution,prefix,score_row['observationRef'],defs,'frontendRubricObservation',label,errors,cache)
            if score is None or len(errors)!=before:continue
            distinct(existing_ref(root,score_row['observationRef'],prefix));at=utc(score['observedAt'])
            if score['candidateId']!=candidate or score['buildId']!=build_id or score['criterionId']!=score_row['criterionId'] or any(score[k]!=policy[k] for k in ('rubricId','rubricVersion','assessorId')) or not recorded_text(score['basis']) or not ai_finite(score['grade']) or score['grade'] not in policy['gradeValues'] or len(score['scenarioRefs'])!=10 or set(score['scenarioRefs'])!=set(trace_refs) or at is None or window is None or not window[0]<=at<=window[1] or len(trace_finished)!=10 or any(at<end for end in trace_finished):errors.append(f'{label}: actual rubric grade/basis must bind approved assessor/version/criterion and completed build scenario evidence');continue
            weighted+=weights[score['criterionId']]*score['grade'];scored+=1
        if scored==3:scores[candidate]=weighted/total_weight
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)};derived=dict(prototype_coverage=coverage*100/20,bundle_baseline=bundle_sizes.get(policy['bundleCandidate']),maintainability_score=scores.get(policy['scoreCandidate']))
    for metric,value in derived.items():
        if not ai_finite(value) or not ai_finite(actual.get(metric)) or not math.isclose(actual[metric],value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive actual both-candidate scenario coverage, selected locked bundle bytes or fixed rubric rows')
    for gate in required:
        equivalent=gate in observed.get('vue',{}) and gate in observed.get('react',{}) and observed['vue'][gate]==observed['react'][gate]
        if equivalent is not True or actual.get(gate) is not equivalent:errors.append(f'{label}: {gate} must derive matching successful outcomes from both frozen candidate scenarios')


def validate_qualified_ai_results(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-09' or status!='pass':return
    label=f"qualified AI results {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('aiResultsRef'),defs,'aiResultsReport',label,errors,cache)
    if report is None or len(errors)!=before:return
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-AI-BENCH'),None)
    if resource is None or report['configurationRef']!=resource.get('configurationRef'):
        errors.append(f'{label}: exact approved AI benchmark configuration required');return
    path=existing_ref(root,report['configurationRef'],prefix)
    try:policy=load(path).get('configuration',{}).get('aiEvaluationPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    before=len(errors);validate_schema(policy,defs.get('aiEvaluationPolicy',{}),label,errors)
    if policy is None or len(errors)!=before:return
    expected=dict(configurationRef=report['configurationRef'],subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []],acceptanceProfile=env.get('acceptanceProfile'),benchmarkId=policy['benchmarkId'],querySetId=policy['querySetId'],corpusId=policy['corpusId'])
    if policy['subjectVersion']!=expected['subjectVersion']:errors.append(f'{label}: approved configuration must pin the complete evaluated model/prompt/parameter/runtime/tool subject')
    if any(report.get(k)!=v for k,v in expected.items()):errors.append(f'{label}: exact approved benchmark/query/corpus/input/model/prompt/parameters/runtime/tool identities required')
    before=len(errors);evaluation=selected_observation(root,execution,prefix,report['evaluationRef'],defs,'aiEvaluationResults',label,errors,cache);usage=selected_observation(root,execution,prefix,report['usageRef'],defs,'aiUsageObservation',label,errors,cache);dispatch=selected_observation(root,execution,prefix,report['dispatchRef'],defs,'aiDispatchOutcomes',label,errors,cache)
    if len(errors)!=before or any(r is None for r in (evaluation,usage,dispatch)):return
    for observation in (evaluation,usage,dispatch):
        if any(observation.get(k)!=v for k,v in expected.items()):errors.append(f'{label}: every result/usage/dispatch observation must bind exact approved subjects')
    artifacts={a.get('ref'):a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and isinstance(a.get('ref'),str)}
    def payload(ref,sha,allow_empty=False):
        file=existing_ref(root,ref,prefix)
        if file is None or ref not in (execution.get('rawOutputRefs') or []) or artifacts.get(ref,{}).get('artifactType')!='produced_media':
            errors.append(f'{label}: actual selected-slot retained output/dispatch bytes required');return None
        info=inspect_artifact(file,cache)
        if info['sha256']!=sha or not allow_empty and info['size']==0:errors.append(f'{label}: retained output hash must bind actual nonempty bytes')
        return info
    items={i['itemId']:i for i in policy['items']};strata={s['stratumId']:s for s in policy['strata']};methods={m['metricId']:m for m in policy['evaluationMethods']};samples={s['id']:s for s in execution.get('samples') or []}
    if len(items)!=len(policy['items']) or len(strata)!=len(policy['strata']) or set(methods)!=AI_EVALUATED_METRICS or len(methods)!=len(policy['evaluationMethods']) or any(i['sampleId'] not in samples or i['stratumId'] not in strata for i in items.values()):
        errors.append(f'{label}: unique approved benchmark items/strata and exact evaluation metric methods required');return
    modes={metric:('f1' if metric=='tag_f1' else 'tool_score' if metric in ('translation_comet','translation_bleu') else 'human_score' if metric=='quality_score' else 'count_ratio') for metric in AI_EVALUATED_METRICS}
    if any(methods[metric]['mode']!=mode for metric,mode in modes.items()):errors.append(f'{label}: retained evaluation methods must implement the frozen metric semantics');return
    pricing=policy['pricing'];gates=policy['gatePolicy'];numeric=(pricing['inputUnitPrice'],pricing['outputUnitPrice'],gates['budgetLimit'])
    if any(not ai_finite(v) or v<0 for v in numeric) or gates['authorizedCallerId']==gates['unauthorizedCallerId'] or gates['currentAclVersion']==gates['revokedAclVersion']:
        errors.append(f'{label}: finite approved pricing/budget and distinct permission/ACL subjects required');return
    records=usage['items'];outputs={};paths=[];cost=0;usage_times=[]
    for item in records:
        identity=items.get(item['itemId']);start,end=utc(item['startedAt']),utc(item['finishedAt'])
        if not all(ai_finite(item[k]) for k in ('inputTokens','outputTokens')):errors.append(f'{label}: finite measured token usage required');continue
        if identity is None or item['itemId'] in outputs or item['sampleId']!=identity['sampleId'] or item['stratumId']!=identity['stratumId'] or item['inputSha256']!=samples[item['sampleId']]['checksum']:
            errors.append(f'{label}: measured usage must cover each exact approved immutable benchmark item once');continue
        if start is None or end is None or window is None or not window[0]<=start<end<=window[1]:errors.append(f'{label}: valid UTC completed-item usage interval required')
        else:usage_times.append((start,end))
        payload(item['outputRef'],item['outputSha256']);file=existing_ref(root,item['outputRef'],prefix)
        if file and any(file.samefile(peer) for peer in paths):errors.append(f'{label}: completed items require distinct retained result artifacts')
        if file:paths.append(file)
        outputs[item['itemId']]=item;cost+=item['inputTokens']*pricing['inputUnitPrice']+item['outputTokens']*pricing['outputUnitPrice']
    if set(outputs)!=set(items):errors.append(f'{label}: exact completed benchmark-item output/usage coverage required')
    before=len(errors);inference=selected_observation(root,execution,prefix,env.get('inferenceObservationRef'),defs,'inferenceObservation',label,errors,cache)
    if inference is None or len(errors)!=before:return
    if inference['completedItemCount']!=len(outputs) or usage['pricingVersion']!=pricing['version'] or usage['currency']!=pricing['currency'] or not usage_times or min(t[0] for t in usage_times)!=utc(inference['observedStartedAt']) or max(t[1] for t in usage_times)!=utc(inference['observedFinishedAt']):errors.append(f'{label}: throughput count/window and pricing must bind measured completed items')
    scores={metric:[] for metric in AI_EVALUATED_METRICS};coverage={};seen=set()
    for row in evaluation['evaluations']:
        metric=row['metricId'];item=outputs.get(row['itemId']);method=methods[metric];at=utc(row['observedAt']);key=(row['itemId'],metric)
        if key in seen or item is None or row['sampleId']!=item['sampleId'] or row['stratumId']!=item['stratumId'] or row['outputRef']!=item['outputRef'] or row['outputSha256']!=item['outputSha256'] or row['methodId']!=method['methodId'] or row['evaluatorBuild']!=method['evaluatorBuild'] or row['rubricVersion']!=method['rubricVersion']:
            errors.append(f'{label}: each evaluation must bind its actual retained output and approved method/build/rubric');continue
        seen.add(key)
        if at is None or window is None or not window[0]<=at<=window[1] or utc(item['finishedAt']) is None or at<utc(item['finishedAt']):errors.append(f'{label}: evaluation must follow the completed output in valid UTC execution scope')
        mode=method['mode']
        if any(not ai_finite(row[k]) for k in ('numerator','denominator','truePositive','falsePositive','falseNegative')):errors.append(f'{label}: finite retained comparison counts required');continue
        if mode=='count_ratio':
            if row['denominator']<=0:errors.append(f'{label}: observed count ratio requires positive reference denominator');continue
            value=derive_ai_count_evidence(root,execution,prefix,row,item,items[row['itemId']],method,expected,window,defs,label,errors,cache,payload)
            if value is None:continue
        elif mode=='f1':
            denominator=2*row['truePositive']+row['falsePositive']+row['falseNegative']
            if denominator<=0:errors.append(f'{label}: F1 requires an observed nonempty label comparison');continue
            value=derive_ai_count_evidence(root,execution,prefix,row,item,items[row['itemId']],method,expected,window,defs,label,errors,cache,payload)
            if value is None:continue
        else:
            value=derive_ai_score_evidence(root,execution,prefix,row,item,items[row['itemId']],method,expected,window,defs,label,errors,cache,payload)
            if value is None:continue
        scores[metric].append(value);coverage.setdefault((row['stratumId'],metric),set()).add(row['itemId'])
    if any(len(coverage.get((s['stratumId'],metric),set()))<s['minimumSamples'] for s in strata.values() for metric in AI_EVALUATED_METRICS):errors.append(f'{label}: every approved language/quality/duration/scenario stratum needs its required samples and quality metrics')
    queries={q['queryId']:q for q in policy['queries']};query_ids=[];retrieval={key:[] for key in ('retrieval_recall','retrieval_mrr','retrieval_ndcg','query_latency')}
    if len(queries)!=len(policy['queries']) or len(set(policy['corpusItemIds']))!=len(policy['corpusItemIds']):errors.append(f'{label}: approved query and corpus item identities must be unique')
    for row in evaluation['queries']:
        query=queries.get(row['queryId']);query_ids.append(row['queryId']);start,end=utc(row['startedAt']),utc(row['finishedAt'])
        if query is None or row['querySetId']!=policy['querySetId'] or row['corpusId']!=policy['corpusId'] or len(row['retrievedIds'])!=len(set(row['retrievedIds'])) or not set(row['retrievedIds']).issubset(policy['corpusItemIds']) or len(row['retrievedIds'])>policy['retrievalCutoff']:
            errors.append(f'{label}: retrieval results must bind exact fixed query/corpus and unique approved ranked items');continue
        if start is None or end is None or window is None or not window[0]<=start<=end<=window[1]:errors.append(f'{label}: valid end-to-end query timestamps required');continue
        payload(row['outputRef'],row['outputSha256']);output_path=existing_ref(root,row['outputRef'],prefix);before=len(errors)
        captured=qualified_observation_report(output_path,defs,'aiRetrievalOutput',label,errors,cache) if output_path else None
        if captured is None or len(errors)!=before:continue
        if any(captured.get(k)!=v for k,v in expected.items()) or captured['queryId']!=row['queryId'] or captured['retrievedIds']!=row['retrievedIds']:errors.append(f'{label}: ranked retrieval items must bind the actual retained model/query output')
        labels={r['itemId']:r['grade'] for r in query['relevance']}
        if len(labels)!=len(query['relevance']) or not set(labels).issubset(policy['corpusItemIds']) or not any(g>0 for g in labels.values()) or any(not ai_finite(g) for g in labels.values()):errors.append(f'{label}: independent relevance labels for approved corpus required');continue
        ranked=[labels.get(item,0) for item in row['retrievedIds']];relevant=sum(g>0 for g in labels.values());ideal=sorted(labels.values(),reverse=True)[:policy['retrievalCutoff']]
        highest=float(max(ideal));weight=lambda grade:math.exp2(float(grade)-highest)-math.exp2(-highest)
        dcg=sum(weight(g)/math.log2(index+2) for index,g in enumerate(ranked));idcg=sum(weight(g)/math.log2(index+2) for index,g in enumerate(ideal))
        retrieval['retrieval_recall'].append(sum(g>0 for g in ranked)/relevant);retrieval['retrieval_mrr'].append(next((1/(index+1) for index,g in enumerate(ranked) if g>0),0));retrieval['retrieval_ndcg'].append(dcg/idcg);retrieval['query_latency'].append((end-start).total_seconds()*1000)
    if len(query_ids)!=len(queries) or set(query_ids)!=set(queries):errors.append(f'{label}: every approved fixed query must have exactly one observed result')
    if len(evaluation['warmupQueries'])!=policy['warmupCount'] or evaluation['percentileMethod']!=policy['percentileMethod']:errors.append(f'{label}: query warmup/sample-count/percentile method must bind approved evaluation configuration')
    query_starts=[utc(q['startedAt']) for q in evaluation['queries']]
    for row in evaluation['warmupQueries']:
        first,last=utc(row['startedAt']),utc(row['finishedAt'])
        if row['queryId'] not in queries or row['querySetId']!=policy['querySetId'] or row['corpusId']!=policy['corpusId'] or first is None or last is None or window is None or not window[0]<=first<last<=window[1] or not query_starts or any(t is None for t in query_starts) or last>min(query_starts):errors.append(f'{label}: retained warmup queries must precede the measured fixed-query observations')
        payload(row['outputRef'],row['outputSha256']);output_path=existing_ref(root,row['outputRef'],prefix);before=len(errors);captured=qualified_observation_report(output_path,defs,'aiRetrievalOutput',label,errors,cache) if output_path else None
        if captured is not None and len(errors)==before and (any(captured.get(k)!=v for k,v in expected.items()) or captured['queryId']!=row['queryId'] or captured['retrievedIds']!=row['retrievedIds']):errors.append(f'{label}: warmup must bind actual retained ranked output')
    outcomes=dispatch['outcomes'];required=set(AI_POLICY_GATES)|{'authorized'}
    if len(outcomes)!=len(required) or {o['case'] for o in outcomes}!=required:errors.append(f'{label}: exact authorized and permission/ACL/budget/request/concurrency denial cases required');return
    estimated=gates['plannedInputTokens']*pricing['inputUnitPrice']+gates['plannedOutputTokens']*pricing['outputUnitPrice']
    for row in outcomes:
        case=row['case'];at=utc(row['observedAt']);outbound=payload(row['outboundRef'],row['outboundSha256'],allow_empty=True)
        if at is None or window is None or not window[0]<=at<=window[1] or outbound is None:errors.append(f'{label}: actual dispatch bytes and valid policy evaluation timestamp required');continue
        if not all(ai_finite(row[k]) for k in ('budgetRemaining','estimatedCost')) or not ai_finite(estimated):errors.append(f'{label}: finite priced policy evaluation required');continue
        if row['assetId']!=gates['assetId'] or row['callerId']!=(gates['unauthorizedCallerId'] if case=='permission_denied' else gates['authorizedCallerId']) or row['aclVersion']!=(gates['revokedAclVersion'] if case=='acl_revoked' else gates['currentAclVersion']) or not 0<=row['budgetRemaining']<=gates['budgetLimit'] or row['budgetPeriodId']!=gates['budgetPeriodId'] or not math.isclose(row['estimatedCost'],estimated,rel_tol=1e-9,abs_tol=1e-12):errors.append(f'{label}: policy outcome must bind exact caller/current asset ACL and priced invocation')
        if row['callerAllowed'] is not (case!='permission_denied') or row['assetAllowed'] is not (case!='acl_revoked'):errors.append(f'{label}: permission and current/revoked ACL decisions must be exercised independently')
        exceeded=(row['estimatedCost']>row['budgetRemaining'],row['requestCount']>gates['requestRateLimit'],row['concurrentCalls']>gates['concurrencyLimit'])
        if exceeded!=(case=='budget_exhausted',case=='request_rate_exceeded',case=='concurrency_exceeded') or row['requestWindowSeconds']!=60:errors.append(f'{label}: each denial must independently exceed its exact approved budget/rate/concurrency ceiling')
        if case=='authorized':
            if row['decision']!='dispatched' or len(row['providerRequestIds'])!=1 or outbound['size']==0:errors.append(f'{label}: authorized control request requires one actual nonempty dispatch observation')
            path=existing_ref(root,row['outboundRef'],prefix);before=len(errors);captured=qualified_observation_report(path,defs,'aiProviderDispatch',label,errors,cache) if path else None
            if captured is not None and len(errors)==before and (any(captured.get(k)!=v for k,v in expected.items()) or captured['requestIds']!=row['providerRequestIds'] or captured['callerId']!=row['callerId'] or captured['assetId']!=row['assetId'] or captured['aclVersion']!=row['aclVersion'] or captured['observedAt']!=row['observedAt']):errors.append(f'{label}: provider dispatch must bind actual authorized request and current evaluated subjects')
        elif row['decision']!=case or row['providerRequestIds'] or outbound['size']!=0:errors.append(f'{label}: denied permission/ACL/budget/quota invocation must produce zero provider requests and outbound bytes')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)};derived={m:sum(values)/len(values) for m,values in scores.items() if values}
    for metric,values in retrieval.items():
        if values:derived[metric]=sorted(values)[max(0,math.ceil(.95*len(values))-1)] if metric=='query_latency' and policy['percentileMethod']=='nearest-rank-p95' else sum(values)/len(values)
    derived.update(cost_estimate=cost*1000/len(outputs) if outputs else 0,provider_budget_limit=gates['budgetLimit'],provider_request_rate_limit=gates['requestRateLimit'],provider_concurrency_limit=gates['concurrencyLimit'])
    for metric,value in derived.items():
        claimed=actual.get(metric)
        if not ai_finite(claimed) or not ai_finite(value) or not math.isclose(claimed,value,rel_tol=1e-9,abs_tol=1e-9):errors.append(f'{label}: {metric} must derive retained evaluation/relevance/pricing/usage/quota observations')
    expected_metrics={m['id'] for m in plan['protocol']['measurements']};provided=set(derived)|{'throughput','fixed_query_set_bound','quality_strata_coverage','license_privacy_pass'}|set(AI_POLICY_GATES.values())
    if provided!=expected_metrics:errors.append(f'{label}: exact plan metric and policy gate coverage required')
    if any(actual.get(gate) is not True for gate in {'fixed_query_set_bound','quality_strata_coverage','license_privacy_pass'}|set(AI_POLICY_GATES.values())):errors.append(f'{label}: true quality/policy gates require the corresponding observed results')
    reviews={r['type']:r.get('reviewRef') for r in execution.get('complianceReviews') or [] if isinstance(r,dict)}
    if report['privacyReviewRef']!=reviews.get('privacy') or report['licenseReviewRef']!=reviews.get('license'):errors.append(f'{label}: policy compatibility must bind the existing independently validated license/privacy reviews')
    validate_qualified_ai_data_policy(root,plan,execution,prefix,window,defs,errors,cache,report,dispatch,policy,expected,payload)



def validate_qualified_ai_data_policy(root,plan,execution,prefix,window,defs,errors,cache,results,dispatch,evaluation_policy,expected,payload):
    label=f"qualified AI data policy {plan['taskId']}";env=execution.get('environmentCaptured') or {};before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('aiDataPolicyRef'),defs,'aiDataPolicyOutcomes',label,errors,cache)
    path=existing_ref(root,results['configurationRef'],prefix)
    try:policy=load(path).get('configuration',{}).get('aiDataPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('aiDataPolicy',{}),label+'/approved policy',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    if policy['providerMode']=='commercial_external' or report['providerMode']=='commercial_external':
        errors.append(f'{label}: commercial_external qualified PASS deferred until actual provider payload validation is implemented');return
    gates=evaluation_policy['gatePolicy']
    if any(report.get(k)!=v for k,v in expected.items()) or report['dispatchRef']!=results['dispatchRef'] or report['privacyReviewRef']!=results['privacyReviewRef']:
        errors.append(f'{label}: exact approved input/model/provider/configuration and privacy/dispatch identities required')
    if policy['subjectVersion']!=expected['subjectVersion'] or policy['assetId']!=gates['assetId'] or policy['privacyReviewRef']!=results['privacyReviewRef'] or policy['allowedPurpose']==policy['deniedPurpose']:
        errors.append(f'{label}: approved data policy must bind tested provider subject/current asset/privacy review and distinct allowed/denied purposes')
    if policy['inputSamples']!=expected['inputSamples'] or policy['assetVersion']!=env.get('input_sample_version') or set(policy['allowedPayloadScope'])!={sample['immutableId'] for sample in expected['inputSamples']} or any(report[k]!=policy[k] for k in ('providerMode','assetVersion')):
        errors.append(f'{label}: approved provider mode/input asset version and payload scope must bind exact immutable inputs')
    rows=report['outcomes']
    if len(rows)!=2 or {row['case'] for row in rows}!={'authorized','data_policy_denied'}:
        errors.append(f'{label}: exact independent allow and data-policy denial observations required');return
    controls=[row for row in dispatch['outcomes'] if row['case']=='authorized']
    if len(controls)!=1:return
    control=controls[0]
    for row in rows:
        allowed=row['case']=='authorized';at=utc(row['evaluatedAt']);sent=utc(row['dispatchedAt'])
        expected_purpose=policy['allowedPurpose'] if allowed else policy['deniedPurpose']
        if any(row[k]!=policy[k] for k in ('policyId','policyVersion','classificationId')) or row['purpose']!=expected_purpose or row['callerId']!=gates['authorizedCallerId'] or row['assetId']!=gates['assetId'] or row['aclVersion']!=gates['currentAclVersion']:
            errors.append(f'{label}: each data decision must bind exact policy version/classification/purpose and otherwise authorized current subjects')
        if at is None or window is None or not window[0]<=at<=window[1] or row['decision']!=('allowed' if allowed else 'denied'):
            errors.append(f'{label}: exercised data-policy decision and valid UTC evaluation required')
        info=payload(row['outboundRef'],row['outboundSha256'],allow_empty=True)
        if allowed:
            if sent is None or at is None or window is None or not window[0]<=at<=sent<=window[1] or row['dispatchedAt']!=control['observedAt'] or any(row[k]!=control[k] for k in ('outboundRef','outboundSha256','providerRequestIds','callerId','assetId','aclVersion')) or info is None or info['size']==0:
                errors.append(f'{label}: data-policy allow must precede and bind the actual authorized provider dispatch')
        elif row['dispatchedAt'] is not None or row['providerRequestIds'] or info is None or info['size']!=0 or row['outboundRef']==control['outboundRef']:
            errors.append(f'{label}: disallowed data must retain zero outbound bytes and no provider request')


def validate_qualified_android_media(root, plan, execution, prefix, status, errors, artifact_cache, defs):
    if plan['pocId'] != 'POC-01' or status != 'pass':
        return
    env = execution.get('environmentCaptured') or {}
    key = 'vm_validation_scope' if env.get('acceptanceProfile') == profile_identity('local-v1') else 'android_validation_scope'
    scope = env.get(key)
    label = f"qualified Android output {plan['taskId']}"
    if not isinstance(scope,dict):
        return  # The existing VM/device validator reports invalid scopes.
    ref = scope.get('rawOutputRef')
    records = env.get('rawExecutionArtifacts') or []
    artifact = next((item for item in records if isinstance(item,dict) and item.get('ref') == ref),None) if isinstance(records,list) else None
    path = existing_ref(root,ref,prefix)
    if artifact is None or artifact.get('artifactType') != 'produced_media' or artifact.get('nodeId') != scope.get('nodeId') or path is None:
        errors.append(f'{label}: encode scope must reference a node-bound typed produced_media artifact')
        return
    try:
        actual = inspect_artifact(path,artifact_cache)
        if actual['size'] == 0 or scope.get('outputSha256') != actual['sha256']:
            errors.append(f'{label}: outputSha256 must bind actual nonempty produced media bytes')
    except OSError:
        errors.append(f'{label}: produced media must be readable')
    probe_label=f"qualified Android media probe {plan['taskId']}"
    probe_ref=env.get('androidMediaProbeRef')
    probes=[item for item in records if isinstance(item,dict) and item.get('ref')==probe_ref]
    probe_path=existing_ref(root,probe_ref,prefix)
    if len(probes)!=1 or probes[0].get('artifactType')!='measurement_output' or probes[0].get('nodeId')!=scope.get('nodeId') or probe_ref not in (execution.get('rawOutputRefs') or []) or probe_path is None:
        errors.append(f'{probe_label}: selected-slot node-bound typed decoder report required')
    elif probe_ref==ref or probe_path.samefile(path):
        errors.append(f'{probe_label}: decoder report must be distinct from produced media')
    else:
        report=qualified_observation_report(probe_path,defs,'androidMediaProbeReport',probe_label,errors,artifact_cache)
        if report is not None:
            expected=dict(nodeId=scope.get('nodeId'),encoderBuild=scope.get('encoderBuild'),inputSha256=scope.get('inputSha256'),outputArtifactRef=ref,outputSha256=scope.get('outputSha256'))
            frames=report.get('decodedFrameCount');duration=report.get('durationSeconds')
            if any(report.get(key)!=value for key,value in expected.items()) or not recorded_text(report.get('decoderBuild')) or report.get('codec')!='av1' or report.get('decodable') is not True or type(frames) is not int or frames<=0 or not good_actual('seconds',duration) or duration<=0 or type(report.get('decodeErrorCount')) is not int or report['decodeErrorCount']!=0:
                errors.append(f'{probe_label}: decodable AV1 frames/duration and zero errors must bind the exact input/output/node/build')
    if env.get('acceptanceProfile') == profile_identity('production'):
        observation = env.get('android_thermal_background_observation')
        observation_ref = observation.get('rawOutputRef') if isinstance(observation,dict) else None
        observation_artifact = next((item for item in records if isinstance(item,dict) and item.get('ref') == observation_ref),None)
        observation_path = existing_ref(root,observation_ref,prefix)
        if observation_artifact is None or observation_artifact.get('artifactType') != 'scope_observation' or observation_artifact.get('nodeId') != scope.get('nodeId') or observation_path is None:
            errors.append(f'{label}: physical device observation requires a node-bound typed scope_observation artifact')
        elif observation_ref == ref or observation_path.samefile(path):
            errors.append(f'{label}: physical device observation must be distinct from encoded media')
        else:
            validate_qualified_phone_observation(root,execution,prefix,scope,observation,observation_path,defs,errors,artifact_cache)


def derive_worker_limit_evidence(root,execution,prefix,case,identity,policy,expected,window,defs,label,errors,cache,paths,process_ids):
    """Derive one worker limit outcome from retained process/counter/listing/exit bytes."""
    before=len(errors);evidence={};env=execution.get('environmentCaptured') or {}
    for name,schema in (('process','workerSafetyLimitProcess'),('runtime','workerSafetyLimitRuntime'),('filesystem','workerSafetyLimitFilesystem'),('exit','workerSafetyLimitExit')):
        ref=case[name+'Ref'];path=existing_ref(root,ref,prefix);records=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==ref]
        capture=bounded_evaluator_json(root,execution,prefix,ref,'command_output',defs,schema,label+'/'+name,errors,cache,1048576)
        if path is None or len(records)!=1 or records[0].get('nodeId')!=identity['nodeId']:errors.append(f'{label}: per-node original runtime/process/filesystem/exit artifacts required');continue
        artifact=inspect_artifact(path,cache)
        if artifact['sha256']!=case[name+'Sha256'] or records[0].get('sha256')!=artifact['sha256'] or records[0].get('byteCount')!=artifact['size'] or any(path.samefile(p) for p in paths):errors.append(f'{label}: original limit materials need exact bytes/hash and physically distinct per-case files')
        paths.append(path);evidence[name]=capture
    if len(errors)!=before or len(evidence)!=4 or any(value is None for value in evidence.values()):return
    process,runtime,filesystem,exit=(evidence[k] for k in ('process','runtime','filesystem','exit'));pid=process['processId']
    binding=dict(context=expected,identity=identity,taskId=policy['taskId'],requestId=case['requestId'],case=case['case'],processId=pid,observerBuild=policy['limitObserverBuild'])
    process_key=(identity['nodeId'],pid)
    if not 1<=int(pid)<=4294967295 or process_key in process_ids or any(any(capture[k]!=v for k,v in binding.items()) for capture in evidence.values()) or process['limits']!=policy['limits'] or process['commandArgs']!=policy['limitCommandArgs']+[case['case']]:errors.append(f'{label}: original limit materials must bind unique per-node native PID, approved command/budgets/observer and exact case/node/input/profile')
    process_ids.add(process_key);start,end=utc(process['startedAt']),utc(exit['observedAt']);samples=runtime['samples'];snapshots=filesystem['snapshots'];runtime_times=[utc(s['observedAt']) for s in samples];fs_times=[utc(s['observedAt']) for s in snapshots]
    all_times=[start,end]+runtime_times+fs_times
    if window is None or any(at is None or not window[0]<=at<=window[1] for at in all_times) or start>=end or runtime_times[0]!=start or runtime_times[-1]!=end or any(a>=b for a,b in zip(runtime_times,runtime_times[1:])) or fs_times[0]!=start or fs_times[-1]<end or any(a>=b for a,b in zip(fs_times,fs_times[1:])) or any(at>end for at in fs_times[:-1]) or case['startedAt']!=process['startedAt'] or case['finishedAt']!=exit['observedAt']:
        errors.append(f'{label}: original process/counter/filesystem/exit clocks must cover one complete selected execution followed by cleanup');return
    counters=[(s['userCpuSeconds'],s['systemCpuSeconds'],s['residentBytes']) for s in samples]
    if any(not ai_finite(v) for values in counters for v in values) or any(any(a[k]>b[k] for k in (0,1)) for a,b in zip(counters,counters[1:])):errors.append(f'{label}: finite monotonic original OS CPU counters and resident samples required');return
    totals=[]
    for snapshot in snapshots:
        names=[f['path'] for f in snapshot['files']]
        if len(names)!=len(set(names)) or any('\\' in name or ':' in name or any(part in ('','.','..') for part in name.split('/')) for name in names) or snapshot['publishedArtifactIds']:
            errors.append(f'{label}: unique canonical forward-slash relative file listings without empty/dot segments must remain unpublished');return
        totals.append({area:sum(f['byteCount'] for f in snapshot['files'] if f['area']==area) for area in ('temporary','output')})
    derived=dict(cpuSeconds=sum(counters[-1][:2])-sum(counters[0][:2]),memoryBytes=max(s['residentBytes'] for s in samples),elapsedSeconds=(end-start).total_seconds(),temporaryBytes=max(t['temporary'] for t,at in zip(totals,fs_times) if at<=end),outputBytes=max(t['output'] for t,at in zip(totals,fs_times) if at<=end))
    remaining=totals[-1];limits=policy['limits'];kind=case['case']
    if any(not ai_finite(v) for v in derived.values()) or {k for k,v in derived.items() if v>limits[k]}!={kind} or any(not ai_finite(case['observed'][k]) or not math.isclose(case['observed'][k],v,rel_tol=1e-9,abs_tol=1e-9) for k,v in derived.items()) or exit['exitCode']==0 or exit['terminationReason']!=kind or exit['remainingProcessIds'] or snapshots[0]['files'] or remaining!={'temporary':0,'output':0} or case['remainingTemporaryBytes']!=remaining['temporary'] or case['remainingOutputBytes']!=remaining['output'] or case['processExited'] is not (not exit['remainingProcessIds']):
        errors.append(f'{label}: limit crossing, failed process exit and complete unpublished cleanup must derive original counters/file entries/exit rather than outcome totals')


def validate_qualified_worker_safety(root,plan,execution,prefix,status,window,defs,errors,cache):
    if plan['pocId']!='POC-01' or status!='pass':return
    env=execution.get('environmentCaptured') or {};label=f"qualified worker safety {plan['taskId']}";before=len(errors)
    report=selected_observation(root,execution,prefix,env.get('workerSafetyRef'),defs,'workerSafetyOutcomes',label,errors,cache)
    resource=next((r for r in execution.get('resources') or [] if isinstance(r,dict) and r.get('id')=='RES-HETEROGENEOUS-WORKERS'),None)
    path=existing_ref(root,resource.get('configurationRef'),prefix) if resource else None
    try:policy=load(path).get('configuration',{}).get('workerSafetyPolicy') if path else None
    except (OSError,ValueError,AttributeError,yaml.YAMLError):policy=None
    validate_schema(policy,defs.get('workerSafetyPolicy',{}),label+'/approved safety policy',errors)
    if len(errors)!=before or report is None or not isinstance(policy,dict):return
    expected=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env.get('acceptanceProfile'),subjectVersion=compliance_subject_version(plan,execution),inputSamples=[{k:s.get(k) for k in ('id','immutableId','checksum')} for s in execution.get('samples') or []])
    inventory=env.get('worker_node_inventory');identities=[{k:n.get(k) for k in ('nodeId','physicalHostId','encoderBuild')} for n in inventory if isinstance(n,dict)] if isinstance(inventory,list) else []
    if any(report[k]!=v for k,v in expected.items()) or policy['subjectVersion']!=expected['subjectVersion'] or not identities or len(identities)!=len(inventory) or policy['nodes']!=identities or len({n['nodeId'] for n in identities})!=len(identities) or len(report['nodes'])!=len(identities) or {r['identity']['nodeId'] for r in report['nodes']}!={n['nodeId'] for n in identities}:
        errors.append(f'{label}: exact selected profile/input/build and approved complete worker inventory required');return
    limits=policy['limits'];request_ids=set();lease_ids=set();registrations=set();process_ids=set()
    paths=[p for ref in [env.get('workerSafetyRef'),resource['configurationRef']]+[a.get('inputArtifactRef') for a in env.get('inputSampleArtifacts') or [] if isinstance(a,dict)]+[a.get('ref') for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('artifactType')=='produced_media'] if (p:=existing_ref(root,ref,prefix)) is not None]
    if not all(ai_finite(v) and v>0 for v in limits.values()) or not ai_finite(policy['maximumRecoverySeconds']) or policy['maximumRecoverySeconds']<=0 or not recorded_text(policy['limitObserverBuild']):errors.append(f'{label}: finite positive approved resource/recovery budgets and concrete limit observer build required');return
    grant_start,grant_end,expired=map(utc,(policy['grantValidFrom'],policy['grantValidUntil'],policy['expiredAt']))
    if grant_start is None or grant_end is None or expired is None or grant_start>=grant_end or policy['grantId']==policy['expiredGrantId']:errors.append(f'{label}: distinct live/expired task grants with valid UTC intervals required')
    try:
        private=urllib.parse.urlsplit(policy['privateTarget']);unsupported=urllib.parse.urlsplit(policy['unsupportedTarget']);admin=urllib.parse.urlsplit(policy['administrativeTarget']);allowed=urllib.parse.urlsplit(policy['allowedTarget'])
        if private.scheme not in ('http','https') or not ipaddress.ip_address(private.hostname).is_private or unsupported.scheme in ('http','https') or admin.scheme not in ('http','https') or not admin.path.startswith('/api/admin') or allowed.scheme not in ('http','https') or allowed.username is not None or not allowed.hostname:raise ValueError()
    except (ValueError,TypeError):errors.append(f'{label}: approved cases must exercise private/unsupported/administrative and authorized task targets')
    def timestamp(value):
        at=utc(value)
        if at is None or window is None or not window[0]<=at<=window[1]:errors.append(f'{label}: observed outcome timestamp must be inside selected UTC execution');return None
        return at
    def request(value):
        if value in request_ids:errors.append(f'{label}: distinct exercised requests required')
        request_ids.add(value)
    for row in report['nodes']:
        identity=next(n for n in identities if n['nodeId']==row['identity']['nodeId'])
        if row['identity']!=identity:errors.append(f'{label}: each outcome must bind exact node/physical host/encoder build')
        cases=row['limitCases']
        if len(cases)!=len(limits) or {c['case'] for c in cases}!=set(limits):errors.append(f'{label}: every node must independently exhaust each approved CPU/memory/time/temp/output limit')
        for case in cases:
            request(case['requestId']);start,end=timestamp(case['startedAt']),timestamp(case['finishedAt']);observed=case['observed'];kind=case['case']
            derive_worker_limit_evidence(root,execution,prefix,case,identity,policy,expected,window,defs,label,errors,cache,paths,process_ids)
            if start is None or end is None or start>=end or not math.isclose((end-start).total_seconds(),observed['elapsedSeconds'],rel_tol=1e-9,abs_tol=1e-9) or any(not ai_finite(v) for v in observed.values()) or {k for k,v in observed.items() if v>limits[k]}!={kind} or case['terminationReason']!=kind or case['processExited'] is not True or case['remainingTemporaryBytes']!=0 or case['remainingOutputBytes']!=0 or case['publishedArtifactIds']:
                errors.append(f'{label}: independent observed limit exhaustion must terminate and clean unpublished task outputs')
        recovery=row['restart'];keys=('disconnectedAt','oldLeaseExpiresAt','expiredLeaseObservedAt','reRegisteredAt','newLeaseIssuedAt','recoveredAt');times=[utc(recovery['oldLeaseIssuedAt'])]+[timestamp(recovery[k]) for k in keys]+[utc(recovery['newLeaseExpiresAt'])]
        old,new=recovery['oldLeaseId'],recovery['newLeaseId'];old_registration,new_registration=recovery['oldRegistrationId'],recovery['newRegistrationId']
        if any(t is None for t in times) or times!=sorted(t for t in times if t is not None) or times[0]>=times[2] or times[5]>=times[7] or (times[6]-times[1]).total_seconds()>policy['maximumRecoverySeconds'] or old==new or old_registration==new_registration or old in lease_ids or new in lease_ids or old_registration in registrations or new_registration in registrations or recovery['taskId']!=policy['taskId'] or recovery['completedTaskId']!=policy['taskId'] or recovery['completionLeaseId']!=new or recovery['completionRegistrationId']!=new_registration or recovery['taskCompletionCount']!=1 or recovery['staleLeasePublicationCount']!=0:
            errors.append(f'{label}: observed disconnect/lease expiry/re-registration must recover the exact task once under a fresh lease within its approved bound')
        lease_ids.update((old,new));registrations.update((old_registration,new_registration))
        network=row['networkCases'];required={'authorized','private_target','unsupported_target','administrative_target','expired_grant'}
        if len(network)!=5 or {c['case'] for c in network}!=required:errors.append(f'{label}: each node must exercise allowed access and every denied target/grant case')
        for case in network:
            request(case['requestId']);kind=case['case'];at=timestamp(case['observedAt']);authorized=kind=='authorized';target=policy[dict(authorized='allowedTarget',private_target='privateTarget',unsupported_target='unsupportedTarget',administrative_target='administrativeTarget',expired_grant='allowedTarget')[kind]]
            if case['taskId']!=policy['taskId'] or case['requestURL']!=target or case['grantId']!=policy['expiredGrantId' if kind=='expired_grant' else 'grantId'] or case['decision']!=('allowed' if authorized else 'denied') or at is None or grant_start is None or grant_end is None or expired is None or not grant_start<=at<grant_end or kind=='expired_grant' and at<=expired:errors.append(f'{label}: actual access decision must bind exact task/target and otherwise live or explicitly expired grant')
            matches=[a for a in env.get('rawExecutionArtifacts') or [] if isinstance(a,dict) and a.get('ref')==case['outboundRef']];payload=existing_ref(root,case['outboundRef'],prefix)
            if payload is None or len(matches)!=1 or matches[0].get('artifactType')!='produced_media' or matches[0].get('nodeId')!=identity['nodeId'] or case['outboundRef'] not in (execution.get('rawOutputRefs') or []):errors.append(f'{label}: node-bound retained outbound bytes required');continue
            try:actual=inspect_artifact(payload,cache)
            except OSError:errors.append(f'{label}: outbound bytes must be readable');continue
            if actual['sha256']!=case['outboundSha256'] or actual['size']!=case['outboundByteCount'] or (actual['size']==0 if authorized else actual['size']!=0):errors.append(f'{label}: authorized control needs real outbound bytes; denied targets/grants must send zero bytes')
    actual={m.get('id'):m.get('actual') for m in execution.get('measurements') or [] if isinstance(m,dict)}
    if any(actual.get(g) is not True for g in ('worker_resource_limits_enforced','worker_restart_recovery','worker_network_boundary_enforced')):errors.append(f'{label}: true worker safety gates require corresponding per-node exercised outcomes')


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
    match = any(isinstance(node,dict) and node.get('platform') == 'android' and node.get('isEmulator') is False and node.get('isVirtualMachine') is False and all(node.get(k) == scope.get(k) for k in ('nodeId','deviceId','physicalHostId','encoderBuild')) for node in inventory) if isinstance(inventory,list) else False
    if scope.get('isEmulator') is not False or scope.get('isVirtualMachine') is not False or not match:
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
    text = str(key)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return re.sub(r'[^a-z0-9]+','_',text.lower()).strip('_')


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
            if key=='credentialReference':
                if not isinstance(item,str) or len(item)>74 or re.fullmatch(r'secretref_[A-Za-z0-9_-]{1,64}',item) is None:
                    errors.append(f"invalid canonical Secret reference at {path}/{key}")
            elif secret_key(key, item):
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
    record_refs: set[str] | None = None,
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
        artifact_cache = {}
        validate_qualified_configuration(root,plan,execution,profile_configuration,record_definitions,reference_boundary,task_reviewer,implementer,window,errors,status)
        validate_qualified_inputs(root,plan,execution,record_definitions,reference_boundary,status,errors,artifact_cache,record_refs,profile_configuration)
        validate_deferred_production_qualification(plan,execution,status,errors)
        validate_qualified_production_capacity(plan,execution,status,errors)
        validate_qualified_source(root,plan,execution,profile_configuration,record_definitions,reference_boundary,errors,record_refs)
        validate_qualified_local_source_faults(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_local_source_listing(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_local_source_authentication(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_h264_fallback(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_media_soak(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_hls_ready(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_media_scheduling(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_resources(root,plan,execution,resource_catalog,record_definitions,reference_boundary,task_reviewer,status,window,errors)
        validate_qualified_hierarchy_sandbox(root,plan,execution,record_definitions,reference_boundary,status,errors)
        validate_qualified_metadata_scan(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_passthrough_identity(root,plan,execution,record_definitions,reference_boundary,status,errors)
        validate_qualified_passthrough_firmware(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_passthrough_transitions(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_production_soak(root,plan,execution,record_definitions,reference_boundary,status,window,errors)
        validate_qualified_domains(root,plan,execution,route,profile_configuration,record_definitions,reference_boundary,task_reviewer,window,errors)
        validate_qualified_a380_encode(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_raw(root,plan,execution,profile_configuration,record_definitions,reference_boundary,status,record_refs or set(),errors,artifact_cache)
        validate_qualified_encode_workers(root,plan,execution,reference_boundary,status,window,errors,artifact_cache,record_definitions)
        validate_qualified_media_quality_timing(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_media_negative(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_android_media(root,plan,execution,reference_boundary,status,errors,artifact_cache,record_definitions)
        validate_qualified_worker_safety(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_worker_capabilities(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_inference_observation(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_recovery_observation(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_recovery_timing(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_access_outcomes(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_public_network(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_range_matrix(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_ai_results(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_frontend_comparison(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
        validate_qualified_local_storage(root,plan,execution,reference_boundary,status,window,record_definitions,errors,artifact_cache)
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
    if poc_id == 'POC-05' and status == 'pass':
        for mid in ('file_count','directory_count','enumeration_rate','source_change_frequency','incremental_scan_cost'):
            value = actual_map.get(mid)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
                errors.append(f'{label}: POC-005 PASS requires positive exercised workload: {mid}')
    if poc_id == 'POC-02' and status == 'pass' and record_definitions is not None:
        for mid in ('encode_throughput','sustained_encode_duration'):
            value = actual_map.get(mid)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
                errors.append(f'{label}: POC-002 PASS requires positive exercised workload: {mid}')
    if poc_id == 'POC-01' and status == 'pass' and record_definitions is not None and execution.get('environmentCaptured',{}).get('acceptanceProfile') == profile_identity('production'):
        duration=actual_map.get('multi_day_stability_duration')
        if not good_actual('hours',duration) or duration<=0:
            errors.append(f'{label}: production POC-001 PASS requires positive multi_day_stability_duration')
    if poc_id == 'POC-09' and status == 'pass' and record_definitions is not None:
        throughput=actual_map.get('throughput')
        if isinstance(throughput,bool) or not isinstance(throughput,(int,float)) or not math.isfinite(throughput) or throughput<=0:
            errors.append(f'{label}: POC-009 PASS requires positive measured inference throughput')
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
        {entry.get('resultRef'),result.get('executionRef')},
    )
    if record_definitions is not None:
        captured_window = (execution.get('environmentCaptured') or {}).get('executionWindow')
        end = utc(captured_window.get('finishedAt')) if isinstance(captured_window,dict) else None
        approval = utc(result.get('approvedAt'))
        if approval is not None and approval > datetime.now(timezone.utc):
            errors.append(f'result record {task_id}: approval must have occurred by validation time')
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

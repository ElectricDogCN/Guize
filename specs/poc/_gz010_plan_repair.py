#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from textwrap import dedent, indent

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "specs" / "poc" / "plans"

ADDITIONS = {
    "POC-001": [
        ("bios_iommu_configuration_verified", "Inspur 5212 BIOS and IOMMU configuration matches the approved passthrough baseline", "boolean", "Capture BIOS virtualization/IOMMU settings and host boot/runtime evidence before assigning the A380.", "APPROVED_POC_SCOPE"),
        ("iommu_group_isolation_verified", "A380 IOMMU group isolation is suitable for passthrough", "boolean", "Record the complete IOMMU group and prove no unrelated required host device must be passed through with the GPU.", "APPROVED_POC_SCOPE"),
        ("above_4g_enabled", "Above 4G decoding is enabled and effective", "boolean", "Capture the firmware setting and host resource allocation showing the passthrough device receives the required address space.", "APPROVED_POC_SCOPE"),
        ("resizable_bar_enabled", "Resizable BAR configuration is captured and compatible with the tested path", "boolean", "Capture the firmware/device setting and verify the selected configuration does not prevent guest enumeration or runtime initialization.", "APPROVED_POC_SCOPE"),
        ("multi_day_stability_duration", "Observed continuous passthrough soak duration", "hours", "Record continuous sandbox execution time from raw timestamps across the approved multi-day workload.", "APPROVED_POC_SCOPE"),
        ("multi_day_stability", "A380 passthrough remains stable through the approved multi-day soak", "boolean", "Require no unrecovered GPU loss, host/guest crash, driver reset loop, corrupt output, or manual passthrough rebuild during the recorded soak duration.", "APPROVED_POC_SCOPE"),
    ],
    "POC-002": [
        ("a380_range_first_byte_latency", "A380-backed Range first-byte latency", "ms", "Measure first-byte latency for approved Range requests whose media output was produced by the recorded A380 encoder path.", "NFR-V1-PERF-002"),
        ("encoder_power_peak_watts", "Peak encoder power during the approved workload", "W", "Capture device/host power telemetry with tool version, sampling interval and workload phase recorded.", "APPROVED_POC_SCOPE"),
        ("encoder_temperature_peak_celsius", "Peak encoder temperature during the approved workload", "celsius", "Capture device temperature telemetry across warmup, concurrency and soak phases with the sampling method recorded.", "APPROVED_POC_SCOPE"),
    ],
    "POC-003": [
        ("range_hot_cache_latency", "Range first-byte latency on hot cache", "ms", "Measure the approved byte-range matrix after cache warmup with percentile method and request count recorded.", "NFR-V1-PERF-002"),
        ("range_cold_cache_latency", "Range first-byte latency on cold cache", "ms", "Purge the approved sandbox cache, then measure cold-fill Range first-byte latency using the same immutable sample.", "NFR-V1-PERF-002"),
        ("range_slow_origin_latency", "Range first-byte latency with controlled slow origin", "ms", "Apply the approved origin delay/bandwidth profile and measure end-to-end Range first-byte latency and timeout behavior.", "NFR-V1-PERF-002"),
        ("range_multi_user_latency", "Range latency under approved multi-user load", "ms", "Measure authorized Range latency under the frozen concurrent-user profile while preserving cache-key isolation.", "NFR-V1-PERF-002"),
    ],
    "POC-004": [
        ("incomplete_replica_rejected", "Incomplete object is rejected as a formal replica", "boolean", "Interrupt or truncate the copy and prove it cannot be promoted to formal-replica state.", "ACCEPTANCE_TRACE_V1"),
        ("hash_mismatch_replica_rejected", "Hash-mismatched object is rejected as a formal replica", "boolean", "Introduce a deterministic checksum mismatch and prove promotion fails closed with auditable evidence.", "ACCEPTANCE_TRACE_V1"),
        ("cache_eviction_preserves_authoritative_state", "Cache eviction preserves asset metadata, retention and formal replicas", "boolean", "Evict the cache copy and verify authoritative asset metadata, retention state and formal-replica records remain unchanged.", "ACCEPTANCE_TRACE_V1"),
        ("replica_migration_preserves_old_valid_copy", "Replica migration retains the old valid copy until the new copy is verified", "boolean", "Migrate a sandbox replica and prove the prior valid copy remains available until checksum and metadata verification complete.", "ACCEPTANCE_TRACE_V1"),
    ],
    "POC-005": [
        ("filename_characteristics_profiled", "Filename and path characteristics are profiled", "boolean", "Measure name length, character-set, extension and path-depth distributions from the approved immutable metadata fixture.", "APPROVED_POC_SCOPE"),
        ("provider_characteristics_profiled", "Provider/source characteristics are recorded", "boolean", "Record provider listing, pagination, consistency, timestamp and object-identity semantics for the tested source profile.", "APPROVED_POC_SCOPE"),
        ("range_support_profiled", "Source Range support is measured", "boolean", "Exercise supported and unsupported Range requests and record status/header/body behavior for the tested provider profile.", "APPROVED_POC_SCOPE"),
        ("etag_behavior_profiled", "Source ETag or equivalent version semantics are measured", "boolean", "Record validator stability for unchanged objects and change behavior after an approved source update.", "APPROVED_POC_SCOPE"),
    ],
    "POC-006": [
        ("rate_limit_429_classified_retried", "Provider 429 responses are classified and retried safely", "boolean", "Inject or receive a sandbox 429, honor retry guidance/backoff and prove no duplicate logical object is created.", "ACCEPT-SOURCE-SYNC"),
        ("upstream_5xx_classified_retried", "Provider 5xx responses are classified and retried safely", "boolean", "Exercise bounded 5xx failures and recovery, retaining checkpoint/idempotency evidence.", "ACCEPT-SOURCE-SYNC"),
        ("network_failure_classified_retried", "Network failures are classified and recovered safely", "boolean", "Interrupt the sandbox network path and verify bounded retry or explicit failure without corrupting sync state.", "ACCEPT-SOURCE-SYNC"),
        ("interrupted_sync_resume_or_idempotent_rerun", "Interrupted synchronization resumes from a safe checkpoint or reruns idempotently", "boolean", "Interrupt synchronization after partial progress and verify checkpoint resume or full idempotent rerun produces the same logical state.", "ACCEPT-SOURCE-SYNC"),
        ("duplicate_objects_prevented", "Failure and retry paths do not create duplicate logical objects", "boolean", "Compare stable source/object identities before and after each retry/recovery scenario.", "ACCEPT-SOURCE-SYNC"),
        ("source_deletion_preserves_logical_asset", "Source deletion does not delete the logical asset", "boolean", "Delete or hide the source object in the sandbox and verify the logical asset remains with governed source-unavailable state.", "ACCEPT-SOURCE-SYNC"),
    ],
    "POC-008": [
        ("million_row_virtual_list_equivalent", "Million-row virtual-list scenario is equivalent in Vue and React", "boolean", "Implement and compare the same million-row virtualization fixture, interactions and measurements.", "FRONTEND_POC_MATRIX"),
        ("dynamic_form_equivalent", "Dynamic-form scenario is equivalent in Vue and React", "boolean", "Implement the same conditional fields, validation and schema-driven updates.", "FRONTEND_POC_MATRIX"),
        ("flowchart_equivalent", "Flowchart scenario is equivalent in Vue and React", "boolean", "Implement the same nodes, edges, editing and state synchronization fixture.", "FRONTEND_POC_MATRIX"),
        ("decision_table_equivalent", "Decision-table scenario is equivalent in Vue and React", "boolean", "Implement the same editable rule-table fixture and validation behavior.", "FRONTEND_POC_MATRIX"),
        ("monitoring_view_equivalent", "Monitoring scenario is equivalent in Vue and React", "boolean", "Render the same metrics, filters, refresh and failure states.", "FRONTEND_POC_MATRIX"),
        ("sse_websocket_equivalent", "SSE/WebSocket scenario is equivalent in Vue and React", "boolean", "Exercise the same streaming updates, reconnect and error behavior.", "FRONTEND_POC_MATRIX"),
        ("player_integration_equivalent", "Player integration scenario is equivalent in Vue and React", "boolean", "Embed the same player/Web Component contract and event handling.", "FRONTEND_POC_MATRIX"),
        ("mobile_experience_equivalent", "Mobile/responsive scenario is equivalent in Vue and React", "boolean", "Exercise the same responsive breakpoints and touch interactions.", "FRONTEND_POC_MATRIX"),
        ("permission_model_equivalent", "Permission-aware UI scenario is equivalent in Vue and React", "boolean", "Exercise the same route, field and action visibility matrix without treating UI hiding as authorization.", "FRONTEND_POC_MATRIX"),
        ("design_token_equivalent", "Design-token scenario is equivalent in Vue and React", "boolean", "Apply the same theme/token set and verify consistent component styling and switching.", "FRONTEND_POC_MATRIX"),
    ],
    "POC-009": [
        ("provider_budget_limit", "Tested external-provider budget ceiling", "currency", "Record the approved numeric budget ceiling and period used by the hard-budget gate.", "NFR-V1-CAP-004"),
        ("provider_request_rate_limit", "Tested external-provider request-rate ceiling", "requests_per_minute", "Record the approved numeric request-rate ceiling exercised by the quota gate.", "NFR-V1-CAP-004"),
        ("provider_concurrency_limit", "Tested external-provider concurrency ceiling", "requests", "Record the approved numeric concurrent-call ceiling exercised by admission control.", "NFR-V1-CAP-004"),
        ("asr_wer", "Automatic speech recognition word error rate", "ratio", "Compute WER on the approved de-identified speech strata.", "ACCEPTANCE_TRACE_V1"),
        ("asr_cer", "Automatic speech recognition character error rate", "ratio", "Compute CER on the approved language/media-quality strata.", "ACCEPTANCE_TRACE_V1"),
        ("speaker_der", "Speaker diarization error rate", "ratio", "Compute DER on the approved multi-speaker fixture.", "ACCEPTANCE_TRACE_V1"),
        ("translation_comet", "Translation COMET score", "score", "Compute COMET on the approved language-pair fixture.", "ACCEPTANCE_TRACE_V1"),
        ("translation_bleu", "Translation BLEU score", "score", "Compute BLEU on the same immutable translation fixture.", "ACCEPTANCE_TRACE_V1"),
        ("ocr_accuracy", "OCR field/text accuracy", "ratio", "Measure OCR accuracy across approved image-quality and document-layout strata.", "ACCEPTANCE_TRACE_V1"),
        ("factual_consistency", "Generated summary or description factual consistency", "ratio", "Score factual consistency against approved references with reviewer protocol recorded.", "ACCEPTANCE_TRACE_V1"),
        ("tag_f1", "Automatic tag F1", "ratio", "Compute F1 against the approved multilabel tag fixture.", "ACCEPTANCE_TRACE_V1"),
        ("thumbnail_human_selection_rate", "Thumbnail human-selection rate", "ratio", "Measure independent reviewer selection of generated thumbnails on the approved fixture.", "ACCEPTANCE_TRACE_V1"),
        ("multimodal_correction_accuracy", "Multimodal correction accuracy", "ratio", "Measure accepted corrections against the approved multimodal error fixture.", "ACCEPTANCE_TRACE_V1"),
        ("quality_strata_coverage", "Required language, media-quality, duration and scenario strata are covered", "boolean", "Prove every frozen evaluation stratum has the required sample count and metric results.", "ACCEPTANCE_TRACE_V1"),
    ],
    "POC-010": [
        ("playback_restore", "Playback capability and authorization recover correctly", "boolean", "Verify representative authorized playback and Range behavior after restore.", "RECOVERY_DESIGN"),
        ("ai_manual_revisions_restore", "AI outputs and manual revision history recover correctly", "boolean", "Compare restored AI provenance, results and human revision records with the pre-backup manifest.", "RECOVERY_DESIGN"),
        ("search_index_consistency_restore", "Search index is consistent with restored authoritative state", "boolean", "Reconcile indexed assets/metadata with restored authoritative records and prove no stale or missing governed entries.", "RECOVERY_DESIGN"),
        ("image_signature_restore", "Deployment image and bundle signatures verify after restore", "boolean", "Verify restored image/bundle digests and signatures against the approved manifest.", "RECOVERY_DESIGN"),
        ("service_recovery_time", "Observed service recovery time", "s", "Measure from recovery start until required services are healthy.", "NFR-V1-AVL-002"),
        ("vm_recovery_time", "Observed VM recovery time", "s", "Measure from recovery start until the required VM set is available and healthy.", "NFR-V1-AVL-002"),
        ("core_browsing_recovery_time", "Observed core browsing recovery time", "s", "Measure until authenticated core asset browsing succeeds against restored state.", "NFR-V1-AVL-002"),
        ("playback_recovery_time", "Observed playback recovery time", "s", "Measure until representative authorized playback succeeds.", "NFR-V1-AVL-002"),
    ],
}

CRITERIA = {
    "POC-001": [
        "Inspur 5212 BIOS virtualization/IOMMU, Above 4G and Resizable BAR settings are captured and match the tested passthrough baseline.",
        "The A380 IOMMU group is isolated sufficiently for the approved passthrough design.",
        "The observed multi-day soak duration is recorded and completes without unrecovered passthrough, host, guest, driver or media-runtime failure.",
    ],
    "POC-002": [
        "A380-backed Range first-byte latency is measured with the encoder provenance and public/origin path recorded.",
        "Peak encoder power and temperature are recorded across warmup, concurrency and soak phases.",
    ],
    "POC-003": [
        "Hot-cache, cold-cache, slow-origin and multi-user Range latency are measured separately under the frozen NFR-V1-PERF-002 scenarios.",
    ],
    "POC-004": [
        "Incomplete and hash-mismatched copies cannot be promoted to formal replicas.",
        "Cache eviction preserves authoritative asset metadata, retention state and formal replicas.",
        "Replica migration retains the old valid copy until the new copy is verified.",
    ],
    "POC-005": [
        "Filename/path and provider characteristics, Range support and ETag/version semantics are captured for the tested source profile.",
    ],
    "POC-006": [
        "429, 5xx and network failures are classified and recover through bounded retry without duplicate logical objects.",
        "Interrupted synchronization resumes from a safe checkpoint or reruns idempotently.",
        "Source deletion preserves the logical asset and records governed source-unavailable state.",
    ],
    "POC-008": [
        "Vue and React are compared on the same frozen ten-scenario matrix: million-row virtualization, dynamic forms, flowchart, decision table, monitoring, SSE/WebSocket, player, mobile, permissions and design tokens.",
    ],
    "POC-009": [
        "The tested numeric budget, request-rate and concurrency ceilings are recorded and the corresponding fail-closed gates are exercised against those values.",
        "WER, CER, DER, COMET, BLEU, OCR accuracy, factual consistency, tag F1, thumbnail human selection and multimodal correction are recorded for all required language, quality, duration and scenario strata.",
    ],
    "POC-010": [
        "Playback, AI/manual revision history, search-index consistency and image/bundle signatures are verified after restore.",
        "Service, VM, core-browsing and playback recovery times are measured separately in addition to overall RTO.",
    ],
}


def repair_plans() -> dict[str, set[str]]:
    if set(ADDITIONS) != set(CRITERIA):
        raise SystemExit("plan/criteria repair sets differ")
    for task_id, items in ADDITIONS.items():
        path = PLAN_DIR / f"{task_id}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        measurements = data["protocol"]["measurements"]
        existing = {item["id"] for item in measurements}
        for item_id, metric, unit, method, source in items:
            if item_id not in existing:
                measurements.append({
                    "id": item_id,
                    "metric": metric,
                    "unit": unit,
                    "method": method,
                    "thresholdSource": source,
                    "actual": None,
                })
        exits = data["protocol"]["exitCriteria"]
        for statement in CRITERIA[task_id]:
            if statement not in exits:
                exits.append(statement)
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=140),
            encoding="utf-8",
        )

    plan_sets: dict[str, set[str]] = {}
    for path in sorted(PLAN_DIR.glob("POC-*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        ids = [item["id"] for item in data["protocol"]["measurements"]]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"duplicate measurement IDs in {path.name}")
        plan_sets[data["pocId"]] = set(ids)
    if set(plan_sets) != {f"POC-{index:02d}" for index in range(1, 11)}:
        raise SystemExit("canonical POC plan set changed")
    return plan_sets


def freeze_measurements(plan_sets: dict[str, set[str]]) -> None:
    checker = ROOT / "specs" / "poc" / "check_program.py"
    text = checker.read_text(encoding="utf-8")
    start = text.index("REQUIRED_MEASUREMENTS = {")
    end = text.index("\nREQUIRED_ENV = {", start)
    block = ["REQUIRED_MEASUREMENTS = {"]
    for poc_id in sorted(plan_sets):
        block.append(f'    "{poc_id}": {{')
        ids = sorted(plan_sets[poc_id])
        for offset in range(0, len(ids), 3):
            block.append("        " + ", ".join(repr(value) for value in ids[offset:offset + 3]) + ",")
        block.append("    },")
    block.append("}")
    checker.write_text(text[:start] + "\n".join(block) + text[end:], encoding="utf-8")


def add_regression_test() -> None:
    tests = ROOT / "specs" / "poc" / "test_program.py"
    text = tests.read_text(encoding="utf-8")
    if "def test_86_every_frozen_measurement_id_is_required" in text:
        return
    marker = '\n\nif __name__ == "__main__":\n'
    if text.count(marker) != 1:
        raise SystemExit("cannot locate unittest main marker")
    method = dedent('''
        def test_86_every_frozen_measurement_id_is_required(self):
            for poc_id, required_ids in sorted(CHECK.REQUIRED_MEASUREMENTS.items()):
                task_id = f"POC-{int(poc_id.split('-')[1]):03d}"
                for measurement_id in sorted(required_ids):
                    with self.subTest(pocId=poc_id, measurementId=measurement_id):
                        temp, root = self.temp_repo()
                        try:
                            baseline = CHECK.validate_repository(root)
                            self.assertEqual(baseline, [], "\\n".join(baseline))
                            path = self.plan_path(root, task_id)
                            data = load_yaml(path)
                            data["protocol"]["measurements"] = [
                                item for item in data["protocol"]["measurements"]
                                if item["id"] != measurement_id
                            ]
                            write_yaml(path, data)
                            errors = CHECK.validate_repository(root)
                            self.assertTrue(
                                any("missing frozen required measurements" in error for error in errors),
                                "\\n".join(errors),
                            )
                        finally:
                            temp.cleanup()
    ''').lstrip("\n")
    text = text.replace(marker, "\n\n" + indent(method, "    ") + marker, 1)
    tests.write_text(text, encoding="utf-8")


def main() -> None:
    plan_sets = repair_plans()
    freeze_measurements(plan_sets)
    add_regression_test()


if __name__ == "__main__":
    main()

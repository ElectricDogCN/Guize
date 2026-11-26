BEGIN;

INSERT INTO source.data_source (id, name, kind, owner_id, status, endpoint, root_path)
VALUES ('src_storage', 'Synthetic storage input', 'LOCAL', 'usr_storage', 'ACTIVE', 'mount:storage', 'media');
INSERT INTO asset.asset (id, canonical_title, asset_type, lifecycle_status)
VALUES ('ast_storage', 'Synthetic media', 'VIDEO', 'ACTIVE');
INSERT INTO source.object (id, data_source_id, asset_id, provider_object_id, current_path, current_filename,
                           size_bytes, etag, last_seen_at, sync_status, availability_status)
VALUES ('obj_storage', 'src_storage', 'ast_storage', 'source-storage', '/fixture.mp4', 'fixture.mp4',
        octet_length('v8-fixture-media'), 'fixture-etag', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE');
INSERT INTO asset.version (id, asset_id, version_number, origin_source_object_id, content_length,
                           mime_type, hash_status, created_reason)
VALUES ('ver_storage', 'ast_storage', 1, 'obj_storage', octet_length('v8-fixture-media'),
        'video/mp4', 'FULL_VERIFIED', 'INITIAL');
UPDATE asset.asset SET current_version_id = 'ver_storage' WHERE id = 'ast_storage';
INSERT INTO asset.content_hash (asset_version_id, algorithm, hash_value, scope, verified_at)
VALUES ('ver_storage', 'SHA256', encode(sha256(convert_to('v8-fixture-media', 'UTF8')), 'hex'), 'FULL', CURRENT_TIMESTAMP);

INSERT INTO media.profile (id, profile_key, version, parameters, parameters_sha256, approved_at)
VALUES ('prof_storage', 'prof_av1', 1, '{"codec":"av1"}',
        encode(sha256(convert_to('{"codec":"av1"}', 'UTF8')), 'hex'), CURRENT_TIMESTAMP);
INSERT INTO media.rendition (id, asset_version_id, kind, codec, container, tool_version, profile_version_id,
                             input_sha256, output_sha256, size_bytes, quality_status, publication_status)
SELECT 'rend_storage', 'ver_storage', 'AV1_MASTER', 'av1', 'mp4', 'fixture-tool-v1', 'prof_storage',
       hash_value, encode(sha256(convert_to('v8-fixture-render', 'UTF8')), 'hex'),
       octet_length('v8-fixture-render'), 'PENDING', 'DRAFT'
FROM asset.content_hash WHERE asset_version_id = 'ver_storage';
INSERT INTO media.track (rendition_id, track_number, kind, codec, duration_ms)
VALUES ('rend_storage', 0, 'VIDEO', 'av1', 1000);

DO $$
BEGIN
    BEGIN
        UPDATE media.rendition SET quality_status = 'PASS', quality_revision = 7, publication_status = 'PUBLISHED'
        WHERE id = 'rend_storage';
        RAISE EXCEPTION 'published rendition without evaluation';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE media.profile SET parameters = '{}' WHERE id = 'prof_storage';
        RAISE EXCEPTION 'approved profile rewrite passed';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;

INSERT INTO media.quality_result (rendition_id, evaluation_revision, status, evidence_id, evaluated_at)
VALUES ('rend_storage', 1, 'PASS', 'evid_storage_quality', CURRENT_TIMESTAMP);
UPDATE media.rendition SET quality_status = 'PASS', quality_revision = 1, publication_status = 'PUBLISHED'
WHERE id = 'rend_storage';

INSERT INTO storage.backend (id, purpose, failure_domain_id, target_ref, connector_kind, storage_class)
VALUES ('stg_cache', 'CACHE', 'fd_local', 'target_temp', 'LOCAL', 'HOT'),
       ('stg_primary', 'FORMAL', 'fd_first', 'target_first', 'LOCAL', 'HOT'),
       ('stg_same_domain', 'FORMAL', 'fd_first', 'target_same_domain', 'LOCAL', 'WARM'),
       ('stg_second', 'FORMAL', 'fd_second', 'target_second', 'WEBDAV', 'COLD'),
       ('stg_quarantine', 'FORMAL', 'fd_quarantine', 'target_quarantine', 'LOCAL', 'OFFLINE');
INSERT INTO storage.retention_policy (id, policy_key, version, minimum_retention_seconds, created_at)
VALUES ('pol_storage', 'pol_retention', 1, 86400, CURRENT_TIMESTAMP);
INSERT INTO storage.watermark_event (id, backend_id, level, available_bytes, observed_at)
VALUES ('wm_storage', 'stg_cache', 'WARNING', 500, CURRENT_TIMESTAMP);

INSERT INTO storage.cache_entry (id, asset_version_id, backend_id, object_key, cache_class, state, size_bytes, expires_at)
VALUES ('cache_ordinary', 'ver_storage', 'stg_cache', 'fixture/ordinary', 'FULL_FILE', 'VALIDATING', 0, CURRENT_TIMESTAMP - interval '1 hour'),
       ('cache_pinned', 'ver_storage', 'stg_cache', 'fixture/pinned', 'PINNED_FILE', 'VALIDATING', 0, CURRENT_TIMESTAMP - interval '1 hour'),
       ('cache_fresh', 'ver_storage', 'stg_cache', 'fixture/fresh', 'FULL_FILE', 'VALIDATING', 0, CURRENT_TIMESTAMP + interval '1 hour');

CREATE FUNCTION pg_temp.measure_cache(p_id task.identifier, p_size bigint, p_hash text, p_evidence task.identifier)
RETURNS void LANGUAGE sql AS $$
    UPDATE storage.cache_entry SET state = CASE cache_class WHEN 'FULL_FILE' THEN 'COMPLETE_CACHE' ELSE 'PINNED_CACHE' END,
        size_bytes = p_size, verified_size_bytes = p_size, verification_algorithm = 'SHA256',
        verification_sha256_or_blake3 = p_hash, verification_evidence_id = p_evidence,
        verified_at = clock_timestamp(), verification_trace_id = 'trace-storage-cache', revision = revision + 1
    WHERE id = p_id;
$$;

DO $$
DECLARE
    actual_digest text := encode(sha256(convert_to('v8-fixture-media', 'UTF8')), 'hex');
    actual_length bigint := octet_length('v8-fixture-media');
    violated text;
BEGIN
    BEGIN
        INSERT INTO storage.cache_entry (id, asset_version_id, backend_id, object_key, cache_class, state, size_bytes, expires_at)
        VALUES ('cache_wrong_backend', 'ver_storage', 'stg_primary', 'fixture/isolated', 'FULL_FILE', 'VALIDATING', 0, CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'formal backend accepted as cache';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'cache_entry_backend' THEN RAISE; END IF;
    END;
    BEGIN
        PERFORM pg_temp.measure_cache('cache_ordinary', actual_length - 1, actual_digest, 'evid_partial');
        RAISE EXCEPTION 'partial readback accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'cache_entry_authoritative_readback' THEN RAISE; END IF;
    END;
    BEGIN
        PERFORM pg_temp.measure_cache('cache_ordinary', actual_length, repeat('0',64), 'evid_wrong_hash');
        RAISE EXCEPTION 'wrong cache hash accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'cache_entry_authoritative_readback' THEN RAISE; END IF;
    END;
    ALTER TABLE outbox.event ADD CONSTRAINT fixture_deny_cache_event CHECK (event_type <> 'cache.complete.verified');
    BEGIN
        PERFORM pg_temp.measure_cache('cache_ordinary', actual_length, actual_digest, 'evid_rolled_cache');
        RAISE EXCEPTION 'cache survived failing event';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'fixture_deny_cache_event' THEN RAISE; END IF;
    END;
    IF NOT EXISTS (SELECT 1 FROM storage.cache_entry WHERE id = 'cache_ordinary' AND state = 'VALIDATING' AND revision = 1)
    THEN RAISE EXCEPTION 'cache advance failed to roll back'; END IF;
    ALTER TABLE outbox.event DROP CONSTRAINT fixture_deny_cache_event;
    PERFORM pg_temp.measure_cache('cache_ordinary', actual_length, actual_digest, 'evid_cache_ordinary');
    PERFORM pg_temp.measure_cache('cache_pinned', actual_length, actual_digest, 'evid_cache_pinned');
    PERFORM pg_temp.measure_cache('cache_fresh', actual_length, actual_digest, 'evid_cache_fresh');
END;
$$;

INSERT INTO storage.replica (id, rendition_id, backend_id, failure_domain_id, object_key, replica_class,
                             status, size_bytes, expected_sha256)
SELECT seed.id, rendition.id, seed.backend_id, seed.failure_domain, 'fixture/render', seed.replica_class,
       'PLANNED', rendition.size_bytes, rendition.output_sha256
FROM media.rendition rendition CROSS JOIN (VALUES
    ('rep_first', 'stg_primary', 'fd_first', 'HOT_FORMAL'),
    ('rep_same', 'stg_same_domain', 'fd_first', 'HOT_FORMAL'),
    ('rep_other', 'stg_second', 'fd_second', 'COLD_CLOUD'),
    ('rep_quarantine', 'stg_quarantine', 'fd_quarantine', 'QUARANTINE')
) AS seed(id, backend_id, failure_domain, replica_class) WHERE rendition.id = 'rend_storage';

CREATE FUNCTION pg_temp.measure_replica(p_id task.identifier, p_size bigint, p_hash text, p_evidence task.identifier)
RETURNS void LANGUAGE sql AS $$
    UPDATE storage.replica SET status = 'VERIFIED', readback_size_bytes = p_size, readback_sha256 = p_hash,
        verification_evidence_id = p_evidence, verified_at = clock_timestamp(), verification_trace_id = 'trace-storage-replica',
        revision = revision + 1 WHERE id = p_id;
$$;

UPDATE storage.replica SET status = 'VERIFYING', revision = revision + 1 WHERE id <> 'rep_other';
UPDATE storage.replica SET status = 'UPLOADED_UNVERIFIED', revision = revision + 1 WHERE id = 'rep_other';

DO $$
DECLARE
    actual_digest text := encode(sha256(convert_to('v8-fixture-render', 'UTF8')), 'hex');
    actual_length bigint := octet_length('v8-fixture-render');
    violated text;
BEGIN
    PERFORM pg_temp.measure_replica('rep_first', actual_length, actual_digest, 'evid_rep_first');
    PERFORM pg_temp.measure_replica('rep_same', actual_length, actual_digest, 'evid_rep_same');
    PERFORM pg_temp.measure_replica('rep_quarantine', actual_length, actual_digest, 'evid_rep_quarantine');
    BEGIN
        PERFORM pg_temp.measure_replica('rep_other', actual_length, actual_digest, 'evid_upload_only');
        RAISE EXCEPTION 'upload alone produced a verified replica';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'replica_transition' THEN RAISE; END IF;
    END;
    BEGIN
        UPDATE storage.replica SET status = 'DELETING', revision = revision + 1 WHERE id = 'rep_first';
        RAISE EXCEPTION 'same-domain, unverified or quarantined copy qualified for retention';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'replica_removal_protected' THEN RAISE; END IF;
    END;
    UPDATE storage.replica SET status = 'VERIFYING', revision = revision + 1 WHERE id = 'rep_other';
    BEGIN
        PERFORM pg_temp.measure_replica('rep_other', actual_length, repeat('0',64), 'evid_wrong_replica_hash');
        RAISE EXCEPTION 'incompatible replica readback accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    ALTER TABLE outbox.event ADD CONSTRAINT fixture_deny_other_replica_event
        CHECK (event_type <> 'replica.verified' OR aggregate_id <> 'rep_other');
    BEGIN
        PERFORM pg_temp.measure_replica('rep_other', actual_length, actual_digest, 'evid_rolled_replica');
        RAISE EXCEPTION 'replica survived failing event';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'fixture_deny_other_replica_event' THEN RAISE; END IF;
    END;
    IF NOT EXISTS (SELECT 1 FROM storage.replica WHERE id = 'rep_other' AND status = 'VERIFYING' AND revision = 3)
    THEN RAISE EXCEPTION 'replica advance did not roll back'; END IF;
    ALTER TABLE outbox.event DROP CONSTRAINT fixture_deny_other_replica_event;
    PERFORM pg_temp.measure_replica('rep_other', actual_length, actual_digest, 'evid_rep_other');
END;
$$;

UPDATE storage.replica SET status = 'DEGRADED', revision = revision + 1 WHERE id = 'rep_same';
INSERT INTO storage.migration (id, rendition_id, from_replica_id, to_replica_id, status, requested_at)
VALUES ('mig_storage', 'rend_storage', 'rep_first', 'rep_other', 'SUCCEEDED', CURRENT_TIMESTAMP);
INSERT INTO storage.retention_hold (id, asset_id, policy_version_id, reason, created_at)
VALUES ('hold_storage', 'ast_storage', 'pol_storage', 'Synthetic test hold', CURRENT_TIMESTAMP);

DO $$
DECLARE
    violated text;
BEGIN
    BEGIN
        UPDATE storage.replica SET status = 'DELETING', revision = revision + 1 WHERE id = 'rep_first';
        RAISE EXCEPTION 'active hold allowed formal removal';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'replica_removal_protected' THEN RAISE; END IF;
    END;
END;
$$;

CREATE ROLE gz_fixture_cache_eviction NOLOGIN;
GRANT USAGE ON SCHEMA storage, task TO gz_fixture_cache_eviction;
SET LOCAL ROLE gz_fixture_cache_eviction;
DO $$
BEGIN
    IF has_function_privilege('storage.advance_expired_cache(task.identifier,bigint,text)', 'EXECUTE') THEN
        RAISE EXCEPTION 'cache function grants public execution';
    END IF;
END;
$$;
RESET ROLE;
GRANT EXECUTE ON FUNCTION storage.advance_expired_cache(task.identifier, bigint, text) TO gz_fixture_cache_eviction;
SET LOCAL ROLE gz_fixture_cache_eviction;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper)
        OR has_any_column_privilege('storage.replica', 'SELECT,UPDATE')
        OR has_table_privilege('storage.replica', 'INSERT,DELETE')
        OR has_any_column_privilege('storage.retention_hold', 'UPDATE')
        OR has_any_column_privilege('storage.cache_entry', 'UPDATE')
    THEN RAISE EXCEPTION 'cache evictor has direct data privileges'; END IF;
    IF storage.advance_expired_cache('cache_pinned', 2, 'EVICTING') IS NOT NULL
        OR storage.advance_expired_cache('cache_fresh', 2, 'EVICTING') IS NOT NULL
        OR storage.advance_expired_cache('cache_ordinary', 2, 'EVICTED') IS NOT NULL
        OR storage.advance_expired_cache('cache_ordinary', 2, 'EVICTING') IS DISTINCT FROM 3
        OR storage.advance_expired_cache('cache_ordinary', 2, 'EVICTING') IS DISTINCT FROM 3
        OR storage.advance_expired_cache('cache_ordinary', 3, 'EVICTED') IS DISTINCT FROM 4
    THEN RAISE EXCEPTION 'cache eviction lifecycle failed'; END IF;
END;
$$;
RESET ROLE;
REVOKE EXECUTE ON FUNCTION storage.advance_expired_cache(task.identifier, bigint, text) FROM gz_fixture_cache_eviction;
REVOKE USAGE ON SCHEMA storage, task FROM gz_fixture_cache_eviction;
DROP ROLE gz_fixture_cache_eviction;

DO $$
BEGIN
    IF (SELECT count(*) FROM storage.replica WHERE status = 'VERIFIED') <> 3
        OR NOT EXISTS (SELECT 1 FROM storage.retention_hold WHERE id = 'hold_storage' AND released_at IS NULL AND revision = 1)
        OR NOT EXISTS (SELECT 1 FROM asset.asset WHERE id = 'ast_storage' AND current_version_id = 'ver_storage' AND revision = 1)
        OR NOT EXISTS (SELECT 1 FROM storage.cache_entry WHERE id = 'cache_ordinary' AND state = 'EVICTED' AND revision = 4)
    THEN RAISE EXCEPTION 'cache eviction affected formal state'; END IF;
END;
$$;

UPDATE storage.retention_hold SET released_at = clock_timestamp(), revision = revision + 1 WHERE id = 'hold_storage';

SAVEPOINT retain_deadline;
UPDATE storage.replica SET retention_until = CURRENT_TIMESTAMP + interval '1 hour', revision = revision + 1 WHERE id = 'rep_first';
DO $$
BEGIN
    BEGIN
        UPDATE storage.replica SET status = 'DELETING', retention_until = CURRENT_TIMESTAMP - interval '1 hour',
                                   revision = revision + 1 WHERE id = 'rep_first';
        RAISE EXCEPTION 'formal removal shortened an active retention deadline';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;
ROLLBACK TO SAVEPOINT retain_deadline;
RELEASE SAVEPOINT retain_deadline;

SAVEPOINT late_hold;
UPDATE storage.replica SET status = 'DELETING', revision = revision + 1 WHERE id = 'rep_first';
INSERT INTO storage.retention_hold (id, asset_id, policy_version_id, reason, created_at)
VALUES ('hold_late', 'ast_storage', 'pol_storage', 'Synthetic late hold', CURRENT_TIMESTAMP);
DO $$
BEGIN
    BEGIN
        UPDATE storage.replica SET status = 'DELETED', revision = revision + 1 WHERE id = 'rep_first';
        RAISE EXCEPTION 'formal removal completed under a late hold';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;
ROLLBACK TO SAVEPOINT late_hold;
RELEASE SAVEPOINT late_hold;

SELECT envelope FROM outbox.event_envelope
WHERE envelope->>'eventType' IN ('cache.complete.verified', 'replica.verified')
ORDER BY envelope->>'aggregateType', envelope->>'aggregateId';

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

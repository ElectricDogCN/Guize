BEGIN;

INSERT INTO source.data_source (id, name, kind, owner_id, status)
VALUES ('src_sync', 'Synthetic WebDAV', 'WEBDAV', 'usr_sync', 'ACTIVE'),
       ('src_isolated', 'Separate synthetic source', 'LOCAL', 'usr_sync', 'ACTIVE');

INSERT INTO source.capability (data_source_id, capability, connector_version, observed_at)
VALUES ('src_sync', 'LIST', '1.0.0', CURRENT_TIMESTAMP),
       ('src_sync', 'RANGE_READ', '1.0.0', CURRENT_TIMESTAMP);

INSERT INTO source.credential_reference (data_source_id, credential_reference, revision, updated_at)
VALUES ('src_sync', 'secretref_fixture_only', 1, CURRENT_TIMESTAMP);

INSERT INTO source.sync_policy (data_source_id, revision, scan_interval_seconds, max_attempts, created_at)
VALUES ('src_sync', 1, 300, 3, CURRENT_TIMESTAMP),
       ('src_sync', 2, 600, 2, CURRENT_TIMESTAMP),
       ('src_isolated', 1, NULL, 2, CURRENT_TIMESTAMP);

INSERT INTO task.task (id, type, owner_id, idempotency_scope, idempotency_key, status, priority, trace_id)
SELECT id, 'source.sync.v1', 'usr_sync', 'fixture-source-sync', id, 'RUNNING', 4, 'trace-source-sync'
FROM unnest(ARRAY['tsk_observe','tsk_reconcile','tsk_isolated','tsk_subfolder','tsk_nextpolicy']) AS ids(id);

INSERT INTO source.sync_request (task_id, data_source_id, policy_revision, scope_key, mode)
VALUES ('tsk_observe', 'src_sync', 1, 'root', 'INCREMENTAL'),
       ('tsk_reconcile', 'src_sync', 1, 'root', 'RECONCILE'),
       ('tsk_isolated', 'src_isolated', 1, 'root', 'INCREMENTAL'),
       ('tsk_subfolder', 'src_sync', 1, 'separate-scope', 'INCREMENTAL'),
       ('tsk_nextpolicy', 'src_sync', 2, 'root', 'INCREMENTAL');

INSERT INTO source.sync_job (id, task_id, data_source_id, policy_revision, scope_key, mode, attempt_number, status, started_at)
VALUES ('job_first', 'tsk_observe', 'src_sync', 1, 'root', 'INCREMENTAL', 1, 'RUNNING', CURRENT_TIMESTAMP),
       ('job_isolated', 'tsk_isolated', 'src_isolated', 1, 'root', 'INCREMENTAL', 1, 'RUNNING', CURRENT_TIMESTAMP),
       ('job_subfolder', 'tsk_subfolder', 'src_sync', 1, 'separate-scope', 'INCREMENTAL', 1, 'RUNNING', CURRENT_TIMESTAMP);

DO $$
DECLARE
    violated_constraint text;
BEGIN
    IF EXISTS (SELECT 1 FROM asset.version) THEN RAISE EXCEPTION 'Source sync seeded an asset version'; END IF;
    BEGIN
        INSERT INTO task.task (id, type, owner_id, idempotency_scope, idempotency_key, status, priority, trace_id)
        VALUES ('tsk_media', 'media.transcode.v1', 'usr_sync', 'fixture-source-sync', 'media', 'RUNNING', 4, 'trace-source-sync');
        RAISE EXCEPTION 'asset-less media task passed';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'task_input_version_required' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO source.sync_job (id, task_id, data_source_id, policy_revision, scope_key, mode, attempt_number, status, started_at)
        VALUES ('job_wrongsrc', 'tsk_observe', 'src_isolated', 1, 'root', 'INCREMENTAL', 2, 'RUNNING', CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'retry changed its source';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'sync_job_request_scope' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO source.sync_job (id, task_id, data_source_id, policy_revision, scope_key, mode, attempt_number, status, started_at)
        VALUES ('job_reconcile', 'tsk_reconcile', 'src_sync', 1, 'root', 'RECONCILE', 1, 'RUNNING', CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'same source scope allowed competing active work';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'sync_job_running_scope_idx' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO source.sync_checkpoint (data_source_id, policy_revision, scope_key, mode, revision, cursor_value, job_id, updated_at)
        VALUES ('src_isolated', 1, 'root', 'INCREMENTAL', 1, 'fixture-wrong-source', 'job_first', CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'checkpoint accepted another source job';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'sync_checkpoint_job_scope' THEN RAISE; END IF;
    END;
    IF source.record_sync_checkpoint('job_first', 0, repeat(chr(27700), 4096)) <> 1
        OR source.record_sync_checkpoint('job_isolated', 0, 'fixture-other-source') <> 1
        OR source.record_sync_checkpoint('job_subfolder', 0, 'fixture-other-scope') <> 1
    THEN RAISE EXCEPTION 'independent first checkpoint failed'; END IF;

    BEGIN
        INSERT INTO asset.asset (id, canonical_title, asset_type, lifecycle_status)
        VALUES ('ast_uncommitted', 'Page observation roll back', 'VIDEO', 'ACTIVE');
        PERFORM source.record_sync_checkpoint('job_first', 0, 'fixture-stale-cursor');
        RAISE EXCEPTION 'stale checkpoint committed';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    IF EXISTS (SELECT 1 FROM asset.asset WHERE id = 'ast_uncommitted') THEN
        RAISE EXCEPTION 'stale checkpoint failed to roll back page writes';
    END IF;
END;
$$;

UPDATE source.sync_job SET status = 'PARTIAL_SUCCESS', finished_at = clock_timestamp() WHERE id = 'job_first';
INSERT INTO source.sync_job (id, task_id, data_source_id, policy_revision, scope_key, mode, attempt_number, status, started_at)
VALUES ('job_retry', 'tsk_observe', 'src_sync', 1, 'root', 'INCREMENTAL', 2, 'RUNNING', clock_timestamp());

DO $$
DECLARE
    violated_constraint text;
BEGIN
    BEGIN
        PERFORM source.record_sync_checkpoint('job_first', 1, 'fixture-finished-job');
        RAISE EXCEPTION 'finished job committed';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    BEGIN
        UPDATE source.sync_job SET status = 'RUNNING', finished_at = NULL WHERE id = 'job_first';
        RAISE EXCEPTION 'finished job reactivated';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'sync_job_transition' THEN RAISE; END IF;
    END;
    IF source.record_sync_checkpoint('job_retry', 1, 'fixture-resumed') <> 2 THEN
        RAISE EXCEPTION 'retry could not resume existing cursor';
    END IF;
END;
$$;

UPDATE source.sync_job SET status = 'SUCCEEDED', finished_at = clock_timestamp() WHERE id = 'job_retry';
INSERT INTO source.sync_job (id, task_id, data_source_id, policy_revision, scope_key, mode, attempt_number, status, started_at)
VALUES ('job_reconcile', 'tsk_reconcile', 'src_sync', 1, 'root', 'RECONCILE', 1, 'RUNNING', clock_timestamp());

DO $$
BEGIN
    IF source.record_sync_checkpoint('job_reconcile', 0, NULL) <> 1 THEN
        RAISE EXCEPTION 'reconciliation did not have independent cursor';
    END IF;
END;
$$;

UPDATE source.sync_job SET status = 'SUCCEEDED', finished_at = clock_timestamp() WHERE id = 'job_reconcile';
INSERT INTO source.sync_job (id, task_id, data_source_id, policy_revision, scope_key, mode, attempt_number, status, started_at)
VALUES ('job_nextpolicy', 'tsk_nextpolicy', 'src_sync', 2, 'root', 'INCREMENTAL', 1, 'RUNNING', clock_timestamp());

DO $$
BEGIN
    IF source.record_sync_checkpoint('job_nextpolicy', 0, 'fixture-new-policy') <> 1 THEN
        RAISE EXCEPTION 'updated policy reused former cursor';
    END IF;
    UPDATE source.data_source SET status = 'REVOKED' WHERE id = 'src_isolated';
    BEGIN
        PERFORM source.record_sync_checkpoint('job_isolated', 1, 'fixture-revoked-source');
        RAISE EXCEPTION 'revoked source checkpoint accepted';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    IF (SELECT count(*) FROM source.sync_checkpoint) <> 5
        OR NOT EXISTS (
            SELECT 1 FROM source.sync_checkpoint WHERE data_source_id = 'src_sync' AND scope_key = 'root'
              AND policy_revision = 1 AND mode = 'INCREMENTAL' AND revision = 2
              AND cursor_value = 'fixture-resumed' AND job_id = 'job_retry'
        ) THEN RAISE EXCEPTION 'unexpected persisted checkpoint state'; END IF;
END;
$$;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

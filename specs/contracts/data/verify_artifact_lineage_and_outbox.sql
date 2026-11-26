BEGIN;

SELECT to_regclass('ai.pipeline') IS NOT NULL AS fixture_registry_present \gset
\if :fixture_registry_present
\ir ai_artifact_registry_fixture.sql
\endif

\ir task_resource_fixture.sql

INSERT INTO asset.version (
    id, asset_id, version_number, origin_source_object_id, content_length, mime_type, created_reason
)
VALUES ('ver_mismatch', 'ast_task', 2, 'obj_task', 64, 'video/mp4', 'CONTENT_CHANGED');

DO $$
DECLARE
    attempt_step bigint;
    other_step bigint;
    input_digest text := repeat('a', 64);
    manifest_digest text := repeat('b', 64);
    violated text;
BEGIN
    SELECT step_key INTO STRICT attempt_step FROM task.attempt WHERE id = 'att_first';
    SELECT step_key INTO STRICT other_step FROM task.attempt WHERE id = 'att_second';

    ALTER TABLE outbox.event ADD CONSTRAINT fixture_deny_attempt_event
        CHECK (event_type <> 'task.attempt.result.accepted');
    BEGIN
        PERFORM task.accept_attempt_result('att_first', 'node_first', 1, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_fixture', manifest_digest);
        RAISE EXCEPTION 'An outbox failure must reject task acceptance';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'fixture_deny_attempt_event' THEN RAISE; END IF;
    END;
    IF EXISTS (SELECT 1 FROM task.accepted_result WHERE step_key = attempt_step)
        OR EXISTS (SELECT 1 FROM task.lease WHERE attempt_id = 'att_first' AND ended_at IS NOT NULL)
    THEN
        RAISE EXCEPTION 'An outbox failure left persisted acceptance or a closed lease';
    END IF;
    ALTER TABLE outbox.event DROP CONSTRAINT fixture_deny_attempt_event;

    IF task.accept_attempt_result('att_first', 'node_first', 1, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_fixture', manifest_digest) <> 'ACCEPTED' THEN
        RAISE EXCEPTION 'The live attempt must be accepted';
    END IF;
    IF task.accept_attempt_result('att_first', 'node_first', 1, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_fixture', manifest_digest) <> 'REPLAYED'
        OR (SELECT count(*) FROM outbox.event WHERE aggregate_id = 'att_first') <> 1
        OR NOT EXISTS (SELECT 1 FROM task.lease WHERE attempt_id = 'att_first' AND ended_at IS NOT NULL)
    THEN
        RAISE EXCEPTION 'Exact result replay must reuse the accepted outcome and event';
    END IF;

    BEGIN
        INSERT INTO ai.derived_artifact (
            id, asset_version_id, producer_attempt_id, producer_step_key, manifest_id, manifest_sha256,
            manifest_entry_key, artifact_type
        ) VALUES ('art_unaccepted', 'ver_task', 'att_second', other_step, 'manifest_fixture', manifest_digest, 'result', 'OCR');
        RAISE EXCEPTION 'An unaccepted attempt must not create a derived artifact';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'artifact_accepted_manifest' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO ai.derived_artifact (
            id, asset_version_id, producer_attempt_id, producer_step_key, manifest_id, manifest_sha256,
            manifest_entry_key, artifact_type
        ) VALUES ('art_wronginput', 'ver_mismatch', 'att_first', attempt_step,
            'manifest_fixture', manifest_digest, 'result', 'OCR');
        RAISE EXCEPTION 'The artifact must bind the exact attempted input';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'artifact_producer_input' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO ai.derived_artifact (
            id, asset_version_id, producer_attempt_id, producer_step_key, manifest_id, manifest_sha256,
            manifest_entry_key, artifact_type
        ) VALUES ('art_wrongmanifest', 'ver_task', 'att_first', attempt_step,
            'manifest_fixture', repeat('c', 64), 'result', 'OCR');
        RAISE EXCEPTION 'The artifact must bind the accepted manifest digest';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'artifact_accepted_manifest' THEN RAISE; END IF;
    END;

    INSERT INTO ai.derived_artifact (
        id, asset_version_id, producer_attempt_id, producer_step_key, manifest_id, manifest_sha256,
        manifest_entry_key, artifact_type
    ) VALUES ('art_fixture', 'ver_task', 'att_first', attempt_step, 'manifest_fixture', manifest_digest, 'result', 'OCR');

    INSERT INTO ai.derived_artifact (
        id, asset_version_id, producer_attempt_id, producer_step_key, manifest_id, manifest_sha256,
        manifest_entry_key, artifact_type
    ) VALUES ('art_replay', 'ver_task', 'att_first', attempt_step, 'manifest_fixture', manifest_digest, 'result', 'OCR')
    ON CONFLICT (producer_attempt_id, manifest_entry_key) DO NOTHING;
    IF FOUND THEN
        RAISE EXCEPTION 'The same manifest entry must not acquire another artifact identity';
    END IF;
END;
$$;

INSERT INTO ai.derived_artifact_revision (
    artifact_id, revision, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence,
    uncertainty, generated, quality_status, publication_status, structured_payload, output_sha256, created_by, trace_id
) VALUES ('art_fixture', 1, 'model-v1', 'prompt-v1', 'pipeline_ocr', encode(sha256(convert_to('{}', 'UTF8')), 'hex'), 0.9,
    false, true, 'ACCEPTED', 'DRAFT', '{"text":"original"}', repeat('e', 64), 'usr_owner', 'trace-artifact');
UPDATE ai.derived_artifact SET current_revision = 1 WHERE id = 'art_fixture';

DO $$
DECLARE
    violated text;
BEGIN
    ALTER TABLE outbox.event ADD CONSTRAINT fixture_deny_artifact_event CHECK (event_type <> 'artifact.published');
    BEGIN
        INSERT INTO ai.derived_artifact_revision (
            artifact_id, revision, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence,
            uncertainty, generated, quality_status, publication_status, structured_payload,
            output_sha256, created_by, trace_id, created_at, published_at
        ) VALUES ('art_fixture', 2, 'model-v1', 'prompt-v1', 'pipeline_ocr', encode(sha256(convert_to('{}', 'UTF8')), 'hex'), 0.9,
            false, true, 'ACCEPTED', 'PUBLISHED', '{"text":"original"}',
            repeat('e', 64), 'usr_owner', 'trace-artifact', statement_timestamp(), statement_timestamp());
        UPDATE ai.derived_artifact SET current_revision = 2 WHERE id = 'art_fixture' AND current_revision = 1;
        RAISE EXCEPTION 'An outbox failure must reject artifact publication';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'fixture_deny_artifact_event' THEN RAISE; END IF;
    END;
    IF (SELECT current_revision FROM ai.derived_artifact WHERE id = 'art_fixture') <> 1
        OR EXISTS (SELECT 1 FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 2)
    THEN
        RAISE EXCEPTION 'Publication failure persisted part of the artifact transaction';
    END IF;
    ALTER TABLE outbox.event DROP CONSTRAINT fixture_deny_artifact_event;
END;
$$;

INSERT INTO ai.derived_artifact_revision (
    artifact_id, revision, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence,
    uncertainty, generated, quality_status, publication_status, structured_payload,
    output_sha256, created_by, trace_id, created_at, published_at
) VALUES ('art_fixture', 2, 'model-v1', 'prompt-v1', 'pipeline_ocr', encode(sha256(convert_to('{}', 'UTF8')), 'hex'), 0.9,
    false, true, 'ACCEPTED', 'PUBLISHED', '{"text":"original"}',
    repeat('e', 64), 'usr_owner', 'trace-artifact', statement_timestamp(), statement_timestamp());
UPDATE ai.derived_artifact SET current_revision = 2 WHERE id = 'art_fixture' AND current_revision = 1;

INSERT INTO ai.derived_artifact_revision (
    artifact_id, revision, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence,
    uncertainty, generated, quality_status, publication_status, structured_payload,
    output_sha256, created_by, trace_id, created_at, published_at
) VALUES ('art_fixture', 3, 'model-v1', 'prompt-v1', 'pipeline_ocr', encode(sha256(convert_to('{}', 'UTF8')), 'hex'), 0.9,
    false, false, 'ACCEPTED', 'PUBLISHED', '{"text":"corrected"}',
    repeat('f', 64), 'usr_editor', 'trace-edited', statement_timestamp(), statement_timestamp());
UPDATE ai.derived_artifact SET current_revision = 3 WHERE id = 'art_fixture' AND current_revision = 2;
UPDATE ai.derived_artifact SET current_revision = 3 WHERE id = 'art_fixture';

DO $$
DECLARE
    thumb record;
    violated text;
BEGIN
    FOR thumb IN
        SELECT * FROM (VALUES
            ('art_real', 'THUMBNAIL_REAL', false),
            ('art_generated', 'THUMBNAIL_GENERATED', true)
        ) AS cases(id, kind, expected_generated)
    LOOP
        INSERT INTO ai.derived_artifact (
            id, asset_version_id, producer_attempt_id, producer_step_key, manifest_id, manifest_sha256,
            manifest_entry_key, artifact_type
        )
        SELECT thumb.id, 'ver_task', attempt_id, step_key, artifact_manifest_id, artifact_manifest_sha256, thumb.id, thumb.kind
        FROM task.accepted_result WHERE attempt_id = 'att_first';
        BEGIN
            INSERT INTO ai.derived_artifact_revision (
                artifact_id, revision, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence,
                uncertainty, generated, quality_status, publication_status, content_reference,
                output_sha256, created_by, trace_id, created_at, published_at
            ) VALUES (thumb.id, 1, 'model-v1', 'prompt-v1', 'pipeline_ocr', encode(sha256(convert_to('{}', 'UTF8')), 'hex'), 1,
                false, NOT thumb.expected_generated, 'ACCEPTED', 'PUBLISHED', 'fixture-ref',
                repeat('e', 64), 'usr_owner', 'trace-thumbnail', statement_timestamp(), statement_timestamp());
            UPDATE ai.derived_artifact SET current_revision = 1 WHERE id = thumb.id;
            RAISE EXCEPTION 'A mismatched thumbnail must not become current or emit a publication event';
        EXCEPTION WHEN check_violation THEN
            GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
            IF violated <> 'artifact_thumbnail_generated' THEN RAISE; END IF;
        END;
        INSERT INTO ai.derived_artifact_revision (
            artifact_id, revision, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence,
            uncertainty, generated, quality_status, publication_status, content_reference,
            output_sha256, created_by, trace_id, created_at, published_at
        ) VALUES (thumb.id, 1, 'model-v1', 'prompt-v1', 'pipeline_ocr', encode(sha256(convert_to('{}', 'UTF8')), 'hex'), 1,
            false, thumb.expected_generated, 'ACCEPTED', 'PUBLISHED', 'fixture-ref',
            repeat('e', 64), 'usr_owner', 'trace-thumbnail', statement_timestamp(), statement_timestamp());
        UPDATE ai.derived_artifact SET current_revision = 1 WHERE id = thumb.id;
    END LOOP;
END;
$$;

DO $$
BEGIN
    BEGIN
        UPDATE ai.derived_artifact_revision SET structured_payload = '{"text":"overwrite"}'
            WHERE artifact_id = 'art_fixture' AND revision = 1;
        RAISE EXCEPTION 'Previously stored artifact content must remain immutable';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    IF NOT EXISTS (
        SELECT 1 FROM ai.derived_artifact_revision
        WHERE artifact_id = 'art_fixture' AND revision = 1 AND structured_payload = '{"text":"original"}'
    ) OR (SELECT count(*) FROM outbox.event) <> 5 THEN
        RAISE EXCEPTION 'Append-only revisions or exactly one event per publication failed';
    END IF;

    INSERT INTO outbox.consumer_offset (consumer_id, event_id) SELECT 'fixture-indexer', event_id FROM outbox.event;
    INSERT INTO outbox.consumer_offset (consumer_id, event_id) SELECT 'fixture-indexer', event_id FROM outbox.event
    ON CONFLICT (consumer_id, event_id) DO NOTHING;
    IF FOUND OR (SELECT count(*) FROM outbox.consumer_offset) <> 5 THEN
        RAISE EXCEPTION 'Exact event acknowledgement retry must be a no-op';
    END IF;
END;
$$;

SELECT envelope::text FROM outbox.event_envelope
ORDER BY envelope->>'eventType', envelope->>'aggregateId', (envelope->'payload'->>'revision')::int;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

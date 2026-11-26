BEGIN;

-- Seed at V9, then apply V10 before executing this transaction.
DO $$
DECLARE
    violated text;
BEGIN
    IF (SELECT count(*) FROM ai.derived_artifact_revision WHERE pipeline_stage_number IS NULL) <> 5
        OR EXISTS (SELECT 1 FROM ai.pipeline)
    THEN RAISE EXCEPTION 'old registry identity changed during migration'; END IF;
    BEGIN
        INSERT INTO ai.derived_artifact_revision (artifact_id, revision, legacy_parent_revision, model_id, model_version,
            prompt_version, pipeline_version_id, parameters_hash, confidence, uncertainty, generated, quality_status,
            publication_status, structured_payload, output_sha256, created_by, trace_id, created_at, published_at)
        SELECT artifact_id, 4, revision, model_id, model_version, prompt_version, pipeline_version_id, parameters_hash,
               confidence, uncertainty, false, quality_status, 'PUBLISHED', structured_payload, output_sha256, created_by,
               'trace-legacy-publication', statement_timestamp(), statement_timestamp()
        FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 3;
        RAISE EXCEPTION 'historical snapshot was re-published without its registry';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'ai_artifact_legacy_provenance' THEN RAISE; END IF;
    END;
END;
$$;

INSERT INTO ai.derived_artifact_revision (artifact_id, revision, legacy_parent_revision, model_id, model_version, prompt_version,
    pipeline_version_id, parameters_hash, confidence, uncertainty, generated, quality_status, publication_status,
    structured_payload, output_sha256, created_by, trace_id)
SELECT artifact_id, 4, revision, model_id, model_version, prompt_version, pipeline_version_id, parameters_hash,
       confidence, uncertainty, false, quality_status, 'DRAFT', '{"text":"review-required"}', repeat('0',64),
       created_by, 'trace-legacy-review'
FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 3;
UPDATE ai.derived_artifact SET current_revision = 4 WHERE id = 'art_fixture';

INSERT INTO ai.derived_artifact_revision (artifact_id, revision, legacy_parent_revision, model_id, model_version, prompt_version,
    pipeline_version_id, parameters_hash, confidence, uncertainty, generated, quality_status, publication_status,
    content_reference, structured_payload, output_sha256, created_by, trace_id)
SELECT artifact_id, 2, revision, model_id, model_version, prompt_version, pipeline_version_id, parameters_hash,
       confidence, uncertainty, generated, quality_status, 'REVOKED', content_reference, structured_payload, output_sha256,
       created_by, 'trace-legacy-revoked'
FROM ai.derived_artifact_revision WHERE artifact_id = 'art_generated' AND revision = 1;
UPDATE ai.derived_artifact SET current_revision = 2 WHERE id = 'art_generated';

DO $$
BEGIN
    IF (SELECT count(*) FROM outbox.event) <> 5
        OR NOT EXISTS (SELECT 1 FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 4 AND publication_status = 'DRAFT')
        OR NOT EXISTS (SELECT 1 FROM ai.derived_artifact_revision WHERE artifact_id = 'art_generated' AND revision = 2 AND publication_status = 'REVOKED')
    THEN RAISE EXCEPTION 'legacy custody changed old events or failed to edit or revoke'; END IF;
END;
$$;

\ir ai_artifact_registry_fixture.sql
INSERT INTO ai.derived_artifact_revision (artifact_id, revision, model_id, model_version, prompt_version, pipeline_version_id,
    parameters_hash, confidence, uncertainty, generated, quality_status, publication_status, structured_payload,
    output_sha256, created_by, trace_id, created_at, published_at)
SELECT artifact_id, 5, model_id, model_version, prompt_version, pipeline_version_id, parameters_hash,
       confidence, uncertainty, false, quality_status, 'PUBLISHED', structured_payload, output_sha256,
       created_by, 'trace-legacy-restored', statement_timestamp(), statement_timestamp()
FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 4;
UPDATE ai.derived_artifact SET current_revision = 5 WHERE id = 'art_fixture';
DO $$
BEGIN
    IF (SELECT count(*) FROM outbox.event) <> 6 OR NOT EXISTS (
        SELECT 1 FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 5
          AND pipeline_stage_number = 1 AND model_id = 'mdl_ai_fixture_v1'
    ) THEN RAISE EXCEPTION 'verified historical registry could not restore forward publication'; END IF;
END;
$$;

ROLLBACK;

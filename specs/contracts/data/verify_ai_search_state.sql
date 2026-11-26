BEGIN;

-- Seed with verify_artifact_lineage_and_outbox.sql using retain_fixture before this transaction.
UPDATE asset.asset SET current_version_id = 'ver_task' WHERE id = 'ast_task';

INSERT INTO ai.model (id, provider_id, model_key, version_label, embedding_dimension, manifest_sha256)
VALUES ('mdl_ai_fixture_v2', 'prov_ai_fixture', 'model-fixture', 'model-v2', 16, repeat('3', 64));
INSERT INTO ai.prompt (id, prompt_key, version_label, template_reference, template_sha256)
VALUES ('prompt_ai_fixture_v2', 'prompt_fixture', 'prompt-v2', 'template_fixture_v2', repeat('4', 64));
INSERT INTO ai.pipeline (id, pipeline_key, version) VALUES ('pipeline_ai_v2', 'pipeline_fixture', 2);

DO $$
DECLARE
    violated text;
BEGIN
    BEGIN
        UPDATE ai.pipeline SET approved_at = clock_timestamp() WHERE id = 'pipeline_ai_v2';
        RAISE EXCEPTION 'empty pipeline approved';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'ai_pipeline_approval' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO ai.pipeline_stage (pipeline_version_id, stage_number, model_version_id, prompt_version_id, canonical_parameters, parameters_hash)
        VALUES ('pipeline_ai_v2', 1, 'mdl_ai_fixture_v2', 'prompt_ai_fixture_v2', '{"temperature":0.5}', repeat('0',64));
        RAISE EXCEPTION 'incorrect parameters digest accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO ai.pipeline_stage (pipeline_version_id, stage_number, model_version_id, prompt_version_id, canonical_parameters, parameters_hash)
        VALUES ('pipeline_ocr', 2, 'mdl_ai_fixture_v1', 'prompt_ai_fixture_v1', '{}', encode(sha256(convert_to('{}', 'UTF8')), 'hex'));
        RAISE EXCEPTION 'sealed pipeline gained a stage';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'ai_pipeline_stage_sealed' THEN RAISE; END IF;
    END;
END;
$$;

INSERT INTO ai.pipeline_stage (pipeline_version_id, stage_number, model_version_id, prompt_version_id, canonical_parameters, parameters_hash)
VALUES ('pipeline_ai_v2', 1, 'mdl_ai_fixture_v2', 'prompt_ai_fixture_v2', '{"temperature":0.5}',
        encode(sha256(convert_to('{"temperature":0.5}', 'UTF8')), 'hex'));
UPDATE ai.pipeline SET approved_at = clock_timestamp() WHERE id = 'pipeline_ai_v2';

DO $$
DECLARE
    violated text;
BEGIN
    IF (SELECT count(*) FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture'
        AND model_id = 'mdl_ai_fixture_v1' AND pipeline_version_id = 'pipeline_ocr' AND pipeline_stage_number = 1) <> 3
    THEN RAISE EXCEPTION 'model upgrade changed prior artifact provenance'; END IF;
    BEGIN
        INSERT INTO ai.derived_artifact_revision (artifact_id, revision, model_version, prompt_version, pipeline_version_id,
            parameters_hash, confidence, uncertainty, generated, quality_status, publication_status, structured_payload,
            output_sha256, created_by, manual_editor_id, trace_id)
        SELECT artifact_id, 4, model_version, prompt_version, pipeline_version_id, repeat('0',64), confidence, uncertainty,
               generated, quality_status, 'DRAFT', structured_payload, output_sha256, created_by, manual_editor_id, 'trace-ai-mismatch'
        FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 3;
        RAISE EXCEPTION 'artifact accepted an unregistered digest';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'ai_artifact_registry_provenance' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO ai.derived_artifact_revision (artifact_id, revision, model_version, prompt_version, pipeline_version_id,
            parameters_hash, confidence, uncertainty, generated, quality_status, publication_status, structured_payload,
            output_sha256, created_by, manual_editor_id, trace_id)
        SELECT r.artifact_id, 4, 'model-v2', 'prompt-v2', s.pipeline_version_id, s.parameters_hash, r.confidence, r.uncertainty,
               r.generated, r.quality_status, 'DRAFT', r.structured_payload, r.output_sha256, r.created_by, r.manual_editor_id, 'trace-ai-reattribute'
        FROM ai.pipeline_stage s CROSS JOIN ai.derived_artifact_revision r
        WHERE s.pipeline_version_id = 'pipeline_ai_v2' AND r.artifact_id = 'art_fixture' AND r.revision = 3;
        RAISE EXCEPTION 'new model was attributed to an old execution';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'ai_artifact_original_provenance' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO ai.derived_artifact_revision (artifact_id, revision, model_version, prompt_version, pipeline_version_id,
            parameters_hash, confidence, uncertainty, generated, quality_status, publication_status, structured_payload,
            output_sha256, created_by, trace_id, created_at, published_at)
        SELECT artifact_id, 4, model_version, prompt_version, pipeline_version_id, parameters_hash, confidence, uncertainty,
               true, quality_status, 'PUBLISHED', '{"text":"another generated result"}', repeat('0',64), created_by,
               'trace-ai-generated-again', statement_timestamp(), statement_timestamp()
        FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 3;
        RAISE EXCEPTION 'same pipeline assigned another generated output to old execution';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'ai_artifact_revision_origin' THEN RAISE; END IF;
    END;
END;
$$;

INSERT INTO ai.quality_evaluation (id, artifact_id, artifact_revision, rubric_version_id, evidence_id, outcome, score, evaluated_at)
VALUES ('eval_ai_fixture', 'art_fixture', 3, 'rub_ai_v1', 'evid_ai_fixture', 'PASS', 0.95, clock_timestamp());

INSERT INTO search.index_generation (id, backend, index_key, generation, external_reference, model_version_id, dimension, normalization)
VALUES ('gen_text_fixture', 'OPENSEARCH', 'idx_text_fixture', 1, 'ext_text_fixture', NULL, NULL, NULL),
       ('gen_vector_one', 'MILVUS', 'idx_vec_fixture', 1, 'ext_vector_one', 'mdl_ai_fixture_v1', 8, 'UNIT_L2'),
       ('gen_vector_two', 'MILVUS', 'idx_vec_fixture', 2, 'ext_vector_two', 'mdl_ai_fixture_v2', 16, 'UNIT_L2');
INSERT INTO search.rebuild_job (id, generation_id, backend, index_key, previous_generation_id, previous_head_revision, status)
VALUES ('job_text_fixture', 'gen_text_fixture', 'OPENSEARCH', 'idx_text_fixture', NULL, NULL, 'PLANNED'),
       ('job_vector_one', 'gen_vector_one', 'MILVUS', 'idx_vec_fixture', NULL, NULL, 'PLANNED'),
       ('job_vector_two', 'gen_vector_two', 'MILVUS', 'idx_vec_fixture', 'gen_vector_one', 1, 'PLANNED');

DO $$
DECLARE
    violated text;
BEGIN
    BEGIN
        INSERT INTO search.generation_head (backend, index_key, generation_id, rebuild_job_id)
        VALUES ('MILVUS', 'idx_vec_fixture', 'gen_vector_one', 'job_vector_one');
        RAISE EXCEPTION 'unverified generation became active';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'search_generation_verified_rebuild' THEN RAISE; END IF;
    END;
END;
$$;

UPDATE search.rebuild_job SET status = 'VALIDATING';
DO $$
BEGIN
    BEGIN
        UPDATE search.rebuild_job SET status = 'SUCCEEDED', finished_at = clock_timestamp(), integrity_evidence_id = 'evid_integrity_fixture'
        WHERE id = 'job_vector_one';
        RAISE EXCEPTION 'rebuild passed without permission evidence';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;
UPDATE search.rebuild_job SET status = 'SUCCEEDED', finished_at = clock_timestamp(),
    integrity_evidence_id = 'evid_integrity_fixture', permission_evidence_id = 'evid_permissions_fixture';
INSERT INTO search.generation_head (backend, index_key, generation_id, rebuild_job_id)
VALUES ('MILVUS', 'idx_vec_fixture', 'gen_vector_one', 'job_vector_one'),
       ('OPENSEARCH', 'idx_text_fixture', 'gen_text_fixture', 'job_text_fixture');

INSERT INTO search.permission_scope (asset_id, scope_version, observed_at) VALUES ('ast_task', 1, clock_timestamp());
INSERT INTO search.index_record (generation_id, asset_version_id, asset_id, external_document_id, source_asset_revision, permission_scope_version, status)
SELECT id, 'ver_task', 'ast_task', 'doc_ai_fixture', 1, 1, 'PENDING' FROM search.index_generation;
UPDATE search.index_record SET status = 'INDEXING', revision = 2;

DO $$
BEGIN
    BEGIN
        INSERT INTO search.embedding_record (id, generation_id, asset_version_id, artifact_id, artifact_revision, model_version_id,
            dimension, normalization, vector_kind, chunk_key, chunk_strategy, external_vector_id, source_asset_revision, permission_scope_version)
        VALUES ('vec_wrong_model', 'gen_vector_one', 'ver_task', 'art_fixture', 3, 'mdl_ai_fixture_v2',
                16, 'UNIT_L2', 'TEXT', 'chunk-0', 'fixture-chunks', 'ext_vector_wrong', 1, 1);
        RAISE EXCEPTION 'generation accepted another model and dimension';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO search.embedding_record (id, generation_id, asset_version_id, artifact_id, artifact_revision, model_version_id,
            dimension, normalization, vector_kind, chunk_key, chunk_strategy, external_vector_id, source_asset_revision, permission_scope_version)
        VALUES ('vec_wrong_revision', 'gen_vector_one', 'ver_task', 'art_fixture', 2, 'mdl_ai_fixture_v1',
                8, 'UNIT_L2', 'TEXT', 'chunk-0', 'fixture-chunks', 'ext_vector_wrong', 1, 1);
        RAISE EXCEPTION 'superseded revision produced a current embedding';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
END;
$$;

INSERT INTO search.embedding_record (id, generation_id, asset_version_id, artifact_id, artifact_revision, model_version_id,
    dimension, normalization, vector_kind, chunk_key, chunk_strategy, external_vector_id, source_asset_revision, permission_scope_version)
VALUES ('vec_fixture_one', 'gen_vector_one', 'ver_task', 'art_fixture', 3, 'mdl_ai_fixture_v1',
        8, 'UNIT_L2', 'TEXT', 'chunk-0', 'fixture-chunks', 'ext_chunk_v1', 1, 1),
       ('vec_fixture_two', 'gen_vector_two', 'ver_task', 'art_fixture', 3, 'mdl_ai_fixture_v2',
        16, 'UNIT_L2', 'TEXT', 'chunk-0', 'fixture-chunks', 'ext_chunk_v2', 1, 1);
UPDATE search.index_record SET status = 'INDEXED', revision = 3, indexed_at = clock_timestamp();

DO $$
BEGIN
    IF (SELECT array_agg(id::text) FROM search.current_embedding) IS DISTINCT FROM ARRAY['vec_fixture_one']
    THEN RAISE EXCEPTION 'shadow index vectors escaped before activation'; END IF;
END;
$$;
UPDATE search.generation_head SET generation_id = 'gen_vector_two', rebuild_job_id = 'job_vector_two', revision = 2
WHERE backend = 'MILVUS';

DO $$
BEGIN
    IF (SELECT array_agg(id::text) FROM search.current_embedding) IS DISTINCT FROM ARRAY['vec_fixture_two']
    THEN RAISE EXCEPTION 'generation switch mixed active vector collections'; END IF;
END;
$$;

SAVEPOINT rollback_generation;
INSERT INTO search.rebuild_job (id, generation_id, backend, index_key, previous_generation_id, previous_head_revision, status)
VALUES ('job_vector_return', 'gen_vector_one', 'MILVUS', 'idx_vec_fixture', 'gen_vector_two', 2, 'PLANNED');
UPDATE search.rebuild_job SET status = 'VALIDATING' WHERE id = 'job_vector_return';
UPDATE search.rebuild_job SET status = 'SUCCEEDED', finished_at = clock_timestamp(),
    integrity_evidence_id = 'evid_return_integrity', permission_evidence_id = 'evid_return_permissions' WHERE id = 'job_vector_return';
UPDATE search.generation_head SET generation_id = 'gen_vector_one', rebuild_job_id = 'job_vector_return', revision = 3
WHERE backend = 'MILVUS';
DO $$
DECLARE
    violated text;
BEGIN
    IF (SELECT array_agg(id::text) FROM search.current_embedding) IS DISTINCT FROM ARRAY['vec_fixture_one']
    THEN RAISE EXCEPTION 'validated rollback failed to restore its prior collection'; END IF;
    BEGIN
        UPDATE search.generation_head SET generation_id = 'gen_vector_two', rebuild_job_id = 'job_vector_two', revision = 4
        WHERE backend = 'MILVUS';
        RAISE EXCEPTION 'old activation proof replayed after generation rollback';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'search_generation_verified_rebuild' THEN RAISE; END IF;
    END;
END;
$$;
ROLLBACK TO SAVEPOINT rollback_generation;
RELEASE SAVEPOINT rollback_generation;

SAVEPOINT revoke_artifact;
INSERT INTO ai.derived_artifact_revision (artifact_id, revision, model_id, model_version, prompt_version, pipeline_version_id,
    parameters_hash, confidence, uncertainty, generated, quality_status, publication_status, structured_payload, output_sha256, created_by, manual_editor_id, trace_id)
SELECT artifact_id, 4, model_id, model_version, prompt_version, pipeline_version_id, parameters_hash,
       confidence, uncertainty, generated, quality_status, 'REVOKED', structured_payload, output_sha256, created_by, manual_editor_id, 'trace-ai-revoked'
FROM ai.derived_artifact_revision WHERE artifact_id = 'art_fixture' AND revision = 3;
UPDATE ai.derived_artifact SET current_revision = 4 WHERE id = 'art_fixture';
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM search.current_embedding) THEN RAISE EXCEPTION 'revoked AI content remained current in vector view'; END IF;
END;
$$;
ROLLBACK TO SAVEPOINT revoke_artifact;
RELEASE SAVEPOINT revoke_artifact;

SAVEPOINT permissions_changed;
UPDATE search.permission_scope SET scope_version = 2, observed_at = clock_timestamp() WHERE asset_id = 'ast_task';
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM search.current_index_record) OR EXISTS (SELECT 1 FROM search.current_embedding)
    THEN RAISE EXCEPTION 'old permission projection remained current'; END IF;
    BEGIN
        UPDATE search.index_record SET status = 'INDEXED', revision = revision + 1, indexed_at = clock_timestamp()
        WHERE generation_id = 'gen_vector_two';
        RAISE EXCEPTION 'old permission scope was re-published';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
END;
$$;
ROLLBACK TO SAVEPOINT permissions_changed;
RELEASE SAVEPOINT permissions_changed;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

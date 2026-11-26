INSERT INTO ai.provider (id, deployment, connector_kind, endpoint_reference)
VALUES ('prov_ai_fixture', 'LOCAL', 'OPENAI_COMPATIBLE', 'endpoint_fixture');
INSERT INTO ai.model (id, provider_id, model_key, version_label, embedding_dimension, manifest_sha256)
VALUES ('mdl_ai_fixture_v1', 'prov_ai_fixture', 'model-fixture', 'model-v1', 8, repeat('1', 64));
INSERT INTO ai.prompt (id, prompt_key, version_label, template_reference, template_sha256)
VALUES ('prompt_ai_fixture_v1', 'prompt_fixture', 'prompt-v1', 'template_fixture_v1', repeat('2', 64));
INSERT INTO ai.pipeline (id, pipeline_key, version) VALUES ('pipeline_ocr', 'pipeline_fixture', 1);
INSERT INTO ai.pipeline_stage (pipeline_version_id, stage_number, model_version_id, prompt_version_id, canonical_parameters, parameters_hash)
VALUES ('pipeline_ocr', 1, 'mdl_ai_fixture_v1', 'prompt_ai_fixture_v1', '{}',
        encode(sha256(convert_to('{}', 'UTF8')), 'hex'));
UPDATE ai.pipeline SET approved_at = statement_timestamp() WHERE id = 'pipeline_ocr';

CREATE TABLE ai.provider (
    id task.identifier PRIMARY KEY,
    deployment text NOT NULL CHECK (deployment IN ('LOCAL', 'EXTERNAL')),
    connector_kind varchar(64) NOT NULL CHECK (connector_kind ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    endpoint_reference task.identifier NOT NULL,
    credential_reference varchar(74) CHECK (credential_reference ~ '^secretref_[A-Za-z0-9_-]{1,64}$'),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai.model (
    id task.identifier PRIMARY KEY,
    provider_id task.identifier NOT NULL REFERENCES ai.provider (id),
    model_key varchar(256) NOT NULL CHECK (length(model_key) > 0),
    version_label varchar(256) NOT NULL CHECK (length(version_label) > 0),
    embedding_dimension integer CHECK (embedding_dimension > 0),
    manifest_sha256 varchar(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    registered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider_id, model_key, version_label),
    UNIQUE (id, embedding_dimension)
);

CREATE TABLE ai.prompt (
    id task.identifier PRIMARY KEY,
    prompt_key task.identifier NOT NULL,
    version_label varchar(256) NOT NULL CHECK (length(version_label) > 0),
    template_reference task.identifier NOT NULL,
    template_sha256 varchar(64) NOT NULL CHECK (template_sha256 ~ '^[0-9a-f]{64}$'),
    registered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (prompt_key, version_label)
);

CREATE TABLE ai.pipeline (
    id task.identifier PRIMARY KEY,
    pipeline_key task.identifier NOT NULL,
    version bigint NOT NULL CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at timestamptz CHECK (approved_at >= created_at),
    UNIQUE (pipeline_key, version)
);

CREATE TABLE ai.pipeline_stage (
    pipeline_version_id task.identifier NOT NULL REFERENCES ai.pipeline (id),
    stage_number integer NOT NULL CHECK (stage_number > 0),
    model_version_id task.identifier NOT NULL REFERENCES ai.model (id),
    prompt_version_id task.identifier NOT NULL REFERENCES ai.prompt (id),
    canonical_parameters text NOT NULL CHECK (jsonb_typeof(canonical_parameters::jsonb) = 'object'),
    parameters_hash varchar(64) NOT NULL CHECK (parameters_hash = encode(sha256(convert_to(canonical_parameters, 'UTF8')), 'hex')),
    PRIMARY KEY (pipeline_version_id, stage_number)
);

CREATE FUNCTION ai.guard_provider_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(OLD.id, OLD.deployment, OLD.connector_kind, OLD.endpoint_reference, OLD.created_at)
        IS DISTINCT FROM ROW(NEW.id, NEW.deployment, NEW.connector_kind, NEW.endpoint_reference, NEW.created_at)
    THEN RAISE check_violation USING CONSTRAINT = 'ai_provider_identity', MESSAGE = 'Register a new provider identity'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ai_provider_identity BEFORE UPDATE ON ai.provider
FOR EACH ROW EXECUTE FUNCTION ai.guard_provider_identity();

CREATE FUNCTION ai.reject_registry_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE check_violation USING CONSTRAINT = 'ai_registry_version_immutable', MESSAGE = 'Append a new AI registry version';
END;
$$;

CREATE TRIGGER ai_model_immutable BEFORE UPDATE OR DELETE ON ai.model
FOR EACH ROW EXECUTE FUNCTION ai.reject_registry_rewrite();
CREATE TRIGGER ai_prompt_immutable BEFORE UPDATE OR DELETE ON ai.prompt
FOR EACH ROW EXECUTE FUNCTION ai.reject_registry_rewrite();
CREATE TRIGGER ai_pipeline_stage_immutable BEFORE UPDATE OR DELETE ON ai.pipeline_stage
FOR EACH ROW EXECUTE FUNCTION ai.reject_registry_rewrite();

CREATE FUNCTION ai.guard_pipeline_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'ai_pipeline_history', MESSAGE = 'Retain the pipeline version';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.approved_at IS NOT NULL THEN
            RAISE check_violation USING CONSTRAINT = 'ai_pipeline_approval', MESSAGE = 'Register stages before approval';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.approved_at IS NULL AND NEW IS NOT DISTINCT FROM OLD THEN RETURN NEW; END IF;
    IF OLD.approved_at IS NOT NULL OR NEW.approved_at IS NULL
        OR ROW(OLD.id, OLD.pipeline_key, OLD.version, OLD.created_at)
           IS DISTINCT FROM ROW(NEW.id, NEW.pipeline_key, NEW.version, NEW.created_at)
        OR NOT EXISTS (SELECT 1 FROM ai.pipeline_stage WHERE pipeline_version_id = OLD.id)
    THEN RAISE check_violation USING CONSTRAINT = 'ai_pipeline_approval', MESSAGE = 'Approval must seal a staged pipeline'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ai_pipeline_approval BEFORE INSERT OR UPDATE OR DELETE ON ai.pipeline
FOR EACH ROW EXECUTE FUNCTION ai.guard_pipeline_approval();

CREATE FUNCTION ai.guard_pipeline_stage_creation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Create an MVCC change so approval cannot use a pre-stage snapshot after waiting.
    UPDATE ai.pipeline SET created_at = created_at WHERE id = NEW.pipeline_version_id AND approved_at IS NULL;
    IF NOT FOUND THEN RAISE check_violation USING CONSTRAINT = 'ai_pipeline_stage_sealed', MESSAGE = 'Pipeline is already sealed'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ai_pipeline_stage_creation BEFORE INSERT ON ai.pipeline_stage
FOR EACH ROW EXECUTE FUNCTION ai.guard_pipeline_stage_creation();

ALTER TABLE ai.derived_artifact_revision ADD COLUMN pipeline_stage_number integer;
ALTER TABLE ai.derived_artifact_revision ADD COLUMN legacy_parent_revision bigint;
ALTER TABLE ai.derived_artifact_revision ADD COLUMN manual_editor_id task.identifier REFERENCES iam.user_account (id);
ALTER TABLE ai.derived_artifact_revision ADD CONSTRAINT ai_artifact_stage_fk FOREIGN KEY (pipeline_version_id, pipeline_stage_number)
    REFERENCES ai.pipeline_stage (pipeline_version_id, stage_number);
ALTER TABLE ai.derived_artifact_revision ADD CONSTRAINT ai_artifact_legacy_parent_fk FOREIGN KEY (artifact_id, legacy_parent_revision)
    REFERENCES ai.derived_artifact_revision (artifact_id, revision);
ALTER TABLE ai.derived_artifact ADD CONSTRAINT ai_artifact_input_identity UNIQUE (id, asset_version_id);

CREATE FUNCTION ai.bind_artifact_registry() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    parent ai.derived_artifact_revision%ROWTYPE;
    bound_stage integer;
    bound_model task.identifier;
BEGIN
    IF NEW.revision > 1 THEN
        PERFORM FROM ai.derived_artifact WHERE id = NEW.artifact_id AND current_revision = NEW.revision - 1 FOR NO KEY UPDATE;
        IF NOT FOUND THEN RAISE serialization_failure USING MESSAGE = 'Artifact revision changed'; END IF;
        SELECT * INTO STRICT parent FROM ai.derived_artifact_revision WHERE artifact_id = NEW.artifact_id AND revision = NEW.revision - 1;
        IF ROW(NEW.output_sha256, NEW.content_reference, NEW.structured_payload, NEW.generated)
            IS DISTINCT FROM ROW(parent.output_sha256, parent.content_reference, parent.structured_payload, parent.generated)
        THEN
            IF NEW.publication_status = 'REVOKED' OR (NOT NEW.generated AND NEW.manual_editor_id IS DISTINCT FROM NEW.created_by)
                OR (NEW.generated AND (NEW.manual_editor_id IS NOT NULL OR NOT EXISTS (
                    SELECT 1 FROM ai.derived_artifact_revision original WHERE original.artifact_id = NEW.artifact_id AND original.revision = 1
                      AND ROW(original.output_sha256, original.content_reference, original.structured_payload, original.generated)
                          IS NOT DISTINCT FROM ROW(NEW.output_sha256, NEW.content_reference, NEW.structured_payload, NEW.generated)
                )))
            THEN RAISE check_violation USING CONSTRAINT = 'ai_artifact_revision_origin', MESSAGE = 'New generated output requires a new accepted execution; manual changes require an editor'; END IF;
        ELSIF NEW.manual_editor_id IS DISTINCT FROM parent.manual_editor_id THEN
            RAISE check_violation USING CONSTRAINT = 'ai_artifact_revision_origin', MESSAGE = 'Retain the editor of unchanged content';
        END IF;
    ELSIF NEW.manual_editor_id IS NOT NULL THEN
        RAISE check_violation USING CONSTRAINT = 'ai_artifact_revision_origin', MESSAGE = 'The first revision retains accepted execution provenance';
    END IF;

    IF NEW.legacy_parent_revision IS NOT NULL THEN
        IF NEW.legacy_parent_revision IS DISTINCT FROM parent.revision
            OR NEW.pipeline_stage_number IS NOT NULL OR parent.pipeline_stage_number IS NOT NULL
            OR ROW(NEW.model_id, NEW.model_version, NEW.prompt_version, NEW.pipeline_version_id, NEW.parameters_hash)
               IS DISTINCT FROM ROW(parent.model_id, parent.model_version, parent.prompt_version, parent.pipeline_version_id, parent.parameters_hash)
            OR NEW.publication_status = 'PUBLISHED'
            OR (NEW.generated AND NEW.publication_status <> 'REVOKED')
        THEN RAISE check_violation USING CONSTRAINT = 'ai_artifact_legacy_provenance', MESSAGE = 'Legacy edits must preserve registry provenance'; END IF;
        RETURN NEW;
    END IF;

    BEGIN
        SELECT s.stage_number, m.id INTO STRICT bound_stage, bound_model
        FROM ai.pipeline p JOIN ai.pipeline_stage s ON s.pipeline_version_id = p.id
        JOIN ai.model m ON m.id = s.model_version_id JOIN ai.prompt pr ON pr.id = s.prompt_version_id
        WHERE p.id = NEW.pipeline_version_id AND p.approved_at <= NEW.created_at
          AND m.version_label = NEW.model_version AND pr.version_label = NEW.prompt_version
          AND s.parameters_hash = NEW.parameters_hash
          AND (NEW.pipeline_stage_number IS NULL OR NEW.pipeline_stage_number = s.stage_number)
          AND (NEW.model_id IS NULL OR NEW.model_id = m.id);
    EXCEPTION WHEN no_data_found OR too_many_rows THEN
        RAISE check_violation USING CONSTRAINT = 'ai_artifact_registry_provenance', MESSAGE = 'Artifact must identify one approved pipeline stage';
    END;
    NEW.pipeline_stage_number := bound_stage;
    NEW.model_id := bound_model;
    IF NEW.revision > 1 AND NOT EXISTS (
        SELECT 1 FROM ai.derived_artifact_revision prior WHERE prior.artifact_id = NEW.artifact_id AND prior.revision = 1
          AND prior.pipeline_version_id = NEW.pipeline_version_id
          AND ((prior.pipeline_stage_number, prior.model_id) = (NEW.pipeline_stage_number, NEW.model_id)
            OR (prior.pipeline_stage_number IS NULL AND (prior.model_id IS NULL OR prior.model_id = NEW.model_id)
                AND (prior.model_version, prior.prompt_version, prior.parameters_hash)
                  = (NEW.model_version, NEW.prompt_version, NEW.parameters_hash)))
    ) THEN RAISE check_violation USING CONSTRAINT = 'ai_artifact_original_provenance', MESSAGE = 'A new execution requires a new derived artifact'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ai_artifact_registry_provenance BEFORE INSERT ON ai.derived_artifact_revision
FOR EACH ROW EXECUTE FUNCTION ai.bind_artifact_registry();

CREATE TABLE ai.quality_evaluation (
    id task.identifier PRIMARY KEY,
    artifact_id task.identifier NOT NULL,
    artifact_revision bigint NOT NULL,
    rubric_version_id task.identifier NOT NULL,
    evidence_id task.identifier NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('PASS', 'FAIL')),
    score numeric CHECK (score BETWEEN 0 AND 1),
    evaluated_at timestamptz NOT NULL,
    FOREIGN KEY (artifact_id, artifact_revision) REFERENCES ai.derived_artifact_revision (artifact_id, revision),
    UNIQUE (artifact_id, artifact_revision, rubric_version_id, evidence_id)
);

CREATE TRIGGER ai_quality_evaluation_immutable BEFORE UPDATE OR DELETE ON ai.quality_evaluation
FOR EACH ROW EXECUTE FUNCTION ai.reject_registry_rewrite();

CREATE TABLE search.index_generation (
    id task.identifier PRIMARY KEY,
    backend text NOT NULL CHECK (backend IN ('OPENSEARCH', 'MILVUS')),
    index_key task.identifier NOT NULL,
    generation bigint NOT NULL CHECK (generation BETWEEN 1 AND 9007199254740991),
    external_reference task.identifier NOT NULL UNIQUE,
    model_version_id task.identifier,
    dimension integer CHECK (dimension > 0),
    normalization text CHECK (normalization IN ('NONE', 'UNIT_L2')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (backend, index_key, generation),
    UNIQUE (id, backend, index_key),
    UNIQUE (id, model_version_id, dimension, normalization),
    FOREIGN KEY (model_version_id, dimension) REFERENCES ai.model (id, embedding_dimension),
    CHECK ((backend = 'MILVUS' AND num_nonnulls(model_version_id, dimension, normalization) = 3)
        OR (backend = 'OPENSEARCH' AND num_nonnulls(model_version_id, dimension, normalization) = 0))
);

CREATE FUNCTION search.reject_history_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE check_violation USING CONSTRAINT = 'search_history_immutable', MESSAGE = 'Retain the indexed generation or embedding evidence';
END;
$$;

CREATE TRIGGER search_generation_immutable BEFORE UPDATE OR DELETE ON search.index_generation
FOR EACH ROW EXECUTE FUNCTION search.reject_history_rewrite();

CREATE TABLE search.rebuild_job (
    id task.identifier PRIMARY KEY,
    generation_id task.identifier NOT NULL,
    backend text NOT NULL,
    index_key task.identifier NOT NULL,
    previous_generation_id task.identifier,
    previous_head_revision bigint CHECK (previous_head_revision BETWEEN 1 AND 9007199254740991),
    status text NOT NULL CHECK (status IN ('PLANNED', 'RUNNING', 'VALIDATING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
    requested_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz CHECK (finished_at >= requested_at),
    integrity_evidence_id task.identifier,
    permission_evidence_id task.identifier,
    UNIQUE (id, generation_id),
    FOREIGN KEY (generation_id, backend, index_key) REFERENCES search.index_generation (id, backend, index_key),
    FOREIGN KEY (previous_generation_id, backend, index_key) REFERENCES search.index_generation (id, backend, index_key),
    CHECK (previous_generation_id IS DISTINCT FROM generation_id),
    CHECK ((previous_generation_id IS NULL) = (previous_head_revision IS NULL)),
    CHECK ((status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')) = (finished_at IS NOT NULL)),
    CHECK (status <> 'SUCCEEDED' OR num_nonnulls(integrity_evidence_id, permission_evidence_id) = 2)
);

CREATE UNIQUE INDEX search_rebuild_active_idx ON search.rebuild_job (generation_id)
WHERE status IN ('PLANNED', 'RUNNING', 'VALIDATING');

CREATE FUNCTION search.guard_rebuild_job() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'search_rebuild_history', MESSAGE = 'Retain the rebuild job';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PLANNED' THEN RAISE check_violation USING CONSTRAINT = 'search_rebuild_transition', MESSAGE = 'Start with a planned rebuild'; END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
        OR ROW(OLD.id, OLD.generation_id, OLD.backend, OLD.index_key, OLD.previous_generation_id, OLD.previous_head_revision, OLD.requested_at)
           IS DISTINCT FROM ROW(NEW.id, NEW.generation_id, NEW.backend, NEW.index_key, NEW.previous_generation_id, NEW.previous_head_revision, NEW.requested_at)
        OR (NEW.status = 'SUCCEEDED' AND OLD.status <> 'VALIDATING')
    THEN RAISE check_violation USING CONSTRAINT = 'search_rebuild_transition', MESSAGE = 'Invalid rebuild transition'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_rebuild_transition BEFORE INSERT OR UPDATE OR DELETE ON search.rebuild_job
FOR EACH ROW EXECUTE FUNCTION search.guard_rebuild_job();

CREATE TABLE search.generation_head (
    backend text NOT NULL,
    index_key task.identifier NOT NULL,
    generation_id task.identifier NOT NULL,
    rebuild_job_id task.identifier NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991),
    changed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (backend, index_key),
    FOREIGN KEY (generation_id, backend, index_key) REFERENCES search.index_generation (id, backend, index_key),
    FOREIGN KEY (rebuild_job_id, generation_id) REFERENCES search.rebuild_job (id, generation_id)
);

CREATE FUNCTION search.guard_generation_head() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    predecessor task.identifier;
    predecessor_revision bigint;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'search_generation_history', MESSAGE = 'Retain the active generation binding';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF NEW.revision <> OLD.revision + 1 OR (NEW.backend, NEW.index_key) IS DISTINCT FROM (OLD.backend, OLD.index_key)
        THEN RAISE serialization_failure USING MESSAGE = 'Search generation revision changed'; END IF;
        predecessor := OLD.generation_id;
        predecessor_revision := OLD.revision;
    ELSIF NEW.revision <> 1 THEN
        RAISE check_violation USING CONSTRAINT = 'search_generation_initial_revision', MESSAGE = 'First generation activation starts at revision one';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM search.rebuild_job WHERE id = NEW.rebuild_job_id AND generation_id = NEW.generation_id
        AND status = 'SUCCEEDED' AND previous_generation_id IS NOT DISTINCT FROM predecessor
        AND previous_head_revision IS NOT DISTINCT FROM predecessor_revision)
    THEN RAISE check_violation USING CONSTRAINT = 'search_generation_verified_rebuild', MESSAGE = 'Generation requires a verified rebuild for the current predecessor'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_generation_verified_rebuild BEFORE INSERT OR UPDATE OR DELETE ON search.generation_head
FOR EACH ROW EXECUTE FUNCTION search.guard_generation_head();

CREATE TABLE search.permission_scope (
    asset_id task.identifier PRIMARY KEY REFERENCES asset.asset (id),
    scope_version bigint NOT NULL CHECK (scope_version BETWEEN 1 AND 9007199254740991),
    observed_at timestamptz NOT NULL
);

CREATE FUNCTION search.guard_permission_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'search_permission_scope_history', MESSAGE = 'Retain the known permission watermark';
    END IF;
    IF NEW.asset_id IS DISTINCT FROM OLD.asset_id OR NEW.scope_version <= OLD.scope_version OR NEW.observed_at < OLD.observed_at
    THEN RAISE serialization_failure USING MESSAGE = 'Search permission watermark cannot retreat'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_permission_scope_history BEFORE UPDATE OR DELETE ON search.permission_scope
FOR EACH ROW EXECUTE FUNCTION search.guard_permission_scope();

CREATE TABLE search.index_record (
    generation_id task.identifier NOT NULL REFERENCES search.index_generation (id),
    asset_version_id task.identifier NOT NULL,
    asset_id task.identifier NOT NULL REFERENCES search.permission_scope (asset_id),
    external_document_id task.identifier NOT NULL,
    source_asset_revision bigint NOT NULL CHECK (source_asset_revision BETWEEN 1 AND 9007199254740991),
    permission_scope_version bigint NOT NULL CHECK (permission_scope_version BETWEEN 1 AND 9007199254740991),
    status text NOT NULL CHECK (status IN ('PENDING', 'INDEXING', 'INDEXED', 'STALE', 'FAILED', 'REBUILD_REQUIRED')),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991),
    indexed_at timestamptz,
    PRIMARY KEY (generation_id, asset_version_id),
    UNIQUE (generation_id, external_document_id),
    FOREIGN KEY (asset_id, asset_version_id) REFERENCES asset.version (asset_id, id),
    CHECK (status <> 'INDEXED' OR indexed_at IS NOT NULL)
);

CREATE INDEX search_index_asset_idx ON search.index_record (asset_id, asset_version_id, source_asset_revision);
CREATE INDEX search_index_pending_idx ON search.index_record (status, generation_id, asset_version_id)
WHERE status IN ('PENDING', 'STALE', 'REBUILD_REQUIRED', 'FAILED');

CREATE FUNCTION asset.lock_search_asset_revision(p_asset_id task.identifier, p_version_id task.identifier, p_revision bigint)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    PERFORM FROM asset.asset WHERE id = p_asset_id AND current_version_id = p_version_id AND revision = p_revision FOR SHARE;
    RETURN FOUND;
END;
$$;

REVOKE EXECUTE ON FUNCTION asset.lock_search_asset_revision(task.identifier, task.identifier, bigint) FROM PUBLIC;

CREATE FUNCTION search.guard_index_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PENDING' OR NEW.revision <> 1 THEN
            RAISE check_violation USING CONSTRAINT = 'search_index_initial_state', MESSAGE = 'Establish a pending index record';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.revision <> OLD.revision + 1 OR NEW.source_asset_revision < OLD.source_asset_revision
        OR NEW.permission_scope_version < OLD.permission_scope_version
        OR ROW(OLD.generation_id, OLD.asset_version_id, OLD.asset_id, OLD.external_document_id)
           IS DISTINCT FROM ROW(NEW.generation_id, NEW.asset_version_id, NEW.asset_id, NEW.external_document_id)
    THEN RAISE serialization_failure USING MESSAGE = 'Search index record is stale'; END IF;

    IF NEW.status = 'INDEXED' THEN
        IF NOT asset.lock_search_asset_revision(NEW.asset_id, NEW.asset_version_id, NEW.source_asset_revision)
        THEN RAISE serialization_failure USING MESSAGE = 'Search asset revision changed'; END IF;
        PERFORM FROM search.permission_scope WHERE asset_id = NEW.asset_id AND scope_version = NEW.permission_scope_version FOR SHARE;
        IF NOT FOUND THEN RAISE serialization_failure USING MESSAGE = 'Search permission watermark changed'; END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_index_state BEFORE INSERT OR UPDATE ON search.index_record
FOR EACH ROW EXECUTE FUNCTION search.guard_index_record();

CREATE VIEW search.current_index_record AS
SELECT i.* FROM search.index_record i
JOIN search.generation_head head ON head.generation_id = i.generation_id
JOIN asset.asset a ON a.id = i.asset_id AND a.current_version_id = i.asset_version_id AND a.revision = i.source_asset_revision
JOIN search.permission_scope p ON p.asset_id = i.asset_id AND p.scope_version = i.permission_scope_version
WHERE i.status = 'INDEXED';

CREATE TABLE search.embedding_record (
    id task.identifier PRIMARY KEY,
    generation_id task.identifier NOT NULL,
    asset_version_id task.identifier NOT NULL,
    artifact_id task.identifier NOT NULL,
    artifact_revision bigint NOT NULL,
    model_version_id task.identifier NOT NULL,
    dimension integer NOT NULL CHECK (dimension > 0),
    normalization text NOT NULL,
    vector_kind text NOT NULL CHECK (vector_kind IN ('TEXT', 'SUBTITLE', 'IMAGE', 'KEYFRAME', 'VIDEO', 'MULTIMODAL', 'TAG', 'SUMMARY')),
    chunk_key varchar(256) NOT NULL CHECK (length(chunk_key) > 0),
    chunk_strategy varchar(128) NOT NULL CHECK (length(chunk_strategy) > 0),
    frame_time_ms bigint CHECK (frame_time_ms >= 0),
    external_vector_id task.identifier NOT NULL,
    source_asset_revision bigint NOT NULL CHECK (source_asset_revision BETWEEN 1 AND 9007199254740991),
    permission_scope_version bigint NOT NULL CHECK (permission_scope_version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_id, asset_version_id) REFERENCES search.index_record (generation_id, asset_version_id),
    FOREIGN KEY (generation_id, model_version_id, dimension, normalization)
        REFERENCES search.index_generation (id, model_version_id, dimension, normalization),
    FOREIGN KEY (artifact_id, asset_version_id) REFERENCES ai.derived_artifact (id, asset_version_id),
    FOREIGN KEY (artifact_id, artifact_revision) REFERENCES ai.derived_artifact_revision (artifact_id, revision),
    UNIQUE (generation_id, external_vector_id),
    UNIQUE (generation_id, artifact_id, artifact_revision, vector_kind, chunk_key, source_asset_revision, permission_scope_version)
);

CREATE FUNCTION ai.lock_published_search_artifact(p_artifact task.identifier, p_version task.identifier, p_revision bigint)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    PERFORM FROM ai.derived_artifact WHERE id = p_artifact AND asset_version_id = p_version AND current_revision = p_revision FOR SHARE;
    IF NOT FOUND THEN RETURN false; END IF;
    RETURN EXISTS (SELECT 1 FROM ai.derived_artifact_revision
        WHERE artifact_id = p_artifact AND revision = p_revision AND publication_status = 'PUBLISHED');
END;
$$;

REVOKE EXECUTE ON FUNCTION ai.lock_published_search_artifact(task.identifier, task.identifier, bigint) FROM PUBLIC;

CREATE FUNCTION search.guard_embedding_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT ai.lock_published_search_artifact(NEW.artifact_id, NEW.asset_version_id, NEW.artifact_revision)
    THEN RAISE serialization_failure USING MESSAGE = 'Embedding input is no longer the published artifact revision'; END IF;
    PERFORM FROM search.index_record i
    JOIN search.permission_scope p ON p.asset_id = i.asset_id AND p.scope_version = NEW.permission_scope_version
    WHERE i.generation_id = NEW.generation_id AND i.asset_version_id = NEW.asset_version_id
      AND i.status IN ('INDEXING', 'INDEXED') AND i.source_asset_revision = NEW.source_asset_revision
      AND i.permission_scope_version = NEW.permission_scope_version FOR SHARE OF i, p;
    IF NOT FOUND THEN RAISE serialization_failure USING MESSAGE = 'Embedding index or permission version changed'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER search_embedding_state BEFORE INSERT ON search.embedding_record
FOR EACH ROW EXECUTE FUNCTION search.guard_embedding_record();
CREATE TRIGGER search_embedding_history BEFORE UPDATE OR DELETE ON search.embedding_record
FOR EACH ROW EXECUTE FUNCTION search.reject_history_rewrite();

CREATE VIEW search.current_embedding AS
SELECT e.* FROM search.embedding_record e
JOIN search.current_index_record i ON (i.generation_id, i.asset_version_id, i.source_asset_revision, i.permission_scope_version)
    = (e.generation_id, e.asset_version_id, e.source_asset_revision, e.permission_scope_version)
JOIN ai.derived_artifact a ON a.id = e.artifact_id AND a.current_revision = e.artifact_revision
JOIN ai.derived_artifact_revision r ON (r.artifact_id, r.revision) = (e.artifact_id, e.artifact_revision)
WHERE r.publication_status = 'PUBLISHED';

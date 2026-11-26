CREATE TABLE outbox.event (
    event_id varchar(80) PRIMARY KEY CHECK (event_id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    event_type varchar(160) NOT NULL CHECK (event_type ~ '^[a-z][a-z0-9_.-]+$'),
    event_version integer NOT NULL CHECK (event_version >= 1),
    aggregate_type varchar(80) NOT NULL CHECK (length(aggregate_type) > 0),
    aggregate_id varchar(80) NOT NULL CHECK (aggregate_id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    aggregate_revision bigint NOT NULL CHECK (aggregate_revision BETWEEN 1 AND 9007199254740991),
    occurred_at timestamptz NOT NULL,
    producer varchar(80) NOT NULL CHECK (length(producer) > 0),
    trace_id varchar(128) NOT NULL CHECK (trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    published_at timestamptz CHECK (published_at >= occurred_at),
    UNIQUE (aggregate_type, aggregate_id, aggregate_revision)
);

CREATE INDEX outbox_pending_idx ON outbox.event (occurred_at, event_id) WHERE published_at IS NULL;

CREATE TABLE outbox.consumer_offset (
    consumer_id varchar(160) NOT NULL CHECK (length(consumer_id) > 0),
    event_id varchar(80) NOT NULL REFERENCES outbox.event (event_id),
    acknowledged_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (consumer_id, event_id)
);

CREATE INDEX outbox_consumer_event_idx ON outbox.consumer_offset (event_id);

CREATE FUNCTION outbox.utc_timestamp(p_at timestamptz) RETURNS text LANGUAGE sql STABLE STRICT AS $$
    SELECT to_char(p_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
$$;

CREATE VIEW outbox.event_envelope AS
SELECT e.event_id, e.published_at, jsonb_build_object(
    'eventId', e.event_id, 'eventType', e.event_type, 'eventVersion', e.event_version,
    'aggregateType', e.aggregate_type, 'aggregateId', e.aggregate_id,
    'occurredAt', outbox.utc_timestamp(e.occurred_at), 'producer', e.producer,
    'traceId', e.trace_id, 'payload', e.payload
) AS envelope
FROM outbox.event e;

CREATE FUNCTION task.enqueue_accepted_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- The successful version-1 attempt follows capability binding (1) and leasing (2).
    INSERT INTO outbox.event (
        event_id, event_type, event_version, aggregate_type, aggregate_id, aggregate_revision,
        occurred_at, producer, trace_id, payload
    )
    SELECT 'evt_' || gen_random_uuid(), 'task.attempt.result.accepted', 1,
        'TaskAttempt', a.id, 3, NEW.accepted_at, 'guize-control', t.trace_id, jsonb_build_object(
        'revision', 3, 'taskId', t.id, 'planId', p.id, 'planVersion', p.version,
        'stepId', s.id, 'stepVersion', s.version, 'attemptId', a.id, 'nodeId', a.node_id,
        'fencing', a.fencing, 'inputVersionId', s.input_version_id, 'inputSha256', s.input_sha256,
        'capabilityId', a.capability_id, 'capabilityVersion', a.capability_version,
        'protocolVersion', a.protocol_version, 'artifactManifestId', NEW.artifact_manifest_id,
        'artifactManifestSha256', NEW.artifact_manifest_sha256,
        'acceptedAt', outbox.utc_timestamp(NEW.accepted_at)
    )
    FROM task.attempt a
    JOIN task.plan_step s ON s.step_key = a.step_key
    JOIN task.plan p ON p.plan_key = s.plan_key
    JOIN task.task t ON t.id = p.task_id
    WHERE a.id = NEW.attempt_id AND s.step_key = NEW.step_key;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Could not bind the outbox event to accepted attempt %', NEW.attempt_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER task_accepted_attempt_outbox
AFTER INSERT ON task.accepted_result
FOR EACH ROW EXECUTE FUNCTION task.enqueue_accepted_attempt();

ALTER TABLE task.plan_step ADD CONSTRAINT task_step_input_identity UNIQUE (step_key, input_version_id);
ALTER TABLE task.accepted_result ADD CONSTRAINT task_accepted_manifest_identity
    UNIQUE (attempt_id, step_key, artifact_manifest_id, artifact_manifest_sha256);

CREATE TABLE ai.derived_artifact (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    asset_version_id varchar(80) NOT NULL REFERENCES asset.version (id),
    producer_attempt_id task.identifier NOT NULL,
    producer_step_key bigint NOT NULL,
    manifest_id task.identifier NOT NULL,
    manifest_sha256 varchar(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    manifest_entry_key varchar(256) NOT NULL CHECK (length(manifest_entry_key) > 0),
    artifact_type text NOT NULL CHECK (artifact_type IN ('ASR', 'ALIGNMENT', 'DIARIZATION', 'OCR',
        'VLM', 'TRANSLATION', 'SUMMARY', 'TAG', 'EMBEDDING', 'THUMBNAIL_REAL', 'THUMBNAIL_GENERATED')),
    current_revision bigint CHECK (current_revision BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (producer_attempt_id, manifest_entry_key),
    CONSTRAINT artifact_accepted_manifest FOREIGN KEY
        (producer_attempt_id, producer_step_key, manifest_id, manifest_sha256)
        REFERENCES task.accepted_result (attempt_id, step_key, artifact_manifest_id, artifact_manifest_sha256),
    CONSTRAINT artifact_producer_input FOREIGN KEY (producer_step_key, asset_version_id)
        REFERENCES task.plan_step (step_key, input_version_id)
);

CREATE INDEX artifact_asset_version_idx ON ai.derived_artifact (asset_version_id, artifact_type, id);

CREATE TABLE ai.derived_artifact_revision (
    artifact_id varchar(80) NOT NULL REFERENCES ai.derived_artifact (id),
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    model_id varchar(80),
    model_version varchar(256) NOT NULL CHECK (length(model_version) > 0),
    prompt_version varchar(256) NOT NULL CHECK (length(prompt_version) > 0),
    pipeline_version_id varchar(80) NOT NULL CHECK (pipeline_version_id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    parameters_hash varchar(64) NOT NULL CHECK (parameters_hash ~ '^[0-9a-f]{64}$'),
    language varchar(64),
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    uncertainty boolean NOT NULL,
    generated boolean NOT NULL,
    quality_status text NOT NULL CHECK (length(quality_status) > 0),
    publication_status text NOT NULL CHECK (publication_status IN ('DRAFT', 'PUBLISHED', 'REVOKED')),
    content_reference text,
    structured_payload jsonb CHECK (jsonb_typeof(structured_payload) = 'object'),
    output_sha256 varchar(64) NOT NULL CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
    created_by varchar(80) NOT NULL CHECK (created_by ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    trace_id varchar(128) NOT NULL CHECK (trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz,
    PRIMARY KEY (artifact_id, revision),
    CHECK (content_reference IS NOT NULL OR structured_payload IS NOT NULL),
    CHECK ((publication_status = 'PUBLISHED') = (published_at IS NOT NULL)),
    CHECK (published_at >= created_at)
);

ALTER TABLE ai.derived_artifact ADD CONSTRAINT artifact_current_revision FOREIGN KEY (id, current_revision)
    REFERENCES ai.derived_artifact_revision (artifact_id, revision);

CREATE FUNCTION ai.reject_artifact_revision_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Artifact revisions are append-only' USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER artifact_revision_append_only
BEFORE UPDATE OR DELETE ON ai.derived_artifact_revision
FOR EACH ROW EXECUTE FUNCTION ai.reject_artifact_revision_rewrite();

CREATE FUNCTION ai.advance_artifact_revision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    r ai.derived_artifact_revision%ROWTYPE;
BEGIN
    IF ROW(OLD.id, OLD.asset_version_id, OLD.producer_attempt_id, OLD.producer_step_key,
           OLD.manifest_id, OLD.manifest_sha256, OLD.manifest_entry_key, OLD.artifact_type, OLD.created_at)
        IS DISTINCT FROM ROW(NEW.id, NEW.asset_version_id, NEW.producer_attempt_id, NEW.producer_step_key,
           NEW.manifest_id, NEW.manifest_sha256, NEW.manifest_entry_key, NEW.artifact_type, NEW.created_at)
    THEN
        RAISE EXCEPTION 'Artifact lineage is immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.current_revision IS NOT DISTINCT FROM OLD.current_revision THEN
        RETURN NEW;
    END IF;
    IF NEW.current_revision IS DISTINCT FROM coalesce(OLD.current_revision, 0) + 1 THEN
        RAISE EXCEPTION 'Artifact must advance to the next revision' USING ERRCODE = '23514';
    END IF;

    SELECT * INTO STRICT r FROM ai.derived_artifact_revision
    WHERE artifact_id = NEW.id AND revision = NEW.current_revision;
    IF r.publication_status = 'PUBLISHED' THEN
        INSERT INTO outbox.event (
            event_id, event_type, event_version, aggregate_type, aggregate_id, aggregate_revision,
            occurred_at, producer, trace_id, payload
        ) VALUES ('evt_' || gen_random_uuid(), 'artifact.published', 1, 'DerivedArtifact', NEW.id,
            r.revision, r.published_at, 'guize-control', r.trace_id, jsonb_build_object(
            'artifactId', NEW.id, 'assetVersionId', NEW.asset_version_id, 'artifactType', NEW.artifact_type,
            'modelVersion', r.model_version, 'promptVersion', r.prompt_version, 'confidence', r.confidence,
            'uncertainty', r.uncertainty, 'generated', r.generated, 'revision', r.revision,
            'pipelineVersionId', r.pipeline_version_id, 'parametersHash', r.parameters_hash,
            'publicationStatus', r.publication_status, 'publishedAt', outbox.utc_timestamp(r.published_at)
        ));
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER artifact_advance_revision
AFTER UPDATE ON ai.derived_artifact
FOR EACH ROW EXECUTE FUNCTION ai.advance_artifact_revision();

REVOKE EXECUTE ON FUNCTION task.enqueue_accepted_attempt() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION ai.reject_artifact_revision_rewrite() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION ai.advance_artifact_revision() FROM PUBLIC;

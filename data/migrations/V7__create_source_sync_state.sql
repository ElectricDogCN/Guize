ALTER TABLE task.task ALTER COLUMN input_version_id DROP NOT NULL;
ALTER TABLE task.task ADD CONSTRAINT task_input_version_required
    CHECK (input_version_id IS NOT NULL OR (type = 'source.sync.v1' AND active_plan_key IS NULL));
ALTER TABLE task.task ADD CONSTRAINT task_id_type_unique UNIQUE (id, type);

CREATE TABLE source.capability (
    data_source_id varchar(80) NOT NULL REFERENCES source.data_source (id),
    capability varchar(64) NOT NULL CHECK (capability ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    connector_version varchar(64) NOT NULL CHECK (length(connector_version) > 0),
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (data_source_id, capability)
);

CREATE TABLE source.credential_reference (
    data_source_id varchar(80) NOT NULL PRIMARY KEY REFERENCES source.data_source (id),
    credential_reference varchar(74) NOT NULL CHECK (credential_reference ~ '^secretref_[A-Za-z0-9_-]{1,64}$'),
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    updated_at timestamptz NOT NULL
);

CREATE TABLE source.sync_policy (
    data_source_id varchar(80) NOT NULL REFERENCES source.data_source (id),
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    scan_interval_seconds integer CHECK (scan_interval_seconds > 0),
    max_attempts integer NOT NULL CHECK (max_attempts > 0),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (data_source_id, revision)
);

CREATE TABLE source.sync_request (
    task_id task.identifier PRIMARY KEY,
    task_type varchar(256) GENERATED ALWAYS AS ('source.sync.v1') STORED,
    data_source_id varchar(80) NOT NULL,
    policy_revision bigint NOT NULL,
    scope_key varchar(256) NOT NULL CHECK (length(scope_key) > 0),
    mode text NOT NULL CHECK (mode IN ('INCREMENTAL', 'RECONCILE')),
    CONSTRAINT sync_request_task FOREIGN KEY (task_id, task_type) REFERENCES task.task (id, type),
    FOREIGN KEY (data_source_id, policy_revision) REFERENCES source.sync_policy (data_source_id, revision),
    UNIQUE (task_id, data_source_id, policy_revision, scope_key, mode)
);

CREATE TABLE source.sync_job (
    id task.identifier PRIMARY KEY,
    task_id task.identifier NOT NULL,
    data_source_id varchar(80) NOT NULL,
    policy_revision bigint NOT NULL,
    scope_key varchar(256) NOT NULL,
    mode text NOT NULL,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED')),
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    CONSTRAINT sync_job_request_scope FOREIGN KEY (task_id, data_source_id, policy_revision, scope_key, mode)
        REFERENCES source.sync_request (task_id, data_source_id, policy_revision, scope_key, mode),
    CONSTRAINT sync_job_attempt UNIQUE (task_id, attempt_number),
    CONSTRAINT sync_job_checkpoint_identity UNIQUE (id, data_source_id, policy_revision, scope_key, mode),
    CHECK ((status = 'RUNNING' AND finished_at IS NULL)
        OR (status <> 'RUNNING' AND finished_at IS NOT NULL AND finished_at >= started_at))
);

CREATE UNIQUE INDEX sync_job_running_scope_idx ON source.sync_job (data_source_id, scope_key)
    WHERE status = 'RUNNING';
CREATE INDEX sync_job_source_policy_idx ON source.sync_job (data_source_id, policy_revision, started_at DESC);

CREATE FUNCTION source.require_sync_job_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'RUNNING' OR ROW(OLD.id, OLD.task_id, OLD.data_source_id, OLD.policy_revision,
                                    OLD.scope_key, OLD.mode, OLD.attempt_number, OLD.started_at)
                            IS DISTINCT FROM ROW(NEW.id, NEW.task_id, NEW.data_source_id, NEW.policy_revision,
                                                 NEW.scope_key, NEW.mode, NEW.attempt_number, NEW.started_at)
    THEN
        RAISE check_violation USING CONSTRAINT = 'sync_job_transition', MESSAGE = 'Invalid sync job transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER sync_job_transition BEFORE UPDATE ON source.sync_job
FOR EACH ROW EXECUTE FUNCTION source.require_sync_job_transition();

CREATE TABLE source.sync_checkpoint (
    data_source_id varchar(80) NOT NULL,
    policy_revision bigint NOT NULL,
    scope_key varchar(256) NOT NULL,
    mode text NOT NULL,
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    cursor_value varchar(4096) CHECK (length(cursor_value) > 0),
    job_id task.identifier NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (data_source_id, policy_revision, scope_key, mode),
    CONSTRAINT sync_checkpoint_job_scope FOREIGN KEY (job_id, data_source_id, policy_revision, scope_key, mode)
        REFERENCES source.sync_job (id, data_source_id, policy_revision, scope_key, mode)
);

CREATE INDEX sync_checkpoint_job_idx ON source.sync_checkpoint (job_id);

CREATE FUNCTION source.record_sync_checkpoint(p_job_id task.identifier, p_expected_revision bigint, p_cursor text)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    source_id varchar(80);
    job source.sync_job%ROWTYPE;
    previous_revision bigint;
    next_revision bigint;
BEGIN
    SELECT s.id INTO source_id
    FROM source.data_source s JOIN source.sync_job j ON j.data_source_id = s.id
    WHERE j.id = p_job_id AND s.status = 'ACTIVE' FOR SHARE OF s;
    IF NOT FOUND THEN
        RAISE serialization_failure USING MESSAGE = 'Source cannot accept this sync checkpoint';
    END IF;

    SELECT * INTO job FROM source.sync_job WHERE id = p_job_id AND data_source_id = source_id FOR UPDATE;
    IF NOT FOUND OR job.status <> 'RUNNING' THEN
        RAISE serialization_failure USING MESSAGE = 'Sync job cannot accept a checkpoint';
    END IF;

    SELECT revision INTO previous_revision FROM source.sync_checkpoint
    WHERE (data_source_id, policy_revision, scope_key, mode)
        = (job.data_source_id, job.policy_revision, job.scope_key, job.mode);
    IF p_expected_revision IS DISTINCT FROM COALESCE(previous_revision, 0) THEN
        RAISE serialization_failure USING MESSAGE = 'Stale sync checkpoint revision';
    END IF;

    next_revision := COALESCE(previous_revision, 0) + 1;
    INSERT INTO source.sync_checkpoint (data_source_id, policy_revision, scope_key, mode,
                                        revision, cursor_value, job_id, updated_at)
    VALUES (job.data_source_id, job.policy_revision, job.scope_key, job.mode,
            next_revision, p_cursor, job.id, clock_timestamp())
    ON CONFLICT (data_source_id, policy_revision, scope_key, mode) DO UPDATE
    SET revision = EXCLUDED.revision, cursor_value = EXCLUDED.cursor_value,
        job_id = EXCLUDED.job_id, updated_at = EXCLUDED.updated_at;
    RETURN next_revision;
END;
$$;

REVOKE EXECUTE ON FUNCTION source.record_sync_checkpoint(task.identifier, bigint, text) FROM PUBLIC;

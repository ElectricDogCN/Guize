CREATE DOMAIN task.identifier AS varchar(80) CHECK (VALUE ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$');

CREATE TABLE task.task (
    id task.identifier PRIMARY KEY,
    type varchar(256) NOT NULL CHECK (length(type) > 0),
    owner_id task.identifier NOT NULL,
    input_version_id task.identifier NOT NULL REFERENCES asset.version (id),
    idempotency_scope text NOT NULL CHECK (length(idempotency_scope) BETWEEN 1 AND 256),
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 256),
    status text NOT NULL CHECK (status IN (
        'CREATED', 'QUEUED', 'DISPATCHING', 'RUNNING', 'PAUSING', 'PAUSED',
        'WAITING_RESOURCE', 'WAITING_BUDGET', 'WAITING_APPROVAL', 'RETRYING',
        'SUCCEEDED', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED'
    )),
    priority smallint NOT NULL CHECK (priority BETWEEN 0 AND 8),
    progress numeric NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991),
    trace_id varchar(128) NOT NULL CHECK (trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    failure jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active_plan_key bigint,
    CONSTRAINT task_idempotency UNIQUE (idempotency_scope, idempotency_key)
);

CREATE INDEX task_dispatch_idx ON task.task (status, priority, created_at, id);
CREATE INDEX task_owner_created_idx ON task.task (owner_id, created_at DESC);

CREATE TABLE task.execution (
    id task.identifier PRIMARY KEY,
    task_id task.identifier NOT NULL REFERENCES task.task (id),
    workflow_id text NOT NULL,
    workflow_run_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (workflow_id, workflow_run_id)
);

CREATE INDEX task_execution_task_idx ON task.execution (task_id);

CREATE TABLE task.worker (
    id task.identifier PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('ONLINE', 'OFFLINE', 'DRAINING')),
    heartbeat_expires_at timestamptz NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991)
);

CREATE TABLE task.worker_capability (
    worker_id task.identifier NOT NULL REFERENCES task.worker (id),
    capability_id task.identifier NOT NULL,
    capability_version varchar(64) NOT NULL CHECK (capability_version ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'),
    protocol_version varchar(64) NOT NULL CHECK (protocol_version ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'),
    PRIMARY KEY (worker_id, capability_id, capability_version, protocol_version)
);

CREATE TABLE task.plan (
    plan_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id task.identifier NOT NULL REFERENCES task.task (id),
    id task.identifier NOT NULL,
    version bigint NOT NULL CHECK (version BETWEEN 1 AND 9007199254740991),
    compiled_plan_sha256 varchar(64) NOT NULL CHECK (compiled_plan_sha256 ~ '^[0-9a-f]{64}$'),
    accepted_at timestamptz NOT NULL,
    UNIQUE (task_id, id, version),
    UNIQUE (task_id, plan_key)
);

ALTER TABLE task.task ADD CONSTRAINT task_active_plan_ownership
    FOREIGN KEY (id, active_plan_key) REFERENCES task.plan (task_id, plan_key);

CREATE TABLE task.plan_step (
    step_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plan_key bigint NOT NULL REFERENCES task.plan (plan_key),
    id task.identifier NOT NULL,
    version bigint NOT NULL CHECK (version BETWEEN 1 AND 9007199254740991),
    input_version_id task.identifier NOT NULL REFERENCES asset.version (id),
    input_sha256 varchar(64) NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    priority smallint NOT NULL CHECK (priority BETWEEN 0 AND 8),
    ready_at timestamptz,
    current_version boolean NOT NULL,
    current_fencing bigint NOT NULL DEFAULT 0 CHECK (current_fencing BETWEEN 0 AND 9007199254740991),
    UNIQUE (plan_key, id, version)
);

CREATE UNIQUE INDEX task_current_step_version_idx ON task.plan_step (plan_key, id) WHERE current_version;

CREATE TABLE task.attempt (
    id task.identifier PRIMARY KEY,
    step_key bigint NOT NULL REFERENCES task.plan_step (step_key),
    node_id task.identifier NOT NULL,
    fencing bigint NOT NULL CHECK (fencing BETWEEN 1 AND 9007199254740991),
    capability_id task.identifier NOT NULL,
    capability_version varchar(64) NOT NULL,
    protocol_version varchar(64) NOT NULL,
    UNIQUE (step_key, fencing),
    UNIQUE (step_key, id),
    FOREIGN KEY (node_id, capability_id, capability_version, protocol_version)
        REFERENCES task.worker_capability (worker_id, capability_id, capability_version, protocol_version)
);

CREATE TABLE task.lease (
    attempt_id task.identifier PRIMARY KEY REFERENCES task.attempt (id),
    leased_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > leased_at),
    cancellation_requested_at timestamptz,
    ended_at timestamptz CHECK (ended_at >= leased_at)
);

CREATE INDEX task_lease_expiry_idx ON task.lease (expires_at) WHERE ended_at IS NULL;

CREATE TABLE task.accepted_result (
    step_key bigint PRIMARY KEY,
    attempt_id task.identifier NOT NULL UNIQUE,
    artifact_manifest_id task.identifier NOT NULL,
    artifact_manifest_sha256 varchar(64) NOT NULL CHECK (artifact_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    accepted_at timestamptz NOT NULL,
    FOREIGN KEY (step_key, attempt_id) REFERENCES task.attempt (step_key, id)
);

CREATE FUNCTION task.lease_attempt(
    p_step_key bigint, p_attempt_id text, p_node_id text, p_capability_id text,
    p_capability_version text, p_protocol_version text, p_expires_at timestamptz
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    task_row task.task%ROWTYPE;
    step_row task.plan_step%ROWTYPE;
    lease_started_at timestamptz;
    next_fencing bigint;
BEGIN
    SELECT t.* INTO task_row
    FROM task.task t JOIN task.plan p ON p.task_id = t.id
    JOIN task.plan_step s ON s.plan_key = p.plan_key
    WHERE s.step_key = p_step_key FOR UPDATE OF t;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT * INTO STRICT step_row FROM task.plan_step WHERE step_key = p_step_key FOR UPDATE;
    lease_started_at := clock_timestamp();
    IF task_row.active_plan_key IS DISTINCT FROM step_row.plan_key
        OR task_row.status NOT IN ('DISPATCHING', 'RUNNING', 'RETRYING')
        OR NOT step_row.current_version OR step_row.ready_at IS NULL OR step_row.ready_at > lease_started_at
        OR p_expires_at IS NULL OR p_expires_at <= lease_started_at
        OR EXISTS (SELECT 1 FROM task.accepted_result WHERE step_key = p_step_key)
        OR EXISTS (
            SELECT 1 FROM task.attempt a JOIN task.lease l ON l.attempt_id = a.id
            WHERE a.step_key = p_step_key AND a.fencing = step_row.current_fencing
              AND l.ended_at IS NULL AND l.expires_at > lease_started_at
        )
        OR NOT EXISTS (
            SELECT 1 FROM task.worker w
            WHERE w.id = p_node_id AND w.status = 'ONLINE' AND w.heartbeat_expires_at > lease_started_at
        )
    THEN
        RETURN NULL;
    END IF;

    next_fencing := step_row.current_fencing + 1;
    UPDATE task.plan_step SET current_fencing = next_fencing WHERE step_key = p_step_key;
    INSERT INTO task.attempt (id, step_key, node_id, fencing, capability_id, capability_version, protocol_version)
    VALUES (p_attempt_id, p_step_key, p_node_id, next_fencing, p_capability_id, p_capability_version, p_protocol_version);
    INSERT INTO task.lease (attempt_id, leased_at, expires_at) VALUES (p_attempt_id, lease_started_at, p_expires_at);
    RETURN next_fencing;
END;
$$;

CREATE FUNCTION task.accept_attempt_result(
    p_attempt_id text, p_node_id text, p_fencing bigint, p_input_version_id text, p_input_sha256 text,
    p_capability_id text, p_capability_version text, p_protocol_version text,
    p_manifest_id text, p_manifest_sha256 text
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    task_row task.task%ROWTYPE;
    step_row task.plan_step%ROWTYPE;
    attempt_row task.attempt%ROWTYPE;
    lease_row task.lease%ROWTYPE;
    result_row task.accepted_result%ROWTYPE;
    received_at timestamptz;
BEGIN
    IF p_manifest_id IS NULL OR p_manifest_id !~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'
        OR p_manifest_sha256 IS NULL OR p_manifest_sha256 !~ '^[0-9a-f]{64}$'
    THEN
        RETURN 'REJECTED';
    END IF;

    SELECT a.* INTO attempt_row FROM task.attempt a WHERE a.id = p_attempt_id;
    IF NOT FOUND OR ROW(attempt_row.node_id, attempt_row.fencing, attempt_row.capability_id,
                       attempt_row.capability_version, attempt_row.protocol_version)
        IS DISTINCT FROM ROW(p_node_id, p_fencing, p_capability_id, p_capability_version, p_protocol_version)
    THEN
        RETURN 'REJECTED';
    END IF;

    SELECT t.* INTO STRICT task_row
    FROM task.task t JOIN task.plan p ON p.task_id = t.id
    JOIN task.plan_step s ON s.plan_key = p.plan_key
    WHERE s.step_key = attempt_row.step_key FOR UPDATE OF t;

    SELECT * INTO STRICT step_row FROM task.plan_step WHERE step_key = attempt_row.step_key FOR UPDATE;
    IF ROW(step_row.input_version_id, step_row.input_sha256) IS DISTINCT FROM ROW(p_input_version_id, p_input_sha256)
    THEN
        RETURN 'REJECTED';
    END IF;

    SELECT * INTO result_row FROM task.accepted_result WHERE step_key = step_row.step_key;
    IF FOUND THEN
        IF ROW(result_row.attempt_id, result_row.artifact_manifest_id, result_row.artifact_manifest_sha256)
            IS NOT DISTINCT FROM ROW(p_attempt_id, p_manifest_id, p_manifest_sha256)
        THEN
            RETURN 'REPLAYED';
        END IF;
        RETURN 'REJECTED';
    END IF;

    SELECT * INTO STRICT lease_row FROM task.lease WHERE attempt_id = p_attempt_id FOR UPDATE;
    received_at := clock_timestamp();
    IF task_row.active_plan_key IS DISTINCT FROM step_row.plan_key
        OR task_row.status NOT IN ('DISPATCHING', 'RUNNING', 'RETRYING')
        OR NOT step_row.current_version OR step_row.current_fencing <> attempt_row.fencing
        OR lease_row.expires_at <= received_at OR lease_row.ended_at IS NOT NULL
        OR lease_row.cancellation_requested_at IS NOT NULL
    THEN
        RETURN 'REJECTED';
    END IF;

    INSERT INTO task.accepted_result (step_key, attempt_id, artifact_manifest_id, artifact_manifest_sha256, accepted_at)
    VALUES (step_row.step_key, p_attempt_id, p_manifest_id, p_manifest_sha256, received_at);
    UPDATE task.lease SET ended_at = received_at WHERE attempt_id = p_attempt_id;
    RETURN 'ACCEPTED';
END;
$$;

REVOKE EXECUTE ON FUNCTION task.lease_attempt(bigint, text, text, text, text, text, timestamptz) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION task.accept_attempt_result(text, text, bigint, text, text, text, text, text, text, text) FROM PUBLIC;

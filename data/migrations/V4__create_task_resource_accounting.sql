CREATE TABLE task.resource_pool (
    id task.identifier PRIMARY KEY,
    node_id task.identifier NOT NULL REFERENCES task.worker (id),
    kind text NOT NULL CHECK (kind IN ('CODEC_SLOT', 'WORKER_SLOT', 'MEMORY_BYTES',
        'TEMP_STORAGE_BYTES', 'EXECUTION_BUDGET_SECONDS')),
    capacity_quantity bigint NOT NULL CHECK (capacity_quantity BETWEEN 0 AND 9007199254740991),
    held_quantity bigint NOT NULL DEFAULT 0 CHECK (held_quantity BETWEEN 0 AND 9007199254740991),
    spent_quantity bigint NOT NULL DEFAULT 0 CHECK (spent_quantity BETWEEN 0 AND 9007199254740991),
    CHECK (held_quantity + spent_quantity <= capacity_quantity),
    CHECK (kind = 'EXECUTION_BUDGET_SECONDS' OR spent_quantity = 0)
);

CREATE INDEX resource_pool_node_idx ON task.resource_pool (node_id, kind);

CREATE TABLE task.resource_reservation (
    id task.identifier PRIMARY KEY,
    attempt_id task.identifier NOT NULL REFERENCES task.attempt (id),
    resource_id task.identifier NOT NULL REFERENCES task.resource_pool (id),
    quantity bigint NOT NULL CHECK (quantity BETWEEN 1 AND 9007199254740991),
    reserved_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > reserved_at),
    charged_quantity bigint CHECK (charged_quantity BETWEEN 0 AND quantity),
    release_reason text CHECK (release_reason IN ('TASK_COMPLETED', 'TASK_FAILED', 'ATTEMPT_CANCELLED',
        'LEASE_EXPIRED', 'ATTEMPT_REPLACED', 'RESERVATION_REVOKED')),
    released_at timestamptz CHECK (released_at >= reserved_at),
    UNIQUE (attempt_id, resource_id),
    CHECK ((released_at IS NULL) = (charged_quantity IS NULL)),
    CHECK ((released_at IS NULL) = (release_reason IS NULL))
);

CREATE INDEX resource_reservation_pending_idx ON task.resource_reservation (expires_at) WHERE released_at IS NULL;
CREATE INDEX resource_reservation_pool_idx ON task.resource_reservation (resource_id, reserved_at);

CREATE FUNCTION task.reserve_resource(
    p_id task.identifier, p_attempt_id task.identifier, p_resource_id task.identifier,
    p_quantity bigint, p_expires_at timestamptz
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    attempt_row task.attempt%ROWTYPE;
    task_row task.task%ROWTYPE;
    step_row task.plan_step%ROWTYPE;
    lease_row task.lease%ROWTYPE;
    pool_row task.resource_pool%ROWTYPE;
    prior task.resource_reservation%ROWTYPE;
    reserved_now timestamptz;
BEGIN
    IF p_id IS NULL OR p_quantity IS NULL OR p_quantity <= 0 OR p_expires_at IS NULL THEN
        RETURN 'REJECTED';
    END IF;

    SELECT * INTO attempt_row FROM task.attempt WHERE id = p_attempt_id;
    IF NOT FOUND THEN
        RETURN 'REJECTED';
    END IF;
    SELECT t.* INTO STRICT task_row
    FROM task.task t JOIN task.plan p ON p.task_id = t.id
    JOIN task.plan_step s ON s.plan_key = p.plan_key
    WHERE s.step_key = attempt_row.step_key FOR UPDATE OF t;
    SELECT * INTO STRICT step_row FROM task.plan_step WHERE step_key = attempt_row.step_key FOR UPDATE;
    SELECT * INTO STRICT lease_row FROM task.lease WHERE attempt_id = p_attempt_id FOR UPDATE;

    SELECT * INTO pool_row FROM task.resource_pool WHERE id = p_resource_id FOR UPDATE;
    IF NOT FOUND OR pool_row.node_id <> attempt_row.node_id THEN
        RETURN 'REJECTED';
    END IF;

    SELECT * INTO prior FROM task.resource_reservation WHERE id = p_id;
    IF FOUND THEN
        IF ROW(prior.attempt_id, prior.resource_id, prior.quantity, prior.expires_at)
            IS NOT DISTINCT FROM ROW(p_attempt_id, p_resource_id, p_quantity, p_expires_at)
        THEN
            RETURN 'REPLAYED';
        END IF;
        RETURN 'REJECTED';
    END IF;

    reserved_now := clock_timestamp();
    IF task_row.active_plan_key IS DISTINCT FROM step_row.plan_key OR NOT step_row.current_version
        OR task_row.status NOT IN ('DISPATCHING', 'RUNNING', 'RETRYING')
        OR step_row.current_fencing <> attempt_row.fencing OR lease_row.ended_at IS NOT NULL
        OR lease_row.cancellation_requested_at IS NOT NULL OR p_expires_at <= reserved_now
        OR p_expires_at > lease_row.expires_at
        OR p_quantity > pool_row.capacity_quantity - pool_row.held_quantity - pool_row.spent_quantity
    THEN
        RETURN 'REJECTED';
    END IF;

    INSERT INTO task.resource_reservation (id, attempt_id, resource_id, quantity, reserved_at, expires_at)
    VALUES (p_id, p_attempt_id, p_resource_id, p_quantity, reserved_now, p_expires_at)
    ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN
        RETURN 'REJECTED';
    END IF;
    UPDATE task.resource_pool SET held_quantity = held_quantity + p_quantity WHERE id = p_resource_id;
    RETURN 'RESERVED';
END;
$$;

CREATE FUNCTION task.settle_resource(
    p_id task.identifier, p_charged_quantity bigint, p_release_reason text
) RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    chosen_resource task.identifier;
    pool_row task.resource_pool%ROWTYPE;
    reservation task.resource_reservation%ROWTYPE;
BEGIN
    IF p_charged_quantity IS NULL OR p_charged_quantity < 0
        OR p_release_reason IS NULL OR p_release_reason NOT IN ('TASK_COMPLETED', 'TASK_FAILED',
            'ATTEMPT_CANCELLED', 'LEASE_EXPIRED', 'ATTEMPT_REPLACED', 'RESERVATION_REVOKED')
    THEN
        RETURN 'REJECTED';
    END IF;
    SELECT resource_id INTO chosen_resource FROM task.resource_reservation WHERE id = p_id;
    IF NOT FOUND THEN
        RETURN 'REJECTED';
    END IF;

    SELECT * INTO STRICT pool_row FROM task.resource_pool WHERE id = chosen_resource FOR UPDATE;
    SELECT * INTO STRICT reservation FROM task.resource_reservation WHERE id = p_id FOR UPDATE;
    IF reservation.released_at IS NOT NULL THEN
        IF ROW(reservation.charged_quantity, reservation.release_reason)
            IS NOT DISTINCT FROM ROW(p_charged_quantity, p_release_reason)
        THEN
            RETURN 'REPLAYED';
        END IF;
        RETURN 'REJECTED';
    END IF;
    IF p_charged_quantity > reservation.quantity THEN
        RETURN 'REJECTED';
    END IF;

    UPDATE task.resource_pool
    SET held_quantity = held_quantity - reservation.quantity,
        spent_quantity = spent_quantity +
            CASE WHEN pool_row.kind = 'EXECUTION_BUDGET_SECONDS' THEN p_charged_quantity ELSE 0 END
    WHERE id = chosen_resource;
    UPDATE task.resource_reservation
    SET charged_quantity = p_charged_quantity, release_reason = p_release_reason, released_at = clock_timestamp()
    WHERE id = p_id;
    RETURN 'SETTLED';
END;
$$;

REVOKE EXECUTE ON FUNCTION task.reserve_resource(task.identifier, task.identifier, task.identifier, bigint, timestamptz) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION task.settle_resource(task.identifier, bigint, text) FROM PUBLIC;

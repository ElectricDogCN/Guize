BEGIN;

\ir task_fixture.sql

DO $$
DECLARE
    plan_key_v1 bigint;
    plan_key_v2 bigint;
    step_key_v1 bigint;
    step_key_v2 bigint;
    other_step_key bigint;
    expiry timestamptz := clock_timestamp() + interval '30 minutes';
    input_digest text := repeat('a', 64);
    result_digest text := repeat('b', 64);
    violated_constraint text;
BEGIN
    BEGIN
        INSERT INTO task.task (id, type, owner_id, input_version_id, idempotency_scope, idempotency_key, status, priority, trace_id)
        SELECT 'tsk_duplicate', type, owner_id, input_version_id, idempotency_scope, idempotency_key, status, priority, trace_id
        FROM task.task WHERE id = 'tsk_fixture';
        RAISE EXCEPTION 'Task creation idempotency key is not unique';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'task_idempotency' THEN RAISE; END IF;
    END;

    INSERT INTO task.plan (task_id, id, version, compiled_plan_sha256, accepted_at)
    VALUES ('tsk_fixture', 'plan_fixture', 1, repeat('c', 64), clock_timestamp()) RETURNING plan_key INTO plan_key_v1;
    UPDATE task.task SET active_plan_key = plan_key_v1 WHERE id = 'tsk_fixture';
    INSERT INTO task.plan_step (plan_key, id, version, input_version_id, input_sha256, priority, ready_at, current_version)
    VALUES (plan_key_v1, 'stp_fixture', 1, 'ver_task', input_digest, 3, clock_timestamp(), true)
    RETURNING step_key INTO step_key_v1;

    IF task.lease_attempt(step_key_v1, 'att_first', 'node_first', 'cap_av1', '1', '1', expiry) IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'First lease must use fencing token 1';
    END IF;
    IF task.lease_attempt(step_key_v1, 'att_blocked', 'node_second', 'cap_av1', '1', '1', expiry) IS NOT NULL THEN
        RAISE EXCEPTION 'A live attempt must exclude a replacement';
    END IF;

    UPDATE task.lease SET leased_at = clock_timestamp() - interval '2 minutes',
        expires_at = clock_timestamp() - interval '1 minute' WHERE attempt_id = 'att_first';
    IF task.accept_attempt_result('att_first', 'node_first', 1, 'ver_task', input_digest,
        'cap_av1', '1', '1', 'manifest_attempt', result_digest) <> 'REJECTED'
        OR task.lease_attempt(step_key_v1, 'att_second', 'node_second', 'cap_av1', '1', '1', expiry) IS DISTINCT FROM 2
    THEN
        RAISE EXCEPTION 'Expiration must prevent acceptance and allow a higher fencing token';
    END IF;

    IF task.accept_attempt_result('att_first', 'node_first', 1, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_attempt', result_digest) <> 'REJECTED'
        OR task.accept_attempt_result('att_second', 'node_first', 2, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_attempt', result_digest) <> 'REJECTED'
        OR task.accept_attempt_result('att_second', 'node_second', 2, 'ver_task', repeat('d', 64),
            'cap_av1', '1', '1', 'manifest_attempt', result_digest) <> 'REJECTED'
        OR task.accept_attempt_result('att_second', 'node_second', 2, 'ver_task', input_digest,
            'cap_av1', '1', '2', 'manifest_attempt', result_digest) <> 'REJECTED'
    THEN
        RAISE EXCEPTION 'Prior fence or mismatching node, input, or protocol must be rejected';
    END IF;

    IF task.accept_attempt_result('att_second', 'node_second', 2, 'ver_task', input_digest,
        'cap_av1', '1', '1', 'manifest_attempt', result_digest) <> 'ACCEPTED'
    THEN
        RAISE EXCEPTION 'The current attempt must be accepted';
    END IF;
    IF task.accept_attempt_result('att_second', 'node_second', 2, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_attempt', result_digest) <> 'REPLAYED'
        OR task.accept_attempt_result('att_second', 'node_second', 2, 'ver_task', input_digest,
            'cap_av1', '1', '1', 'manifest_attempt', repeat('e', 64)) <> 'REJECTED'
        OR task.lease_attempt(step_key_v1, 'att_closed', 'node_first', 'cap_av1', '1', '1', expiry) IS NOT NULL
    THEN
        RAISE EXCEPTION 'One result must be accepted and exact retries must not add a result';
    END IF;

    INSERT INTO task.plan_step (plan_key, id, version, input_version_id, input_sha256, priority, ready_at, current_version)
    VALUES (plan_key_v1, 'stp_other', 1, 'ver_task', input_digest, 3, clock_timestamp(), true)
    RETURNING step_key INTO other_step_key;
    IF task.lease_attempt(other_step_key, 'att_other', 'node_first', 'cap_av1', '1', '1', expiry) IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'Ready step could not be leased';
    END IF;
    UPDATE task.lease SET cancellation_requested_at = clock_timestamp() WHERE attempt_id = 'att_other';
    IF task.accept_attempt_result('att_other', 'node_first', 1, 'ver_task', input_digest,
        'cap_av1', '1', '1', 'manifest_other', result_digest) <> 'REJECTED'
    THEN
        RAISE EXCEPTION 'Cancellation request must close result acceptance';
    END IF;

    INSERT INTO task.plan (task_id, id, version, compiled_plan_sha256, accepted_at)
    VALUES ('tsk_fixture', 'plan_fixture', 2, repeat('e', 64), clock_timestamp()) RETURNING plan_key INTO plan_key_v2;
    UPDATE task.task SET active_plan_key = plan_key_v2 WHERE id = 'tsk_fixture';
    INSERT INTO task.plan_step (plan_key, id, version, input_version_id, input_sha256, priority, ready_at, current_version)
    VALUES (plan_key_v2, 'stp_other', 2, 'ver_task', input_digest, 3, clock_timestamp(), true)
    RETURNING step_key INTO step_key_v2;
    IF task.lease_attempt(other_step_key, 'att_outdated', 'node_second', 'cap_av1', '1', '1', expiry) IS NOT NULL
        OR task.lease_attempt(step_key_v2, 'att_newplan', 'node_second', 'cap_av1', '1', '1', expiry) IS DISTINCT FROM 1
        OR (SELECT count(*) FROM task.accepted_result) <> 1
    THEN
        RAISE EXCEPTION 'Only the current plan may issue new leases and replay must have one stored result';
    END IF;
END;
$$;

ROLLBACK;

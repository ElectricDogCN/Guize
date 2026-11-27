\ir task_fixture.sql

INSERT INTO task.task (id, type, owner_id, input_version_id, idempotency_scope, idempotency_key, status, priority, trace_id)
VALUES ('tsk_other', 'transcode', 'usr_owner', 'ver_task', 'usr_owner:transcode', 'other-request', 'RUNNING', 3, 'trace-other');

INSERT INTO task.resource_pool (id, node_id, kind, capacity_quantity)
VALUES ('res_codec', 'node_first', 'CODEC_SLOT', 1),
       ('res_budget', 'node_first', 'EXECUTION_BUDGET_SECONDS', 10),
       ('res_foreign', 'node_second', 'MEMORY_BYTES', 20);

DO $$
DECLARE
    plan_first bigint;
    plan_second bigint;
    step_first bigint;
    step_second bigint;
    lease_deadline timestamptz := clock_timestamp() + interval '30 minutes';
    input_digest text := repeat('a', 64);
BEGIN
    INSERT INTO task.plan (task_id, id, version, compiled_plan_sha256, accepted_at)
    VALUES ('tsk_fixture', 'plan_fixture', 1, input_digest, clock_timestamp()) RETURNING plan_key INTO plan_first;
    INSERT INTO task.plan (task_id, id, version, compiled_plan_sha256, accepted_at)
    VALUES ('tsk_other', 'plan_other', 1, input_digest, clock_timestamp()) RETURNING plan_key INTO plan_second;
    UPDATE task.task SET active_plan_key = plan_first WHERE id = 'tsk_fixture';
    UPDATE task.task SET active_plan_key = plan_second WHERE id = 'tsk_other';

    INSERT INTO task.plan_step (plan_key, id, version, input_version_id, input_sha256, priority, ready_at, current_version)
    VALUES (plan_first, 'stp_first', 1, 'ver_task', input_digest, 3, clock_timestamp(), true) RETURNING step_key INTO step_first;
    INSERT INTO task.plan_step (plan_key, id, version, input_version_id, input_sha256, priority, ready_at, current_version)
    VALUES (plan_second, 'stp_second', 1, 'ver_task', input_digest, 3, clock_timestamp(), true) RETURNING step_key INTO step_second;
    IF task.lease_attempt(step_first, 'att_first', 'node_first', 'cap_av1', '1', '1', lease_deadline) IS DISTINCT FROM 1
        OR task.lease_attempt(step_second, 'att_second', 'node_first', 'cap_av1', '1', '1', lease_deadline) IS DISTINCT FROM 1
    THEN
        RAISE EXCEPTION 'Both fixture attempts must have a live lease';
    END IF;
END;
$$;

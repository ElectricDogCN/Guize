BEGIN;

\ir task_resource_fixture.sql

CREATE ROLE guize_fixture_control NOLOGIN;
GRANT USAGE ON SCHEMA task, outbox TO guize_fixture_control;
GRANT SELECT ON task.attempt, task.task, task.plan, task.plan_step, task.lease, task.accepted_result,
    task.accepted_attempt_event_data TO guize_fixture_control;
GRANT UPDATE (active_plan_key) ON task.task TO guize_fixture_control;
GRANT UPDATE (current_fencing) ON task.plan_step TO guize_fixture_control;
GRANT UPDATE (ended_at) ON task.lease TO guize_fixture_control;
GRANT INSERT ON task.accepted_result, outbox.event TO guize_fixture_control;
GRANT EXECUTE ON FUNCTION task.accept_attempt_result(text, text, bigint, text, text, text, text, text, text, text)
    TO guize_fixture_control;

SET LOCAL ROLE guize_fixture_control;
DO $$
BEGIN
    IF task.accept_attempt_result('att_first', 'node_first', 1, 'ver_task', repeat('a', 64),
        'cap_av1', '1', '1', 'manifest_role', repeat('b', 64)) <> 'ACCEPTED' THEN
        RAISE EXCEPTION 'The control role could not accept an authorized fixture result';
    END IF;
END;
$$;
RESET ROLE;

SELECT envelope::text FROM outbox.event_envelope WHERE envelope->>'aggregateId' = 'att_first';

ROLLBACK;

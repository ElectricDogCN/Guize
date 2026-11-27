BEGIN;

CREATE ROLE gz_fixture_source_control NOLOGIN;
GRANT USAGE ON SCHEMA source, task TO gz_fixture_source_control;

SET LOCAL ROLE gz_fixture_source_control;
DO $$
BEGIN
    IF has_function_privilege('task.lock_running_source_sync(task.identifier)', 'EXECUTE')
        OR has_function_privilege('source.record_sync_checkpoint(task.identifier,bigint,text)', 'EXECUTE')
    THEN RAISE EXCEPTION 'checkpoint functions allow public execution'; END IF;
END;
$$;
RESET ROLE;

GRANT EXECUTE ON FUNCTION task.lock_running_source_sync(task.identifier) TO gz_fixture_source_control;
GRANT EXECUTE ON FUNCTION source.record_sync_checkpoint(task.identifier, bigint, text) TO gz_fixture_source_control;
GRANT SELECT ON source.data_source, source.sync_job, source.sync_checkpoint TO gz_fixture_source_control;
GRANT UPDATE ON source.data_source, source.sync_job TO gz_fixture_source_control;
GRANT INSERT, UPDATE ON source.sync_checkpoint TO gz_fixture_source_control;

SET LOCAL ROLE gz_fixture_source_control;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper)
       OR has_any_column_privilege('task.task', 'SELECT,UPDATE')
       OR has_table_privilege('task.task', 'INSERT,DELETE')
    THEN RAISE EXCEPTION 'control role has task table authority'; END IF;
    IF source.record_sync_checkpoint('job_nextpolicy', 1, 'fixture-source-control-role') <> 2 THEN
        RAISE EXCEPTION 'limited control role could not checkpoint';
    END IF;
END;
$$;

RESET ROLE;
ROLLBACK;

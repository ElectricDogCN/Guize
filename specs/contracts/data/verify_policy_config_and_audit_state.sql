BEGIN;

INSERT INTO iam.user_account (id, username, status)
VALUES ('usr_release_fixture', 'Synthetic release requester', 'ACTIVE'),
       ('usr_review_fixture', 'Synthetic independent approver', 'ACTIVE');

INSERT INTO policy.definition (id, name) VALUES ('pol_release_fixture', 'Synthetic decision');
INSERT INTO config.definition (id, name, kind) VALUES ('cfg_release_fixture', 'Synthetic settings', 'SEARCH_PROFILE');

INSERT INTO policy.version (id, definition_id, version_number, schema_version, format, definition_text, definition_sha256, created_by)
SELECT id, 'pol_release_fixture', version, 1, 'JSON_DSL', definition, encode(sha256(convert_to(definition,'UTF8')),'hex'), 'usr_release_fixture'
FROM (VALUES ('polver_fixture_one', 1, '{"fixture":1}'), ('polver_fixture_two', 2, '{"fixture":2}'),
             ('polver_fixture_unused', 3, '{"fixture":3}')) AS seed(id, version, definition);

INSERT INTO config.version (id, definition_id, version_number, base_revision, schema_id, schema_version, schema_sha256,
                            redacted_document, document_sha256, created_by)
SELECT id, 'cfg_release_fixture', version, 1, 'schema_fixture', 1, repeat('c',64), definition,
       encode(sha256(convert_to(definition,'UTF8')),'hex'), 'usr_release_fixture'
FROM (VALUES ('cfgver_fixture_one', 1, '{"profile":1}'), ('cfgver_fixture_two', 2, '{"profile":2}')) AS seed(id, version, definition);

INSERT INTO policy.test_run (id, version_id, expected_case_count)
VALUES ('run_fixture_one', 'polver_fixture_one', 1), ('run_fixture_two', 'polver_fixture_two', 1),
       ('run_fixture_unused', 'polver_fixture_unused', 1), ('run_fixture_failed', 'polver_fixture_one', 1),
       ('run_fixture_short', 'polver_fixture_one', 1);
INSERT INTO policy.test_case (id, version_id, test_run_id, case_key, input_sha256, expected_sha256, actual_sha256, executed_at)
SELECT 'case_' || id, version_id, id, 'case_fixture', repeat('a',64), repeat('b',64),
    CASE WHEN id = 'run_fixture_failed' THEN repeat('d',64) ELSE repeat('b',64) END, clock_timestamp()
FROM policy.test_run WHERE id <> 'run_fixture_short';
UPDATE policy.test_run SET sealed_at = clock_timestamp() WHERE id <> 'run_fixture_short';

CREATE FUNCTION pg_temp.prepare_release(
    p_approval task.identifier, p_version task.identifier, expected_revision bigint, next_action text, validation task.identifier
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    proposed_policy policy.version%ROWTYPE;
    proposed_config config.version%ROWTYPE;
    check_id task.identifier := 'chk_' || p_approval;
BEGIN
    SELECT * INTO proposed_policy FROM policy.version WHERE id = p_version;
    SELECT * INTO proposed_config FROM config.version WHERE id = p_version;
    INSERT INTO config.release_check (id, resource_id, policy_version_id, config_version_id, version_sha256, expected_head_revision,
        action, validation_evidence_id, simulation_evidence_id, health_evidence_id, checked_at)
    VALUES (check_id, COALESCE(proposed_policy.definition_id, proposed_config.definition_id), proposed_policy.id, proposed_config.id,
        COALESCE(proposed_policy.definition_sha256, proposed_config.document_sha256), expected_revision, next_action,
        validation, 'evid_fixture_simulation', CASE WHEN next_action <> 'CANARY' THEN 'evid_fixture_health' END, clock_timestamp());
    INSERT INTO config.approval (id, check_id, payload_sha256, requested_by, approved_by, approved_at, expires_at)
    VALUES (p_approval, check_id, encode(sha256(convert_to(p_approval, 'UTF8')),'hex'), 'usr_release_fixture', 'usr_review_fixture',
            clock_timestamp(), clock_timestamp() + interval '1 hour');
END;
$$;

CREATE FUNCTION pg_temp.apply_fixture(p_approval task.identifier) RETURNS bigint LANGUAGE sql AS $$
    SELECT config.apply_release(p_approval, 'usr_release_fixture', encode(sha256(convert_to(p_approval,'UTF8')),'hex'), 'trace-release-fixture')
$$;

SELECT pg_temp.prepare_release('apr_failed_run', 'polver_fixture_one', 1, 'CANARY', 'run_fixture_failed');
SELECT pg_temp.prepare_release('apr_unobserved', 'polver_fixture_one', 1, 'PUBLISH', 'run_fixture_one');

DO $$
DECLARE
    rejected text;
BEGIN
    BEGIN
        UPDATE policy.test_run SET sealed_at = clock_timestamp() WHERE id = 'run_fixture_short';
        RAISE EXCEPTION 'empty test run sealed';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'policy_test_run_seal' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO policy.test_case (id, version_id, test_run_id, case_key, input_sha256, expected_sha256, actual_sha256, executed_at)
        VALUES ('case_future_fixture', 'polver_fixture_one', 'run_fixture_short', 'case_future_fixture', repeat('a',64),
            repeat('b',64), repeat('b',64), clock_timestamp() + interval '1 hour');
        RAISE EXCEPTION 'future test result was registered';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'policy_test_case_time' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO policy.test_case (id, version_id, test_run_id, case_key, input_sha256, expected_sha256, actual_sha256, executed_at)
        VALUES ('case_unsealed_fixture', 'polver_fixture_one', 'run_fixture_short', 'case_unsealed_fixture', repeat('a',64),
            repeat('b',64), repeat('b',64), clock_timestamp());
        UPDATE policy.test_run SET sealed_at = created_at WHERE id = 'run_fixture_short';
        RAISE EXCEPTION 'test run sealed before its recorded result';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'policy_test_run_seal' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO policy.test_case (id, version_id, test_run_id, case_key, input_sha256, expected_sha256, actual_sha256, executed_at)
        VALUES ('case_late_fixture', 'polver_fixture_one', 'run_fixture_one', 'case_late_fixture', repeat('a',64), repeat('a',64), repeat('b',64), clock_timestamp());
        RAISE EXCEPTION 'sealed test run gained a result';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'policy_test_case_sealed' THEN RAISE; END IF;
    END;
    BEGIN
        PERFORM pg_temp.apply_fixture('apr_failed_run');
        RAISE EXCEPTION 'failed policy test allowed deployment';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'policy_release_passed_tests' THEN RAISE; END IF;
    END;
    BEGIN
        PERFORM pg_temp.apply_fixture('apr_unobserved');
        RAISE EXCEPTION 'publication did not require the observed canary';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'release_observed_canary' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO config.approval (id, check_id, payload_sha256, requested_by, approved_by, approved_at, expires_at)
        VALUES ('apr_self_fixture', 'chk_apr_unobserved', repeat('a',64), 'usr_release_fixture', 'usr_release_fixture',
            clock_timestamp(), clock_timestamp() + interval '1 hour');
        RAISE EXCEPTION 'self approval was accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'release_approval_separation' THEN RAISE; END IF;
    END;
END;
$$;

SELECT pg_temp.prepare_release('apr_pol_canary_one', 'polver_fixture_one', 1, 'CANARY', 'run_fixture_one');
SELECT pg_temp.prepare_release('apr_revoked_fixture', 'polver_fixture_one', 1, 'CANARY', 'run_fixture_one');
UPDATE config.approval SET revoked_at = clock_timestamp() WHERE id = 'apr_revoked_fixture';

DO $$
BEGIN
    BEGIN
        PERFORM config.apply_release('apr_pol_canary_one', 'usr_release_fixture', repeat('0',64), 'trace-fixture-mismatch');
        RAISE EXCEPTION 'wrong request digest used an approval';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        PERFORM pg_temp.apply_fixture('apr_revoked_fixture');
        RAISE EXCEPTION 'revoked approval was accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    IF pg_temp.apply_fixture('apr_pol_canary_one') <> 2 THEN RAISE EXCEPTION 'canary failed'; END IF;
    IF NOT EXISTS (SELECT 1 FROM policy.definition WHERE id = 'pol_release_fixture'
        AND head_revision = 2 AND active_version_id IS NULL AND canary_version_id = 'polver_fixture_one')
        OR EXISTS (SELECT 1 FROM outbox.event)
    THEN RAISE EXCEPTION 'canary prematurely became active'; END IF;
END;
$$;

SELECT pg_temp.prepare_release('apr_pol_publish_one', 'polver_fixture_one', 2, 'PUBLISH', 'run_fixture_one');
ALTER TABLE outbox.event ADD CONSTRAINT fixture_block_policy_publication CHECK (event_type <> 'policy.published');
DO $$
DECLARE
    rejected text;
BEGIN
    BEGIN
        PERFORM pg_temp.apply_fixture('apr_pol_publish_one');
        RAISE EXCEPTION 'release survived failure to write its event';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'fixture_block_policy_publication' THEN RAISE; END IF;
    END;
    IF (SELECT head_revision FROM policy.definition WHERE id = 'pol_release_fixture') <> 2
        OR EXISTS (SELECT 1 FROM config.release_operation WHERE approval_id = 'apr_pol_publish_one')
        OR EXISTS (SELECT 1 FROM audit.event WHERE approval_id = 'apr_pol_publish_one')
    THEN RAISE EXCEPTION 'policy outbox rollback lost atomicity'; END IF;
END;
$$;
ALTER TABLE outbox.event DROP CONSTRAINT fixture_block_policy_publication;

DO $$
DECLARE
    published bigint;
    replayed bigint;
BEGIN
    published := pg_temp.apply_fixture('apr_pol_publish_one');
    replayed := pg_temp.apply_fixture('apr_pol_publish_one');
    IF published IS DISTINCT FROM 3 OR replayed IS DISTINCT FROM 3 OR (SELECT count(*) FROM outbox.event) <> 1
    THEN RAISE EXCEPTION 'publish retry duplicated a release'; END IF;
END;
$$;

SELECT pg_temp.prepare_release('apr_pol_canary_two', 'polver_fixture_two', 3, 'CANARY', 'run_fixture_two');
SELECT pg_temp.apply_fixture('apr_pol_canary_two');
SELECT pg_temp.prepare_release('apr_pol_publish_two', 'polver_fixture_two', 4, 'PUBLISH', 'run_fixture_two');
SELECT pg_temp.apply_fixture('apr_pol_publish_two');
SELECT pg_temp.prepare_release('apr_pol_unused', 'polver_fixture_unused', 5, 'ROLLBACK', 'run_fixture_unused');
SELECT pg_temp.prepare_release('apr_pol_restore', 'polver_fixture_one', 5, 'ROLLBACK', 'run_fixture_one');

DO $$
DECLARE
    rejected text;
BEGIN
    BEGIN
        PERFORM pg_temp.apply_fixture('apr_pol_unused');
        RAISE EXCEPTION 'rollback targeted an unpublished version';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'release_retained_rollback' THEN RAISE; END IF;
    END;
    IF pg_temp.apply_fixture('apr_pol_restore') <> 6 THEN RAISE EXCEPTION 'policy rollback did not complete'; END IF;
END;
$$;

SELECT pg_temp.prepare_release('apr_cfg_canary_one', 'cfgver_fixture_one', 1, 'CANARY', 'evid_cfg_validation');
CREATE ROLE gz_fixture_release_control NOLOGIN;
GRANT USAGE ON SCHEMA task, config, policy, audit TO gz_fixture_release_control;
SET LOCAL ROLE gz_fixture_release_control;
DO $$
BEGIN
    IF has_function_privilege('config.apply_release(task.identifier,task.identifier,text,text)', 'EXECUTE')
    THEN RAISE EXCEPTION 'release function has public execute'; END IF;
END;
$$;
RESET ROLE;
GRANT EXECUTE ON FUNCTION config.apply_release(task.identifier,task.identifier,text,text) TO gz_fixture_release_control;
SET LOCAL ROLE gz_fixture_release_control;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper)
        OR has_any_column_privilege('config.definition', 'UPDATE') OR has_any_column_privilege('policy.definition', 'UPDATE')
        OR has_table_privilege('config.approval', 'INSERT,UPDATE') OR has_table_privilege('audit.event', 'INSERT,UPDATE')
        OR config.apply_release('apr_cfg_canary_one', 'usr_release_fixture',
            encode(sha256(convert_to('apr_cfg_canary_one','UTF8')),'hex'), 'trace-role-release') <> 2
    THEN RAISE EXCEPTION 'least-privilege release failed'; END IF;
END;
$$;
RESET ROLE;
REVOKE EXECUTE ON FUNCTION config.apply_release(task.identifier,task.identifier,text,text) FROM gz_fixture_release_control;
REVOKE USAGE ON SCHEMA task, config, policy, audit FROM gz_fixture_release_control;
DROP ROLE gz_fixture_release_control;

SELECT pg_temp.prepare_release('apr_cfg_publish_one', 'cfgver_fixture_one', 2, 'PUBLISH', 'evid_cfg_validation');
ALTER TABLE audit.event ADD CONSTRAINT fixture_block_config_audit CHECK (approval_id IS DISTINCT FROM 'apr_cfg_publish_one');
DO $$
DECLARE
    rejected text;
BEGIN
    BEGIN
        PERFORM pg_temp.apply_fixture('apr_cfg_publish_one');
        RAISE EXCEPTION 'configuration survived audit insert failure';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS rejected = CONSTRAINT_NAME;
        IF rejected <> 'fixture_block_config_audit' THEN RAISE; END IF;
    END;
    IF (SELECT head_revision FROM config.definition WHERE id = 'cfg_release_fixture') <> 2
        OR EXISTS (SELECT 1 FROM config.release_operation WHERE approval_id = 'apr_cfg_publish_one')
    THEN RAISE EXCEPTION 'configuration audit rollback lost atomicity'; END IF;
END;
$$;
ALTER TABLE audit.event DROP CONSTRAINT fixture_block_config_audit;
SELECT pg_temp.apply_fixture('apr_cfg_publish_one');
SELECT pg_temp.prepare_release('apr_cfg_canary_two', 'cfgver_fixture_two', 3, 'CANARY', 'evid_cfg_validation');
SELECT pg_temp.apply_fixture('apr_cfg_canary_two');
SELECT pg_temp.prepare_release('apr_cfg_publish_two', 'cfgver_fixture_two', 4, 'PUBLISH', 'evid_cfg_validation');
SELECT pg_temp.apply_fixture('apr_cfg_publish_two');
SELECT pg_temp.prepare_release('apr_cfg_restore', 'cfgver_fixture_one', 5, 'ROLLBACK', 'evid_cfg_validation');
SELECT pg_temp.apply_fixture('apr_cfg_restore');
SELECT pg_temp.prepare_release('apr_cfg_race_first', 'cfgver_fixture_two', 6, 'CANARY', 'evid_cfg_validation');
SELECT pg_temp.prepare_release('apr_cfg_race_second', 'cfgver_fixture_two', 6, 'CANARY', 'evid_cfg_validation');

INSERT INTO audit.event (id, actor_id, origin_reference, resource_kind, resource_id, action, reason_code, outcome, trace_id, occurred_at)
VALUES ('aud_security_fixture', 'usr_release_fixture', 'origin_fixture', 'POLICY', 'pol_release_fixture', 'RELEASE',
        'FIXTURE_DENIED', 'DENIED', 'trace-fixture-security', clock_timestamp());
INSERT INTO audit.security_event (event_id, category, severity, evidence_id)
VALUES ('aud_security_fixture', 'AUTHORIZATION', 'WARNING', 'evid_security_fixture');

DO $$
BEGIN
    IF (SELECT active_version_id FROM policy.definition WHERE id = 'pol_release_fixture') <> 'polver_fixture_one'
        OR (SELECT active_version_id FROM config.definition WHERE id = 'cfg_release_fixture') <> 'cfgver_fixture_one'
        OR (SELECT count(*) FROM policy.deployment) <> 5 OR (SELECT count(*) FROM outbox.event) <> 3
        OR (SELECT count(*) FROM audit.event) <> 11
    THEN RAISE EXCEPTION 'release history or restored pointers disagree'; END IF;
    BEGIN
        UPDATE audit.event SET reason_code = 'REWRITTEN' WHERE id = 'aud_security_fixture';
        RAISE EXCEPTION 'audit event was modified';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        DELETE FROM audit.security_event WHERE event_id = 'aud_security_fixture';
        RAISE EXCEPTION 'security history disappeared';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

BEGIN;

\ir task_fixture.sql

INSERT INTO iam.user_account (id, username, status, password_credential_ref)
VALUES ('usr_owner', 'Owner', 'ACTIVE', 'cred_owner'),
       ('usr_reader', 'Reader', 'ACTIVE', NULL);
INSERT INTO iam.role (id, name) VALUES ('role_viewer', 'Viewer');
INSERT INTO iam.role_capability (role_id, capability) VALUES ('role_viewer', 'asset.read');
INSERT INTO iam.user_role (user_id, role_id) VALUES ('usr_reader', 'role_viewer');
INSERT INTO iam."group" (id, name) VALUES ('grp_editors', 'Editors');
INSERT INTO iam.group_member (group_id, user_id) VALUES ('grp_editors', 'usr_owner');
INSERT INTO iam.asset_acl (asset_id, user_id, permission, effect)
VALUES ('ast_task', 'usr_reader', 'READ', 'ALLOW');
INSERT INTO iam.asset_acl (asset_id, group_id, permission, effect)
VALUES ('ast_task', 'grp_editors', 'EDIT', 'ALLOW');
INSERT INTO iam.asset_acl (asset_id, role_id, permission, effect)
VALUES ('ast_task', 'role_viewer', 'PROCESS', 'DENY');

DO $$
DECLARE
    violated text;
BEGIN
    BEGIN
        INSERT INTO iam.user_account (id, username, status) VALUES ('usr_conflict', 'reader', 'ACTIVE');
        RAISE EXCEPTION 'Canonical usernames must be unique';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'iam_username_normalized' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO iam.asset_acl (asset_id, user_id, group_id, permission, effect)
        VALUES ('ast_task', 'usr_reader', 'grp_editors', 'PLAY', 'ALLOW');
        RAISE EXCEPTION 'An ACL entry must have exactly one principal';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'iam_acl_principal_type' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO iam.asset_acl (asset_id, user_id, permission, effect)
        VALUES ('ast_task', 'usr_missing', 'PLAY', 'ALLOW');
        RAISE EXCEPTION 'An ACL entry cannot reference an unknown principal';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'asset_acl_user_id_fkey' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO iam.asset_acl (asset_id, user_id, permission, effect)
        VALUES ('ast_task', 'usr_reader', 'READ', 'DENY');
        RAISE EXCEPTION 'An ACL action must not contain duplicate conflicting effects';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'iam_acl_principal_action' THEN RAISE; END IF;
    END;
END;
$$;

INSERT INTO iam.passkey_credential (credential_id, user_id, public_key_cose)
VALUES (decode('02', 'hex'), 'usr_reader', decode('01', 'hex'));

INSERT INTO iam.session (session_digest, user_id, csrf_digest, expires_at)
VALUES (repeat('a', 64), 'usr_reader', repeat('b', 64), clock_timestamp() + interval '30 minutes');
INSERT INTO iam.session_method (session_digest, method) VALUES (repeat('a', 64), 'PASSKEY');

UPDATE iam.session SET revoked_at = clock_timestamp() WHERE session_digest = repeat('a', 64);
INSERT INTO iam.session (session_digest, user_id, csrf_digest, expires_at)
VALUES (repeat('c', 64), 'usr_reader', repeat('d', 64), clock_timestamp() + interval '15 minutes');
INSERT INTO iam.session_method (session_digest, method) VALUES (repeat('c', 64), 'PASSKEY');
INSERT INTO iam.login_event (user_id, method, outcome, trace_id)
VALUES ('usr_reader', 'PASSKEY', 'ACCEPTED', 'trace-login');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM asset.version v
        JOIN iam.asset_acl acl ON acl.asset_id = v.asset_id
        WHERE v.id = 'ver_task' AND acl.user_id = 'usr_reader' AND acl.permission = 'READ' AND acl.effect = 'ALLOW'
    ) OR (SELECT count(*) FROM iam.session WHERE user_id = 'usr_reader' AND revoked_at IS NULL) <> 1
       OR NOT EXISTS (
           SELECT 1 FROM iam.session s JOIN iam.session_method m ON m.session_digest = s.session_digest
           WHERE s.user_id = 'usr_reader' AND s.revoked_at IS NULL AND m.method = 'PASSKEY'
       )
    THEN
        RAISE EXCEPTION 'Asset permission binding or session rotation was not retained';
    END IF;
END;
$$;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

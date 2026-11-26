CREATE TABLE iam.user_account (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    username varchar(256) NOT NULL CHECK (length(username) > 0 AND username = btrim(username)),
    status text NOT NULL CHECK (status IN ('ACTIVE', 'LOCKED', 'DISABLED')),
    password_credential_ref varchar(80) CHECK (password_credential_ref ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (updated_at >= created_at)
);

CREATE UNIQUE INDEX iam_username_normalized ON iam.user_account (lower(username));

CREATE TABLE iam.role (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    name varchar(256) NOT NULL UNIQUE CHECK (length(name) > 0),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991)
);

CREATE TABLE iam.role_capability (
    role_id varchar(80) NOT NULL REFERENCES iam.role (id),
    capability varchar(256) NOT NULL CHECK (length(capability) > 0),
    PRIMARY KEY (role_id, capability)
);

CREATE TABLE iam.user_role (
    user_id varchar(80) NOT NULL REFERENCES iam.user_account (id),
    role_id varchar(80) NOT NULL REFERENCES iam.role (id),
    assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX iam_user_role_by_role_idx ON iam.user_role (role_id, user_id);

CREATE TABLE iam."group" (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    name varchar(256) NOT NULL UNIQUE CHECK (length(name) > 0),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991)
);

CREATE TABLE iam.group_member (
    group_id varchar(80) NOT NULL REFERENCES iam."group" (id),
    user_id varchar(80) NOT NULL REFERENCES iam.user_account (id),
    assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (group_id, user_id)
);

CREATE INDEX iam_group_member_by_user_idx ON iam.group_member (user_id, group_id);

CREATE TABLE iam.asset_acl (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id varchar(80) NOT NULL REFERENCES asset.asset (id),
    user_id varchar(80) REFERENCES iam.user_account (id),
    group_id varchar(80) REFERENCES iam."group" (id),
    role_id varchar(80) REFERENCES iam.role (id),
    permission text NOT NULL CHECK (permission IN ('READ', 'PLAY', 'EDIT', 'SHARE', 'PROCESS', 'RETAIN')),
    effect text NOT NULL CHECK (effect IN ('ALLOW', 'DENY')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT iam_acl_principal_type CHECK (num_nonnulls(user_id, group_id, role_id) = 1),
    CONSTRAINT iam_acl_principal_action UNIQUE NULLS NOT DISTINCT (asset_id, user_id, group_id, role_id, permission)
);

CREATE INDEX iam_acl_user_idx ON iam.asset_acl (user_id, asset_id) WHERE user_id IS NOT NULL;
CREATE INDEX iam_acl_group_idx ON iam.asset_acl (group_id, asset_id) WHERE group_id IS NOT NULL;
CREATE INDEX iam_acl_role_idx ON iam.asset_acl (role_id, asset_id) WHERE role_id IS NOT NULL;

CREATE TABLE iam.passkey_credential (
    credential_id bytea PRIMARY KEY CHECK (octet_length(credential_id) BETWEEN 1 AND 1536),
    user_id varchar(80) NOT NULL REFERENCES iam.user_account (id),
    public_key_cose bytea NOT NULL CHECK (octet_length(public_key_cose) BETWEEN 1 AND 16384),
    signature_counter bigint NOT NULL DEFAULT 0 CHECK (signature_counter BETWEEN 0 AND 4294967295),
    registered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_used_at timestamptz CHECK (last_used_at >= registered_at),
    revoked_at timestamptz CHECK (revoked_at >= registered_at)
);

CREATE INDEX iam_passkey_user_idx ON iam.passkey_credential (user_id);

CREATE TABLE iam.session (
    session_digest varchar(64) PRIMARY KEY CHECK (session_digest ~ '^[0-9a-f]{64}$'),
    user_id varchar(80) NOT NULL REFERENCES iam.user_account (id),
    csrf_digest varchar(64) NOT NULL CHECK (csrf_digest ~ '^[0-9a-f]{64}$'),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL CHECK (expires_at > issued_at),
    revoked_at timestamptz CHECK (revoked_at >= issued_at)
);

CREATE INDEX iam_session_active_user_idx ON iam.session (user_id, expires_at) WHERE revoked_at IS NULL;

CREATE TABLE iam.session_method (
    session_digest varchar(64) NOT NULL REFERENCES iam.session (session_digest),
    method text NOT NULL CHECK (method IN ('PASSWORD', 'PASSKEY', 'TOTP')),
    PRIMARY KEY (session_digest, method)
);

CREATE TABLE iam.login_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id varchar(80) REFERENCES iam.user_account (id),
    method text CHECK (method IN ('PASSWORD', 'PASSKEY', 'TOTP')),
    outcome text NOT NULL CHECK (outcome IN ('ACCEPTED', 'REJECTED')),
    trace_id varchar(128) NOT NULL CHECK (trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (outcome <> 'ACCEPTED' OR (user_id IS NOT NULL AND method IS NOT NULL))
);

CREATE INDEX iam_login_event_user_idx ON iam.login_event (user_id, occurred_at DESC);
CREATE INDEX iam_login_event_trace_idx ON iam.login_event (trace_id);

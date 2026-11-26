CREATE FUNCTION audit.reject_history_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE check_violation USING CONSTRAINT = 'release_history_immutable', MESSAGE = 'Append a new historical record';
END;
$$;

CREATE TABLE audit.event (
    id task.identifier PRIMARY KEY,
    actor_id task.identifier REFERENCES iam.user_account (id),
    origin_reference task.identifier,
    resource_kind varchar(64) NOT NULL CHECK (resource_kind ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    resource_id task.identifier NOT NULL,
    action varchar(64) NOT NULL CHECK (action ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    reason_code varchar(64) NOT NULL CHECK (reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    outcome text NOT NULL CHECK (outcome IN ('SUCCEEDED', 'DENIED', 'FAILED')),
    previous_hash varchar(64) CHECK (previous_hash ~ '^[0-9a-f]{64}$'),
    result_hash varchar(64) CHECK (result_hash ~ '^[0-9a-f]{64}$'),
    approval_id task.identifier,
    task_id task.identifier REFERENCES task.task (id),
    trace_id varchar(128) NOT NULL CHECK (trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    occurred_at timestamptz NOT NULL
);

CREATE INDEX audit_event_resource_idx ON audit.event (resource_kind, resource_id, occurred_at DESC);
CREATE INDEX audit_event_trace_idx ON audit.event (trace_id, occurred_at);
CREATE TRIGGER audit_event_immutable BEFORE UPDATE OR DELETE ON audit.event
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE TABLE audit.security_event (
    event_id task.identifier PRIMARY KEY REFERENCES audit.event (id),
    category varchar(64) NOT NULL CHECK (category ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    severity text NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'HIGH', 'CRITICAL')),
    evidence_id task.identifier
);

CREATE INDEX audit_security_category_idx ON audit.security_event (category, severity, event_id);
CREATE TRIGGER audit_security_event_immutable BEFORE UPDATE OR DELETE ON audit.security_event
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE TABLE policy.definition (
    id task.identifier PRIMARY KEY,
    name varchar(256) NOT NULL CHECK (length(trim(name)) > 0),
    head_revision bigint NOT NULL DEFAULT 1 CHECK (head_revision BETWEEN 1 AND 9007199254740991),
    active_version_id task.identifier,
    canary_version_id task.identifier
);

CREATE TABLE policy.version (
    id task.identifier PRIMARY KEY,
    definition_id task.identifier NOT NULL REFERENCES policy.definition (id),
    version_number bigint NOT NULL CHECK (version_number BETWEEN 1 AND 9007199254740991),
    schema_version bigint NOT NULL CHECK (schema_version BETWEEN 1 AND 9007199254740991),
    format text NOT NULL CHECK (format IN ('JSON_DSL', 'YAML_DSL', 'LITEFLOW_EL', 'DECISION_TABLE')),
    definition_text text NOT NULL CHECK (length(definition_text) BETWEEN 1 AND 65536),
    definition_sha256 varchar(64) NOT NULL CHECK (definition_sha256 = encode(sha256(convert_to(definition_text, 'UTF8')), 'hex')),
    created_by task.identifier NOT NULL REFERENCES iam.user_account (id),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (definition_id, version_number),
    UNIQUE (definition_id, id),
    UNIQUE (definition_id, id, definition_sha256)
);

ALTER TABLE policy.definition ADD CONSTRAINT policy_active_version_owner FOREIGN KEY (id, active_version_id)
    REFERENCES policy.version (definition_id, id);
ALTER TABLE policy.definition ADD CONSTRAINT policy_canary_version_owner FOREIGN KEY (id, canary_version_id)
    REFERENCES policy.version (definition_id, id);

CREATE TRIGGER policy_version_immutable BEFORE UPDATE OR DELETE ON policy.version
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE TABLE policy.test_run (
    id task.identifier PRIMARY KEY,
    version_id task.identifier NOT NULL REFERENCES policy.version (id),
    expected_case_count integer NOT NULL CHECK (expected_case_count > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sealed_at timestamptz CHECK (sealed_at >= created_at),
    UNIQUE (id, version_id)
);

CREATE TABLE policy.test_case (
    id task.identifier PRIMARY KEY,
    version_id task.identifier NOT NULL REFERENCES policy.version (id),
    test_run_id task.identifier NOT NULL,
    case_key task.identifier NOT NULL,
    input_sha256 varchar(64) NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    expected_sha256 varchar(64) NOT NULL CHECK (expected_sha256 ~ '^[0-9a-f]{64}$'),
    actual_sha256 varchar(64) NOT NULL CHECK (actual_sha256 ~ '^[0-9a-f]{64}$'),
    matched boolean GENERATED ALWAYS AS (expected_sha256 = actual_sha256) STORED,
    executed_at timestamptz NOT NULL,
    FOREIGN KEY (test_run_id, version_id) REFERENCES policy.test_run (id, version_id),
    UNIQUE (version_id, test_run_id, case_key)
);

CREATE TRIGGER policy_test_case_immutable BEFORE UPDATE OR DELETE ON policy.test_case
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE FUNCTION policy.guard_test_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'policy_test_run_history', MESSAGE = 'Retain test history';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.sealed_at IS NOT NULL OR NEW.created_at > clock_timestamp() OR NOT EXISTS (
            SELECT 1 FROM policy.version WHERE id = NEW.version_id AND created_at <= NEW.created_at
        ) THEN
            RAISE check_violation USING CONSTRAINT = 'policy_test_run_seal', MESSAGE = 'Register the test results before sealing';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.sealed_at IS NULL AND NEW IS NOT DISTINCT FROM OLD THEN RETURN NEW; END IF;
    IF OLD.sealed_at IS NOT NULL OR NEW.sealed_at IS NULL OR NEW.sealed_at > clock_timestamp()
        OR ROW(OLD.id, OLD.version_id, OLD.expected_case_count, OLD.created_at)
           IS DISTINCT FROM ROW(NEW.id, NEW.version_id, NEW.expected_case_count, NEW.created_at)
        OR NEW.expected_case_count <> (SELECT count(*) FROM policy.test_case WHERE test_run_id = OLD.id)
        OR EXISTS (SELECT 1 FROM policy.test_case WHERE test_run_id = OLD.id AND executed_at > NEW.sealed_at)
    THEN RAISE check_violation USING CONSTRAINT = 'policy_test_run_seal', MESSAGE = 'Only complete test runs can be sealed'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER policy_test_run_seal BEFORE INSERT OR UPDATE OR DELETE ON policy.test_run
FOR EACH ROW EXECUTE FUNCTION policy.guard_test_run();

CREATE FUNCTION policy.guard_test_case_creation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.executed_at > clock_timestamp() THEN
        RAISE check_violation USING CONSTRAINT = 'policy_test_case_time', MESSAGE = 'Test execution cannot be in the future';
    END IF;
    UPDATE policy.test_run SET created_at = created_at WHERE id = NEW.test_run_id AND version_id = NEW.version_id
        AND sealed_at IS NULL AND created_at <= NEW.executed_at;
    IF NOT FOUND THEN RAISE check_violation USING CONSTRAINT = 'policy_test_case_sealed', MESSAGE = 'Test run is missing or sealed'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER policy_test_case_sealed BEFORE INSERT ON policy.test_case
FOR EACH ROW EXECUTE FUNCTION policy.guard_test_case_creation();

CREATE TABLE config.definition (
    id task.identifier PRIMARY KEY,
    name varchar(256) NOT NULL CHECK (length(trim(name)) > 0),
    kind text NOT NULL CHECK (kind IN ('MEDIA_PROFILE', 'AI_PROVIDER', 'AI_PIPELINE', 'PROMPT', 'SEARCH_PROFILE',
        'WORKER', 'BUDGET', 'STORAGE_TARGET', 'DEPLOYMENT_PROFILE', 'SECURITY')),
    head_revision bigint NOT NULL DEFAULT 1 CHECK (head_revision BETWEEN 1 AND 9007199254740991),
    active_version_id task.identifier,
    canary_version_id task.identifier
);

CREATE TABLE config.version (
    id task.identifier PRIMARY KEY,
    definition_id task.identifier NOT NULL REFERENCES config.definition (id),
    version_number bigint NOT NULL CHECK (version_number BETWEEN 1 AND 9007199254740991),
    base_revision bigint NOT NULL CHECK (base_revision BETWEEN 1 AND 9007199254740991),
    schema_id task.identifier NOT NULL,
    schema_version bigint NOT NULL CHECK (schema_version BETWEEN 1 AND 9007199254740991),
    schema_sha256 varchar(64) NOT NULL CHECK (schema_sha256 ~ '^[0-9a-f]{64}$'),
    redacted_document text NOT NULL CHECK (length(redacted_document) BETWEEN 1 AND 65536),
    document_sha256 varchar(64) NOT NULL CHECK (document_sha256 = encode(sha256(convert_to(redacted_document, 'UTF8')), 'hex')),
    created_by task.identifier NOT NULL REFERENCES iam.user_account (id),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (definition_id, version_number),
    UNIQUE (definition_id, id),
    UNIQUE (definition_id, id, document_sha256)
);

ALTER TABLE config.definition ADD CONSTRAINT config_active_version_owner FOREIGN KEY (id, active_version_id)
    REFERENCES config.version (definition_id, id);
ALTER TABLE config.definition ADD CONSTRAINT config_canary_version_owner FOREIGN KEY (id, canary_version_id)
    REFERENCES config.version (definition_id, id);

CREATE TRIGGER config_version_immutable BEFORE UPDATE OR DELETE ON config.version
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE FUNCTION config.guard_draft_base() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM FROM config.definition WHERE id = NEW.definition_id AND head_revision = NEW.base_revision FOR SHARE;
    IF NOT FOUND THEN RAISE serialization_failure USING MESSAGE = 'Configuration draft base revision changed'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER config_draft_base BEFORE INSERT ON config.version
FOR EACH ROW EXECUTE FUNCTION config.guard_draft_base();

CREATE TABLE config.release_check (
    id task.identifier PRIMARY KEY,
    resource_id task.identifier NOT NULL,
    policy_version_id task.identifier,
    config_version_id task.identifier,
    version_sha256 varchar(64) NOT NULL CHECK (version_sha256 ~ '^[0-9a-f]{64}$'),
    expected_head_revision bigint NOT NULL CHECK (expected_head_revision BETWEEN 1 AND 9007199254740991),
    action text NOT NULL CHECK (action IN ('CANARY', 'PUBLISH', 'ROLLBACK')),
    validation_evidence_id task.identifier NOT NULL,
    simulation_evidence_id task.identifier NOT NULL,
    health_evidence_id task.identifier,
    checked_at timestamptz NOT NULL,
    CONSTRAINT release_check_subject CHECK (num_nonnulls(policy_version_id, config_version_id) = 1),
    CONSTRAINT release_check_health CHECK (action = 'CANARY' OR health_evidence_id IS NOT NULL),
    FOREIGN KEY (resource_id, policy_version_id, version_sha256) REFERENCES policy.version (definition_id, id, definition_sha256),
    FOREIGN KEY (resource_id, config_version_id, version_sha256) REFERENCES config.version (definition_id, id, document_sha256)
);

CREATE TRIGGER release_check_immutable BEFORE UPDATE OR DELETE ON config.release_check
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE TABLE config.approval (
    id task.identifier PRIMARY KEY,
    check_id task.identifier NOT NULL REFERENCES config.release_check (id),
    payload_sha256 varchar(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    requested_by task.identifier NOT NULL REFERENCES iam.user_account (id),
    approved_by task.identifier NOT NULL REFERENCES iam.user_account (id),
    approved_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL CHECK (expires_at > approved_at),
    revoked_at timestamptz CHECK (revoked_at >= approved_at),
    CONSTRAINT release_approval_separation CHECK (requested_by <> approved_by)
);

CREATE FUNCTION config.guard_approval_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'release_approval_history', MESSAGE = 'Retain the release approval';
    END IF;
    IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
        OR ROW(OLD.id, OLD.check_id, OLD.payload_sha256, OLD.requested_by, OLD.approved_by, OLD.approved_at, OLD.expires_at)
            IS DISTINCT FROM ROW(NEW.id, NEW.check_id, NEW.payload_sha256, NEW.requested_by, NEW.approved_by, NEW.approved_at, NEW.expires_at)
    THEN RAISE check_violation USING CONSTRAINT = 'release_approval_history', MESSAGE = 'Release approval only allows a revocation'; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER release_approval_history BEFORE UPDATE OR DELETE ON config.approval
FOR EACH ROW EXECUTE FUNCTION config.guard_approval_history();

CREATE TABLE config.release_operation (
    approval_id task.identifier PRIMARY KEY REFERENCES config.approval (id),
    resource_kind text NOT NULL CHECK (resource_kind IN ('POLICY', 'CONFIG')),
    resource_id task.identifier NOT NULL,
    version_id task.identifier NOT NULL,
    previous_active_version_id task.identifier,
    head_revision bigint NOT NULL CHECK (head_revision BETWEEN 2 AND 9007199254740991),
    action text NOT NULL CHECK (action IN ('CANARY', 'PUBLISH', 'ROLLBACK')),
    audit_event_id task.identifier NOT NULL UNIQUE REFERENCES audit.event (id),
    applied_at timestamptz NOT NULL,
    UNIQUE (resource_kind, resource_id, head_revision)
);

CREATE INDEX release_operation_version_idx ON config.release_operation (resource_kind, resource_id, version_id, action);
CREATE TRIGGER release_operation_immutable BEFORE UPDATE OR DELETE ON config.release_operation
FOR EACH ROW EXECUTE FUNCTION audit.reject_history_rewrite();

CREATE VIEW policy.deployment AS SELECT * FROM config.release_operation WHERE resource_kind = 'POLICY';

CREATE FUNCTION config.apply_release(
    p_approval_id task.identifier, p_actor_id task.identifier, p_payload_sha256 text, p_trace_id text
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    approval_row config.approval%ROWTYPE;
    check_row config.release_check%ROWTYPE;
    operation_kind text;
    previous_head bigint;
    prior_active task.identifier;
    prior_canary task.identifier;
    intended_version task.identifier;
    prior_hash varchar(64);
    target_schema_version bigint;
    target_created_at timestamptz;
    current_time_utc timestamptz;
    applied_revision bigint;
    audit_id task.identifier;
BEGIN
    SELECT * INTO approval_row FROM config.approval WHERE id = p_approval_id FOR UPDATE;
    IF NOT FOUND OR approval_row.requested_by IS DISTINCT FROM p_actor_id
        OR approval_row.payload_sha256 IS DISTINCT FROM p_payload_sha256 OR approval_row.revoked_at IS NOT NULL
    THEN RAISE insufficient_privilege USING MESSAGE = 'Release approval did not match the operation'; END IF;

    current_time_utc := clock_timestamp();
    IF approval_row.approved_at > current_time_utc OR approval_row.expires_at <= current_time_utc
    THEN RAISE insufficient_privilege USING MESSAGE = 'Release approval is outside its validity window'; END IF;
    SELECT head_revision INTO applied_revision FROM config.release_operation WHERE approval_id = p_approval_id;
    IF FOUND THEN RETURN applied_revision; END IF;

    SELECT * INTO STRICT check_row FROM config.release_check WHERE id = approval_row.check_id;
    IF check_row.policy_version_id IS NOT NULL THEN
        operation_kind := 'POLICY';
        intended_version := check_row.policy_version_id;
        SELECT d.head_revision, d.active_version_id, d.canary_version_id INTO STRICT previous_head, prior_active, prior_canary
        FROM policy.definition d WHERE d.id = check_row.resource_id FOR UPDATE;
        SELECT schema_version, created_at INTO STRICT target_schema_version, target_created_at FROM policy.version WHERE id = intended_version;
        SELECT definition_sha256 INTO prior_hash FROM policy.version WHERE id = prior_active;
        IF NOT EXISTS (SELECT 1 FROM policy.test_run WHERE id = check_row.validation_evidence_id AND version_id = intended_version
            AND sealed_at IS NOT NULL AND sealed_at <= check_row.checked_at)
            OR EXISTS (SELECT 1 FROM policy.test_case WHERE test_run_id = check_row.validation_evidence_id AND NOT matched)
        THEN RAISE check_violation USING CONSTRAINT = 'policy_release_passed_tests', MESSAGE = 'Release requires a passing sealed test run'; END IF;
    ELSE
        operation_kind := 'CONFIG';
        intended_version := check_row.config_version_id;
        SELECT d.head_revision, d.active_version_id, d.canary_version_id INTO STRICT previous_head, prior_active, prior_canary
        FROM config.definition d WHERE d.id = check_row.resource_id FOR UPDATE;
        SELECT schema_version, created_at INTO STRICT target_schema_version, target_created_at FROM config.version WHERE id = intended_version;
        SELECT document_sha256 INTO prior_hash FROM config.version WHERE id = prior_active;
    END IF;

    current_time_utc := clock_timestamp();
    IF approval_row.expires_at <= current_time_utc THEN
        RAISE insufficient_privilege USING MESSAGE = 'Release approval expired while waiting';
    END IF;
    IF previous_head <> check_row.expected_head_revision
    THEN RAISE serialization_failure USING MESSAGE = 'Release head revision changed'; END IF;
    IF check_row.checked_at < target_created_at OR check_row.checked_at > approval_row.approved_at
    THEN RAISE check_violation USING CONSTRAINT = 'release_check_time', MESSAGE = 'Approval must bind completed validation'; END IF;
    IF check_row.action = 'PUBLISH' AND (prior_canary IS DISTINCT FROM intended_version OR NOT EXISTS (
        SELECT 1 FROM config.release_operation r WHERE r.resource_kind = operation_kind AND r.resource_id = check_row.resource_id
          AND r.head_revision = previous_head AND r.action = 'CANARY' AND r.version_id = intended_version
          AND r.applied_at <= check_row.checked_at
    )) THEN RAISE check_violation USING CONSTRAINT = 'release_observed_canary', MESSAGE = 'Publication requires current canary observation'; END IF;
    IF check_row.action = 'ROLLBACK' AND (prior_active IS NULL OR prior_active = intended_version OR NOT EXISTS (
        SELECT 1 FROM config.release_operation r WHERE r.resource_kind = operation_kind AND r.resource_id = check_row.resource_id
          AND r.version_id = intended_version AND r.action IN ('PUBLISH', 'ROLLBACK')
    ) OR NOT EXISTS (
        SELECT 1 FROM config.release_operation r WHERE r.resource_kind = operation_kind AND r.resource_id = check_row.resource_id
          AND r.head_revision = previous_head AND r.applied_at <= check_row.checked_at
    )) THEN RAISE check_violation USING CONSTRAINT = 'release_retained_rollback', MESSAGE = 'Rollback requires freshly checked retained release'; END IF;

    applied_revision := previous_head + 1;
    IF operation_kind = 'POLICY' THEN
        UPDATE policy.definition SET head_revision = applied_revision,
            active_version_id = CASE WHEN check_row.action = 'CANARY' THEN prior_active ELSE intended_version END,
            canary_version_id = CASE WHEN check_row.action = 'CANARY' THEN intended_version END
        WHERE id = check_row.resource_id;
    ELSE
        UPDATE config.definition SET head_revision = applied_revision,
            active_version_id = CASE WHEN check_row.action = 'CANARY' THEN prior_active ELSE intended_version END,
            canary_version_id = CASE WHEN check_row.action = 'CANARY' THEN intended_version END
        WHERE id = check_row.resource_id;
    END IF;

    audit_id := 'aud_' || gen_random_uuid();
    INSERT INTO audit.event (id, actor_id, resource_kind, resource_id, action, reason_code, outcome, previous_hash, result_hash,
                             approval_id, trace_id, occurred_at)
    VALUES (audit_id, p_actor_id, operation_kind, check_row.resource_id, check_row.action, 'APPROVED_RELEASE', 'SUCCEEDED',
            prior_hash, check_row.version_sha256, p_approval_id, p_trace_id, current_time_utc);
    INSERT INTO config.release_operation (approval_id, resource_kind, resource_id, version_id, previous_active_version_id,
                                          head_revision, action, audit_event_id, applied_at)
    VALUES (p_approval_id, operation_kind, check_row.resource_id, intended_version, prior_active, applied_revision,
            check_row.action, audit_id, current_time_utc);

    IF operation_kind = 'POLICY' AND check_row.action <> 'CANARY' THEN
        INSERT INTO outbox.event (event_id, event_type, event_version, aggregate_type, aggregate_id, aggregate_revision,
                                 occurred_at, producer, trace_id, payload)
        VALUES ('evt_' || gen_random_uuid(), 'policy.published', 1, 'PolicyDefinition', check_row.resource_id, applied_revision,
                current_time_utc, 'guize-control', p_trace_id, jsonb_build_object(
                    'policyId', check_row.resource_id, 'policyVersionId', intended_version, 'revision', applied_revision,
                    'schemaVersion', target_schema_version, 'state', 'PUBLISHED', 'definitionHash', check_row.version_sha256,
                    'publishedAt', outbox.utc_timestamp(current_time_utc)));
    END IF;
    RETURN applied_revision;
END;
$$;

REVOKE EXECUTE ON FUNCTION config.apply_release(task.identifier, task.identifier, text, text) FROM PUBLIC;

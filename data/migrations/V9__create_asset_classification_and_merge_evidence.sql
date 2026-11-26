CREATE INDEX source_history_alias_path_idx ON source.object_history USING hash (old_path)
WHERE operation IN ('RENAME', 'MOVE') AND old_path IS NOT NULL AND old_path IS DISTINCT FROM new_path;

CREATE FUNCTION source.reject_object_history_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE check_violation USING CONSTRAINT = 'source_history_append_only', MESSAGE = 'Append a source history revision';
END;
$$;

CREATE TRIGGER source_history_append_only BEFORE UPDATE OR DELETE ON source.object_history
FOR EACH ROW EXECUTE FUNCTION source.reject_object_history_rewrite();

CREATE VIEW asset.alias AS
SELECT h.id AS history_id, o.id AS source_object_id, o.data_source_id, o.asset_id, h.source_revision,
       h.old_path AS alias_path, substring(h.old_path FROM '[^/]+$') AS alias_name, h.observed_at
FROM source.object_history h JOIN source.object o ON o.id = h.source_object_id
WHERE h.operation IN ('RENAME', 'MOVE') AND h.old_path IS NOT NULL AND h.old_path IS DISTINCT FROM h.new_path;

CREATE FUNCTION asset.guard_version_provenance() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(OLD.id, OLD.asset_id, OLD.version_number, OLD.origin_source_object_id,
           OLD.content_length, OLD.created_reason, OLD.supersedes_version_id, OLD.created_at)
        IS DISTINCT FROM ROW(NEW.id, NEW.asset_id, NEW.version_number, NEW.origin_source_object_id,
                             NEW.content_length, NEW.created_reason, NEW.supersedes_version_id, NEW.created_at)
    THEN RAISE check_violation USING CONSTRAINT = 'asset_version_provenance', MESSAGE = 'Create a new content version';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER asset_version_provenance BEFORE UPDATE ON asset.version
FOR EACH ROW EXECUTE FUNCTION asset.guard_version_provenance();

CREATE INDEX asset_verified_full_hash_idx ON asset.content_hash (asset_version_id, algorithm)
WHERE scope = 'FULL' AND verified_at IS NOT NULL;

CREATE VIEW asset.authoritative_content_hash AS
SELECT h.asset_version_id, h.algorithm, h.hash_value, h.verified_at
FROM asset.content_hash h
WHERE h.scope = 'FULL' AND h.verified_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM asset.content_hash conflicting
      WHERE conflicting.asset_version_id = h.asset_version_id AND conflicting.algorithm = h.algorithm
        AND conflicting.scope = 'FULL' AND conflicting.verified_at IS NOT NULL AND conflicting.hash_value <> h.hash_value
  );

CREATE FUNCTION asset.guard_verified_content_hash() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.scope = 'FULL' AND OLD.verified_at IS NOT NULL THEN
        IF TG_OP = 'DELETE' THEN
            RAISE check_violation USING CONSTRAINT = 'asset_verified_hash_history', MESSAGE = 'Retain verified content proof';
        END IF;
        IF ROW(OLD.id, OLD.asset_version_id, OLD.algorithm, OLD.hash_value, OLD.scope, OLD.verified_at, OLD.verified_by)
            IS DISTINCT FROM ROW(NEW.id, NEW.asset_version_id, NEW.algorithm, NEW.hash_value, NEW.scope,
                                 NEW.verified_at, NEW.verified_by)
        THEN RAISE check_violation USING CONSTRAINT = 'asset_verified_hash_history', MESSAGE = 'Retain verified content proof';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER asset_verified_hash_history BEFORE UPDATE OR DELETE ON asset.content_hash
FOR EACH ROW EXECUTE FUNCTION asset.guard_verified_content_hash();

CREATE TABLE asset.tag (
    id task.identifier PRIMARY KEY,
    namespace varchar(64) NOT NULL CHECK (namespace ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    name varchar(128) NOT NULL CHECK (length(name) > 0 AND name = btrim(name)),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX asset_tag_namespace_name_idx ON asset.tag (namespace, lower(name));

CREATE TABLE asset.tag_assignment (
    id task.identifier PRIMARY KEY,
    tag_id task.identifier NOT NULL REFERENCES asset.tag (id),
    asset_id task.identifier REFERENCES asset.asset (id),
    source_object_id task.identifier REFERENCES source.object (id),
    assigned_by task.identifier NOT NULL REFERENCES iam.user_account (id),
    assigned_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT tag_assignment_subject CHECK (num_nonnulls(asset_id, source_object_id) = 1),
    CONSTRAINT tag_assignment_unique UNIQUE NULLS NOT DISTINCT (tag_id, asset_id, source_object_id)
);

CREATE INDEX asset_tag_assignment_lookup_idx ON asset.tag_assignment (asset_id, tag_id) WHERE asset_id IS NOT NULL;
CREATE INDEX source_tag_assignment_lookup_idx ON asset.tag_assignment (source_object_id, tag_id) WHERE source_object_id IS NOT NULL;

CREATE TABLE asset.version_source (
    asset_id task.identifier NOT NULL,
    asset_version_id task.identifier NOT NULL,
    source_object_id task.identifier NOT NULL REFERENCES source.object (id),
    source_revision bigint NOT NULL CHECK (source_revision BETWEEN 1 AND 9007199254740991),
    algorithm text NOT NULL,
    accepted_hash varchar(64) NOT NULL,
    hash_scope text GENERATED ALWAYS AS ('FULL') STORED,
    evidence_id task.identifier NOT NULL,
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (asset_version_id, source_object_id, source_revision),
    FOREIGN KEY (asset_id, asset_version_id) REFERENCES asset.version (asset_id, id),
    FOREIGN KEY (asset_version_id, algorithm, accepted_hash, hash_scope)
        REFERENCES asset.content_hash (asset_version_id, algorithm, hash_value, scope)
);

CREATE INDEX asset_version_source_object_idx ON asset.version_source (source_object_id, source_revision);

CREATE FUNCTION source.lock_asset_observation(p_source_object_id task.identifier, p_asset_id task.identifier, p_revision bigint)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    PERFORM FROM source.object WHERE id = p_source_object_id AND asset_id = p_asset_id
        AND revision = p_revision FOR SHARE;
    RETURN FOUND;
END;
$$;

REVOKE EXECUTE ON FUNCTION source.lock_asset_observation(task.identifier, task.identifier, bigint) FROM PUBLIC;

CREATE FUNCTION asset.guard_version_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE check_violation USING CONSTRAINT = 'asset_version_source_history', MESSAGE = 'Retain the source observation';
    END IF;
    PERFORM FROM asset.asset WHERE id = NEW.asset_id AND current_version_id = NEW.asset_version_id FOR SHARE;
    IF NOT FOUND THEN RAISE serialization_failure USING MESSAGE = 'The asset version is no longer current'; END IF;

    IF NOT source.lock_asset_observation(NEW.source_object_id, NEW.asset_id, NEW.source_revision)
    THEN RAISE serialization_failure USING MESSAGE = 'The source is no longer in the observed revision or asset'; END IF;

    PERFORM v.id FROM asset.version v JOIN asset.authoritative_content_hash h ON h.asset_version_id = v.id
    WHERE v.id = NEW.asset_version_id AND v.hash_status = 'FULL_VERIFIED'
      AND h.algorithm = NEW.algorithm AND h.hash_value = NEW.accepted_hash FOR SHARE OF v;
    IF NOT FOUND
    THEN RAISE check_violation USING CONSTRAINT = 'asset_version_source_verified', MESSAGE = 'Source evidence needs a verified version digest';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER asset_version_source_history BEFORE INSERT OR UPDATE OR DELETE ON asset.version_source
FOR EACH ROW EXECUTE FUNCTION asset.guard_version_source();

CREATE VIEW asset.current_version_source AS
SELECT v.asset_id, v.asset_version_id, v.source_object_id, v.source_revision, v.evidence_id
FROM asset.version_source v
JOIN asset.asset a ON (a.id, a.current_version_id) = (v.asset_id, v.asset_version_id)
JOIN source.object o ON (o.id, o.asset_id, o.revision) = (v.source_object_id, v.asset_id, v.source_revision)
JOIN asset.version av ON av.id = v.asset_version_id AND av.hash_status = 'FULL_VERIFIED'
JOIN asset.authoritative_content_hash h ON (h.asset_version_id, h.algorithm, h.hash_value)
    = (v.asset_version_id, v.algorithm, v.accepted_hash);

CREATE TABLE asset.merge_decision (
    id task.identifier PRIMARY KEY,
    source_asset_id task.identifier NOT NULL,
    source_version_id task.identifier NOT NULL,
    source_expected_revision bigint NOT NULL CHECK (source_expected_revision BETWEEN 1 AND 9007199254740991),
    target_asset_id task.identifier NOT NULL,
    target_version_id task.identifier NOT NULL,
    target_expected_revision bigint NOT NULL CHECK (target_expected_revision BETWEEN 1 AND 9007199254740991),
    outcome text NOT NULL CHECK (outcome IN ('APPROVED', 'DECLINED')),
    reason varchar(256) NOT NULL CHECK (length(btrim(reason)) > 0),
    decided_by task.identifier NOT NULL REFERENCES iam.user_account (id),
    decided_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hash_scope text GENERATED ALWAYS AS ('FULL') STORED,
    algorithm text,
    verified_hash varchar(64),
    FOREIGN KEY (source_asset_id, source_version_id) REFERENCES asset.version (asset_id, id),
    FOREIGN KEY (target_asset_id, target_version_id) REFERENCES asset.version (asset_id, id),
    FOREIGN KEY (source_version_id, algorithm, verified_hash, hash_scope)
        REFERENCES asset.content_hash (asset_version_id, algorithm, hash_value, scope),
    FOREIGN KEY (target_version_id, algorithm, verified_hash, hash_scope)
        REFERENCES asset.content_hash (asset_version_id, algorithm, hash_value, scope),
    CHECK (source_asset_id <> target_asset_id),
    CHECK (num_nonnulls(algorithm, verified_hash) IN (0, 2)),
    CHECK (outcome <> 'APPROVED' OR verified_hash IS NOT NULL)
);

CREATE INDEX merge_decision_source_idx ON asset.merge_decision (source_asset_id, decided_at DESC);
CREATE INDEX merge_decision_target_idx ON asset.merge_decision (target_asset_id, decided_at DESC);

CREATE FUNCTION asset.guard_merge_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    matched_versions integer;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE check_violation USING CONSTRAINT = 'asset_merge_decision_history', MESSAGE = 'Retain the merge decision';
    END IF;
    PERFORM id FROM asset.asset WHERE id IN (NEW.source_asset_id, NEW.target_asset_id) ORDER BY id FOR UPDATE;
    IF NOT EXISTS (SELECT 1 FROM asset.asset WHERE id = NEW.source_asset_id
        AND current_version_id = NEW.source_version_id AND revision = NEW.source_expected_revision)
        OR NOT EXISTS (SELECT 1 FROM asset.asset WHERE id = NEW.target_asset_id
        AND current_version_id = NEW.target_version_id AND revision = NEW.target_expected_revision)
    THEN RAISE serialization_failure USING MESSAGE = 'Merge version or asset revision changed';
    END IF;

    IF NEW.verified_hash IS NOT NULL THEN
        PERFORM v.id FROM asset.version v JOIN asset.authoritative_content_hash h ON h.asset_version_id = v.id
        WHERE v.id IN (NEW.source_version_id, NEW.target_version_id) AND v.hash_status = 'FULL_VERIFIED'
          AND h.algorithm = NEW.algorithm AND h.hash_value = NEW.verified_hash
        ORDER BY v.id FOR SHARE OF v;
        GET DIAGNOSTICS matched_versions = ROW_COUNT;
        IF matched_versions <> 2 OR (SELECT content_length FROM asset.version WHERE id = NEW.source_version_id)
            <> (SELECT content_length FROM asset.version WHERE id = NEW.target_version_id)
        THEN RAISE check_violation USING CONSTRAINT = 'asset_merge_full_hash', MESSAGE = 'Both current versions need the same verified content';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER asset_merge_decision_history BEFORE INSERT OR UPDATE OR DELETE ON asset.merge_decision
FOR EACH ROW EXECUTE FUNCTION asset.guard_merge_decision();

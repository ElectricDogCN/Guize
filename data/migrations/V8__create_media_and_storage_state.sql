CREATE TABLE media.profile (
    id task.identifier PRIMARY KEY,
    profile_key task.identifier NOT NULL,
    version bigint NOT NULL CHECK (version BETWEEN 1 AND 9007199254740991),
    parameters jsonb NOT NULL CHECK (jsonb_typeof(parameters) = 'object'),
    parameters_sha256 varchar(64) NOT NULL CHECK (parameters_sha256 ~ '^[0-9a-f]{64}$'),
    approved_at timestamptz NOT NULL,
    UNIQUE (profile_key, version)
);

CREATE FUNCTION media.reject_profile_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE check_violation USING CONSTRAINT = 'media_profile_immutable', MESSAGE = 'Use a new approved profile version';
END;
$$;

CREATE TRIGGER media_profile_immutable BEFORE UPDATE OR DELETE ON media.profile
FOR EACH ROW EXECUTE FUNCTION media.reject_profile_rewrite();

CREATE TABLE media.rendition (
    id task.identifier PRIMARY KEY,
    asset_version_id task.identifier NOT NULL REFERENCES asset.version (id),
    kind text NOT NULL CHECK (kind IN ('ORIGINAL', 'AV1_MASTER', 'ABR_HLS', 'ABR_DASH', 'H264_COMPAT', 'PREVIEW')),
    codec varchar(256) NOT NULL CHECK (length(codec) > 0),
    container varchar(64) NOT NULL CHECK (length(container) > 0),
    tool_version varchar(256) NOT NULL CHECK (length(tool_version) > 0),
    profile_version_id task.identifier NOT NULL REFERENCES media.profile (id),
    input_sha256 varchar(64) NOT NULL CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
    input_hash_algorithm text GENERATED ALWAYS AS ('SHA256') STORED,
    input_hash_scope text GENERATED ALWAYS AS ('FULL') STORED,
    output_sha256 varchar(64) NOT NULL CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    quality_status text NOT NULL CHECK (quality_status IN ('PENDING', 'PASS', 'FAIL')),
    quality_revision bigint,
    publication_status text NOT NULL CHECK (publication_status IN ('DRAFT', 'PUBLISHED', 'REVOKED')),
    CHECK ((quality_status = 'PENDING') = (quality_revision IS NULL)),
    CHECK (publication_status <> 'PUBLISHED' OR quality_status = 'PASS'),
    CONSTRAINT rendition_input_hash FOREIGN KEY (asset_version_id, input_hash_algorithm, input_sha256, input_hash_scope)
        REFERENCES asset.content_hash (asset_version_id, algorithm, hash_value, scope),
    UNIQUE (id, size_bytes, output_sha256)
);

CREATE INDEX media_rendition_version_idx ON media.rendition (asset_version_id, kind, publication_status);

CREATE FUNCTION media.guard_rendition_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NOT EXISTS (
            SELECT 1 FROM asset.content_hash h WHERE h.asset_version_id = NEW.asset_version_id
              AND h.algorithm = 'SHA256' AND h.scope = 'FULL' AND h.hash_value = NEW.input_sha256 AND h.verified_at IS NOT NULL
        ) THEN RAISE check_violation USING CONSTRAINT = 'media_rendition_verified_input', MESSAGE = 'Rendition must bind a verified input';
        END IF;
        RETURN NEW;
    END IF;
    IF ROW(OLD.id, OLD.asset_version_id, OLD.kind, OLD.codec, OLD.container, OLD.tool_version,
           OLD.profile_version_id, OLD.input_sha256, OLD.output_sha256, OLD.size_bytes)
        IS DISTINCT FROM ROW(NEW.id, NEW.asset_version_id, NEW.kind, NEW.codec, NEW.container, NEW.tool_version,
                             NEW.profile_version_id, NEW.input_sha256, NEW.output_sha256, NEW.size_bytes)
    THEN RAISE check_violation USING CONSTRAINT = 'media_rendition_identity', MESSAGE = 'Use a new rendition identity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER media_rendition_identity BEFORE INSERT OR UPDATE ON media.rendition
FOR EACH ROW EXECUTE FUNCTION media.guard_rendition_identity();

CREATE TABLE media.track (
    rendition_id task.identifier NOT NULL REFERENCES media.rendition (id),
    track_number integer NOT NULL CHECK (track_number >= 0),
    kind text NOT NULL CHECK (kind IN ('VIDEO', 'AUDIO', 'SUBTITLE', 'DATA')),
    codec varchar(256) NOT NULL CHECK (length(codec) > 0),
    language varchar(64),
    duration_ms bigint CHECK (duration_ms >= 0),
    PRIMARY KEY (rendition_id, track_number)
);

CREATE TABLE media.quality_result (
    rendition_id task.identifier NOT NULL REFERENCES media.rendition (id),
    evaluation_revision bigint NOT NULL CHECK (evaluation_revision BETWEEN 1 AND 9007199254740991),
    status text NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    evidence_id task.identifier NOT NULL,
    evaluated_at timestamptz NOT NULL,
    PRIMARY KEY (rendition_id, evaluation_revision),
    UNIQUE (rendition_id, evaluation_revision, status)
);

ALTER TABLE media.rendition ADD CONSTRAINT rendition_published_quality FOREIGN KEY (id, quality_revision, quality_status)
    REFERENCES media.quality_result (rendition_id, evaluation_revision, status);

CREATE TABLE storage.backend (
    id task.identifier PRIMARY KEY,
    purpose text NOT NULL CHECK (purpose IN ('CACHE', 'FORMAL')),
    failure_domain_id task.identifier NOT NULL,
    target_ref task.identifier NOT NULL UNIQUE,
    connector_kind varchar(64) NOT NULL CHECK (length(connector_kind) > 0),
    storage_class text NOT NULL CHECK (storage_class IN ('HOT', 'WARM', 'COLD', 'ARCHIVE', 'OFFLINE')),
    UNIQUE (id, purpose),
    UNIQUE (id, purpose, failure_domain_id)
);

CREATE FUNCTION storage.reject_backend_rebind() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(OLD.id, OLD.purpose, OLD.failure_domain_id, OLD.target_ref, OLD.connector_kind)
        IS DISTINCT FROM ROW(NEW.id, NEW.purpose, NEW.failure_domain_id, NEW.target_ref, NEW.connector_kind)
    THEN RAISE check_violation USING CONSTRAINT = 'storage_backend_identity', MESSAGE = 'Use a new storage target identity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER storage_backend_identity BEFORE UPDATE ON storage.backend
FOR EACH ROW EXECUTE FUNCTION storage.reject_backend_rebind();

CREATE TABLE storage.retention_policy (
    id task.identifier PRIMARY KEY,
    policy_key task.identifier NOT NULL,
    version bigint NOT NULL CHECK (version BETWEEN 1 AND 9007199254740991),
    minimum_retention_seconds bigint NOT NULL CHECK (minimum_retention_seconds >= 0),
    created_at timestamptz NOT NULL,
    UNIQUE (policy_key, version)
);

CREATE FUNCTION storage.reject_retention_policy_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE check_violation USING CONSTRAINT = 'retention_policy_history', MESSAGE = 'Use a new retention policy version';
END;
$$;

CREATE TRIGGER retention_policy_history BEFORE UPDATE OR DELETE ON storage.retention_policy
FOR EACH ROW EXECUTE FUNCTION storage.reject_retention_policy_rewrite();

CREATE TABLE storage.retention_hold (
    id task.identifier PRIMARY KEY,
    asset_id task.identifier NOT NULL REFERENCES asset.asset (id),
    policy_version_id task.identifier NOT NULL REFERENCES storage.retention_policy (id),
    reason varchar(256) NOT NULL CHECK (length(reason) > 0),
    created_at timestamptz NOT NULL,
    released_at timestamptz CHECK (released_at >= created_at),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991)
);

CREATE INDEX retention_hold_active_idx ON storage.retention_hold (asset_id) WHERE released_at IS NULL;

CREATE TABLE storage.asset_lifecycle_lock (
    asset_id task.identifier PRIMARY KEY REFERENCES asset.asset (id)
);

CREATE FUNCTION storage.lock_asset_lifecycle(p_asset_id task.identifier) RETURNS void LANGUAGE sql AS $$
    INSERT INTO storage.asset_lifecycle_lock (asset_id) VALUES (p_asset_id)
    ON CONFLICT (asset_id) DO UPDATE SET asset_id = EXCLUDED.asset_id
$$;

CREATE FUNCTION storage.guard_retention_hold() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'retention_hold_history', MESSAGE = 'Retain hold history';
    END IF;
    PERFORM storage.lock_asset_lifecycle(NEW.asset_id);
    IF TG_OP = 'UPDATE' AND (OLD.released_at IS NOT NULL OR NEW.released_at IS NULL
        OR NEW.revision <> OLD.revision + 1
        OR ROW(OLD.id, OLD.asset_id, OLD.policy_version_id, OLD.reason, OLD.created_at)
           IS DISTINCT FROM ROW(NEW.id, NEW.asset_id, NEW.policy_version_id, NEW.reason, NEW.created_at))
    THEN RAISE check_violation USING CONSTRAINT = 'retention_hold_history', MESSAGE = 'Invalid hold release';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER retention_hold_history BEFORE INSERT OR UPDATE OR DELETE ON storage.retention_hold
FOR EACH ROW EXECUTE FUNCTION storage.guard_retention_hold();

ALTER TABLE asset.version ADD CONSTRAINT asset_version_length_identity UNIQUE (id, content_length);

CREATE TABLE storage.cache_entry (
    id task.identifier PRIMARY KEY,
    asset_version_id task.identifier NOT NULL REFERENCES asset.version (id),
    backend_id task.identifier NOT NULL,
    backend_purpose text GENERATED ALWAYS AS ('CACHE') STORED,
    object_key text NOT NULL CHECK (octet_length(object_key) BETWEEN 1 AND 1024),
    cache_class text NOT NULL CHECK (cache_class IN ('FULL_FILE', 'PINNED_FILE')),
    state text NOT NULL CHECK (state IN ('REMOTE_ONLY', 'DOWNLOAD_QUEUED', 'DOWNLOADING', 'COMPLETE_CACHE',
        'PINNED_CACHE', 'VALIDATING', 'PROMOTING', 'EVICTING', 'EVICTED', 'FAILED')),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    expires_at timestamptz NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991),
    verified_size_bytes bigint CHECK (verified_size_bytes = size_bytes),
    verification_scope text GENERATED ALWAYS AS ('FULL') STORED,
    verification_algorithm text,
    verification_sha256_or_blake3 varchar(64),
    verification_evidence_id task.identifier,
    verified_at timestamptz,
    verification_trace_id varchar(128) CHECK (verification_trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    UNIQUE (backend_id, object_key),
    CONSTRAINT cache_entry_backend FOREIGN KEY (backend_id, backend_purpose) REFERENCES storage.backend (id, purpose),
    CONSTRAINT cache_entry_verified_size FOREIGN KEY (asset_version_id, verified_size_bytes)
        REFERENCES asset.version (id, content_length),
    CONSTRAINT cache_entry_verified_hash FOREIGN KEY (asset_version_id, verification_algorithm,
                                                     verification_sha256_or_blake3, verification_scope)
        REFERENCES asset.content_hash (asset_version_id, algorithm, hash_value, scope),
    CHECK (num_nonnulls(verified_size_bytes, verification_algorithm, verification_sha256_or_blake3,
                       verification_evidence_id, verified_at, verification_trace_id) IN (0, 6)),
    CHECK (state NOT IN ('COMPLETE_CACHE', 'PINNED_CACHE', 'PROMOTING', 'EVICTING', 'EVICTED') OR verified_at IS NOT NULL),
    CHECK (state <> 'COMPLETE_CACHE' OR cache_class = 'FULL_FILE'),
    CHECK (state <> 'PINNED_CACHE' OR cache_class = 'PINNED_FILE'),
    CHECK (state NOT IN ('EVICTING', 'EVICTED') OR cache_class = 'FULL_FILE')
);

CREATE INDEX cache_entry_version_idx ON storage.cache_entry (asset_version_id, state);
CREATE INDEX cache_entry_expiry_idx ON storage.cache_entry (expires_at, id)
    WHERE state = 'COMPLETE_CACHE' AND cache_class = 'FULL_FILE';

CREATE TABLE storage.replica (
    id task.identifier PRIMARY KEY,
    rendition_id task.identifier NOT NULL,
    backend_id task.identifier NOT NULL,
    backend_purpose text GENERATED ALWAYS AS ('FORMAL') STORED,
    failure_domain_id task.identifier NOT NULL,
    object_key text NOT NULL CHECK (octet_length(object_key) BETWEEN 1 AND 1024),
    replica_class text NOT NULL CHECK (replica_class IN ('HOT_FORMAL', 'COLD_CLOUD', 'ARCHIVE', 'OFFLINE_BACKUP', 'QUARANTINE')),
    status text NOT NULL CHECK (status IN ('PLANNED', 'COPYING', 'UPLOADING', 'UPLOADED_UNVERIFIED', 'VERIFYING',
        'VERIFIED', 'DEGRADED', 'UNAVAILABLE', 'CORRUPTED', 'REPAIRING', 'DELETING', 'DELETED')),
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    expected_sha256 varchar(64) NOT NULL CHECK (expected_sha256 ~ '^[0-9a-f]{64}$'),
    readback_sha256 varchar(64) CHECK (readback_sha256 = expected_sha256),
    readback_size_bytes bigint CHECK (readback_size_bytes = size_bytes),
    verification_evidence_id task.identifier,
    verified_at timestamptz,
    verification_trace_id varchar(128) CHECK (verification_trace_id ~ '^[A-Za-z0-9-]{8,128}$'),
    retention_until timestamptz,
    last_accessed_at timestamptz,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision BETWEEN 1 AND 9007199254740991),
    UNIQUE (backend_id, object_key),
    UNIQUE (id, rendition_id),
    CONSTRAINT replica_expected_content FOREIGN KEY (rendition_id, size_bytes, expected_sha256)
        REFERENCES media.rendition (id, size_bytes, output_sha256),
    CONSTRAINT replica_formal_backend FOREIGN KEY (backend_id, backend_purpose, failure_domain_id)
        REFERENCES storage.backend (id, purpose, failure_domain_id),
    CHECK (num_nonnulls(readback_sha256, readback_size_bytes, verification_evidence_id,
                       verified_at, verification_trace_id) IN (0, 5)),
    CHECK (status <> 'VERIFIED' OR verified_at IS NOT NULL)
);

CREATE INDEX replica_verified_domain_idx ON storage.replica (rendition_id, failure_domain_id)
    WHERE status = 'VERIFIED' AND replica_class <> 'QUARANTINE';

CREATE TABLE storage.migration (
    id task.identifier PRIMARY KEY,
    rendition_id task.identifier NOT NULL,
    from_replica_id task.identifier NOT NULL,
    to_replica_id task.identifier NOT NULL,
    status text NOT NULL CHECK (status IN ('PLANNED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
    requested_at timestamptz NOT NULL,
    FOREIGN KEY (from_replica_id, rendition_id) REFERENCES storage.replica (id, rendition_id),
    FOREIGN KEY (to_replica_id, rendition_id) REFERENCES storage.replica (id, rendition_id),
    CHECK (from_replica_id <> to_replica_id)
);

CREATE INDEX storage_migration_rendition_idx ON storage.migration (rendition_id, requested_at DESC);

CREATE TABLE storage.watermark_event (
    id task.identifier PRIMARY KEY,
    backend_id task.identifier NOT NULL REFERENCES storage.backend (id),
    level text NOT NULL CHECK (level IN ('NORMAL', 'WARNING', 'CRITICAL', 'SAFETY_FLOOR')),
    available_bytes bigint NOT NULL CHECK (available_bytes >= 0),
    observed_at timestamptz NOT NULL
);

CREATE INDEX storage_watermark_latest_idx ON storage.watermark_event (backend_id, observed_at DESC, id);

CREATE FUNCTION storage.guard_cache_entry() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'cache_entry_history', MESSAGE = 'Retain cache history';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.state NOT IN ('REMOTE_ONLY', 'DOWNLOAD_QUEUED', 'DOWNLOADING', 'VALIDATING')
            OR NEW.verified_at IS NOT NULL OR NEW.revision <> 1
        THEN RAISE check_violation USING CONSTRAINT = 'cache_entry_initial_state', MESSAGE = 'Invalid initial cache state';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.revision <> OLD.revision + 1
        OR ROW(OLD.id, OLD.asset_version_id, OLD.backend_id, OLD.object_key)
           IS DISTINCT FROM ROW(NEW.id, NEW.asset_version_id, NEW.backend_id, NEW.object_key)
        OR OLD.state = 'EVICTED'
        OR (OLD.state = 'EVICTING' AND NEW.state <> 'EVICTED')
        OR (NEW.state = 'EVICTED' AND OLD.state <> 'EVICTING')
        OR (NEW.state = 'EVICTING' AND (OLD.state <> 'COMPLETE_CACHE' OR OLD.expires_at > clock_timestamp()))
        OR (NEW.state = 'PROMOTING' AND OLD.state NOT IN ('COMPLETE_CACHE', 'PINNED_CACHE', 'PROMOTING'))
        OR (NEW.state IN ('COMPLETE_CACHE', 'PINNED_CACHE')
            AND OLD.state NOT IN ('COMPLETE_CACHE', 'PINNED_CACHE', 'PROMOTING')
            AND NEW.verification_evidence_id IS NOT DISTINCT FROM OLD.verification_evidence_id)
    THEN RAISE check_violation USING CONSTRAINT = 'cache_entry_transition', MESSAGE = 'Invalid cache transition';
    END IF;
    IF ROW(OLD.verified_size_bytes, OLD.verification_algorithm, OLD.verification_sha256_or_blake3,
           OLD.verification_evidence_id, OLD.verified_at, OLD.verification_trace_id)
        IS DISTINCT FROM ROW(NEW.verified_size_bytes, NEW.verification_algorithm, NEW.verification_sha256_or_blake3,
                             NEW.verification_evidence_id, NEW.verified_at, NEW.verification_trace_id)
    THEN
        IF OLD.state <> 'VALIDATING' OR NEW.state NOT IN ('COMPLETE_CACHE', 'PINNED_CACHE')
            OR NEW.verification_evidence_id IS NOT DISTINCT FROM OLD.verification_evidence_id
            OR NOT EXISTS (
                SELECT 1 FROM asset.version v JOIN asset.content_hash h ON h.asset_version_id = v.id
                WHERE v.id = NEW.asset_version_id AND v.hash_status = 'FULL_VERIFIED'
                  AND v.content_length = NEW.verified_size_bytes AND h.scope = 'FULL' AND h.verified_at IS NOT NULL
                  AND h.algorithm = NEW.verification_algorithm AND h.hash_value = NEW.verification_sha256_or_blake3
            )
        THEN RAISE check_violation USING CONSTRAINT = 'cache_entry_authoritative_readback', MESSAGE = 'Cache readback does not match authoritative content';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER cache_entry_transition BEFORE INSERT OR UPDATE OR DELETE ON storage.cache_entry
FOR EACH ROW EXECUTE FUNCTION storage.guard_cache_entry();

CREATE FUNCTION storage.emit_cache_verification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO outbox.event (
        event_id, event_type, event_version, aggregate_type, aggregate_id, aggregate_revision,
        occurred_at, producer, trace_id, payload
    ) VALUES ('evt_' || gen_random_uuid(), 'cache.complete.verified', 1, 'CacheEntry', NEW.id, NEW.revision,
        NEW.verified_at, 'guize-control', NEW.verification_trace_id, jsonb_build_object(
            'cacheEntryId', NEW.id, 'assetVersionId', NEW.asset_version_id, 'cacheClass', NEW.cache_class,
            'sizeBytes', NEW.size_bytes, 'revision', NEW.revision, 'state', NEW.state, 'verification',
            jsonb_build_object('algorithm', NEW.verification_algorithm, 'expectedHash', NEW.verification_sha256_or_blake3,
                'actualHash', NEW.verification_sha256_or_blake3, 'evidenceId', NEW.verification_evidence_id,
                'verifiedAt', outbox.utc_timestamp(NEW.verified_at))));
    RETURN NEW;
END;
$$;

CREATE TRIGGER cache_entry_verified AFTER UPDATE ON storage.cache_entry FOR EACH ROW
WHEN (NEW.state IN ('COMPLETE_CACHE', 'PINNED_CACHE')
      AND ROW(OLD.verified_size_bytes, OLD.verification_algorithm, OLD.verification_sha256_or_blake3,
              OLD.verification_evidence_id, OLD.verified_at, OLD.verification_trace_id)
          IS DISTINCT FROM ROW(NEW.verified_size_bytes, NEW.verification_algorithm, NEW.verification_sha256_or_blake3,
                               NEW.verification_evidence_id, NEW.verified_at, NEW.verification_trace_id))
EXECUTE FUNCTION storage.emit_cache_verification();

CREATE FUNCTION storage.advance_expired_cache(
    p_cache_id task.identifier, p_expected_revision bigint, p_next_state text
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    next_revision bigint;
BEGIN
    IF p_next_state IS NULL OR p_next_state NOT IN ('EVICTING', 'EVICTED') THEN RETURN NULL; END IF;

    UPDATE storage.cache_entry SET state = p_next_state, revision = revision + 1
    WHERE id = p_cache_id AND revision = p_expected_revision AND cache_class = 'FULL_FILE'
      AND ((state = 'COMPLETE_CACHE' AND p_next_state = 'EVICTING' AND expires_at <= clock_timestamp())
           OR (state = 'EVICTING' AND p_next_state = 'EVICTED'))
    RETURNING revision INTO next_revision;
    IF NOT FOUND THEN
        SELECT revision INTO next_revision FROM storage.cache_entry
        WHERE id = p_cache_id AND revision - 1 = p_expected_revision AND state = p_next_state;
    END IF;
    RETURN next_revision;
END;
$$;

REVOKE EXECUTE ON FUNCTION storage.advance_expired_cache(task.identifier, bigint, text) FROM PUBLIC;

CREATE FUNCTION storage.guard_replica() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    protected_asset task.identifier;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE check_violation USING CONSTRAINT = 'replica_history', MESSAGE = 'Retain formal replica history';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PLANNED' OR NEW.verified_at IS NOT NULL OR NEW.revision <> 1
        THEN RAISE check_violation USING CONSTRAINT = 'replica_initial_state', MESSAGE = 'Replica must begin as planned';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.revision <> OLD.revision + 1
        OR ROW(OLD.id, OLD.rendition_id, OLD.backend_id, OLD.failure_domain_id, OLD.object_key,
               OLD.replica_class, OLD.size_bytes, OLD.expected_sha256)
           IS DISTINCT FROM ROW(NEW.id, NEW.rendition_id, NEW.backend_id, NEW.failure_domain_id, NEW.object_key,
                                NEW.replica_class, NEW.size_bytes, NEW.expected_sha256)
        OR OLD.status = 'DELETED'
        OR (OLD.status = 'DELETING' AND NEW.status NOT IN ('DELETING', 'DELETED', 'DEGRADED'))
        OR (NEW.status = 'DELETED' AND OLD.status <> 'DELETING')
        OR (NEW.status = 'VERIFIED' AND (OLD.status NOT IN ('VERIFYING', 'VERIFIED')
            OR (OLD.status = 'VERIFYING' AND NEW.verification_evidence_id IS NOT DISTINCT FROM OLD.verification_evidence_id)))
    THEN RAISE check_violation USING CONSTRAINT = 'replica_transition', MESSAGE = 'Invalid replica transition';
    END IF;
    IF ROW(OLD.readback_sha256, OLD.readback_size_bytes, OLD.verification_evidence_id, OLD.verified_at, OLD.verification_trace_id)
        IS DISTINCT FROM ROW(NEW.readback_sha256, NEW.readback_size_bytes, NEW.verification_evidence_id, NEW.verified_at, NEW.verification_trace_id)
        AND (NEW.status <> 'VERIFIED' OR NEW.verified_at IS NULL
            OR NEW.verification_evidence_id IS NOT DISTINCT FROM OLD.verification_evidence_id)
    THEN RAISE check_violation USING CONSTRAINT = 'replica_readback_state', MESSAGE = 'Replica readback must accompany verification';
    END IF;
    IF OLD.retention_until > clock_timestamp() AND (NEW.retention_until IS NULL OR NEW.retention_until < OLD.retention_until)
    THEN RAISE check_violation USING CONSTRAINT = 'replica_retention_deadline', MESSAGE = 'An active retention deadline cannot be shortened';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status AND (NEW.status IN ('VERIFIED', 'DELETING', 'DELETED') OR OLD.status = 'VERIFIED') THEN
        SELECT v.asset_id INTO STRICT protected_asset
        FROM media.rendition r JOIN asset.version v ON v.id = r.asset_version_id
        WHERE r.id = OLD.rendition_id;
        PERFORM storage.lock_asset_lifecycle(protected_asset);
        IF NEW.status IN ('DELETING', 'DELETED') AND (
            OLD.retention_until > clock_timestamp() OR NEW.retention_until > clock_timestamp()
            OR EXISTS (SELECT 1 FROM storage.retention_hold WHERE asset_id = protected_asset AND released_at IS NULL)
            OR (OLD.verified_at IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM storage.replica other WHERE other.rendition_id = OLD.rendition_id
                  AND other.failure_domain_id <> OLD.failure_domain_id AND other.status = 'VERIFIED'
                  AND other.replica_class <> 'QUARANTINE'
            ))
        ) THEN RAISE check_violation USING CONSTRAINT = 'replica_removal_protected', MESSAGE = 'Formal replica removal is protected';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER replica_transition BEFORE INSERT OR UPDATE OR DELETE ON storage.replica
FOR EACH ROW EXECUTE FUNCTION storage.guard_replica();

CREATE FUNCTION storage.emit_replica_verification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO outbox.event (
        event_id, event_type, event_version, aggregate_type, aggregate_id, aggregate_revision,
        occurred_at, producer, trace_id, payload
    ) VALUES ('evt_' || gen_random_uuid(), 'replica.verified', 1, 'Replica', NEW.id, NEW.revision,
        NEW.verified_at, 'guize-control', NEW.verification_trace_id, jsonb_build_object(
            'replicaId', NEW.id, 'renditionId', NEW.rendition_id, 'storageTargetId', NEW.backend_id,
            'failureDomainId', NEW.failure_domain_id, 'revision', NEW.revision, 'status', NEW.status,
            'sizeBytes', NEW.size_bytes, 'verification', jsonb_build_object('algorithm', 'SHA256',
                'expectedHash', NEW.expected_sha256, 'actualHash', NEW.readback_sha256,
                'evidenceId', NEW.verification_evidence_id, 'verifiedAt', outbox.utc_timestamp(NEW.verified_at))));
    RETURN NEW;
END;
$$;

CREATE TRIGGER replica_verified AFTER UPDATE ON storage.replica FOR EACH ROW
WHEN (NEW.status = 'VERIFIED'
      AND ROW(OLD.readback_sha256, OLD.readback_size_bytes, OLD.verification_evidence_id, OLD.verified_at, OLD.verification_trace_id)
          IS DISTINCT FROM ROW(NEW.readback_sha256, NEW.readback_size_bytes, NEW.verification_evidence_id, NEW.verified_at, NEW.verification_trace_id))
EXECUTE FUNCTION storage.emit_replica_verification();

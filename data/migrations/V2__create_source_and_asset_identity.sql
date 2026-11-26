CREATE TABLE source.data_source (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    name varchar(256) NOT NULL,
    kind text NOT NULL CHECK (kind IN ('WEBDAV', 'LOCAL', 'BAIDU', 'GOOGLE_DRIVE', 'HTTP', 'S3', 'SMB', 'NFS', 'ONEDRIVE')),
    visibility text NOT NULL DEFAULT 'PRIVATE' CHECK (visibility IN ('PRIVATE', 'SHARED', 'ADMIN_PUBLIC')),
    owner_id varchar(80) NOT NULL CHECK (owner_id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    status text NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'REVOKED', 'ERROR')),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX data_source_owner_idx ON source.data_source (owner_id);

CREATE TABLE asset.duplicate_group (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE asset.asset (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    canonical_title varchar(256) NOT NULL,
    description varchar(4096),
    asset_type text NOT NULL CHECK (asset_type IN ('VIDEO', 'AUDIO', 'IMAGE', 'DOCUMENT', 'ARCHIVE', 'OTHER')),
    current_version_id varchar(80),
    duplicate_group_id varchar(80) REFERENCES asset.duplicate_group (id),
    visibility_status text NOT NULL DEFAULT 'PRIVATE' CHECK (visibility_status IN ('PRIVATE', 'SHARED', 'PUBLIC')),
    lifecycle_status text NOT NULL,
    security_status text NOT NULL DEFAULT 'SCAN_PENDING' CHECK (security_status IN (
        'SCAN_PENDING', 'SCAN_CLEAN', 'MIME_MISMATCH', 'MALWARE_SUSPECTED',
        'MALWARE_CONFIRMED', 'ARCHIVE_UNSAFE', 'QUARANTINED', 'ADMIN_RELEASED'
    )),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX asset_current_version_idx ON asset.asset (current_version_id);
CREATE INDEX asset_lifecycle_idx ON asset.asset (lifecycle_status);
CREATE INDEX asset_duplicate_group_idx ON asset.asset (duplicate_group_id);

CREATE TABLE source.object (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    data_source_id varchar(80) NOT NULL REFERENCES source.data_source (id),
    asset_id varchar(80) NOT NULL REFERENCES asset.asset (id),
    provider_object_id varchar(256) NOT NULL CHECK (length(provider_object_id) > 0),
    parent_provider_object_id varchar(256),
    current_path varchar(4096) NOT NULL,
    current_filename varchar(256) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    mime_declared varchar(256),
    mime_detected varchar(256),
    etag varchar(256) NOT NULL,
    provider_hash text,
    modified_at timestamptz,
    last_seen_at timestamptz NOT NULL,
    sync_status text NOT NULL,
    availability_status text NOT NULL CHECK (availability_status IN ('AVAILABLE', 'UNAVAILABLE', 'UNKNOWN')),
    metadata_json jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata_json) = 'object'),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision >= 1),
    CONSTRAINT source_object_provider_identity UNIQUE (data_source_id, provider_object_id)
);

CREATE INDEX source_object_path_idx ON source.object USING hash (current_path);
CREATE INDEX source_object_filename_idx ON source.object (current_filename);
CREATE INDEX source_object_asset_idx ON source.object (asset_id);
CREATE INDEX source_object_seen_idx ON source.object (data_source_id, last_seen_at);

CREATE TABLE source.object_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_object_id varchar(80) NOT NULL REFERENCES source.object (id),
    source_revision bigint NOT NULL CHECK (source_revision >= 1),
    operation text NOT NULL CHECK (operation IN ('CREATE', 'RENAME', 'MOVE', 'CONTENT_UPDATE', 'DELETE', 'RESTORE', 'MERGE', 'SPLIT')),
    old_path varchar(4096),
    new_path varchar(4096),
    observed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_object_id, source_revision)
);

CREATE TABLE asset.version (
    id varchar(80) PRIMARY KEY CHECK (id ~ '^[a-z]{2,12}_[A-Za-z0-9_-]{1,64}$'),
    asset_id varchar(80) NOT NULL REFERENCES asset.asset (id),
    version_number bigint NOT NULL CHECK (version_number >= 1),
    origin_source_object_id varchar(80) NOT NULL REFERENCES source.object (id),
    content_length bigint NOT NULL CHECK (content_length >= 0),
    mime_type varchar(256) NOT NULL,
    hash_status text NOT NULL DEFAULT 'UNKNOWN' CHECK (hash_status IN ('UNKNOWN', 'SAMPLE', 'FULL_VERIFIED')),
    created_reason text NOT NULL,
    supersedes_version_id varchar(80),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at timestamptz,
    CONSTRAINT asset_version_number UNIQUE (asset_id, version_number),
    CONSTRAINT asset_version_identity UNIQUE (asset_id, id),
    CONSTRAINT asset_version_predecessor FOREIGN KEY (asset_id, supersedes_version_id)
        REFERENCES asset.version (asset_id, id),
    CHECK (supersedes_version_id IS NULL OR supersedes_version_id <> id)
);

CREATE INDEX asset_version_origin_idx ON asset.version (origin_source_object_id);

ALTER TABLE asset.asset ADD CONSTRAINT asset_current_version_ownership
    FOREIGN KEY (id, current_version_id) REFERENCES asset.version (asset_id, id);

CREATE TABLE asset.content_hash (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_version_id varchar(80) NOT NULL REFERENCES asset.version (id),
    algorithm text NOT NULL CHECK (algorithm IN ('SHA256', 'BLAKE3', 'SAMPLE_V1', 'PROVIDER')),
    hash_value varchar(256) NOT NULL CHECK (length(hash_value) > 0),
    scope text NOT NULL CHECK (scope IN ('FULL', 'SAMPLE', 'PROVIDER')),
    verified_at timestamptz,
    verified_by varchar(80),
    CHECK (scope <> 'FULL' OR (algorithm IN ('SHA256', 'BLAKE3') AND hash_value ~ '^[0-9a-f]{64}$')),
    CHECK ((scope = 'SAMPLE') = (algorithm = 'SAMPLE_V1')),
    CHECK ((scope = 'PROVIDER') = (algorithm = 'PROVIDER')),
    UNIQUE (asset_version_id, algorithm, hash_value, scope)
);

CREATE INDEX content_hash_lookup_idx ON asset.content_hash (algorithm, scope, hash_value);

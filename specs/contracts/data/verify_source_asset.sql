BEGIN;

INSERT INTO source.data_source (id, name, kind, owner_id, status, endpoint, root_path)
VALUES ('src_catalog', 'Synthetic catalog', 'WEBDAV', 'usr_owner', 'ACTIVE',
        'https://source.example/remote.php/dav', 'media');

INSERT INTO asset.asset (id, canonical_title, asset_type, lifecycle_status)
VALUES ('ast_clip', 'Synthetic clip', 'VIDEO', 'ACTIVE'),
       ('ast_other', 'Other clip', 'VIDEO', 'ACTIVE');

INSERT INTO source.object (
    id, data_source_id, asset_id, provider_object_id, current_path, current_filename,
    size_bytes, etag, last_seen_at, sync_status, availability_status
)
VALUES (
    'obj_clip', 'src_catalog', 'ast_clip', 'provider_clip', '/original.mp4', 'original.mp4',
    4096, 'fixture-etag', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE'
);

INSERT INTO asset.version (
    id, asset_id, version_number, origin_source_object_id, content_length, mime_type, created_reason
)
VALUES ('ver_clip_v1', 'ast_clip', 1, 'obj_clip', 4096, 'video/mp4', 'INITIAL');

UPDATE asset.asset SET current_version_id = 'ver_clip_v1' WHERE id = 'ast_clip';

UPDATE source.object
SET current_path = '/' || repeat(chr(29255), 4000),
    current_filename = 'renamed.mp4',
    revision = revision + 1
WHERE id = 'obj_clip';

INSERT INTO source.object_history (source_object_id, source_revision, operation, old_path, new_path)
SELECT id, revision, 'RENAME', '/original.mp4', current_path FROM source.object WHERE id = 'obj_clip';

DO $$
DECLARE
    violated_constraint text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM source.object AS object
        JOIN source.object_history AS history ON history.source_object_id = object.id
        JOIN asset.asset AS asset ON asset.id = object.asset_id
        JOIN asset.version AS version ON version.id = asset.current_version_id
        WHERE object.id = 'obj_clip'
          AND object.provider_object_id = 'provider_clip'
          AND object.current_path = '/' || repeat(chr(29255), 4000)
          AND object.revision = history.source_revision
          AND history.operation = 'RENAME'
          AND version.id = 'ver_clip_v1'
          AND version.origin_source_object_id = object.id
    ) OR (SELECT count(*) FROM asset.version WHERE asset_id = 'ast_clip') <> 1 THEN
        RAISE EXCEPTION 'Renaming must retain source and content-version identity';
    END IF;

    BEGIN
        INSERT INTO source.object (
            id, data_source_id, asset_id, provider_object_id, current_path, current_filename,
            size_bytes, etag, last_seen_at, sync_status, availability_status
        )
        SELECT 'obj_duplicate', data_source_id, asset_id, provider_object_id, current_path, current_filename,
               size_bytes, etag, last_seen_at, sync_status, availability_status
        FROM source.object WHERE id = 'obj_clip';
        RAISE EXCEPTION 'Source provider identity must remain unique';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'source_object_provider_identity' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO asset.version (
            id, asset_id, version_number, origin_source_object_id, content_length, mime_type, created_reason
        )
        VALUES ('ver_duplicate', 'ast_clip', 1, 'obj_clip', 4096, 'video/mp4', 'INITIAL');
        RAISE EXCEPTION 'Content version number must remain unique per asset';
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'asset_version_number' THEN RAISE; END IF;
    END;

    BEGIN
        UPDATE asset.asset SET current_version_id = 'ver_clip_v1' WHERE id = 'ast_other';
        RAISE EXCEPTION 'An asset cannot reference another asset''s current version';
    EXCEPTION WHEN foreign_key_violation THEN
        GET STACKED DIAGNOSTICS violated_constraint = CONSTRAINT_NAME;
        IF violated_constraint <> 'asset_current_version_ownership' THEN RAISE; END IF;
    END;
END;
$$;

ROLLBACK;

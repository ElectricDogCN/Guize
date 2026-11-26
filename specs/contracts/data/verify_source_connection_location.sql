\set ON_ERROR_STOP on
BEGIN;

INSERT INTO source.data_source (id, name, kind, owner_id, status, endpoint, root_path)
VALUES ('src_route_webdav', 'Source draft WebDAV', 'WEBDAV', 'usr_route', 'ACTIVE',
        'https://source.example:8443/remote.php/dav', '合成媒体/节目'),
       ('src_route_local', 'Source draft local', 'LOCAL', 'usr_route', 'ACTIVE',
        'mount:media_fixture', '合成媒体/节目'),
       ('src_route_smb', 'Source draft SMB', 'SMB', 'usr_route', 'ACTIVE',
        'smb://source.example/media', 'archive'),
       ('src_route_nfs', 'Source draft NFS', 'NFS', 'usr_route', 'ACTIVE',
        'nfs://source.example/media', 'archive');

INSERT INTO source.credential_reference (data_source_id, credential_reference, revision, updated_at)
VALUES ('src_route_webdav', 'secretref_fixture', 1, CURRENT_TIMESTAMP);

DO $$
DECLARE
    failed_constraint text;
BEGIN
    IF NOT EXISTS (
        SELECT FROM source.data_source AS s
        JOIN source.credential_reference AS c ON c.data_source_id = s.id
        WHERE (s.id, s.endpoint, s.root_path, c.credential_reference) =
            ('src_route_webdav', 'https://source.example:8443/remote.php/dav', '合成媒体/节目', 'secretref_fixture')
    ) OR NOT EXISTS (
        SELECT FROM source.data_source
        WHERE (id, endpoint, root_path) = ('src_route_local', 'mount:media_fixture', '合成媒体/节目')
    ) THEN
        RAISE EXCEPTION 'Source draft connection location did not round-trip';
    END IF;

    BEGIN
        INSERT INTO source.data_source (id, name, kind, owner_id, status)
        VALUES ('src_route_missing', 'Missing location', 'WEBDAV', 'usr_route', 'ACTIVE');
        RAISE EXCEPTION 'New source without a location was accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS failed_constraint = CONSTRAINT_NAME;
        IF failed_constraint <> 'data_source_location_required' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO source.data_source (id, name, kind, owner_id, status, endpoint)
        VALUES ('src_route_partial', 'Missing root', 'WEBDAV', 'usr_route', 'ACTIVE', 'https://source.example');
        RAISE EXCEPTION 'New source with only an endpoint was accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS failed_constraint = CONSTRAINT_NAME;
        IF failed_constraint <> 'data_source_location_pair' THEN RAISE; END IF;
    END;

    BEGIN
        INSERT INTO source.data_source (id, name, kind, owner_id, status, endpoint, root_path)
        VALUES ('src_route_wrong_kind', 'Incorrect kind', 'LOCAL', 'usr_route', 'ACTIVE',
                'https://source.example', 'media');
        RAISE EXCEPTION 'LOCAL source with an HTTP endpoint was accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS failed_constraint = CONSTRAINT_NAME;
        IF failed_constraint <> 'data_source_location_format' THEN RAISE; END IF;
    END;

    BEGIN
        UPDATE source.data_source SET root_path = 'another-root' WHERE id = 'src_route_webdav';
        RAISE EXCEPTION 'Configured source switched from its existing scan root';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS failed_constraint = CONSTRAINT_NAME;
        IF failed_constraint <> 'data_source_location_immutable' THEN RAISE; END IF;
    END;

    UPDATE source.data_source SET name = 'Renamed source', revision = revision + 1 WHERE id = 'src_route_webdav';
    IF NOT EXISTS (
        SELECT FROM source.data_source WHERE id = 'src_route_webdav'
        AND (name, revision, root_path) = ('Renamed source', 2, '合成媒体/节目')
    ) THEN
        RAISE EXCEPTION 'Metadata change did not preserve the configured route';
    END IF;
END;
$$;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

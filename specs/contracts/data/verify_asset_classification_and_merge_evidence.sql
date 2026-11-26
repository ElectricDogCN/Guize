BEGIN;

INSERT INTO iam.user_account (id, username, status) VALUES ('usr_merge_fixture', 'Synthetic merge tester', 'ACTIVE');
INSERT INTO source.data_source (id, name, kind, owner_id, status)
VALUES ('src_alias_fixture', 'Synthetic source A', 'LOCAL', 'usr_merge_fixture', 'ACTIVE'),
       ('src_other_fixture', 'Synthetic source B', 'WEBDAV', 'usr_merge_fixture', 'ACTIVE');

INSERT INTO asset.duplicate_group (id) VALUES ('dup_fixture');
INSERT INTO asset.asset (id, canonical_title, asset_type, lifecycle_status, duplicate_group_id)
VALUES ('ast_alias_left', 'Left fixture', 'VIDEO', 'ACTIVE', 'dup_fixture'),
       ('ast_alias_right', 'Right fixture', 'VIDEO', 'ACTIVE', 'dup_fixture'),
       ('ast_alias_diff', 'Different fixture', 'VIDEO', 'ACTIVE', NULL),
       ('ast_alias_ambiguous', 'Conflicting proof fixture', 'VIDEO', 'ACTIVE', NULL);

INSERT INTO source.object (id, data_source_id, asset_id, provider_object_id, current_path, current_filename,
                           size_bytes, etag, last_seen_at, sync_status, availability_status)
VALUES ('obj_alias_left', 'src_alias_fixture', 'ast_alias_left', 'fixture-left', '/left.mp4', 'left.mp4', 4, 'fixture-left', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE'),
       ('obj_alias_right', 'src_other_fixture', 'ast_alias_right', 'fixture-right', '/right.mp4', 'right.mp4', 4, 'fixture-right', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE'),
       ('obj_alias_diff', 'src_other_fixture', 'ast_alias_diff', 'fixture-diff', '/diff.mp4', 'diff.mp4', 4, 'fixture-diff', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE'),
       ('obj_alias_ambiguous', 'src_other_fixture', 'ast_alias_ambiguous', 'fixture-ambiguous', '/ambiguous.mp4', 'ambiguous.mp4', 4, 'fixture-ambiguous', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE');

INSERT INTO asset.version (id, asset_id, version_number, origin_source_object_id, content_length, mime_type, hash_status, created_reason)
VALUES ('ver_alias_left', 'ast_alias_left', 1, 'obj_alias_left', 4, 'video/mp4', 'FULL_VERIFIED', 'INITIAL'),
       ('ver_alias_right', 'ast_alias_right', 1, 'obj_alias_right', 4, 'video/mp4', 'FULL_VERIFIED', 'INITIAL'),
       ('ver_alias_diff', 'ast_alias_diff', 1, 'obj_alias_diff', 4, 'video/mp4', 'FULL_VERIFIED', 'INITIAL'),
       ('ver_alias_ambiguous', 'ast_alias_ambiguous', 1, 'obj_alias_ambiguous', 4, 'video/mp4', 'FULL_VERIFIED', 'INITIAL');
UPDATE asset.asset a SET current_version_id = v.id FROM asset.version v WHERE v.asset_id = a.id;

INSERT INTO asset.content_hash (asset_version_id, algorithm, hash_value, scope, verified_at)
SELECT id, 'SHA256', encode(sha256(convert_to(CASE WHEN id = 'ver_alias_diff' THEN 'diff' ELSE 'same' END, 'UTF8')), 'hex'),
       'FULL', CURRENT_TIMESTAMP FROM asset.version;
INSERT INTO asset.content_hash (asset_version_id, algorithm, hash_value, scope, verified_at)
VALUES ('ver_alias_ambiguous', 'SHA256', encode(sha256(convert_to('diff', 'UTF8')), 'hex'), 'FULL', CURRENT_TIMESTAMP);

UPDATE source.object SET current_path = '/renamed.mp4', current_filename = 'renamed.mp4', revision = 2 WHERE id = 'obj_alias_left';
INSERT INTO source.object_history (source_object_id, source_revision, operation, old_path, new_path)
VALUES ('obj_alias_left', 2, 'RENAME', '/' || repeat(chr(29255), 3800) || '/older.mp4', '/renamed.mp4'),
       ('obj_alias_right', 1, 'CREATE', NULL, '/right.mp4');

INSERT INTO asset.tag (id, namespace, name) VALUES ('tag_fixture', 'USER', 'Keep'), ('tag_fixture_safety', 'SAFETY', 'Keep');
INSERT INTO asset.tag_assignment (id, tag_id, asset_id, source_object_id, assigned_by)
VALUES ('asg_asset_fixture', 'tag_fixture', 'ast_alias_left', NULL, 'usr_merge_fixture'),
       ('asg_source_fixture', 'tag_fixture', NULL, 'obj_alias_left', 'usr_merge_fixture');

DO $$
BEGIN
    IF (SELECT count(*) FROM asset.alias) <> 1 OR NOT EXISTS (
        SELECT 1 FROM asset.alias WHERE source_object_id = 'obj_alias_left' AND asset_id = 'ast_alias_left'
          AND alias_name = 'older.mp4' AND alias_path = '/' || repeat(chr(29255), 3800) || '/older.mp4'
    ) THEN RAISE EXCEPTION 'historical alias is wrong'; END IF;
    BEGIN
        UPDATE source.object_history SET old_path = '/rewrite.mp4' WHERE source_object_id = 'obj_alias_left';
        RAISE EXCEPTION 'source history was rewritten';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE asset.version SET origin_source_object_id = 'obj_alias_right' WHERE id = 'ver_alias_left';
        RAISE EXCEPTION 'version origin was rewritten';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        UPDATE asset.content_hash SET verified_at = NULL WHERE asset_version_id = 'ver_alias_left';
        RAISE EXCEPTION 'verified history was invalidated in place';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO asset.tag (id, namespace, name) VALUES ('tag_fixture_duplicate', 'USER', 'keep');
        RAISE EXCEPTION 'duplicate case-folded tag was accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO asset.tag_assignment (id, tag_id, asset_id, source_object_id, assigned_by)
        VALUES ('asg_mixed_fixture', 'tag_fixture', 'ast_alias_left', 'obj_alias_left', 'usr_merge_fixture');
        RAISE EXCEPTION 'mixed asset and source subject was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO asset.tag_assignment (id, tag_id, source_object_id, assigned_by)
        VALUES ('asg_repeat_fixture', 'tag_fixture', 'obj_alias_left', 'usr_merge_fixture');
        RAISE EXCEPTION 'duplicate source assignment was accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
END;
$$;

CREATE ROLE gz_fixture_asset_link NOLOGIN;
GRANT USAGE ON SCHEMA task, asset, source TO gz_fixture_asset_link;
SET LOCAL ROLE gz_fixture_asset_link;
DO $$
BEGIN
    IF has_function_privilege('source.lock_asset_observation(task.identifier,task.identifier,bigint)', 'EXECUTE')
    THEN RAISE EXCEPTION 'source lock is executable without grant'; END IF;
END;
$$;
RESET ROLE;
GRANT EXECUTE ON FUNCTION source.lock_asset_observation(task.identifier, task.identifier, bigint) TO gz_fixture_asset_link;
GRANT INSERT ON asset.version_source TO gz_fixture_asset_link;
GRANT SELECT, UPDATE ON asset.asset, asset.version TO gz_fixture_asset_link;
GRANT SELECT ON asset.authoritative_content_hash TO gz_fixture_asset_link;
SET LOCAL ROLE gz_fixture_asset_link;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper)
       OR has_any_column_privilege('source.object', 'SELECT,UPDATE')
       OR has_table_privilege('source.object', 'INSERT,DELETE')
    THEN RAISE EXCEPTION 'asset role has direct source privileges'; END IF;
END;
$$;
INSERT INTO asset.version_source (asset_id, asset_version_id, source_object_id, source_revision, algorithm, accepted_hash, evidence_id, observed_at)
VALUES ('ast_alias_left', 'ver_alias_left', 'obj_alias_left', 2, 'SHA256',
        encode(sha256(convert_to('same', 'UTF8')), 'hex'), 'evid_link_left', CURRENT_TIMESTAMP);
RESET ROLE;
REVOKE SELECT ON asset.authoritative_content_hash FROM gz_fixture_asset_link;
REVOKE SELECT, UPDATE ON asset.asset, asset.version FROM gz_fixture_asset_link;
REVOKE INSERT ON asset.version_source FROM gz_fixture_asset_link;
REVOKE EXECUTE ON FUNCTION source.lock_asset_observation(task.identifier, task.identifier, bigint) FROM gz_fixture_asset_link;
REVOKE USAGE ON SCHEMA task, asset, source FROM gz_fixture_asset_link;
DROP ROLE gz_fixture_asset_link;

DO $$
DECLARE
    digest text := encode(sha256(convert_to('same', 'UTF8')), 'hex');
    violated text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM asset.current_version_source WHERE source_object_id = 'obj_alias_left' AND source_revision = 2)
    THEN RAISE EXCEPTION 'exact current association is missing'; END IF;
    BEGIN
        INSERT INTO asset.version_source (asset_id, asset_version_id, source_object_id, source_revision, algorithm, accepted_hash, evidence_id, observed_at)
        VALUES ('ast_alias_left', 'ver_alias_left', 'obj_alias_right', 1, 'SHA256', digest, 'evid_wrong_source', CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'foreign source was attached';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    BEGIN
        INSERT INTO asset.version_source (asset_id, asset_version_id, source_object_id, source_revision, algorithm, accepted_hash, evidence_id, observed_at)
        VALUES ('ast_alias_left', 'ver_alias_left', 'obj_alias_left', 1, 'SHA256', digest, 'evid_stale_source', CURRENT_TIMESTAMP);
        RAISE EXCEPTION 'stale source revision was attached';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    BEGIN
        INSERT INTO asset.merge_decision (id, source_asset_id, source_version_id, source_expected_revision,
            target_asset_id, target_version_id, target_expected_revision, outcome, reason, decided_by, algorithm, verified_hash)
        VALUES ('mrg_wrong', 'ast_alias_left', 'ver_alias_left', 1, 'ast_alias_diff', 'ver_alias_diff', 1,
                'APPROVED', 'mismatched content', 'usr_merge_fixture', 'SHA256', digest);
        RAISE EXCEPTION 'different version digest accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'asset_merge_full_hash' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO asset.merge_decision (id, source_asset_id, source_version_id, source_expected_revision,
            target_asset_id, target_version_id, target_expected_revision, outcome, reason, decided_by, algorithm, verified_hash)
        VALUES ('mrg_conflict', 'ast_alias_left', 'ver_alias_left', 1, 'ast_alias_ambiguous', 'ver_alias_ambiguous', 1,
                'APPROVED', 'conflicting proofs', 'usr_merge_fixture', 'SHA256', digest);
        RAISE EXCEPTION 'ambiguous version accepted';
    EXCEPTION WHEN check_violation THEN
        GET STACKED DIAGNOSTICS violated = CONSTRAINT_NAME;
        IF violated <> 'asset_merge_full_hash' THEN RAISE; END IF;
    END;
    BEGIN
        INSERT INTO asset.merge_decision (id, source_asset_id, source_version_id, source_expected_revision,
            target_asset_id, target_version_id, target_expected_revision, outcome, reason, decided_by, algorithm, verified_hash)
        VALUES ('mrg_stale', 'ast_alias_left', 'ver_alias_left', 1, 'ast_alias_right', 'ver_alias_right', 2,
                'APPROVED', 'wrong expected revision', 'usr_merge_fixture', 'SHA256', digest);
        RAISE EXCEPTION 'stale target revision accepted';
    EXCEPTION WHEN serialization_failure THEN NULL;
    END;
    INSERT INTO asset.merge_decision (id, source_asset_id, source_version_id, source_expected_revision,
        target_asset_id, target_version_id, target_expected_revision, outcome, reason, decided_by, algorithm, verified_hash)
    VALUES ('mrg_fixture_approved', 'ast_alias_left', 'ver_alias_left', 1, 'ast_alias_right', 'ver_alias_right', 1,
            'APPROVED', 'verified equal content', 'usr_merge_fixture', 'SHA256', digest),
           ('mrg_fixture_declined', 'ast_alias_left', 'ver_alias_left', 1, 'ast_alias_diff', 'ver_alias_diff', 1,
            'DECLINED', 'do not consolidate', 'usr_merge_fixture', NULL, NULL);
    BEGIN
        UPDATE asset.merge_decision SET reason = 'rewritten' WHERE id = 'mrg_fixture_approved';
        RAISE EXCEPTION 'merge history was rewritten';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;

-- Exercise provenance after an application reassociation, using a synthetic update.
UPDATE source.object SET asset_id = 'ast_alias_right', revision = revision + 1 WHERE id = 'obj_alias_left';
INSERT INTO source.object_history (source_object_id, source_revision, operation, old_path, new_path)
VALUES ('obj_alias_left', 3, 'MERGE', '/renamed.mp4', '/renamed.mp4');

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM asset.current_version_source WHERE source_object_id = 'obj_alias_left')
        OR NOT EXISTS (SELECT 1 FROM asset.version_source WHERE source_object_id = 'obj_alias_left' AND source_revision = 2
                      AND asset_version_id = 'ver_alias_left' AND evidence_id = 'evid_link_left')
        OR NOT EXISTS (SELECT 1 FROM asset.version WHERE id = 'ver_alias_left' AND origin_source_object_id = 'obj_alias_left')
        OR NOT EXISTS (SELECT 1 FROM asset.alias WHERE source_object_id = 'obj_alias_left' AND asset_id = 'ast_alias_right')
        OR NOT EXISTS (SELECT 1 FROM asset.tag_assignment WHERE id = 'asg_source_fixture' AND source_object_id = 'obj_alias_left')
        OR NOT EXISTS (SELECT 1 FROM asset.tag_assignment WHERE id = 'asg_asset_fixture' AND asset_id = 'ast_alias_left')
        OR (SELECT count(*) FROM asset.merge_decision) <> 2
    THEN RAISE EXCEPTION 'reassociation discarded history, membership, or independent labels'; END IF;
END;
$$;

\if :{?retain_fixture}
COMMIT;
\else
ROLLBACK;
\endif

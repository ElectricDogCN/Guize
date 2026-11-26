INSERT INTO source.data_source (id, name, kind, owner_id, status, endpoint, root_path)
VALUES ('src_task', 'Task fixture', 'LOCAL', 'usr_owner', 'ACTIVE', 'mount:task', 'media');
INSERT INTO asset.asset (id, canonical_title, asset_type, lifecycle_status)
VALUES ('ast_task', 'Task fixture', 'VIDEO', 'ACTIVE');
INSERT INTO source.object (
    id, data_source_id, asset_id, provider_object_id, current_path, current_filename,
    size_bytes, etag, last_seen_at, sync_status, availability_status
)
VALUES ('obj_task', 'src_task', 'ast_task', 'source-task', '/task.mp4', 'task.mp4',
        64, 'fixture-etag', CURRENT_TIMESTAMP, 'SYNCED', 'AVAILABLE');
INSERT INTO asset.version (
    id, asset_id, version_number, origin_source_object_id, content_length, mime_type, created_reason
)
VALUES ('ver_task', 'ast_task', 1, 'obj_task', 64, 'video/mp4', 'INITIAL');

INSERT INTO task.task (id, type, owner_id, input_version_id, idempotency_scope, idempotency_key, status, priority, trace_id)
VALUES ('tsk_fixture', 'transcode', 'usr_owner', 'ver_task', 'usr_owner:transcode', 'same-request', 'RUNNING', 3, 'trace-task');
INSERT INTO task.worker (id, status, heartbeat_expires_at)
VALUES ('node_first', 'ONLINE', clock_timestamp() + interval '1 hour'),
       ('node_second', 'ONLINE', clock_timestamp() + interval '1 hour');
INSERT INTO task.worker_capability VALUES ('node_first', 'cap_av1', '1', '1'), ('node_second', 'cap_av1', '1', '1');

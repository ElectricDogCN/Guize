BEGIN;

CREATE TEMP TABLE expected_relation AS
SELECT schema_name, unnest(relations) AS relation_name
FROM (VALUES
    ('iam', ARRAY['user_account','role','user_role','group','group_member','asset_acl','passkey_credential','session','login_event']),
    ('source', ARRAY['data_source','capability','sync_policy','sync_job','sync_checkpoint','object','object_history','credential_reference']),
    ('asset', ARRAY['asset','alias','version','content_hash','duplicate_group','merge_decision','tag','tag_assignment']),
    ('media', ARRAY['rendition','track','profile','quality_result']),
    ('storage', ARRAY['backend','replica','cache_entry','retention_policy','retention_hold','migration','watermark_event']),
    ('ai', ARRAY['provider','model','prompt','pipeline','derived_artifact','quality_evaluation']),
    ('search', ARRAY['index_record','embedding_record','rebuild_job']),
    ('task', ARRAY['task','execution','worker','worker_capability','lease']),
    ('policy', ARRAY['definition','version','test_case','deployment']),
    ('config', ARRAY['definition','version','approval']),
    ('audit', ARRAY['event','security_event']),
    ('outbox', ARRAY['event','consumer_offset'])
) AS expectation(schema_name, relations);

CREATE TEMP TABLE key_coverage AS
WITH expected(schema_name, relation_name, required_columns) AS (VALUES
    ('source', 'object', ARRAY['data_source_id','provider_object_id']),
    ('asset', 'version', ARRAY['asset_id','version_number']),
    ('storage', 'replica', ARRAY['rendition_id','backend_id','object_key']),
    ('task', 'task', ARRAY['idempotency_scope','idempotency_key'])
), actual AS (
    SELECT n.nspname::text AS schema_name, c.relname::text AS relation_name,
        array_agg(a.attname::text ORDER BY k.ordinality) AS key_columns
    FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid JOIN pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ordinality)
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
    WHERE i.indisunique AND i.indisvalid AND i.indpred IS NULL AND i.indexprs IS NULL AND k.ordinality <= i.indnkeyatts
    GROUP BY n.nspname, c.relname, i.indexrelid
)
SELECT e.schema_name, e.relation_name, e.required_columns,
    ARRAY(SELECT array_to_string(a.key_columns, ',') FROM actual a
        WHERE a.schema_name = e.schema_name AND a.relation_name = e.relation_name AND a.key_columns <@ e.required_columns
        ORDER BY a.key_columns) AS enforcing_keys
FROM expected e;

DO $$
BEGIN
    IF (SELECT count(*) FROM expected_relation) <> 61 OR EXISTS (
        SELECT 1 FROM expected_relation e
        LEFT JOIN pg_namespace n ON n.nspname = e.schema_name
        LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = e.relation_name
        WHERE c.oid IS NULL OR c.relkind <> CASE WHEN (e.schema_name, e.relation_name) IN (('asset','alias'), ('policy','deployment'))
                                               THEN 'v'::"char" ELSE 'r'::"char" END
    ) THEN RAISE EXCEPTION 'A V1 logical entity is missing or has the wrong storage kind'; END IF;
    IF (SELECT count(*) FROM key_coverage WHERE cardinality(enforcing_keys) > 0) <> 4
    THEN RAISE EXCEPTION 'A V1 uniqueness invariant is missing'; END IF;
END;
$$;

SELECT schema_name, count(*) FROM expected_relation GROUP BY schema_name ORDER BY schema_name;
SELECT schema_name, relation_name, required_columns, enforcing_keys FROM key_coverage ORDER BY schema_name, relation_name;

ROLLBACK;

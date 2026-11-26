ALTER TABLE source.data_source
    ADD COLUMN endpoint varchar(2048),
    ADD COLUMN root_path varchar(2048),
    ADD CONSTRAINT data_source_location_pair CHECK (
        (endpoint IS NULL AND root_path IS NULL)
        OR (endpoint IS NOT NULL AND root_path IS NOT NULL AND length(root_path) > 0)
    ),
    ADD CONSTRAINT data_source_location_format CHECK (
        endpoint IS NULL OR CASE kind
            WHEN 'LOCAL' THEN endpoint ~ '^mount:[a-z][a-z0-9_-]{0,63}$'
                AND root_path !~ '(^|/)([.]{1,2})?(/|$)'
                AND root_path !~ $re$[%:\x01-\x1f\x7f]$re$
                AND strpos(root_path, chr(92)) = 0
            ELSE endpoint ~ (CASE kind
                    WHEN 'SMB' THEN '^smb://'
                    WHEN 'NFS' THEN '^nfs://'
                    ELSE '^https?://'
                END || '[^/?#@%]+(/[^?#]*)?$')
                AND endpoint !~ '[[:space:][:cntrl:]]'
                AND strpos(endpoint, chr(92)) = 0
        END
    );

CREATE FUNCTION source.require_data_source_location() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.endpoint IS NULL THEN
        RAISE check_violation USING CONSTRAINT = 'data_source_location_required',
            MESSAGE = 'A configured source requires a connection endpoint and scan root';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.endpoint IS NOT NULL
        AND ROW(NEW.kind, NEW.endpoint, NEW.root_path)
            IS DISTINCT FROM ROW(OLD.kind, OLD.endpoint, OLD.root_path)
    THEN
        RAISE check_violation USING CONSTRAINT = 'data_source_location_immutable',
            MESSAGE = 'A configured source location cannot change its identity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER data_source_location_required
BEFORE INSERT OR UPDATE OF kind, endpoint, root_path ON source.data_source
FOR EACH ROW EXECUTE FUNCTION source.require_data_source_location();

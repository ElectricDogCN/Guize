BEGIN;

\ir task_resource_fixture.sql

DO $$
DECLARE
    lease_deadline timestamptz;
    reservation_deadline timestamptz := clock_timestamp() + interval '15 minutes';
BEGIN
    SELECT expires_at INTO STRICT lease_deadline FROM task.lease WHERE attempt_id = 'att_first';
    IF task.reserve_resource('reserve_first', 'att_first', 'res_codec', 1, reservation_deadline) <> 'RESERVED' THEN
        RAISE EXCEPTION 'First codec reservation failed';
    END IF;
    IF task.reserve_resource('reserve_first', 'att_first', 'res_codec', 1, reservation_deadline) <> 'REPLAYED'
        OR task.reserve_resource('reserve_second', 'att_second', 'res_codec', 1, reservation_deadline) <> 'REJECTED'
        OR task.reserve_resource('reserve_foreign', 'att_first', 'res_foreign', 1, reservation_deadline) <> 'REJECTED'
    THEN
        RAISE EXCEPTION 'Codec and node ownership must prevent double reservation';
    END IF;
    IF task.settle_resource('reserve_first', 1, 'TASK_COMPLETED') <> 'SETTLED' THEN
        RAISE EXCEPTION 'Codec settlement failed';
    END IF;
    IF task.settle_resource('reserve_first', 1, 'TASK_COMPLETED') <> 'REPLAYED'
        OR (SELECT held_quantity <> 0 OR spent_quantity <> 0 FROM task.resource_pool WHERE id = 'res_codec')
    THEN
        RAISE EXCEPTION 'Codec settlement must release capacity exactly once';
    END IF;
    IF task.reserve_resource('reserve_second', 'att_second', 'res_codec', 1, reservation_deadline) <> 'RESERVED' THEN
        RAISE EXCEPTION 'Released codec slot must be available to another task';
    END IF;

    IF task.reserve_resource('reserve_budget1', 'att_first', 'res_budget', 8, reservation_deadline) <> 'RESERVED' THEN
        RAISE EXCEPTION 'First budget reservation failed';
    END IF;
    IF task.reserve_resource('reserve_budget2', 'att_second', 'res_budget', 3, reservation_deadline) <> 'REJECTED'
        OR task.settle_resource('reserve_budget1', 9, 'TASK_COMPLETED') <> 'REJECTED'
    THEN
        RAISE EXCEPTION 'Reserved or charged amounts must not exceed budget';
    END IF;
    IF task.settle_resource('reserve_budget1', 6, 'TASK_COMPLETED') <> 'SETTLED' THEN
        RAISE EXCEPTION 'Budget settlement failed';
    END IF;
    IF task.settle_resource('reserve_budget1', 6, 'TASK_COMPLETED') <> 'REPLAYED'
        OR task.settle_resource('reserve_budget1', 5, 'TASK_COMPLETED') <> 'REJECTED'
        OR task.reserve_resource('reserve_budget2', 'att_second', 'res_budget', 5, reservation_deadline) <> 'REJECTED'
    THEN
        RAISE EXCEPTION 'Spent budget must remain charged after release and on replay';
    END IF;
    IF task.reserve_resource('reserve_budget2', 'att_second', 'res_budget', 4, reservation_deadline) <> 'RESERVED'
        OR task.reserve_resource('reserve_outlives', 'att_first', 'res_budget', 1, lease_deadline + interval '1 minute') <> 'REJECTED'
    THEN
        RAISE EXCEPTION 'Budget remainder or reservation expiry did not match policy';
    END IF;
    IF (SELECT held_quantity <> 4 OR spent_quantity <> 6 FROM task.resource_pool WHERE id = 'res_budget')
        OR (SELECT count(*) FROM task.resource_reservation) <> 4
    THEN
        RAISE EXCEPTION 'Accounting must explain the remaining capacity';
    END IF;
END;
$$;

ROLLBACK;

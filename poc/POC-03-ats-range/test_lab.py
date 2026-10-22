"""Offline boundaries only; this does not attest to a real ATS experiment."""
import unittest
from grants import Grant
from lab import interval, unique_json, context


class RangeAndGrantTests(unittest.TestCase):
    def setUp(self):
        self.grant = Grant('grant-a', 'alice', '2026-10-22T00:00:00Z',
                           '2026-10-22T01:00:00Z')

    def test_revocation_denies_same_unexpired_grant(self):
        at = '2026-10-22T00:05:00Z'
        self.assertEqual(self.grant.decision('alice', at), 'allowed')
        revoked = self.grant.revoke(at)
        self.assertEqual(revoked.decision('alice', at), 'revoked')
        self.assertEqual(revoked.decision('alice', '2026-10-22T00:59:59Z'), 'revoked')
        self.assertEqual(revoked.grant_id, self.grant.grant_id)
        self.assertEqual(revoked.valid_until, self.grant.valid_until)

    def test_time_boundaries_and_other_principal_fail_closed(self):
        cases = [('alice', '2026-10-21T23:59:59Z', 'not_yet_valid'),
                 ('alice', '2026-10-22T00:00:00Z', 'allowed'),
                 ('alice', '2026-10-22T01:00:00Z', 'expired'),
                 ('bob', '2026-10-22T00:05:00Z', 'principal_mismatch')]
        for user, at, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.grant.decision(user, at), expected)

    def test_revoke_is_idempotent_without_moving_effective_time(self):
        first = self.grant.revoke('2026-10-22T00:05:00Z')
        self.assertIs(first.revoke('2026-10-22T00:10:00Z'), first)

    def test_invalid_grant_intervals_are_rejected(self):
        for start, end in [('2026-10-22T00:00:00', '2026-10-22T01:00:00Z'),
                           ('2026-10-22T01:00:00Z', '2026-10-22T01:00:00Z'),
                           ('2026-10-22T02:00:00Z', '2026-10-22T01:00:00Z')]:
            with self.assertRaises(ValueError):
                Grant('g', 'a', start, end)

    def test_two_gib_range_offsets_and_unsatisfiable_boundary(self):
        size = 2147483648
        self.assertEqual(interval('bytes=2147483640-2147483647', size),
                         (206, 2147483640, 2147483647))
        self.assertEqual(interval('bytes=-8', size),
                         (206, 2147483640, 2147483647))
        self.assertEqual(interval('bytes=2147483648-', size), (416, 0, -1))

    def test_stale_if_range_and_slice_crossing(self):
        self.assertEqual(interval('bytes=0-7', 67108864, '"old"', '"new"'),
                         (200, 0, 67108863))
        self.assertEqual(interval('bytes=1048560-1048591', 67108864),
                         (206, 1048560, 1048591))

    def test_multi_range_is_explicitly_rejected(self):
        for value in ['bytes=0-1,4-5', 'bytes=', 'items=0-7', 'bytes=a-b']:
            with self.assertRaises(ValueError):
                interval(value, 16)

    def test_duplicate_controls_and_context_collision_are_rejected(self):
        with self.assertRaises(ValueError):
            unique_json('{"action":"witness","action":"clear-cache"}')
        self.assertNotEqual(context('acl', 'alice'), context('acl', 'bob'))
        self.assertNotEqual(context('acl', 'alice'), context('acl2', 'alice'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RangeAndGrantTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 8 or result.skipped:
        raise SystemExit('Expected eight actual offline tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

from datetime import datetime, timezone
import unittest

from run_local_replay import playback_grants


class PlaybackGrantTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 26, 21, 0, tzinfo=timezone.utc)
        self.schedule = {
            "grantValidFrom": "2026-11-26T20:50:00Z",
            "grantValidUntil": "2026-11-26T21:15:00Z",
            "expiredAt": "2026-11-26T20:40:00Z",
        }

    def test_fixed_schedule_controls_the_live_and_expired_grants(self):
        active, expired = playback_grants(self.schedule, self.now)
        self.assertEqual(active.valid_from, "2026-11-26T20:50:00+00:00")
        self.assertEqual(active.valid_until, "2026-11-26T21:15:00+00:00")
        self.assertEqual(expired.valid_until, "2026-11-26T20:40:00+00:00")
        self.assertEqual(active.decision("sample-owner", self.now.isoformat()), "allowed")
        self.assertEqual(expired.decision("sample-owner", self.now.isoformat()), "expired")

    def test_schedule_must_be_usable_at_start(self):
        for changes in (
            {"grantValidFrom": "2026-11-26T21:01:00Z"},
            {"grantValidUntil": self.now.isoformat()},
            {"expiredAt": "2026-11-26T21:01:00Z"},
            {"expiredAt": "2026-11-26T20:40:00"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                playback_grants(self.schedule | changes, self.now)

    def test_unpinned_preflight_still_uses_a_live_and_expired_grant(self):
        active, expired = playback_grants(None, self.now)
        self.assertEqual(active.decision("sample-owner", self.now.isoformat()), "allowed")
        self.assertEqual(expired.decision("sample-owner", self.now.isoformat()), "expired")

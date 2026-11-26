"""Regression checks for the V1 UI permissions and presentation contract."""

from copy import deepcopy
import unittest

from check_contract import MANIFEST, authority_operations, read_yaml, validate_manifest


class UIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authority, cls.digest = authority_operations()
        cls.canonical_manifest = read_yaml(MANIFEST)

    def setUp(self):
        self.manifest = deepcopy(self.canonical_manifest)

    def test_rejects_unmapped_operation(self):
        self.manifest["pages"][0]["actions"].remove("verifyPasskey")
        with self.assertRaisesRegex(ValueError, r"Missing .*verifyPasskey"):
            validate_manifest(self.manifest, self.authority, self.digest)

    def test_rejects_duplicate_operation(self):
        self.manifest["pages"][0]["actions"].append("loginPassword")
        with self.assertRaisesRegex(ValueError, r"duplicate .*loginPassword"):
            validate_manifest(self.manifest, self.authority, self.digest)

    def test_rejects_authenticated_operation_on_public_page(self):
        self.manifest["pages"][0]["actions"][0] = "listAssets"
        with self.assertRaisesRegex(ValueError, r"listAssets .*incompatible"):
            validate_manifest(self.manifest, self.authority, self.digest)

    def test_rejects_changed_authority_digest(self):
        self.manifest["authoritySha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "acceptance links changed"):
            validate_manifest(self.manifest, self.authority, self.digest)

    def test_playback_separates_ready_from_pending(self):
        report = validate_manifest(self.manifest, self.authority, self.digest)
        playback = self.action(report, "playback", "createPlaybackPlan")
        self.assertEqual(playback["onSuccess"], {"201": "ready", "202": "pending"})

    def test_passkey_creation_enters_challenge_state(self):
        report = validate_manifest(self.manifest, self.authority, self.digest)
        challenge = self.action(report, "sign-in", "createPasskeyChallenge")
        self.assertEqual(challenge["onSuccess"], {"201": "challenge"})

    def test_task_events_enter_streaming_state(self):
        report = validate_manifest(self.manifest, self.authority, self.digest)
        events = self.action(report, "tasks", "streamTaskEvents")
        self.assertEqual(events["onSuccess"], {"200": "streaming"})

    @staticmethod
    def action(report, page_id, operation):
        page = next(page for page in report["pages"] if page["id"] == page_id)
        return next(action for action in page["actions"] if action["operationId"] == operation)


if __name__ == "__main__":
    unittest.main()

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_plugin_contract import assess, validate_lock
from check_policy_contract import evaluate, validate_policy
from check_worker_contract import decide
from validation import read_json
from jsonschema import Draft202012Validator

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class PolicyContractTests(unittest.TestCase):
    def setUp(self):
        self.policy = read_json(FIXTURES / "policy-v1.json")
        self.context = read_json(FIXTURES / "policy-context-v1.json")

    def test_approved_budgeted_playback_has_deterministic_trace(self):
        result = evaluate(self.policy, self.context)
        self.assertEqual(result, evaluate(self.policy, self.context))
        self.assertEqual((result["decision"], result["priority"]), ("RECOMMEND", 0))
        self.assertEqual([row["id"] for row in result["nodes"]], ["eligible", "needsWork", "eager"])

    def test_declined_branch_and_missing_fact_are_distinct(self):
        self.context["facts"]["renditionMissing"] = False
        self.assertEqual(evaluate(self.policy, self.context)["reason"], "DECLINE")
        self.context["facts"].clear()
        self.assertEqual(evaluate(self.policy, self.context)["reason"], "FACT_UNAVAILABLE")

    def test_exact_version_and_live_authorization_are_required(self):
        denied = self.context | {"authorized": False}
        self.assertEqual(evaluate(self.policy, denied)["reason"], "AUTHORIZATION_REQUIRED")
        mismatched = self.context | {"policyVersionId": "polv_02"}
        self.assertEqual(evaluate(self.policy, mismatched)["reason"], "POLICY_VERSION_MISMATCH")
        self.policy["nodes"]["eager"]["priority"] = 3
        self.assertEqual(evaluate(self.policy, self.context)["reason"], "POLICY_CONTENT_MISMATCH")

    def test_high_risk_approval_scope_and_expiry(self):
        self.context["approval"]["action"] = "DELETE"
        self.assertEqual(evaluate(self.policy, self.context)["decision"], "REQUIRE_APPROVAL")
        self.context["approval"]["action"] = "BATCH_TRANSCODE"
        self.context["approval"]["expiresAt"] = self.context["observedAt"]
        self.assertEqual(evaluate(self.policy, self.context)["decision"], "REQUIRE_APPROVAL")

    def test_resource_set_and_each_limit_are_required(self):
        self.context["budgets"]["codecSlots"]["available"] = 0
        self.assertEqual(evaluate(self.policy, self.context)["reason"], "BUDGET_EXCEEDED")
        del self.context["budgets"]["codecSlots"]
        self.assertEqual(evaluate(self.policy, self.context)["reason"], "BUDGET_SCOPE_MISMATCH")

    def test_raw_expression_cannot_supply_unregistered_nodes(self):
        self.policy["chain"]["el"] = "THEN(eligible,custom);"
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_policy(self.policy)
        self.policy["chain"]["expression"] = "custom"
        with self.assertRaisesRegex(ValueError, "registered decision"):
            validate_policy(self.policy)


class PluginContractTests(unittest.TestCase):
    def setUp(self):
        fixture = read_json(FIXTURES / "release-conformance-v1.json")
        self.lock, self.inventory = fixture["lock"], fixture["inventory"]
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        for name, text in fixture["assets"].items():
            (self.directory / name).write_bytes(text.encode("utf-8"))

    def test_core_starts_without_plugins_and_nodes(self):
        lock = self.lock | {"plugins": [], "nodeReleases": []}
        self.assertEqual(assess(lock, {"plugins": {}, "nodes": {}}, self.directory),
                         {"coreMayStart": True, "plugins": {}, "nodes": {}})

    def test_matching_package_and_node_release_are_ready(self):
        result = assess(self.lock, self.inventory, self.directory)
        self.assertTrue(result["coreMayStart"])
        self.assertEqual(result["plugins"]["offline-ocr"], {"state": "READY", "capabilities": ["OCR"]})
        self.assertEqual(result["nodes"], {"android": "READY", "windows": "READY", "linux": "READY"})

    def test_missing_failed_and_incompatible_plugins_do_not_block_core(self):
        self.inventory["plugins"]["offline-ocr"]["health"] = "FAILED"
        del self.inventory["nodes"]["android"]
        self.lock["nodeReleases"][1]["supportedProtocols"] = ["worker-v2"]
        self.lock["plugins"][0]["platformMin"] = "1.2.0"
        result = assess(self.lock, self.inventory, self.directory)
        self.assertTrue(result["coreMayStart"])
        self.assertEqual(result["plugins"]["offline-ocr"]["state"], "UNAVAILABLE")
        self.assertEqual(result["plugins"]["media-analysis"]["state"], "INCOMPATIBLE_PLATFORM")
        self.assertEqual(result["nodes"], {"android": "MISSING", "windows": "INCOMPATIBLE_PROTOCOL", "linux": "READY"})

    def test_undocumented_capability_and_unverified_release_stay_disabled(self):
        self.inventory["plugins"]["offline-ocr"]["observedCapabilities"].append("TRANSCODE")
        self.inventory["nodes"]["android"]["signatureVerified"] = False
        checked = assess(self.lock, self.inventory, self.directory)
        self.assertEqual(checked["plugins"]["offline-ocr"], {"state": "CAPABILITY_MISMATCH", "capabilities": []})
        self.assertEqual(checked["nodes"]["android"], "UNVERIFIED_RELEASE")
        self.assertEqual(checked["plugins"]["media-analysis"]["state"], "READY")

    def test_wrong_ocr_model_isolated_from_other_capabilities(self):
        (self.directory / "offline-ocr-model.txt").write_text("changed", encoding="utf-8")
        checked = assess(self.lock, self.inventory, self.directory)
        self.assertEqual(checked["plugins"]["offline-ocr"]["state"], "PACKAGE_COMPONENT_MISMATCH")
        self.assertEqual(checked["plugins"]["media-analysis"]["state"], "READY")

    def test_offline_ocr_cannot_declare_external_network(self):
        path = self.directory / "offline-ocr-manifest.json"
        manifest = read_json(path)
        manifest["spec"]["permissions"]["network"] = ["PUBLIC_INTERNET"]
        content = json.dumps(manifest).encode("utf-8")
        path.write_bytes(content)
        self.lock["plugins"][1]["manifestSha256"] = sha256(content).hexdigest()
        checked = assess(self.lock, self.inventory, self.directory)
        self.assertEqual(checked["plugins"]["offline-ocr"]["state"], "PACKAGE_NETWORK_MISMATCH")

    def test_worker_sdk_bytes_are_bound_by_the_lock(self):
        validate_lock(self.lock)
        self.lock["workerProtocol"]["sdkSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "actual Worker schema, SDK and vectors"):
            validate_lock(self.lock)

    def test_policy_priority_and_admitted_package_bind_same_attempt(self):
        plugin = next(entry for entry in self.lock["plugins"] if entry["pluginId"] == "av1-worker")
        ready = assess(self.lock, self.inventory, self.directory)["plugins"][plugin["pluginId"]]
        self.assertIn("TRANSCODE", ready["capabilities"])
        package = read_json(self.directory / "av1-worker-package.json")
        policy = evaluate(read_json(FIXTURES / "policy-v1.json"), read_json(FIXTURES / "policy-context-v1.json"))
        self.assertEqual((policy["action"], package["kind"]), ("BATCH_TRANSCODE", "AV1_ENCODE"))
        worker = read_json(FIXTURES / "worker-conformance-v1.json")
        binding = worker["offer"]["binding"] | {
            "capabilityId": package["capabilityId"], "capabilityVersion": package["version"],
            "executionGroupId": package["executionGroupId"], "packageSha256": plugin["packageSha256"],
        }
        policy_binding = {key: policy[key] for key in ("policyId", "policyVersionId", "policySha256", "action")} | {
            "decisionTraceId": "trace_joint"
        }
        offer = worker["offer"] | {"binding": binding, "priority": policy["priority"], "policyBinding": policy_binding}
        msg = worker["message"] | {"binding": binding, "operation": "CLAIM", "payload": {}}
        trusted = worker["trusted"] | {"state": "OFFERED"}
        trusted["release"] = {name: binding[name] for name in trusted["release"]}
        trusted["admittedPolicy"] = {"binding": policy_binding, "priority": policy["priority"]}
        trusted["observation"]["executionGroupId"] = binding["executionGroupId"]
        self.assertEqual(decide(offer, msg, trusted), "CLAIM_ACCEPTABLE")
        msg["binding"] = binding | {"packageSha256": "0" * 64}
        self.assertEqual(decide(offer, msg, trusted), "CAPABILITY_MISMATCH")

    def test_worker_binding_can_project_to_frozen_task_event_identity(self):
        offer = read_json(FIXTURES / "worker-conformance-v1.json")["offer"]
        event_file = FIXTURES.parents[3] / "contracts" / "events" / "task" / "task.attempt.result.accepted-v1.schema.json"
        payload = read_json(event_file)["allOf"][1]["properties"]["payload"]
        properties = payload["properties"]
        binding = {key: value for key, value in offer["binding"].items() if key in properties}
        self.assertEqual(len(binding), 13)
        for key, value in binding.items():
            Draft202012Validator(properties[key]).validate(value)


if __name__ == "__main__":
    unittest.main()

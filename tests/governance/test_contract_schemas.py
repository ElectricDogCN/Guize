import os
import unittest

import jsonschema
import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCHEMA_PATH = os.path.join(REPO_ROOT, "contracts", "schemas", "plugin-manifest.schema.yaml")


class TestPluginManifestSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
            cls.schema = yaml.safe_load(handle)

    def _manifest(self):
        return {
            "apiVersion": "guize.plugin/v1",
            "kind": "SourceConnector",
            "metadata": {"id": "source-webdav", "version": "1.0.0"},
            "spec": {
                "runtime": {"mode": "EXTERNAL_SERVICE", "healthEndpoint": "/health"},
                "capabilities": ["LIST", "STAT", "RANGE_READ", "FULL_READ"],
                "permissions": {
                    "network": ["PUBLIC_INTERNET"],
                    "secrets": ["source/webdav/credential"],
                },
            },
        }

    def test_known_manifest_passes(self):
        jsonschema.Draft202012Validator(self.schema).validate(self._manifest())

    def test_unknown_capability_fails(self):
        manifest = self._manifest()
        manifest["spec"]["capabilities"].append("ARBITRARY_CODE_EXECUTION")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(manifest)

    def test_unknown_permission_key_fails(self):
        manifest = self._manifest()
        manifest["spec"]["permissions"]["rootShell"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(manifest)

    def test_unknown_runtime_key_fails(self):
        manifest = self._manifest()
        manifest["spec"]["runtime"]["privileged"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(self.schema).validate(manifest)


if __name__ == "__main__":
    unittest.main()

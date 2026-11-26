"""Check a fixed plugin release lock and evaluate optional plugin availability offline."""

import argparse
from hashlib import file_digest, sha256
import json
from pathlib import Path
import re

from build_worker_sdk import SDK_VERSION, build_sdk
from check_worker_contract import PROTOCOL, VERSION
from validation import read_json, validate_shape

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "contracts" / "connectors" / "v1"
VECTORS = Path(__file__).resolve().parent / "fixtures" / "worker-conformance-v1.json"
MANIFEST = ROOT / "contracts" / "schemas" / "plugin-manifest.schema.yaml"
PACKAGE_CAPABILITY = {"AV1_ENCODE": "TRANSCODE", "MEDIA_ANALYSIS": "MEDIA_PROBE", "OFFLINE_OCR": "OCR"}


def protocol_identity():
    return {
        "version": VERSION,
        "sdkVersion": SDK_VERSION,
        "schemaSha256": sha256(PROTOCOL.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "sdkSha256": sha256(build_sdk()).hexdigest(),
        "conformanceSha256": sha256(VECTORS.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    }


def version(value):
    return tuple(map(int, value.split(".")))


def validate_lock(lock):
    validate_shape(CONTRACT / "release-lock.schema.yaml", lock)
    if lock["workerProtocol"] != protocol_identity():
        raise ValueError("The lock does not match the actual Worker schema, SDK and vectors")
    targets = [node["target"] for node in lock["nodeReleases"]]
    if len(targets) != len(set(targets)):
        raise ValueError("Multiple releases for the same node target")
    plugins = [plugin["pluginId"] for plugin in lock["plugins"]]
    if len(plugins) != len(set(plugins)):
        raise ValueError("Multiple releases for the same plugin identity")
    if any(version(plugin["platformMin"]) >= version(plugin["platformMaxExclusive"]) for plugin in lock["plugins"]):
        raise ValueError("Invalid plugin platform compatibility range")


def asset_file(directory, name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
        raise ValueError("Expected an asset filename inside the fixture directory")
    path = (directory / name).resolve(strict=True)
    if path.parent != directory:
        raise ValueError("The asset is outside the observed fixture directory")
    return path


def matches_digest(path, expected):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest() == expected


def inspect_plugin(candidate, observed, directory, platform_version):
    if observed is None:
        return {"state": "MISSING", "capabilities": []}
    if not isinstance(observed, dict):
        return {"state": "INVALID_PLUGIN", "capabilities": []}
    if not version(candidate["platformMin"]) <= platform_version < version(candidate["platformMaxExclusive"]):
        return {"state": "INCOMPATIBLE_PLATFORM", "capabilities": []}
    if observed.get("signatureVerified") is not True or observed.get("release") != candidate["artifact"]:
        return {"state": "UNVERIFIED_RELEASE", "capabilities": []}
    try:
        path = asset_file(directory, observed["manifestFile"])
        if not matches_digest(path, candidate["manifestSha256"]):
            return {"state": "MANIFEST_MISMATCH", "capabilities": []}
        manifest = read_json(path)
        validate_shape(MANIFEST, manifest)
        if (manifest["apiVersion"], manifest["metadata"]["id"], manifest["metadata"]["version"]) != (
            candidate["manifestApiVersion"], candidate["pluginId"], candidate["version"]
        ):
            return {"state": "MANIFEST_MISMATCH", "capabilities": []}
        if not matches_digest(asset_file(directory, observed["artifactFile"]), candidate["artifact"]["artifactSha256"]):
            return {"state": "ARTIFACT_MISMATCH", "capabilities": []}
        declared = set(manifest["spec"]["capabilities"])
        if "packageSha256" in candidate:
            package_file = asset_file(directory, observed["packageFile"])
            if not matches_digest(package_file, candidate["packageSha256"]):
                return {"state": "PACKAGE_MISMATCH", "capabilities": []}
            package = read_json(package_file)
            validate_shape(CONTRACT / "capability-package.schema.yaml", package)
            if PACKAGE_CAPABILITY[package["kind"]] not in declared:
                return {"state": "PACKAGE_CAPABILITY_MISMATCH", "capabilities": []}
            network = manifest["spec"].get("permissions", {}).get("network", [])
            if package["network"] == "OFFLINE" and set(network) - {"LOOPBACK"}:
                return {"state": "PACKAGE_NETWORK_MISMATCH", "capabilities": []}
            parts = {"runtime": package["runtimeSha256"], "config": package["configSha256"]}
            if "model" in package:
                parts["model"] = package["model"]["sha256"]
            files = observed["packageComponents"]
            if not isinstance(files, dict) or files.keys() != parts.keys() or any(
                not matches_digest(asset_file(directory, files[key]), digest) for key, digest in parts.items()
            ):
                return {"state": "PACKAGE_COMPONENT_MISMATCH", "capabilities": []}
        if observed.get("health") != "READY":
            return {"state": "UNAVAILABLE", "capabilities": []}
        capabilities = observed["observedCapabilities"]
        if not isinstance(capabilities, list) or any(not isinstance(item, str) or item not in declared for item in capabilities):
            return {"state": "CAPABILITY_MISMATCH", "capabilities": []}
        return {"state": "READY", "capabilities": sorted(set(capabilities))}
    except FileNotFoundError:
        return {"state": "MISSING", "capabilities": []}
    except (OSError, ValueError, KeyError, TypeError):
        return {"state": "INVALID_PLUGIN", "capabilities": []}


def inspect_node(candidate, observed, directory):
    if VERSION not in candidate["supportedProtocols"]:
        return "INCOMPATIBLE_PROTOCOL"
    if observed is None:
        return "MISSING"
    if not isinstance(observed, dict):
        return "INVALID_NODE"
    if observed.get("signatureVerified") is not True or observed.get("release") != candidate["artifact"]:
        return "UNVERIFIED_RELEASE"
    if observed.get("supportedProtocols") != candidate["supportedProtocols"]:
        return "INCOMPATIBLE_PROTOCOL"
    try:
        content = asset_file(directory, observed["artifactFile"])
        if not matches_digest(content, candidate["artifact"]["artifactSha256"]):
            return "ARTIFACT_MISMATCH"
    except FileNotFoundError:
        return "MISSING"
    except (OSError, ValueError, KeyError):
        return "INVALID_NODE"
    return "READY" if observed.get("health") == "READY" else "UNAVAILABLE"


def assess(lock, inventory, directory):
    validate_lock(lock)
    directory = directory.resolve(strict=True)
    platform_version = version(lock["platform"]["version"])
    plugin_inventory = inventory["plugins"]
    node_inventory = inventory["nodes"]
    if not isinstance(plugin_inventory, dict) or not isinstance(node_inventory, dict):
        raise ValueError("Expected separate plugin and node inventories")
    plugins = {entry["pluginId"]: inspect_plugin(entry, plugin_inventory.get(entry["pluginId"]), directory, platform_version)
               for entry in lock["plugins"]}
    nodes = {entry["target"]: inspect_node(entry, node_inventory.get(entry["target"]), directory)
             for entry in lock["nodeReleases"]}
    return {"coreMayStart": True, "plugins": plugins, "nodes": nodes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    try:
        result = assess(read_json(args.lock), read_json(args.inventory), args.inventory.parent)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()

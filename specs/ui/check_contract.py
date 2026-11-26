"""Validate and expand the V1 UI mapping from its approved authorities."""
from argparse import ArgumentParser
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("ui-contract-v1.yaml")
API_ROOT = ROOT / "contracts/openapi"
API = API_ROOT / "common/openapi.yaml"
COVERAGE = ROOT / "specs/contracts/openapi/coverage.yaml"
ERRORS = API_ROOT / "common/errors.yaml"
ACCEPTANCE = ROOT / "specs/acceptance/requirements/acceptance.yaml"
METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
PAGE_FIELDS = {"id", "route", "title", "audience", "actions"}
AUDIENCES = {"public", "session", "administration"}
PAGE_STATES = ["loading", "ready", "empty", "unavailable"]
ERROR_STATES = {
    400: "invalid-input",
    401: "authentication-required",
    403: "restricted",
    404: "unavailable",
    409: "conflict",
    422: "invalid-input",
    429: "throttled",
    503: "unavailable",
}
CHALLENGES = {
    "createPasskeyChallenge", "createPasskeyRegistrationChallenge",
    "createStepUpPasskeyChallenge",
}


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def unique_rows(rows, key, label):
    values = {row[key]: row for row in rows}
    if len(values) != len(rows):
        raise ValueError(f"Duplicate {label}")
    return values


def authority_operations():
    api = read_yaml(API)
    coverage = unique_rows(read_yaml(COVERAGE)["operations"], "operationId", "coverage operation")
    errors_doc = read_yaml(ERRORS)
    errors = unique_rows(errors_doc["errors"], "code", "error code")
    acceptance = unique_rows(read_yaml(ACCEPTANCE)["acceptances"], "id", "acceptance")
    operations = {}
    fragments = {}
    for url, target in api["paths"].items():
        filename, pointer = target["$ref"].split("#/", 1)
        path = (API.parent / filename).resolve()
        key = pointer.replace("~1", "/").replace("~0", "~")
        if API_ROOT not in path.parents or key != url:
            raise ValueError(f"Invalid OpenAPI authority for {url}")
        if path not in fragments:
            fragments[path] = read_yaml(path)
        for method in METHODS:
            spec = fragments[path][key].get(method)
            if spec:
                add_operation(operations, coverage, errors, acceptance, url, method, spec)
    if set(operations) != set(coverage):
        raise ValueError("The API roots and operation coverage describe different operations")
    authority = {
        "apiVersion": api["info"]["version"],
        "errorCatalogVersion": errors_doc["version"],
        "operations": operations,
    }
    canonical = json.dumps(authority, sort_keys=True, separators=(",", ":")).encode()
    return authority, sha256(canonical).hexdigest()


def add_operation(operations, coverage, errors, acceptance, url, method, spec):
    name = spec["operationId"]
    requirements = spec["x-requirement-ids"]
    expected = {
        "operationId": name, "path": url, "method": method.upper(),
        "moduleId": spec["x-module-id"], "requirementIds": requirements,
    }
    if name in operations or coverage.get(name) != expected:
        raise ValueError(f"Duplicate or inconsistent API operation {name}")
    acceptance_ids = []
    for requirement in requirements:
        matches = [key for key, value in acceptance.items() if requirement in value["requirementIds"]]
        if not matches:
            raise ValueError(f"{name} lacks an acceptance entry for {requirement}")
        acceptance_ids.extend(matches)
    success = {}
    for status in spec["responses"]:
        code = str(status)
        if code.startswith("2"):
            success[code] = success_state(name, code)
    if not success:
        raise ValueError(f"{name} has no successful response contract")
    error_states = {}
    for code in spec["x-error-codes"]:
        canonical = errors[code]
        error_states[code] = {
            "state": ERROR_STATES.get(canonical["httpStatus"], "failed"),
            "httpStatus": canonical["httpStatus"],
            "retryable": canonical["retryable"],
        }
    operations[name] = {
        **expected,
        "authorization": spec["x-authorization"],
        "onSuccess": success,
        "onError": error_states,
        "acceptanceIds": list(dict.fromkeys(acceptance_ids)),
    }


def success_state(name, status):
    if status == "202":
        return "pending"
    if name == "streamTaskEvents":
        return "streaming"
    if name in CHALLENGES:
        return "challenge"
    return "ready"


def validate_manifest(manifest, authority, digest):
    keys = {"schemaVersion", "apiVersion", "errorCatalogVersion", "authoritySha256", "pageStates", "pages", "integrationOnly"}
    if (
        not isinstance(manifest, dict)
        or set(manifest) != keys
        or type(manifest["schemaVersion"]) is not int
        or manifest["schemaVersion"] != 1
    ):
        raise ValueError("Invalid UI contract structure or schema version")
    for version in ("apiVersion", "errorCatalogVersion"):
        if manifest[version] != authority[version]:
            raise ValueError(f"UI contract has a stale {version}")
    if manifest["authoritySha256"] != digest:
        raise ValueError("The API, permissions, errors or acceptance links changed. Review the affected UI actions.")
    if manifest["pageStates"] != PAGE_STATES:
        raise ValueError("The UI must distinguish loading, ready, empty and unavailable states")

    pages = manifest["pages"]
    unique_rows(pages, "id", "page ID")
    unique_rows(pages, "route", "UI route")
    machine = manifest["integrationOnly"]
    if set(machine) != {"registerWorker", "heartbeatWorker"} or any(not reason.strip() for reason in machine.values()):
        raise ValueError("Keep worker registration and heartbeat on the node integration interface")
    mapped = Counter(machine.keys())
    expanded = []
    for page in pages:
        actions = page["actions"]
        if (set(page) != PAGE_FIELDS or not page["title"].strip() or not page["route"].startswith("/")
                or page["audience"] not in AUDIENCES or not actions):
            raise ValueError(f"Invalid page {page.get('id')}")
        entries = []
        for name in actions:
            mapped[name] += 1
            entry = authority["operations"][name]
            public = entry["authorization"]["mode"] == "PUBLIC_RATE_LIMITED"
            if public != (page["audience"] == "public"):
                raise ValueError(f"{name} is on an incompatible public or session page")
            entries.append(entry)
        expanded.append({**page, "actions": entries})
    missing = set(authority["operations"]) - set(mapped)
    duplicate = [name for name, count in mapped.items() if count != 1]
    if missing or duplicate:
        raise ValueError(f"Every API operation must have one destination. Missing {sorted(missing)}, duplicate {sorted(duplicate)}")
    return {"pages": expanded, "integrationOnly": {
        name: {"reason": reason, **authority["operations"][name]} for name, reason in machine.items()
    }}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--json", action="store_true", help="Show the resolved operation and UI mapping")
    args = parser.parse_args()
    try:
        authority, fingerprint = authority_operations()
        report = validate_manifest(read_yaml(args.manifest), authority, fingerprint)
    except (KeyError, TypeError, ValueError, OSError, AttributeError, yaml.YAMLError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"PASS: {len(report['pages'])} UI pages, {len(authority['operations'])} API operations and "
              f"{len(report['integrationOnly'])} node-only operations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

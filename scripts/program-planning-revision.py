#!/usr/bin/env python3
"""Authenticate exact future-plan transactions and pending baseline consumers.

No checker entry points are imported. Callers retain their existing scope,
schema, lifecycle, frozen, completion and history checks. A failed transaction
never supplies a projected Program or a list of task IDs to exclude.
"""
from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from referencing import Registry, Resource

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
PROGRAM_SCHEMA = "specs/coordination/program-plan.schema.yaml"
MANIFEST_SCHEMA = "specs/coordination/planning-revision.schema.yaml"
EXECUTION = {"in_progress", "integration"}
METADATA = {PLAN, ACTIVE, LEDGER}
EDGE_SCOPE = "AGENT-EDGE-104"
EDGE_PLANNER = "GZ-022"
EDGE_V1_EDIT_IDS = frozenset({"GZ-006", "GZ-007", "GZ-008", "GZ-011", "GZ-012", "GZ-013", "GZ-016", "GZ-018"})
FIRST_USE = "evidence/OPS-011/agent-edge-104-first-use.json"
EDGE_DEFINITION = "evidence/GZ-022/agent-edge-104-definition.json"
FIRST_USE_SHA256 = "2815479d0d322abc8afdf94e73518f0b9a0fa23fbcc0a5bd39c9e9daaa6017d9"
V1_TASK_IDS = [
    "GZ-004", "GZ-005", "GZ-006", "GZ-007", "GZ-008", "GZ-009", "GZ-010",
    *[f"POC-{number:03d}" for number in range(1, 11)],
    "GZ-011", "GZ-012", "GZ-013", "GZ-015", "GZ-016", "GZ-017", "GZ-018",
    "GZ-019", "GZ-020", "GZ-021",
]
EDGE_PATHS = {
    "requirements": "specs/requirements/agent-edge-104.md",
    "requirementIndex": "specs/requirements/agent-edge-104.yaml",
    "acceptanceIndex": "specs/acceptance/agent-edge-104.yaml",
}


class PlanningError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanningError(message)


def git(root: str, *args: str, missing: bool = False) -> str | None:
    result = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        if missing:
            return None
        raise PlanningError(f"Cannot read Git {' '.join(args)}")
    return result.stdout.strip()


def snapshot(root: str, ref: str) -> tuple[str, str]:
    source = ref if re.fullmatch(r"[0-9a-f]{40}", ref) else git(root, "rev-parse", f"{ref}^{{commit}}")
    require(bool(source) and bool(re.fullmatch(r"[0-9a-f]{40}", source)), "Snapshot requires an actual immutable commit")
    return str(Path(root).resolve()), source


@lru_cache(maxsize=1024)
def committed_blob(root: str, source: str, path: str) -> bytes | None:
    result = subprocess.run(["git", "-C", root, "show", f"{source}:{path}"], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def blob(root: str, ref: str, path: str) -> bytes | None:
    return committed_blob(*snapshot(root, ref), path)


@lru_cache(maxsize=512)
def committed_document(root: str, source: str, path: str) -> dict[str, Any]:
    raw = committed_blob(root, source, path)
    value = yaml.safe_load(raw.decode("utf-8")) if raw is not None else {}
    require(isinstance(value, dict), f"Invalid document {path} at {source}")
    return value


def document(root: str, ref: str, path: str) -> dict[str, Any]:
    # Cache data by immutable SHA, never alias resolution or admission results.
    return copy.deepcopy(committed_document(*snapshot(root, ref), path))


def records(items: Any, key: str = "taskId") -> dict[str, dict[str, Any]]:
    require(isinstance(items, list), f"Expected list of {key} records")
    result = {}
    for row in items:
        require(isinstance(row, dict) and isinstance(row.get(key), str), f"Invalid {key} record")
        require(row[key] not in result, f"Duplicate {key}: {row[key]}")
        result[row[key]] = row
    return result


def tasks(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ordinary = records(plan.get("tasks", []))
    foundations = records(plan.get("foundationTasks", []))
    require(not (ordinary.keys() & foundations.keys()), "Duplicate ordinary/Foundation task ID")
    return {**ordinary, **foundations}


def task_scope(plan: dict[str, Any], task_id: str) -> str:
    """Classify an existing member; this never grants a new Task or scope."""
    by_id = tasks(plan)
    require(task_id in by_id, f"Unknown Program member {task_id}")
    if task_id in records(plan.get("foundationTasks", [])):
        return "FOUNDATION"
    if "scopeBoundary" not in plan:
        return "V1"
    boundary = plan["scopeBoundary"]
    require(isinstance(boundary, dict) and isinstance(boundary.get("agentEdge104"), dict), "Invalid fixed scope boundary")
    if task_id in boundary.get("v1TaskIds", []):
        return "V1"
    require(task_id in boundary["agentEdge104"].get("taskIds", []), f"Unclassified Program member {task_id}")
    return EDGE_SCOPE


def _dependency_closure(plan: dict[str, Any], task_id: str) -> set[str]:
    by_id, visiting, done = tasks(plan), set(), set()
    def visit(tid: str) -> None:
        require(tid in by_id, f"Unknown dependency {tid}")
        require(tid not in visiting, "Program dependency cycle")
        if tid in done:
            return
        visiting.add(tid)
        for dependency in by_id[tid].get("dependsOn", []):
            visit(dependency)
        visiting.remove(tid)
        done.add(tid)
    visit(task_id)
    return done - {task_id}


def validate_scope_boundary(plan: dict[str, Any]) -> None:
    """Preserve the frozen V1 boundary and the one registered follow-up."""
    ordinary = records(plan.get("tasks", []))
    if "scopeBoundary" not in plan:
        require(all(isinstance(rid, str) and re.fullmatch(r"REQ-V1-\d{4}", rid)
                    for row in ordinary.values() for rid in row.get("requirementIds", [])),
                "EDGE requirements require the fixed registered scope boundary")
        return
    boundary = plan["scopeBoundary"]
    require(isinstance(boundary, dict) and set(boundary) == {"v1TaskIds", "v1FinalTask", "agentEdge104"}, "Unknown fixed scope boundary fields")
    require(boundary["v1TaskIds"] == V1_TASK_IDS and boundary["v1FinalTask"] == "GZ-020", "Original twenty-seven V1 members/final task changed")
    edge = boundary["agentEdge104"]
    expected_keys = {"id", "sourceIssue", "state", "planningTaskId", "taskIds", "requiredFinalTask", *EDGE_PATHS}
    require(isinstance(edge, dict) and set(edge) == expected_keys, "Unknown Agent Edge 104 scope fields")
    require(edge["id"] == EDGE_SCOPE and edge["sourceIssue"] == 104 and edge["planningTaskId"] == EDGE_PLANNER,
            "Fixed Agent Edge 104 identity changed")
    require(all(edge[key] == value for key, value in EDGE_PATHS.items()), "Fixed independent index paths changed")
    members = edge["taskIds"]
    require(isinstance(members, list) and all(isinstance(tid, str) for tid in members) and
            len(members) == len(set(members)) and EDGE_PLANNER in members, "Invalid Agent Edge 104 membership")
    require(not (set(members) & set(V1_TASK_IDS)) and set(ordinary) == set(V1_TASK_IDS) | set(members),
            "Program tasks must belong to exactly their fixed scope")
    require({row.get("taskId") for row in plan.get("pocs", [])} == {f"POC-{n:03d}" for n in range(1, 11)}, "Original ten POC members changed")
    planner = ordinary[EDGE_PLANNER]
    require(planner.get("kind") == "requirements" and planner.get("requirementIds") == ["REQ-V1-0010"], "GZ-022 retains its V1 governance requirement")
    baseline = records(plan.get("planningBaselines", []), "id").get("BASELINE-GZ-022")
    require(baseline == {"id": "BASELINE-GZ-022", "taskId": EDGE_PLANNER, "requiredBy": ["POC-003", "POC-005"]},
            "Fixed GZ-022 planning baseline changed or missing")
    for tid, row in ordinary.items():
        pattern = r"REQ-EDGE-104-\d{4}" if tid in members and tid != EDGE_PLANNER else r"REQ-V1-\d{4}"
        require(all(isinstance(rid, str) and re.fullmatch(pattern, rid) for rid in row.get("requirementIds", [])),
                f"Requirement namespace does not match real scope: {tid}")
    if edge["state"] == "planning":
        require(members == [EDGE_PLANNER] and edge["requiredFinalTask"] is None, "Planning scope cannot contain business execution members or a fake final")
        require(planner.get("status") != "completed", "GZ-022 cannot complete without its full registered definition")
    else:
        require(edge["state"] == "defined", "Scope state cannot claim runtime completion")
        final = edge["requiredFinalTask"]
        require(isinstance(final, str) and final in members and final != EDGE_PLANNER and len(members) > 1, "Defined scope requires a nonempty business final closure")
        require(ordinary[final].get("kind") == "release" and ordinary[final].get("riskLevel") == "critical", "EDGE final task must be critical release acceptance")
        require(set(members) - {final} <= _dependency_closure(plan, final), "EDGE final task omits scope members from its dependency closure")
    if plan.get("status") == "completed":
        require(edge["state"] == "defined" and all(row.get("status") == "completed" for row in ordinary.values()),
                "Program completion requires real completed V1 and EDGE tasks, not planning alone")


def _safe_path(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith("/") and not re.match(r"^[A-Za-z]:", value) and "\\" not in value and not any(part in {"", ".", ".."} for part in value.split("/"))


def validate_edge_indexes(root: str, plan: dict[str, Any], *, ref: str | None = None) -> dict[str, dict[str, Any]]:
    """Join only the fixed independent indexes; legacy indexes remain closed."""
    validate_scope_boundary(plan)
    ordinary, by_id = records(plan.get("tasks", [])), tasks(plan)
    def read(path: str) -> dict[str, Any]:
        value = document(root, ref, path) if ref is not None else yaml.safe_load((Path(root) / path).read_text(encoding="utf-8"))
        require(isinstance(value, dict), f"Invalid independent index {path}")
        return value
    active_exists = blob(root, ref, ACTIVE) is not None if ref is not None else (Path(root) / ACTIVE).exists()
    if active_exists:
        active = read(ACTIVE)
        require(isinstance(active, dict), "Invalid Active registry")
        for tid, entry in records(active.get("tasks", [])).items():
            reqs = entry.get("requirementIds", [])
            business = tid in ordinary and task_scope(plan, tid) == EDGE_SCOPE
            if business:
                require(set(reqs) == set(ordinary[tid].get("requirementIds", [])), f"Registry requirement binding differs from real Program member {tid}")
            else:
                require(all(isinstance(rid, str) and re.fullmatch(r"REQ-V1-\d{4}", rid) for rid in reqs),
                        f"Non-EDGE registry task cannot consume EDGE requirements: {tid}")
    empty = {"requirements": {}, "acceptances": {}}
    edge = plan.get("scopeBoundary", {}).get("agentEdge104")
    if edge is None or edge["state"] == "planning":
        return empty
    req_doc, ac_doc = read(edge["requirementIndex"]), read(edge["acceptanceIndex"])
    for document_, key in ((req_doc, "requirements"), (ac_doc, "acceptances")):
        require(set(document_) == {"schemaVersion", "scopeId", "sourceIssue", key} and
                document_["schemaVersion"] == 1 and document_["scopeId"] == EDGE_SCOPE and document_["sourceIssue"] == 104,
                f"Invalid fixed {key} index root")
    requirements, acceptances = records(req_doc["requirements"], "id"), records(ac_doc["acceptances"], "id")
    require(requirements and acceptances, "Defined EDGE indexes must be nonempty")
    members = set(edge["taskIds"]) - {EDGE_PLANNER}
    ownership_doc = read("specs/designs/module-ownership.yaml")
    module_ids = {row["id"] for row in ownership_doc.get("modules", [])}
    text_raw = blob(root, ref, edge["requirements"]) if ref is not None else (Path(root) / edge["requirements"]).read_bytes()
    require(text_raw is not None, "Fixed EDGE requirements document is absent")
    text = text_raw.decode("utf-8")
    def strings(value: Any, label: str) -> set[str]:
        require(isinstance(value, list) and value and all(isinstance(item, str) and item for item in value) and len(value) == len(set(value)), f"Invalid {label}")
        return set(value)
    for rid, row in requirements.items():
        require(re.fullmatch(r"REQ-EDGE-104-\d{4}", rid) and set(row) == {"id", "title", "requirementPath", "moduleIds", "taskIds", "acceptanceIds"}, f"Invalid EDGE requirement {rid}")
        require(isinstance(row["title"], str) and row["title"].strip(), f"Missing EDGE requirement title {rid}")
        anchor = rid.lower()
        require(row["requirementPath"] == edge["requirements"] + "#" + anchor and
                (re.search(r"(?m)^#{1,6}\s+" + re.escape(rid) + r"\s*$", text) or
                 re.search(r"<a\s+id=[\"']" + re.escape(anchor) + r"[\"']\s*>\s*</a>", text)),
                f"Requirement anchor does not exist: {rid}")
        ids, modules, acs = strings(row["taskIds"], rid + " tasks"), strings(row["moduleIds"], rid + " modules"), strings(row["acceptanceIds"], rid + " acceptances")
        require(ids <= members and modules <= module_ids and acs <= acceptances.keys(), f"Unknown EDGE requirement binding {rid}")
        covered_modules = set().union(*(set(by_id[tid].get("moduleIds", [])) for tid in ids))
        require(modules <= covered_modules and all(modules & set(by_id[tid].get("moduleIds", [])) for tid in ids), f"EDGE requirement modules lack actual delivery coverage {rid}")
    for aid, row in acceptances.items():
        require(re.fullmatch(r"AC-EDGE-104-\d{4}", aid) and set(row) == {"id", "title", "requirementIds", "taskIds", "verification", "evidencePath"}, f"Invalid EDGE acceptance {aid}")
        require(all(isinstance(row[key], str) and row[key].strip() for key in ("title", "verification")), f"Missing EDGE acceptance description {aid}")
        ids, reqs = strings(row["taskIds"], aid + " tasks"), strings(row["requirementIds"], aid + " requirements")
        require(ids <= members and reqs <= requirements.keys(), f"Unknown EDGE acceptance binding {aid}")
        require(_safe_path(row["evidencePath"]) and any(row["evidencePath"].startswith(f"evidence/{tid}/") for tid in ids), f"Unsafe or unbound EDGE acceptance evidence {aid}")
        require(all(aid in requirements[rid]["acceptanceIds"] and ids <= set(requirements[rid]["taskIds"]) for rid in reqs), f"EDGE acceptance/requirement join differs {aid}")
    for rid, row in requirements.items():
        require(all(rid in acceptances[aid]["requirementIds"] for aid in row["acceptanceIds"]), f"EDGE requirement/acceptance join differs {rid}")
        require(set(row["taskIds"]) <= set().union(*(set(acceptances[aid]["taskIds"]) for aid in row["acceptanceIds"])), f"EDGE requirement has no acceptance for a delivery task {rid}")
    for tid in members:
        reqs = {rid for rid, row in requirements.items() if tid in row["taskIds"]}
        acs = {aid for aid, row in acceptances.items() if tid in row["taskIds"]}
        require(reqs and reqs == set(ordinary[tid].get("requirementIds", [])) and acs and acs == set(ordinary[tid].get("acceptanceIds", [])), f"EDGE Task/index exact requirement/acceptance join differs: {tid}")
    final = ordinary[edge["requiredFinalTask"]]
    require(set(final.get("requirementIds", [])) == set(requirements) and set(final.get("acceptanceIds", [])) == set(acceptances),
            "EDGE final task must directly cover every independent requirement and acceptance")
    return {"requirements": requirements, "acceptances": acceptances}


def registered_manifest_path(root: str, ref: str, owner: str) -> str | None:
    """Discover actual typed paths without aliasing them to the legacy file."""
    candidates = [f"evidence/{owner}/planning-revision.json"]
    if owner == "OPS-011":
        candidates.append(FIRST_USE)
    if owner == EDGE_PLANNER:
        candidates.append(EDGE_DEFINITION)
    found = [path for path in candidates if blob(root, ref, path) is not None]
    require(len(found) <= 1, f"Ambiguous registered planning declaration {owner}")
    return found[0] if found else None


def immutable_manifest(root: str, registration: str, head: str, owner: str) -> tuple[str, bytes]:
    """Bind the actual typed file to its original canonical reservation."""
    path = registered_manifest_path(root, registration, owner)
    require(path is not None, "Original registered planning manifest absent")
    raw = blob(root, registration, path)
    require(raw is not None and registered_manifest_path(root, head, owner) == path and blob(root, head, path) == raw,
            "Original registered planning manifest changed in history")
    candidates = [f"evidence/{owner}/planning-revision.json"]
    if owner == "OPS-011":
        candidates.append(FIRST_USE)
    if owner == EDGE_PLANNER:
        candidates.append(EDGE_DEFINITION)
    for node in (git(root, "log", "--format=%H", head, "--", *candidates) or "").splitlines():
        if ancestor(root, registration, node):
            require(registered_manifest_path(root, node, owner) == path and blob(root, node, path) == raw,
                    "Original registered planning manifest changed in intermediate history")
    return path, raw


def validate_edge_v1_edit(target: dict[str, Any]) -> None:
    """Keep the follow-up planner within its eight registered V1 touchpoints."""
    require(target["id"] in EDGE_V1_EDIT_IDS, "Scope definition may amend only its eight registered V1 tasks")
    require(all(target["before"].get(key) == target["after"].get(key) for key in ("requirementIds", "acceptanceIds", "pocIds")),
            "Scope definition rewrote existing V1 obligations")


def validate_frozen_edge_catalogs(root: str, authority: str, head_ref: str, plan: dict[str, Any]) -> None:
    """Bind complete catalogs to GZ022's own original canonical declaration."""
    require(plan == document(root, head_ref, PLAN), "EDGE catalog view must bind its actual Git snapshot")
    introductions, present = [], False
    for node in (git(root, "rev-list", "--first-parent", "--reverse", authority) or "").splitlines():
        current = EDGE_PLANNER in records(document(root, node, ACTIVE).get("tasks", []))
        if current and not present:
            introductions.append(node)
        present = current
    require(len(introductions) == 1, "EDGE catalogs require GZ-022's unique canonical original reservation")
    registration, parent, original = original_registration(root, introductions[0], EDGE_PLANNER)
    path, raw = immutable_manifest(root, registration, head_ref, EDGE_PLANNER)
    require(path == EDGE_DEFINITION, "EDGE catalogs require the original typed GZ-022 definition")
    manifest = json.loads(raw.decode("utf-8"))
    require(manifest.get("issue") == original.get("issue") and manifest.get("reservationParent") == parent,
            "EDGE catalog declaration has wrong original Issue or parent")
    program_schema, manifest_schema = document(root, head_ref, PROGRAM_SCHEMA), document(root, head_ref, MANIFEST_SCHEMA)
    registry = Registry().with_resources([(program_schema["$id"], Resource.from_contents(program_schema)), (manifest_schema["$id"], Resource.from_contents(manifest_schema))])
    jsonschema.Draft202012Validator({"$ref": manifest_schema["$id"] + "#/$defs/agentEdge104Definition"}, registry=registry).validate(manifest)
    for key in ("requirementIndex", "acceptanceIndex"):
        actual = document(root, head_ref, EDGE_PATHS[key])
        # Canonical JSON equality also distinguishes bool/int and typed values.
        require(json.dumps(actual, sort_keys=True, ensure_ascii=False) == json.dumps(manifest[key], sort_keys=True, ensure_ascii=False),
                f"EDGE {key} differs from complete original registered records")
    validate_edge_indexes(root, plan, ref=head_ref)


@lru_cache(maxsize=32)
def spec_index(root: str, source: str) -> tuple:
    result = []
    for path in (git(root, "ls-tree", "-r", "--name-only", source, "specs/tasks") or "").splitlines():
        raw = blob(root, source, path)
        if not raw or not raw.startswith(b"---\n"):
            continue
        front = yaml.safe_load(raw.decode("utf-8").split("---", 2)[1])
        if isinstance(front, dict):
            result.append((path, front))
    return tuple(result)


def spec(root: str, ref: str, task_id: str) -> tuple[str, dict[str, Any]] | None:
    # Cache only immutable committed inputs, never refs or admission results.
    source = ref if re.fullmatch(r"[0-9a-f]{40}", ref) else git(root, "rev-parse", f"{ref}^{{commit}}")
    candidates = [(path, front) for path, front in spec_index(str(Path(root).resolve()), source) if front.get("id") == task_id]
    require(len(candidates) <= 1, f"Duplicate Task Spec identity {task_id}")
    return copy.deepcopy(candidates[0]) if candidates else None


def ancestor(root: str, older: str, newer: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", older)) and subprocess.run(
        ["git", "-C", root, "merge-base", "--is-ancestor", older, newer], capture_output=True
    ).returncode == 0


def changed_paths(root: str, before: str, after: str) -> set[str]:
    result = set()
    for line in (git(root, "diff", "--name-status", "-M", before, after) or "").splitlines():
        parts = line.split("\t")
        result.update(parts[1:3] if parts[0].startswith(("R", "C")) else parts[1:2])
    return result


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, "Lease must use UTC")
    return result


def commit_time(root: str, ref: str) -> datetime:
    return datetime.fromtimestamp(int(git(root, "show", "-s", "--format=%ct", ref) or "0"), timezone.utc)


def lease(entry: dict[str, Any], when: datetime) -> None:
    require(isinstance(entry.get("lease"), dict), "Planner requires a lease")
    acquired = utc(entry["lease"]["acquiredAt"])
    expires = utc(entry["lease"]["expiresAt"])
    require(acquired <= when < expires and 0 < (expires - acquired).total_seconds() <= 168 * 3600, "Planner lease expired, future or over 168h")


def sequence(value: Any) -> list[str]:
    return value if isinstance(value, list) else [s.strip() for s in str(value or "").split(",") if s.strip()]


def ownership(root: str, ref: str, entry: dict[str, Any]) -> None:
    declared = entry.get("moduleIds", [])
    modules = document(root, ref, "specs/designs/module-ownership.yaml").get("modules", [])
    patterns = [p for module in modules if module.get("id") in declared for p in module.get("ownedPaths", [])]
    require(patterns and "MOD-GOV" in declared, "Planner has no declared governance ownership")
    foundation = entry["taskId"] in records(document(root, ref, PLAN).get("foundationTasks", []))
    def overlaps(left: str, right: str) -> bool:
        if fnmatch.fnmatchcase(left, right) or fnmatch.fnmatchcase(right, left):
            return True
        left_prefix = re.split(r"[*?\[]", left, maxsplit=1)[0].rstrip("/")
        right_prefix = re.split(r"[*?\[]", right, maxsplit=1)[0].rstrip("/")
        return not left_prefix or not right_prefix or left_prefix == right_prefix or left_prefix.startswith(right_prefix+"/") or right_prefix.startswith(left_prefix+"/")
    for claim in entry.get("exclusivePaths", []) + entry.get("sharedPaths", []):
        require(isinstance(claim, str) and claim not in {"", "*", "**", "/"} and not claim.startswith("/") and ".." not in claim.split("/") and "\\" not in claim, "Planner has unsafe or repository-wide claim")
        if foundation:
            require(any(fnmatch.fnmatchcase(claim, pattern) for pattern in patterns), f"Foundation planner claim outside governance ownership: {claim}")
        else:
            require(not re.search(r"[*?\[]", claim), f"Ordinary planner requires exact document/specification claims: {claim}")
            require(claim.startswith(("docs/", "adr/", "specs/")) or claim == "poc/README.md", f"Ordinary planner claim outside document/specification surfaces: {claim}")
            # Ordinary tasks may claim a reviewed common document with no
            # module owner. Existing owned surfaces require their actual module.
            for module in modules:
                if any(overlaps(claim, pattern) for pattern in module.get("ownedPaths", [])):
                    require(module["id"] in declared, f"Planner claim overlaps undeclared module {module['id']}: {claim}")


def capacity(registry: dict[str, Any], plan: dict[str, Any]) -> None:
    policy = registry.get("policy", {})
    live = list(records(registry.get("tasks", [])).values())
    require(policy.get("maxActiveTasks") == 3 and policy.get("maxHighRiskTasks") == 1, "Planner capacity policy changed")
    require(len(live) <= 3 and sum(row.get("riskLevel") in {"high", "critical"} for row in live) <= 1, "Planner exceeds active/high-risk capacity")
    require(not any(row.get("riskLevel") == "critical" for row in live) or len(live) == 1, "Critical task must remain standalone")
    require(plan.get("parallelPolicy", {}).get("maxActiveTasks") == 3 and plan.get("parallelPolicy", {}).get("maxHighRiskTasks") == 1, "Program planner capacity mismatch")


def bind_spec(root: str, ref: str, owner: str, entry: dict[str, Any]) -> str:
    found = spec(root, ref, owner)
    require(found is not None, f"Planner {owner} has no Task Spec")
    path, front = found
    require(front.get("schemaVersion") == 2 and front.get("coordinationMode") == "registry", "Planner requires registry Task schemaVersion2")
    for key in ("status", "baseSha", "agentRole", "riskLevel", "coordinator", "implementer", "reviewer", "integrator", "coordinationGroup", "integrationOrder"):
        require(front.get(key) == entry.get(key), f"Planner Task/Registry mismatch: {key}")
    for key in ("dependsOn", "moduleIds", "requirementIds", "producesContracts", "consumesContracts"):
        require(sequence(front.get(key)) == entry.get(key), f"Planner Task/Registry mismatch: {key}")
    require(front.get("issue") == entry.get("issue") and front.get("workBranch") == entry.get("branch"), "Planner Issue/branch mismatch")
    return path


def original_registration(root: str, base: str, owner: str) -> tuple[str, str, dict[str, Any]]:
    """Use the final introduction on audited main first-parent history."""
    introductions = []
    present = False
    for node in (git(root, "rev-list", "--first-parent", "--reverse", base) or "").splitlines():
        row = records(document(root, node, ACTIVE).get("tasks", [])).get(owner)
        if row is not None and not present:
            introductions.append((node, row))
        present = row is not None
    require(len(introductions) == 1 and present, "Planner has no unique live canonical reservation")
    registration, entry = introductions[0]
    canonical_refs = [ref for ref in ("origin/main", "main") if git(root, "rev-parse", "--verify", ref, missing=True)]
    require(any(
        ancestor(root, base, git(root, "rev-parse", ref) or "")
        and registration in (git(root, "rev-list", "--first-parent", ref) or "").splitlines()
        for ref in canonical_refs
    ), "Planner introduction is not on canonical main history")
    parent = git(root, "rev-parse", f"{registration}^1") or ""
    require(entry.get("status") == "reserved" and entry.get("agentRole") == "coordinator" and entry.get("baseSha") == parent, "Original planner registration must be reserved and parent-bound")
    lease(entry, commit_time(root, registration))
    task_path = bind_spec(root, registration, owner, entry)
    paths = changed_paths(root, parent, registration)
    require(all(p in {PLAN, ACTIVE, task_path} or p.startswith(f"evidence/{owner}/") for p in paths), "Original planner registration contains implementation")
    old_program, new_program = document(root, parent, PLAN), document(root, registration, PLAN)
    old_registry, new_registry = document(root, parent, ACTIVE), document(root, registration, ACTIVE)
    ownership(root, registration, entry)
    capacity(new_registry, new_program)
    require(entry.get("implementer") and entry.get("reviewer") and entry["implementer"] != entry["reviewer"], "Original planner roles are not independent")
    previous_tasks = tasks(old_program)
    previous_ledger = records(document(root, parent, LEDGER).get("records", []))
    for dependency in entry.get("dependsOn", []):
        prior = previous_tasks.get(dependency, {})
        code = previous_ledger.get(dependency, {}).get("mergeCommit", prior.get("mergeCommit", ""))
        require(prior.get("status") == "completed" and ancestor(root, code, parent), f"Original planner dependency not actually integrated: {dependency}")
    section = "foundationTasks" if owner in records(new_program.get("foundationTasks", [])) else "tasks"
    old_rows = records(old_program.get(section, []))
    registered = records(new_program.get(section, [])).get(owner)
    require(registered is not None and registered.get("status") == "reserved", "Original Program registration missing")
    restored = copy.deepcopy(new_program)
    restored[section] = [r for r in restored[section] if r["taskId"] != owner]
    if section == "foundationTasks":
        require(owner not in old_rows and entry.get("moduleIds") == ["MOD-GOV"] and entry.get("riskLevel") == "high", "Foundation planner original identity invalid")
    else:
        require(old_rows.get(owner, {}).get("status") == "planned", "Ordinary planner must reserve a planned definition")
        for index, row in enumerate(new_program[section]):
            if row["taskId"] == owner:
                restored[section].insert(index, old_rows[owner])
                break
        permitted = copy.deepcopy(old_rows[owner])
        permitted.update(status="reserved", issue=registered.get("issue"))
        require(permitted == registered, "Ordinary planner reservation rewrote its definition")
    restored_registry = copy.deepcopy(new_registry)
    restored_registry["tasks"] = [r for r in restored_registry["tasks"] if r["taskId"] != owner]
    require(restored == old_program and restored_registry == old_registry, "Planner reservation changed foreign metadata or policy")
    return registration, parent, entry


def registered_scope(root: str, base: str, owner: str, registration: str, original: dict[str, Any]) -> dict[str, Any]:
    """Authorize claims only from earlier canonical metadata registrations."""
    phase_fields = {"status", "agentRole", "baseSha", "lease"}
    scope_fields = {"branch", "exclusivePaths", "sharedPaths"}
    stable = {k: v for k, v in original.items() if k not in phase_fields | scope_fields}
    canonical = (git(root, "rev-list", "--first-parent", "--reverse", base) or "").splitlines()
    require(registration in canonical, "Planner scope has no canonical original reservation")
    authorized = copy.deepcopy(original)
    manifest_path, _ = immutable_manifest(root, registration, base, owner)
    for node in canonical[canonical.index(registration) + 1:]:
        current_registry = document(root, node, ACTIVE)
        entry = records(current_registry.get("tasks", [])).get(owner)
        require(entry is not None, "Planner scope registration disappeared")
        require({k: v for k, v in entry.items() if k not in phase_fields | scope_fields} == stable, "Planner scope history changed stable identity")
        if any(entry.get(k) != authorized.get(k) for k in scope_fields):
            parent = git(root, "rev-parse", f"{node}^1") or ""
            prior_registry = document(root, parent, ACTIVE)
            prior = records(prior_registry.get("tasks", [])).get(owner, {})
            require(owner in records(document(root, parent, PLAN).get("foundationTasks", [])), "Ordinary planner cannot amend its original scope")
            require(prior.get("status") == entry.get("status") == "reserved" and prior.get("agentRole") == entry.get("agentRole") == "coordinator", "Planner scope amendment must remain reserved/coordinator")
            require(entry.get("baseSha") == parent and entry.get("lease") == prior.get("lease"), "Planner scope amendment must bind its parent and preserve lease")
            task_path = bind_spec(root, node, owner, entry)
            require(all(p in {ACTIVE, task_path} or p.startswith(f"evidence/{owner}/") for p in changed_paths(root, parent, node)), "Planner scope amendment includes code or foreign files")
            for path in (PLAN, LEDGER, manifest_path):
                require(blob(root, parent, path) == blob(root, node, path), "Planner scope amendment changed Program, Ledger or immutable manifest")
            foreign_before, foreign_after = copy.deepcopy(prior_registry), copy.deepcopy(current_registry)
            for snapshot in (foreign_before, foreign_after):
                snapshot["tasks"] = [row for row in snapshot.get("tasks", []) if row["taskId"] != owner]
            require(foreign_before == foreign_after, "Planner scope amendment changed foreign Registry or policy")
            require(entry.get("moduleIds") == ["MOD-GOV"] and entry.get("riskLevel") == "high", "Foundation scope requires exact MOD-GOV/high identity")
            require(entry.get("implementer") != entry.get("reviewer"), "Planner scope amendment lacks independent roles")
            ownership(root, node, entry)
            capacity(current_registry, document(root, node, PLAN))
            lease(entry, commit_time(root, node))
            authorized = copy.deepcopy(entry)
    return authorized


def frontier(plan: dict[str, Any], roots: list[str]) -> set[str]:
    by_id = tasks(plan)
    require(set(roots) <= by_id.keys(), "Baseline references unknown consumer")
    result = set(roots)
    while True:
        added = {tid for tid, row in by_id.items() if set(row.get("dependsOn", [])) & result} - result
        if not added:
            return result
        result |= added


def validate_baselines(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    baselines = records(plan.get("planningBaselines", []), "id")
    by_id = tasks(plan)
    waves = records(plan.get("waves", []), "id")
    foundations = records(plan.get("foundationTasks", []))
    graph = {tid: set(row.get("dependsOn", [])) for tid, row in by_id.items()}
    for row in baselines.values():
        require(set(row) == {"id", "taskId", "requiredBy"}, "Unknown baseline fields")
        producer, roots = row["taskId"], row["requiredBy"]
        require(producer in by_id and isinstance(roots, list) and roots and all(isinstance(r, str) for r in roots) and len(set(roots)) == len(roots), "Invalid baseline producer/consumers")
        require(producer not in roots and set(roots) <= by_id.keys(), "Baseline self edge or unknown consumer")
        for consumer in roots:
            producer_wave, consumer_wave = by_id[producer].get("wave"), by_id[consumer].get("wave")
            require(producer in foundations or producer_wave in waves, "Baseline producer references unknown wave")
            require(consumer in foundations or consumer_wave in waves, "Baseline consumer references unknown wave")
            producer_order = 0 if producer in foundations else waves[producer_wave]["order"]
            consumer_order = 0 if consumer in foundations else waves[consumer_wave]["order"]
            require(task_scope(plan, producer) != task_scope(plan, consumer) or producer_order <= consumer_order, "Baseline consumer depends on later-wave producer")
            graph[consumer].add(producer)
    visiting, done = set(), set()
    def visit(tid: str) -> None:
        require(tid in graph, f"Unknown dependency {tid}")
        require(tid not in visiting, "Program/baseline dependency cycle")
        if tid in done:
            return
        visiting.add(tid)
        for dependency in graph[tid]:
            visit(dependency)
        visiting.remove(tid)
        done.add(tid)
    for tid in graph:
        visit(tid)
    return baselines


@lru_cache(maxsize=128)
def baseline_snapshot(root: str, source: str, baseline_id: str) -> tuple[str, str, frozenset[str]]:
    """Return immutable creation data, not an admission or completion result."""
    for node in (git(root, "log", "--first-parent", "--reverse", "--format=%H", source, "--", PLAN) or "").splitlines():
        plan = document(root, node, PLAN)
        row = records(plan.get("planningBaselines", []), "id").get(baseline_id)
        if row:
            return node, json.dumps(row, sort_keys=True, separators=(",", ":")), frozenset(frontier(plan, row["requiredBy"]))
    raise PlanningError(f"Baseline {baseline_id} has no creation snapshot")


def original_consumers(root: str, ref: str, row: dict[str, Any]) -> set[str]:
    _, original, consumers = baseline_snapshot(*snapshot(root, ref), row["id"])
    require(original == json.dumps(row, sort_keys=True, separators=(",", ":")), "Baseline differs from its original creation snapshot")
    return set(consumers)


def preserve_consumer_closures(root: str, base_ref: str, after: dict[str, Any], rows: dict[str, dict[str, Any]], *, admitted_base_ref: str | None = None) -> None:
    for row in rows.values():
        original = original_consumers(root, base_ref, row)
        if not original <= frontier(after, row["requiredBy"]):
            require(completed_producer(root, admitted_base_ref or base_ref, row["taskId"]), "Pending baseline original consumer closure was narrowed")


def audit_changed_manifests(root: str, base_ref: str, head_ref: str, *, admitted_base_ref: str | None = None) -> None:
    """Audit original manifest bytes even when no Program definition changes."""
    for path in changed_paths(root, base_ref, head_ref):
        match = re.fullmatch(r"evidence/([A-Z]+-\d{3})/(planning-revision|agent-edge-104-first-use|agent-edge-104-definition)\.json", path)
        if not match:
            continue
        owner = match.group(1)
        require(match.group(2) == "planning-revision" or (owner, path) in {("OPS-011", FIRST_USE), (EDGE_PLANNER, EDGE_DEFINITION)}, "Typed planning manifest has wrong owner/path")
        before_active = records(document(root, base_ref, ACTIVE).get("tasks", []))
        authority = admitted_base_ref or before_active.get(owner, {}).get("baseSha") or base_ref
        authority = snapshot(root, authority)[1]
        canonical = [ref for ref in ("origin/main", "main") if git(root, "rev-parse", "--verify", ref, missing=True)]
        require(any(ancestor(root, authority, git(root, "rev-parse", ref) or "") for ref in canonical), "Manifest audit requires an admitted canonical base")
        prior = False
        introduction = None
        for node in (git(root, "rev-list", "--first-parent", "--reverse", authority) or "").splitlines():
            present = owner in records(document(root, node, ACTIVE).get("tasks", []))
            if present and not prior:
                require(introduction is None, "Manifest owner has multiple canonical introductions")
                introduction = node
            prior = present
        if introduction is None:
            # Unmerged original reservation proposals supply no permission.
            continue
        registration, _, _ = original_registration(root, introduction, owner)
        original = blob(root, registration, path)
        require(registered_manifest_path(root, registration, owner) == path and original is not None and original == blob(root, base_ref, path) == blob(root, head_ref, path), "Original registered planning manifest changed in history")


def unstarted(root: str, ref: str, plan: dict[str, Any], ids: set[str], allow_missing: bool = False) -> None:
    by_id = tasks(plan)
    active = records(document(root, ref, ACTIVE).get("tasks", []))
    completed = records(document(root, ref, LEDGER).get("records", []))
    for tid in ids:
        require((allow_missing and tid not in by_id) or by_id.get(tid, {}).get("status") == "planned", f"Planning target/consumer {tid} already started")
        require(tid not in active and tid not in completed and spec(root, ref, tid) is None, f"Planning target/consumer {tid} has Task Spec, lease or completion")


def validate_new_consumers(root: str, base_ref: str, head_ref: str, before: dict[str, Any], after: dict[str, Any], rows: dict[str, dict[str, Any]]) -> None:
    for row in rows.values():
        added = frontier(after, row["requiredBy"]) - frontier(before, row["requiredBy"])
        unstarted(root, base_ref, before, added, allow_missing=True)
        unstarted(root, head_ref, after, added)


def classifier(root: str, base_ref: str, head_ref: str, before: dict[str, Any], after: dict[str, Any], errors: list[str], *, owner_hint: str = "", observed_at: datetime | None = None, admitted_base_ref: str | None = None) -> dict[str, Any] | None:
    """Return only a fully authenticated exact transaction projection."""
    try:
        old_tasks, new_tasks = records(before.get("tasks", [])), records(after.get("tasks", []))
        changed = {tid for tid in old_tasks.keys() | new_tasks.keys() if {k: v for k, v in old_tasks.get(tid, {}).items() if k not in {"status", "issue"}} != {k: v for k, v in new_tasks.get(tid, {}).items() if k not in {"status", "issue"}}}
        real_before, real_after = document(root, base_ref, PLAN), document(root, head_ref, PLAN)
        def definitions(plan):
            return {tid: {k: v for k, v in row.items() if k not in {"status", "issue"}} for tid, row in records(plan.get("tasks", [])).items()}
        def baseline_view(plan):
            return "planningBaselines" in plan, plan.get("planningBaselines")
        def scope_view(plan):
            return "scopeBoundary" in plan, plan.get("scopeBoundary")
        scope_changed = scope_view(real_before) != scope_view(real_after)
        if changed or definitions(real_before) != definitions(real_after) or scope_changed or "planningBaselines" in real_before or "planningBaselines" in real_after:
            require(before == real_before and after == real_after, "Planning/baseline views must bind the actual Git snapshots")
        audit_changed_manifests(root, base_ref, head_ref, admitted_base_ref=admitted_base_ref)
        validate_scope_boundary(after)
        if after.get("scopeBoundary", {}).get("agentEdge104", {}).get("state") == "defined" and (
            scope_changed or changed_paths(root, base_ref, head_ref) & {EDGE_PATHS["requirementIndex"], EDGE_PATHS["acceptanceIndex"]}
        ):
            validate_frozen_edge_catalogs(root, admitted_base_ref or base_ref, head_ref, after)
        if definitions(real_before) == definitions(real_after) and baseline_view(real_before) == baseline_view(real_after) and not scope_changed:
            # No projection or planning permission is supplied. Ordinary
            # lifecycle/history and relevant consumer gates still run.
            return None
        old_baselines, new_baselines = validate_baselines(before), validate_baselines(after)
        preserve_consumer_closures(root, base_ref, after, old_baselines, admitted_base_ref=admitted_base_ref)
        validate_new_consumers(root, base_ref, head_ref, before, after, old_baselines)
        require(all(new_baselines.get(bid) == row for bid, row in old_baselines.items()), "Existing planning baseline removed, narrowed or substituted")
        added_baselines = new_baselines.keys() - old_baselines.keys()
        if not changed and not added_baselines and not scope_changed:
            return None
        require(before.get("status") == after.get("status") == "active", "Future planning cannot bypass frozen/recovery admission")
        base = git(root, "rev-parse", f"{base_ref}^{{commit}}") or ""
        head = git(root, "rev-parse", f"{head_ref}^{{commit}}") or ""
        admitted_base = git(root, "rev-parse", f"{admitted_base_ref or base_ref}^{{commit}}") or ""
        require(base != head and ancestor(root, base, head), "Planning execution must descend from its real integration base")
        require(ancestor(root, admitted_base, base), "Historical planning node predates its admitted main base")
        prior_active = document(root, base, ACTIVE)
        current_active = document(root, head, ACTIVE)
        eligible = [r for r in prior_active.get("tasks", []) if PLAN in r.get("exclusivePaths", []) and registered_manifest_path(root, base, r.get("taskId", "")) is not None]
        if owner_hint:
            prior_hint, current_hint = tasks(before).get(owner_hint, {}), tasks(after).get(owner_hint, {})
            prior_spec, current_spec = spec(root, base, owner_hint), spec(root, head, owner_hint)
            paths = changed_paths(root, base, head)
            historical_context = (
                prior_hint.get("status") == current_hint.get("status") == "completed"
                and prior_hint == current_hint
                and owner_hint not in records(prior_active.get("tasks", []))
                and owner_hint not in records(current_active.get("tasks", []))
                and prior_spec == current_spec
                and (prior_spec is None or blob(root, base, prior_spec[0]) == blob(root, head, prior_spec[0]))
                and not any(p.startswith(f"evidence/{owner_hint}/") or p.startswith(f"specs/tasks/{owner_hint}") for p in paths)
                and blob(root, base, LEDGER) == blob(root, head, LEDGER)
            )
            if not historical_context:
                eligible = [r for r in eligible if r["taskId"] == owner_hint]
        require(len(eligible) == 1, "Planning transaction requires one previously registered manifest owner")
        owner = eligible[0]["taskId"]
        entry = records(current_active.get("tasks", [])).get(owner)
        require(entry is not None and entry.get("status") in EXECUTION and entry.get("agentRole") in {"implementer", "integrator"}, "Planning requires active implementer/integrator phase")
        require(tasks(after).get(owner, {}).get("status") == entry["status"], "Planner Program/Registry phase mismatch")
        registration, parent, original = original_registration(root, admitted_base, owner)
        require(ancestor(root, registration, admitted_base), "Planner reservation must be integrated before execution")
        path, raw = immutable_manifest(root, registration, head, owner)
        require(registered_manifest_path(root, base, owner) == path and raw == blob(root, base, path), "Original planning manifest was changed or absent")
        manifest = json.loads(raw.decode("utf-8"))
        require(manifest.get("taskId") == owner and manifest.get("reservationParent") == parent, "Manifest owner/registration parent mismatch")
        program_schema = document(root, head, PROGRAM_SCHEMA)
        manifest_schema = document(root, head, MANIFEST_SCHEMA)
        registry = Registry().with_resources([(program_schema["$id"], Resource.from_contents(program_schema)), (manifest_schema["$id"], Resource.from_contents(manifest_schema))])
        schema_ref = manifest_schema["$id"]
        if path == FIRST_USE:
            require(owner == "OPS-011" and hashlib.sha256(raw).hexdigest() == FIRST_USE_SHA256, "First-use declaration differs from fixed original intent")
            require(manifest.get("issue") == original.get("issue") and manifest.get("originalV1TaskIds") == [row["taskId"] for row in before["tasks"]], "First-use V1 inventory/Issue differs from original registration")
            require(manifest.get("originalPocTaskIds") == [row["taskId"] for row in before.get("pocs", [])], "First-use POC inventory changed")
            schema_ref += "#/$defs/agentEdge104FirstUse"
        elif path == EDGE_DEFINITION:
            require(owner == EDGE_PLANNER and manifest.get("issue") == original.get("issue"), "Scope definition Issue differs from its own reservation")
            schema_ref += "#/$defs/agentEdge104Definition"
        else:
            require(not scope_changed, "Legacy manifest cannot define or amend a fixed scope")
        jsonschema.Draft202012Validator({"$ref": schema_ref}, registry=registry).validate(manifest)
        jsonschema.Draft202012Validator(program_schema, registry=registry).validate(after)
        authorized = registered_scope(root, admitted_base, owner, registration, original)
        mutable = {"status", "agentRole", "baseSha", "lease"}
        require({k: v for k, v in authorized.items() if k not in mutable} == {k: v for k, v in entry.items() if k not in mutable}, "Planner stable identity or prior registered claims changed")
        require(entry.get("baseSha") == admitted_base and entry.get("riskLevel") == "high" and "MOD-GOV" in entry.get("moduleIds", []), "Planner requires high risk, MOD-GOV and exact admitted base")
        ownership(root, head, entry)
        capacity(current_active, after)
        require(entry.get("implementer") and entry.get("reviewer") and entry["implementer"] != entry["reviewer"], "Planner requires independent roles")
        require(PLAN in original.get("exclusivePaths", []) and not entry.get("sharedPaths"), "Planner requires exact exclusive Program claim")
        lease(entry, observed_at or datetime.now(timezone.utc))
        bind_spec(root, head, owner, entry)
        expected = copy.deepcopy(before)
        target_ids, baseline_ids, scope_targets = set(), set(), set()
        for target in manifest["targets"]:
            kind = target["kind"]
            if kind == "add-fixed-scope-boundary":
                require(path == FIRST_USE and not scope_targets and "scopeBoundary" not in before and target["before"] is None, "Fixed scope first use is not original")
                expected["scopeBoundary"] = copy.deepcopy(target["after"])
                scope_targets.add(EDGE_SCOPE)
                continue
            if kind == "define-fixed-scope":
                require(path == EDGE_DEFINITION and not scope_targets and before.get("scopeBoundary", {}).get("agentEdge104") == target["before"], "Scope before definition mismatch")
                expected["scopeBoundary"]["agentEdge104"] = copy.deepcopy(target["after"])
                scope_targets.add(EDGE_SCOPE)
                continue
            tid = target["id"]
            bucket = baseline_ids if kind == "add-planning-baseline" else target_ids
            require(tid not in bucket, "Duplicate manifest target")
            bucket.add(tid)
            if kind == "add-planning-baseline":
                require(tid not in old_baselines and target["after"]["id"] == tid, "Baseline original/after mismatch")
                expected.setdefault("planningBaselines", []).append(target["after"])
                producer = target["after"]["taskId"]
                consumer_ids = frontier(after, target["after"]["requiredBy"])
                require(producer not in consumer_ids, "Baseline producer is its own consumer")
                unstarted(root, base, before, consumer_ids | {producer}, allow_missing=True)
                unstarted(root, head, after, consumer_ids | {producer})
                continue
            require(target["after"]["taskId"] == tid and tid != owner, "Planner cannot rewrite its own definition")
            unstarted(root, base, before, {tid}, allow_missing=kind in {"add-planned-task", "add-edge-planned-task"})
            unstarted(root, head, after, {tid})
            if kind in {"add-planned-task", "add-edge-planned-task"}:
                require(tid not in old_tasks, "New planning task already exists")
                require((kind == "add-edge-planned-task") == (path == EDGE_DEFINITION), "Task addition has wrong scope declaration")
                expected["tasks"].append(target["after"])
            else:
                original_definition = old_tasks.get(tid)
                require(original_definition == target["before"], "Planning before definition mismatch")
                digest = hashlib.sha256(json.dumps(original_definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
                require(digest == target["originalDefinitionSha256"], "Planning original definition hash mismatch")
                fields = {key for key in set(target["before"]) | set(target["after"]) if target["before"].get(key) != target["after"].get(key)}
                require(fields == set(target["allowedFields"]), "Planning changed undeclared or unused fields")
                if path == EDGE_DEFINITION:
                    validate_edge_v1_edit(target)
                expected["tasks"] = [target["after"] if row["taskId"] == tid else row for row in expected["tasks"]]
        section = "foundationTasks" if owner in records(expected.get("foundationTasks", [])) else "tasks"
        for row in expected[section]:
            if row["taskId"] == owner:
                row["status"] = entry["status"]
        require(target_ids == changed and baseline_ids == added_baselines and expected == after, "Planning transaction is incomplete or contains undeclared Program changes")
        require(bool(scope_targets) == scope_changed, "Fixed scope change must be declared exactly once")
        if path == EDGE_DEFINITION:
            added_edge = {target["id"] for target in manifest["targets"] if target["kind"] == "add-edge-planned-task"}
            require(set(after["scopeBoundary"]["agentEdge104"]["taskIds"]) == added_edge | {EDGE_PLANNER}, "Scope members differ from complete original task definitions")
        prior_foreign, current_foreign = copy.deepcopy(prior_active), copy.deepcopy(current_active)
        for active in (prior_foreign, current_foreign):
            active["tasks"] = [r for r in active["tasks"] if r["taskId"] != owner]
        require(prior_foreign == current_foreign, "Planning transaction changed Registry policy or peer")
        require(blob(root, base, LEDGER) == blob(root, head, LEDGER), "Planning cannot rewrite completion ledger")
        projected = copy.deepcopy(before)
        for row in projected[section]:
            if row["taskId"] == owner:
                row["status"] = entry["status"]
        return {"owner": owner, "registration": registration, "targetTaskIds": target_ids, "projectedPlan": projected}
    except (PlanningError, OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError, jsonschema.SchemaError) as exc:
        errors.append(f"Planning revision rejected: {exc}")
        return None


def completed_producer(root: str, base: str, producer: str) -> bool:
    """Require pre-existing real reservation/code/review/completion ancestry.

    Full normal history/Completion validators remain mandatory. This bounded
    admission proof rejects candidate-only, sibling and forged ledger identities.
    """
    plan = document(root, base, PLAN)
    if tasks(plan).get(producer, {}).get("status") != "completed":
        return False
    record = records(document(root, base, LEDGER).get("records", [])).get(producer)
    if not record:
        return False
    code, reservation = record.get("mergeCommit", ""), record.get("reservationCommit", "")
    if not ancestor(root, reservation, code) or reservation == code or not ancestor(root, code, base):
        return False
    canonical = (git(root, "rev-list", "--first-parent", "--reverse", base) or "").splitlines()
    if code not in canonical or reservation not in canonical:
        return False
    original = records(document(root, reservation, ACTIVE).get("tasks", [])).get(producer)
    code_entry = records(document(root, code, ACTIVE).get("tasks", [])).get(producer)
    reservation_parent = git(root, "rev-parse", f"{reservation}^1") or ""
    if not original or original.get("status") != "reserved" or producer in records(document(root, reservation_parent, ACTIVE).get("tasks", [])):
        return False
    if not code_entry or code_entry.get("status") not in {"in_progress", "review", "integration"} or code_entry.get("implementer") == code_entry.get("reviewer"):
        return False
    bind_spec(root, reservation, producer, original)
    bind_spec(root, code, producer, code_entry)
    lease(original, commit_time(root, reservation))
    lease(code_entry, commit_time(root, code))
    code_parent = git(root, "rev-parse", f"{code}^1") or ""
    task_path = spec(root, code, producer)[0]
    implemented = changed_paths(root, code_parent, code) - {PLAN, ACTIVE, LEDGER, task_path}
    implemented = {p for p in implemented if not p.startswith(f"evidence/{producer}/")}
    claims = original.get("exclusivePaths", []) + original.get("sharedPaths", [])
    if not implemented or any(not any(fnmatch.fnmatchcase(p, claim) for claim in claims) for p in implemented):
        return False
    reference = str(record.get("completionRef", ""))
    message = git(root, "show", "-s", "--format=%B", code) or ""
    if not re.fullmatch(r"PR-[0-9]+", reference) or producer not in message or not re.search(rf"(?:#{reference[3:]}|\b{reference}\b)", message):
        return False
    reviewed = False
    for node in canonical[canonical.index(code) + 1:]:
        snapshot = document(root, node, PLAN)
        state = tasks(snapshot).get(producer, {}).get("status")
        active = records(document(root, node, ACTIVE).get("tasks", [])).get(producer)
        if state in {"review", "integration"} and active and active.get("agentRole") in {"reviewer", "integrator"}:
            reviewed = True
        if state == "completed":
            parent = git(root, "rev-parse", f"{node}^1") or ""
            actual = records(document(root, node, LEDGER).get("records", [])).get(producer)
            previous = tasks(document(root, parent, PLAN)).get(producer, {}).get("status")
            final_spec = spec(root, node, producer)
            return bool(reviewed and previous in {"review", "integration"} and actual == record and active is None and final_spec and final_spec[1].get("status") == "completed")
    return False


def serial_baseline_pairs(root: str, head_ref: str, plan: dict[str, Any], errors: list[str]) -> set[frozenset[str]]:
    """Authenticate prospective serialization without waiving live conflicts."""
    try:
        current = validate_baselines(plan)
        if not current:
            return set()
        head = git(root, "rev-parse", f"{head_ref}^{{commit}}") or ""
        require(plan == document(root, head, PLAN), "Readiness baseline view must bind its actual Git snapshot")
        require(not git(root, "status", "--porcelain", "--", ACTIVE, LEDGER, "specs/tasks"), "Readiness baseline identities must bind their actual Git snapshot")
        proven = {}
        manifests = {}
        registrations = {}
        nodes = (git(root, "log", "--first-parent", "--reverse", "--format=%H", head, "--", PLAN) or "").splitlines()
        for node in nodes:
            node_plan = document(root, node, PLAN)
            if not node_plan.get("planningBaselines") and not proven:
                continue
            baselines = validate_baselines(node_plan)
            require(all(baselines.get(key) == row for key, row in proven.items()), "Historical baseline removed, narrowed or substituted")
            if proven:
                preserve_consumer_closures(root, node, node_plan, proven)
                parent = git(root, "rev-parse", f"{node}^1") or ""
                validate_new_consumers(root, parent, node, document(root, parent, PLAN), node_plan, proven)
            added = baselines.keys() - proven.keys()
            if added:
                parent = git(root, "rev-parse", f"{node}^1") or ""
                prior_active = records(document(root, parent, ACTIVE).get("tasks", []))
                owners = [tid for tid, row in prior_active.items() if PLAN in row.get("exclusivePaths", []) and registered_manifest_path(root, parent, tid) is not None]
                require(len(owners) == 1, "Readiness baseline has no unique prior manifest owner")
                owner = owners[0]
                entry = records(document(root, node, ACTIVE).get("tasks", [])).get(owner, {})
                admission_errors = []
                decision = classifier(root, parent, node, document(root, parent, PLAN), node_plan, admission_errors, owner_hint=owner, observed_at=commit_time(root, node), admitted_base_ref=entry.get("baseSha", ""))
                require(decision is not None and not admission_errors, "Readiness baseline introduction unauthenticated: " + "; ".join(admission_errors))
                manifest_path = registered_manifest_path(root, parent, owner)
                manifests[owner] = (manifest_path, blob(root, parent, manifest_path))
                registrations[owner] = decision["registration"]
                proven.update({key: baselines[key] for key in added})
        require(proven == current, "Readiness baseline lacks authenticated history")
        require(all(registered_manifest_path(root, head, owner) == path and blob(root, head, path) == original for owner, (path, original) in manifests.items()), "Readiness baseline original manifest changed")
        for owner, registration in registrations.items():
            path, original = manifests[owner]
            for node in (git(root, "log", "--first-parent", "--format=%H", head, "--", path) or "").splitlines():
                if ancestor(root, registration, node):
                    require(blob(root, node, path) == original, "Readiness original manifest changed in intermediate history")
        by_id = tasks(plan)
        active = records(document(root, head, ACTIVE).get("tasks", []))
        completed = records(document(root, head, LEDGER).get("records", []))
        pairs = set()
        for row in current.values():
            for consumer in frontier(plan, row["requiredBy"]):
                if by_id[consumer].get("status") == "planned" and consumer not in active and consumer not in completed and spec(root, head, consumer) is None:
                    pairs.add(frozenset((row["taskId"], consumer)))
        return pairs
    except (PlanningError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Readiness baseline authentication rejected: {exc}")
        return set()


def enforce_consumers(root: str, base_ref: str, head_ref: str, before: dict[str, Any], after: dict[str, Any], affected: set[str], paths: set[str], errors: list[str], *, admitted_base_ref: str | None = None) -> None:
    """Apply pending baselines to explicit IDs and no-task code owner diffs."""
    try:
        rows = after.get("planningBaselines", [])
        baseline_changed = ("planningBaselines" in before, before.get("planningBaselines")) != ("planningBaselines" in after, after.get("planningBaselines"))
        has_edge = "scopeBoundary" in after
        if not rows and not baseline_changed and not has_edge:
            return
        by_id = tasks(after)
        consumers = set(affected)
        live = records(document(root, head_ref, ACTIVE).get("tasks", []))
        prior_live = records(document(root, base_ref, ACTIVE).get("tasks", []))
        consumers.update(tid for tid in live.keys() | prior_live.keys() if live.get(tid) != prior_live.get(tid))
        source = snapshot(root, head_ref)[1]
        if any(p.startswith("specs/tasks/") for p in paths):
            consumers.update(front.get("id") for path, front in spec_index(str(Path(root).resolve()), source) if path in paths and isinstance(front.get("id"), str))
        for path in paths - METADATA:
            if path.startswith("specs/tasks/") or path.startswith("evidence/"):
                continue
            owners = {tid for tid, row in live.items() if any(fnmatch.fnmatchcase(path, claim) for claim in row.get("exclusivePaths", []) + row.get("sharedPaths", []))}
            # A registered requirements planner may own a future consumer's
            # input specification. Bind actual owners before falling back to
            # unregistered code matching a planned consumer's output paths.
            if not owners:
                owners = {tid for tid, row in by_id.items() if any(fnmatch.fnmatchcase(path, claim) for claim in row.get("outputPaths", []) + row.get("sharedPaths", []))}
            consumers.update(owners)
            affected.update(owners)
        if has_edge:
            validate_scope_boundary(after)
            edge = after["scopeBoundary"]["agentEdge104"]
            business = consumers & (set(edge["taskIds"]) - {EDGE_PLANNER})
            if business:
                base = git(root, "rev-parse", f"{admitted_base_ref or base_ref}^{{commit}}") or ""
                require(edge["state"] == "defined" and completed_producer(root, base, EDGE_PLANNER),
                        "Agent Edge business execution requires real completed producer GZ-022; consumers rejected: " + ", ".join(sorted(business)))
        pending_by_baseline = {row["id"]: consumers & (frontier(after, row["requiredBy"]) | original_consumers(root, head_ref, row)) for row in rows}
        if not baseline_changed and not any(pending_by_baseline.values()):
            return
        old_baselines, baselines = validate_baselines(before), validate_baselines(after)
        require(all(baselines.get(key) == row for key, row in old_baselines.items()), "Existing planning baseline removed, narrowed or substituted")
        preserve_consumer_closures(root, base_ref, after, old_baselines, admitted_base_ref=admitted_base_ref)
        base = git(root, "rev-parse", f"{admitted_base_ref or base_ref}^{{commit}}") or ""
        for baseline in baselines.values():
            pending = pending_by_baseline[baseline["id"]]
            if not pending:
                continue
            if not completed_producer(root, base, baseline["taskId"]):
                errors.append(f"Planning baseline {baseline['id']} pending real completed producer {baseline['taskId']}; consumers rejected: {', '.join(sorted(pending))}")
    except (PlanningError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Planning baseline admission rejected: {exc}")

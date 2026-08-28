#!/usr/bin/env python3
"""Validate requirement traceability, module ownership and planned task dependencies."""

import argparse
import fnmatch
import json
import os
import re
import sys

import yaml

REQ_STATES = {"frozen", "approved", "draft", "deprecated"}
CONTRACT_STATES = {"gap", "planned", "partial", "frozen", "implemented"}
IMPLEMENTATION_STATES = {"not_started", "governance_only", "in_progress", "implemented", "verified"}
MODULE_STATES = {"active", "planned", "deprecated"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
REQ_ID_RE = re.compile(r"^REQ-V1-\d{4}$")
MODULE_ID_RE = re.compile(r"^MOD-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
TASK_ID_RE = re.compile(r"^[A-Z]+-\d+$")
GLOB_CHARS = "*?["


def parse_args():
    parser = argparse.ArgumentParser(description="Validate Guize project implementation readiness indexes")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--requirements", default="specs/requirements/requirements-index.yaml")
    parser.add_argument("--modules", default="specs/designs/module-ownership.yaml")
    parser.add_argument("--plan", default="specs/coordination/work-package-plan.yaml")
    parser.add_argument("--strict-ready", action="store_true")
    return parser.parse_args()


def report(status, message, details=None):
    payload = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def existing_ref(root, value):
    path = str(value).split("#", 1)[0].strip().strip("`")
    return bool(path) and os.path.exists(os.path.join(root, path))


def find_task_file(root, task_id):
    directory = os.path.join(root, "specs", "tasks")
    exact = os.path.join(directory, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    matches = []
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if name.startswith(f"{task_id}-") and name.endswith(".md"):
                matches.append(os.path.join(directory, name))
    return matches[0] if len(matches) == 1 else None


def has_cycle(graph):
    visiting = set()
    visited = set()

    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency in graph and visit(dependency):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def require_fields(item, fields, label, errors):
    for field in fields:
        if field not in item or item[field] is None or item[field] == "":
            errors.append(f"{label} missing required field: {field}")


def require_non_empty_list(item, field, label, errors):
    value = item.get(field)
    if not isinstance(value, list) or not value:
        errors.append(f"{label} field {field} must be a non-empty list")


def normalize_pattern(value):
    value = str(value).strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    value = re.sub(r"/+", "/", value)
    return value.rstrip("/")


def static_prefix(pattern):
    pattern = normalize_pattern(pattern)
    indexes = [pattern.find(char) for char in GLOB_CHARS if pattern.find(char) >= 0]
    if not indexes:
        return pattern
    return pattern[: min(indexes)].rstrip("/")


def patterns_overlap(left, right):
    left = normalize_pattern(left)
    right = normalize_pattern(right)
    if not left or not right:
        return True
    if left == right:
        return True
    if fnmatch.fnmatch(left, right) or fnmatch.fnmatch(right, left):
        return True
    left_prefix = static_prefix(left)
    right_prefix = static_prefix(right)
    if not left_prefix or not right_prefix:
        return True
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
    )


def validate_baseline_task(root, document, label, errors):
    baseline = str(document.get("baseline", "")).strip()
    if not baseline:
        errors.append(f"{label} missing baseline")
    elif not TASK_ID_RE.fullmatch(baseline):
        errors.append(f"{label} baseline has invalid task ID: {baseline}")
    elif not find_task_file(root, baseline):
        errors.append(f"{label} baseline task does not exist: {baseline}")


def main():
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors = []
    warnings = []

    try:
        req_doc = load_yaml(os.path.join(root, args.requirements))
        module_doc = load_yaml(os.path.join(root, args.modules))
        plan_doc = load_yaml(os.path.join(root, args.plan))
    except Exception as exc:
        report("FAIL", f"Cannot load readiness index: {exc}")
        sys.exit(1)

    if not isinstance(req_doc, dict) or not isinstance(module_doc, dict) or not isinstance(plan_doc, dict):
        report("FAIL", "Readiness index roots must be mappings")
        sys.exit(1)

    requirements = req_doc.get("requirements", [])
    modules = module_doc.get("modules", [])
    plan_tasks = plan_doc.get("tasks", [])
    foundation = set(plan_doc.get("foundationTasks", []))

    if req_doc.get("version") != 1:
        errors.append("Requirements index version must be 1")
    if module_doc.get("version") != 1:
        errors.append("Module ownership version must be 1")
    if plan_doc.get("version") != 1:
        errors.append("Work-package plan version must be 1")
    if not existing_ref(root, req_doc.get("sourceOfTruth", "")):
        errors.append(f"Requirements sourceOfTruth does not exist: {req_doc.get('sourceOfTruth')}")
    validate_baseline_task(root, req_doc, "Requirements index", errors)
    validate_baseline_task(root, module_doc, "Module ownership index", errors)

    if not requirements:
        errors.append("Requirements index must contain at least one requirement")
    if not modules:
        errors.append("Module ownership index must contain at least one module")
    if not plan_tasks:
        errors.append("Work-package plan must contain at least one planned task")
    if not isinstance(foundation, set) or not foundation:
        errors.append("Work-package plan must contain foundationTasks")

    req_ids = [item.get("id") for item in requirements]
    module_ids = [item.get("id") for item in modules]
    plan_ids = [item.get("taskId") for item in plan_tasks]
    if len(req_ids) != len(set(req_ids)):
        errors.append("Requirement IDs must be unique")
    if len(module_ids) != len(set(module_ids)):
        errors.append("Module IDs must be unique")
    if len(plan_ids) != len(set(plan_ids)):
        errors.append("Planned task IDs must be unique")
    req_set = set(req_ids)
    module_set = set(module_ids)
    plan_set = set(plan_ids)
    known_tasks = foundation | plan_set

    for task_id in sorted(foundation):
        if not TASK_ID_RE.fullmatch(task_id):
            errors.append(f"Invalid foundation task ID: {task_id}")
        elif not find_task_file(root, task_id):
            errors.append(f"Foundation task spec does not exist: {task_id}")

    aliases = {}
    req_by_id = {item.get("id"): item for item in requirements}
    module_by_id = {item.get("id"): item for item in modules}

    for item in requirements:
        req_id = item.get("id", "<unknown>")
        require_fields(
            item,
            ["id", "aliases", "title", "status", "source", "designRefs", "moduleIds", "workPackages", "acceptanceIds", "machineContractState", "implementationState", "blockers", "nextTasks"],
            f"Requirement {req_id}",
            errors,
        )
        for list_field in ["aliases", "designRefs", "moduleIds", "workPackages", "acceptanceIds", "nextTasks"]:
            require_non_empty_list(item, list_field, f"Requirement {req_id}", errors)
        if not REQ_ID_RE.fullmatch(str(req_id)):
            errors.append(f"Requirement ID format invalid: {req_id}")
        if item.get("status") not in REQ_STATES:
            errors.append(f"Requirement {req_id} has invalid status {item.get('status')}")
        if item.get("machineContractState") not in CONTRACT_STATES:
            errors.append(f"Requirement {req_id} has invalid machineContractState")
        if item.get("implementationState") not in IMPLEMENTATION_STATES:
            errors.append(f"Requirement {req_id} has invalid implementationState")
        if not existing_ref(root, item.get("source", "")):
            errors.append(f"Requirement {req_id} source does not exist: {item.get('source')}")
        for ref in item.get("designRefs", []):
            if not existing_ref(root, ref):
                errors.append(f"Requirement {req_id} design reference does not exist: {ref}")
        for module_id in item.get("moduleIds", []):
            if module_id not in module_set:
                errors.append(f"Requirement {req_id} references unknown module {module_id}")
            elif req_id not in module_by_id[module_id].get("requirementIds", []):
                errors.append(f"Requirement/module mapping is asymmetric: {req_id} -> {module_id} only")
        for next_task in item.get("nextTasks", []):
            if next_task not in known_tasks:
                errors.append(f"Requirement {req_id} references unknown next task {next_task}")
        for alias in item.get("aliases", []):
            if alias in aliases and aliases[alias] != req_id:
                errors.append(f"Alias {alias} is assigned to both {aliases[alias]} and {req_id}")
            aliases[alias] = req_id

    module_graph = {}
    schema_owners = {}
    path_claims = []
    for item in modules:
        module_id = item.get("id", "<unknown>")
        require_fields(
            item,
            ["id", "name", "status", "owner", "ownedPaths", "ownedSchemas", "publicContracts", "dependsOn", "requirementIds", "workPackages"],
            f"Module {module_id}",
            errors,
        )
        for list_field in ["ownedPaths", "requirementIds", "workPackages"]:
            require_non_empty_list(item, list_field, f"Module {module_id}", errors)
        for optional_list in ["ownedSchemas", "publicContracts", "dependsOn"]:
            if not isinstance(item.get(optional_list), list):
                errors.append(f"Module {module_id} field {optional_list} must be a list")
        if not MODULE_ID_RE.fullmatch(str(module_id)):
            errors.append(f"Module ID format invalid: {module_id}")
        if item.get("status") not in MODULE_STATES:
            errors.append(f"Module {module_id} has invalid status {item.get('status')}")
        for dependency in item.get("dependsOn", []):
            if dependency not in module_set:
                errors.append(f"Module {module_id} depends on unknown module {dependency}")
        for req_id in item.get("requirementIds", []):
            if req_id not in req_set:
                errors.append(f"Module {module_id} references unknown requirement {req_id}")
            elif module_id not in req_by_id[req_id].get("moduleIds", []):
                errors.append(f"Requirement/module mapping is asymmetric: {module_id} -> {req_id} only")
        module_graph[module_id] = list(item.get("dependsOn", []))

        normalized_paths = [normalize_pattern(path) for path in item.get("ownedPaths", [])]
        if len(normalized_paths) != len(set(normalized_paths)):
            errors.append(f"Module {module_id} contains duplicate ownedPaths")
        for path in normalized_paths:
            if path in {"", "*", "**"}:
                errors.append(f"Module {module_id} may not own the entire repository")
            path_claims.append((module_id, path))
        schemas = item.get("ownedSchemas", [])
        if len(schemas) != len(set(schemas)):
            errors.append(f"Module {module_id} contains duplicate ownedSchemas")
        for schema in schemas:
            if schema in schema_owners:
                errors.append(f"Schema {schema} is owned by both {schema_owners[schema]} and {module_id}")
            else:
                schema_owners[schema] = module_id

    if has_cycle(module_graph):
        errors.append("Module dependency graph contains a cycle")
    for index, (left_module, left_path) in enumerate(path_claims):
        for right_module, right_path in path_claims[index + 1 :]:
            if left_module != right_module and patterns_overlap(left_path, right_path):
                errors.append(
                    f"Module path ownership overlaps: {left_module}:{left_path} and {right_module}:{right_path}"
                )

    task_graph = {}
    covered_requirements = set()
    for item in plan_tasks:
        task_id = item.get("taskId", "<unknown>")
        require_fields(
            item,
            ["taskId", "title", "workPackage", "riskLevel", "parallelGroup", "dependsOn", "requirementIds", "moduleIds", "outputPaths", "exitGate"],
            f"Planned task {task_id}",
            errors,
        )
        for list_field in ["requirementIds", "moduleIds", "outputPaths"]:
            require_non_empty_list(item, list_field, f"Planned task {task_id}", errors)
        if not isinstance(item.get("dependsOn"), list):
            errors.append(f"Planned task {task_id} field dependsOn must be a list")
        if not TASK_ID_RE.fullmatch(str(task_id)):
            errors.append(f"Planned task ID format invalid: {task_id}")
        if item.get("riskLevel") not in RISK_LEVELS:
            errors.append(f"Planned task {task_id} has invalid riskLevel")
        for dependency in item.get("dependsOn", []):
            if dependency not in known_tasks:
                errors.append(f"Planned task {task_id} depends on unknown task {dependency}")
        for req_id in item.get("requirementIds", []):
            covered_requirements.add(req_id)
            if req_id not in req_set:
                errors.append(f"Planned task {task_id} references unknown requirement {req_id}")
        for module_id in item.get("moduleIds", []):
            if module_id not in module_set:
                errors.append(f"Planned task {task_id} references unknown module {module_id}")
        task_graph[task_id] = list(item.get("dependsOn", []))
    if has_cycle(task_graph):
        errors.append("Planned task dependency graph contains a cycle")

    uncovered = sorted(req_set - covered_requirements)
    if uncovered:
        warnings.append(f"Requirements without a planned next task: {', '.join(uncovered)}")
    contract_gaps = sorted(item["id"] for item in requirements if item.get("machineContractState") not in {"frozen", "implemented"})
    implementation_gaps = sorted(item["id"] for item in requirements if item.get("implementationState") not in {"implemented", "verified"})

    invariant_files = {
        "README.md": "V1 不设置对外 Beta",
        "docs/00-guize-engineering-design-baseline.md": "V1 不设置对外 Beta",
    }
    for relative_path, phrase in invariant_files.items():
        path = os.path.join(root, relative_path)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                if phrase not in handle.read():
                    errors.append(f"Frozen delivery invariant missing from {relative_path}: {phrase}")
        except OSError:
            errors.append(f"Invariant file missing: {relative_path}")

    required_headings = ["## 7.", "## 8.", "## 9.", "## 10.", "## 13.", "## 14.", "## 16.", "## 18."]
    baseline_path = os.path.join(root, "docs", "00-guize-engineering-design-baseline.md")
    try:
        with open(baseline_path, "r", encoding="utf-8") as handle:
            baseline = handle.read()
        for heading in required_headings:
            if heading not in baseline:
                errors.append(f"Engineering baseline missing required section prefix: {heading}")
    except OSError:
        errors.append("Engineering baseline is missing")

    if args.strict_ready and (contract_gaps or implementation_gaps):
        errors.append("Strict readiness requested but contract or implementation gaps remain")
    elif contract_gaps:
        warnings.append(f"Machine contracts not frozen for {len(contract_gaps)} requirements")
    if implementation_gaps:
        warnings.append(f"Implementation not verified for {len(implementation_gaps)} requirements")

    for error in errors:
        report("FAIL", error)
    for warning in warnings:
        report("WARN", warning)
    if errors:
        sys.exit(1)
    report(
        "PASS",
        "Project readiness indexes are structurally consistent",
        {
            "requirements": len(requirements),
            "modules": len(modules),
            "plannedTasks": len(plan_tasks),
            "ownedSchemas": len(schema_owners),
            "contractGapCount": len(contract_gaps),
            "implementationGapCount": len(implementation_gaps),
        },
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate Guize requirement, module, contract namespace and Program Plan readiness."""

import argparse
import fnmatch
import json
import os
import re
import sys
from collections import defaultdict

import jsonschema
import yaml

REQ_RE = re.compile(r"^REQ-V1-\d{4}$")
MOD_RE = re.compile(r"^MOD-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
TASK_RE = re.compile(r"^[A-Z]+-\d{3}$")
RISKS = {"low", "medium", "high", "critical"}
REQ_STATES = {"frozen", "approved", "draft", "deprecated"}
CONTRACT_STATES = {"gap", "planned", "partial", "frozen", "implemented"}
IMPL_STATES = {"not_started", "governance_only", "in_progress", "implemented", "verified"}
MODULE_STATES = {"active", "planned", "deprecated"}
GLOB_CHARS = "*?["


def args_parser():
    p = argparse.ArgumentParser(description="Validate Guize implementation readiness")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--requirements", default="specs/requirements/requirements-index.yaml")
    p.add_argument("--modules", default="specs/designs/module-ownership.yaml")
    p.add_argument("--plan", default="specs/coordination/program-plan.yaml")
    p.add_argument("--plan-schema", default="specs/coordination/program-plan.schema.yaml")
    p.add_argument("--strict-ready", action="store_true")
    return p.parse_args()


def emit(status, message, details=None):
    obj = {"status": status, "message": message}
    if details is not None:
        obj["details"] = details
    print(json.dumps(obj, ensure_ascii=False))


def load(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ref_exists(root, value):
    path = str(value or "").split("#", 1)[0].strip().strip("`")
    return bool(path) and os.path.exists(os.path.join(root, path))


def task_file(root, task_id):
    base = os.path.join(root, "specs", "tasks")
    exact = os.path.join(base, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    if not os.path.isdir(base):
        return None
    found = [os.path.join(base, name) for name in os.listdir(base) if name.startswith(task_id + "-") and name.endswith(".md")]
    return found[0] if len(found) == 1 else None


def task_front_matter(path):
    if not path:
        return {}
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out = {}
    for line in parts[1].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def norm(pattern):
    value = str(pattern).strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return re.sub(r"/+", "/", value).rstrip("/")


def prefix(pattern):
    pattern = norm(pattern)
    indexes = [pattern.find(char) for char in GLOB_CHARS if pattern.find(char) >= 0]
    return pattern if not indexes else pattern[: min(indexes)].rstrip("/")


def overlaps(left, right):
    left, right = norm(left), norm(right)
    if not left or not right or left == right:
        return True
    if fnmatch.fnmatch(left, right) or fnmatch.fnmatch(right, left):
        return True
    left_prefix, right_prefix = prefix(left), prefix(right)
    return not left_prefix or not right_prefix or left_prefix == right_prefix or left_prefix.startswith(right_prefix + "/") or right_prefix.startswith(left_prefix + "/")


def cycle(graph):
    visiting, done = set(), set()

    def visit(node):
        if node in visiting:
            return True
        if node in done:
            return False
        visiting.add(node)
        if any(dependency in graph and visit(dependency) for dependency in graph.get(node, [])):
            return True
        visiting.remove(node)
        done.add(node)
        return False

    return any(visit(node) for node in graph)


def ancestors(task_id, graph, cache):
    if task_id in cache:
        return cache[task_id]
    result = set()
    for dependency in graph.get(task_id, []):
        result.add(dependency)
        if dependency in graph:
            result |= ancestors(dependency, graph, cache)
    cache[task_id] = result
    return result


def unique_ids(items, field, label, errors):
    identifiers = [item.get(field) for item in items]
    if None in identifiers or "" in identifiers:
        errors.append(f"{label} contains an empty {field}")
    if len(identifiers) != len(set(identifiers)):
        errors.append(f"{label} {field} values must be unique")
    return set(identifiers)


def require_lists(item, fields, label, errors, allow_empty=()):
    for field in fields:
        value = item.get(field)
        if not isinstance(value, list) or (not value and field not in allow_empty):
            suffix = " non-empty" if field not in allow_empty else ""
            errors.append(f"{label} field {field} must be a{suffix} list")


def main():
    args = args_parser()
    root = os.path.abspath(args.repo_root)
    errors, warnings = [], []
    try:
        requirement_document = load(os.path.join(root, args.requirements))
        module_document = load(os.path.join(root, args.modules))
        plan = load(os.path.join(root, args.plan))
        plan_schema = load(os.path.join(root, args.plan_schema))
        jsonschema.Draft202012Validator.check_schema(plan_schema)
        jsonschema.Draft202012Validator(plan_schema, format_checker=jsonschema.FormatChecker()).validate(plan)
    except Exception as exc:
        emit("FAIL", f"Program Plan schema violation or readiness data load failure: {exc}")
        return 1

    if requirement_document.get("version") != 2:
        errors.append("Requirements index version must be 2")
    if module_document.get("version") != 2:
        errors.append("Module ownership version must be 2")
    if plan.get("sourceOfTruth") != args.plan:
        errors.append("Program Plan sourceOfTruth must equal its canonical path")
    if not ref_exists(root, requirement_document.get("sourceOfTruth")):
        errors.append("Requirements sourceOfTruth does not exist")
    for key, value in plan.get("authority", {}).items():
        if not ref_exists(root, value):
            errors.append(f"Program Plan authority reference does not exist: {key}={value}")

    requirements = requirement_document.get("requirements") or []
    modules = module_document.get("modules") or []
    namespaces = module_document.get("contractNamespaces") or []
    tasks = plan.get("tasks") or []
    pocs = plan.get("pocs") or []
    waves = plan.get("waves") or []
    foundations = plan.get("foundationTasks") or []
    requirement_ids = unique_ids(requirements, "id", "Requirement", errors)
    module_ids = unique_ids(modules, "id", "Module", errors)
    namespace_ids = unique_ids(namespaces, "id", "Contract namespace", errors)
    task_ids = unique_ids(tasks, "taskId", "Program task", errors)
    poc_ids = unique_ids(pocs, "pocId", "POC", errors)
    poc_task_ids = unique_ids(pocs, "taskId", "POC task", errors)
    wave_ids = unique_ids(waves, "id", "Wave", errors)
    foundation_ids = unique_ids(foundations, "taskId", "Foundation task", errors)
    all_task_ids = task_ids | foundation_ids
    requirement_by_id = {item.get("id"): item for item in requirements}
    module_by_id = {item.get("id"): item for item in modules}

    aliases = {}
    for requirement in requirements:
        requirement_id = requirement.get("id", "<unknown>")
        if not REQ_RE.fullmatch(str(requirement_id)):
            errors.append(f"Requirement ID format invalid: {requirement_id}")
        if requirement.get("status") not in REQ_STATES:
            errors.append(f"Requirement {requirement_id} has invalid status")
        if requirement.get("machineContractState") not in CONTRACT_STATES:
            errors.append(f"Requirement {requirement_id} has invalid machineContractState")
        if requirement.get("implementationState") not in IMPL_STATES:
            errors.append(f"Requirement {requirement_id} has invalid implementationState")
        require_lists(requirement, ["aliases", "designRefs", "moduleIds", "workPackages", "acceptanceIds", "nextTasks"], f"Requirement {requirement_id}", errors)
        if not ref_exists(root, requirement.get("source")):
            errors.append(f"Requirement {requirement_id} source does not exist")
        for reference in requirement.get("designRefs", []):
            if not ref_exists(root, reference):
                errors.append(f"Requirement {requirement_id} design reference does not exist: {reference}")
        for module_id in requirement.get("moduleIds", []):
            if module_id not in module_ids:
                errors.append(f"Requirement {requirement_id} references unknown module {module_id}")
            elif requirement_id not in module_by_id[module_id].get("requirementIds", []):
                errors.append(f"Requirement/module mapping is asymmetric: {requirement_id} -> {module_id} only")
        for next_task in requirement.get("nextTasks", []):
            if next_task not in task_ids:
                errors.append(f"Requirement {requirement_id} references unknown next task {next_task}")
        for alias in requirement.get("aliases", []):
            if alias in aliases and aliases[alias] != requirement_id:
                errors.append(f"Alias {alias} is assigned to two requirements")
            aliases[alias] = requirement_id

    module_graph, schema_owners, owned_paths = {}, {}, []
    for module in modules:
        module_id = module.get("id", "<unknown>")
        if not MOD_RE.fullmatch(str(module_id)):
            errors.append(f"Module ID format invalid: {module_id}")
        if module.get("status") not in MODULE_STATES:
            errors.append(f"Module {module_id} has invalid status")
        require_lists(module, ["ownedPaths", "requirementIds", "workPackages"], f"Module {module_id}", errors)
        require_lists(module, ["ownedSchemas", "providedContracts", "consumedContracts", "dependsOn"], f"Module {module_id}", errors, allow_empty=("ownedSchemas", "providedContracts", "consumedContracts", "dependsOn"))
        for dependency in module.get("dependsOn", []):
            if dependency not in module_ids:
                errors.append(f"Module {module_id} depends on unknown module {dependency}")
        module_graph[module_id] = module.get("dependsOn", [])
        for requirement_id in module.get("requirementIds", []):
            if requirement_id not in requirement_ids:
                errors.append(f"Module {module_id} references unknown requirement {requirement_id}")
            elif module_id not in requirement_by_id[requirement_id].get("moduleIds", []):
                errors.append(f"Requirement/module mapping is asymmetric: {module_id} -> {requirement_id} only")
        for schema in module.get("ownedSchemas", []):
            if schema in schema_owners:
                errors.append(f"Schema {schema} is owned by both {schema_owners[schema]} and {module_id}")
            schema_owners[schema] = module_id
        for path in module.get("ownedPaths", []):
            if norm(path) in {"", "*", "**"}:
                errors.append(f"Module {module_id} may not own the entire repository")
            owned_paths.append((module_id, path))
    if cycle(module_graph):
        errors.append("Module dependency graph contains a cycle")
    for index, (left_module, left_path) in enumerate(owned_paths):
        for right_module, right_path in owned_paths[index + 1 :]:
            if left_module != right_module and overlaps(left_path, right_path):
                errors.append(f"Module path ownership overlaps: {left_module}:{left_path} and {right_module}:{right_path}")

    namespace_by_id = {}
    namespace_paths = []
    for namespace in namespaces:
        namespace_id = namespace.get("id", "<unknown>")
        owner = namespace.get("ownerModule")
        consumers = namespace.get("consumerModules")
        writers = namespace.get("sharedWriterModules")
        if owner not in module_ids:
            errors.append(f"Contract namespace {namespace_id} has unknown owner {owner}")
        if not isinstance(consumers, list) or not isinstance(writers, list):
            errors.append(f"Contract namespace {namespace_id} consumer/shared-writer fields must be lists")
            continue
        for module_id in consumers + writers:
            if module_id not in module_ids:
                errors.append(f"Contract namespace {namespace_id} references unknown module {module_id}")
        if owner in writers or set(consumers) & set(writers):
            errors.append(f"Contract namespace {namespace_id} owner/consumer/shared-writer roles overlap")
        namespace_by_id[namespace_id] = namespace
        namespace_paths.append((namespace_id, namespace.get("pattern", "")))
    for index, (left_namespace, left_path) in enumerate(namespace_paths):
        for right_namespace, right_path in namespace_paths[index + 1 :]:
            if overlaps(left_path, right_path):
                errors.append(f"Contract namespace patterns overlap: {left_namespace}:{left_path} and {right_namespace}:{right_path}")
    for module in modules:
        module_id = module["id"]
        for namespace_id in module.get("providedContracts", []):
            if namespace_id not in namespace_ids:
                errors.append(f"Module {module_id} provides unknown contract {namespace_id}")
            elif namespace_by_id[namespace_id].get("ownerModule") != module_id and module_id not in namespace_by_id[namespace_id].get("sharedWriterModules", []):
                errors.append(f"Module {module_id} is not an owner/shared writer of {namespace_id}")
        for namespace_id in module.get("consumedContracts", []):
            if namespace_id not in namespace_ids:
                errors.append(f"Module {module_id} consumes unknown contract {namespace_id}")
            elif module_id not in namespace_by_id[namespace_id].get("consumerModules", []):
                errors.append(f"Module {module_id} is not declared as consumer of {namespace_id}")
    for namespace_id, namespace in namespace_by_id.items():
        owner = namespace.get("ownerModule")
        if namespace_id not in module_by_id.get(owner, {}).get("providedContracts", []):
            errors.append(f"Contract namespace {namespace_id} missing from owner module {owner} providedContracts")
        for module_id in namespace.get("consumerModules", []):
            if namespace_id not in module_by_id.get(module_id, {}).get("consumedContracts", []):
                errors.append(f"Contract namespace {namespace_id} consumer {module_id} does not list it as consumed")

    wave_by_id = {wave["id"]: wave for wave in waves}
    if sorted(wave["order"] for wave in waves) != list(range(1, len(waves) + 1)):
        errors.append("Wave order must be unique and contiguous from 1")
    expected_pocs = {f"POC-{index:02d}" for index in range(1, 11)}
    expected_poc_tasks = {f"POC-{index:03d}" for index in range(1, 11)}
    if poc_ids != expected_pocs or poc_task_ids != expected_poc_tasks:
        errors.append("Program Plan must map exactly POC-01..10 to POC-001..010")
    for poc in pocs:
        if poc.get("taskId") not in task_ids:
            errors.append(f"POC {poc.get('pocId')} task is missing from Program Plan tasks")
        else:
            planned = next(task for task in tasks if task.get("taskId") == poc.get("taskId"))
            if set(planned.get("requirementIds", [])) != set(poc.get("requirementIds", [])) or set(planned.get("moduleIds", [])) != set(poc.get("moduleIds", [])):
                errors.append(f"POC {poc.get('pocId')} requirement/module mapping differs from task {poc.get('taskId')}")
        for requirement_id in poc.get("requirementIds", []):
            if requirement_id not in requirement_ids:
                errors.append(f"POC {poc.get('pocId')} references unknown requirement {requirement_id}")
        for module_id in poc.get("moduleIds", []):
            if module_id not in module_ids:
                errors.append(f"POC {poc.get('pocId')} references unknown module {module_id}")

    graph, tasks_by_wave, contract_producers = {}, defaultdict(list), {}
    covered_requirements = set()
    for task in tasks:
        task_id = task.get("taskId", "<unknown>")
        if not TASK_RE.fullmatch(str(task_id)):
            errors.append(f"Planned task ID format invalid: {task_id}")
        if task.get("riskLevel") not in RISKS:
            errors.append(f"Planned task {task_id} has invalid riskLevel")
        if task.get("wave") not in wave_ids:
            errors.append(f"Planned task {task_id} references unknown wave")
        require_lists(task, ["requirementIds", "moduleIds", "outputPaths"], f"Planned task {task_id}", errors)
        require_lists(task, ["dependsOn", "sharedPaths", "producesContracts", "consumesContracts", "acceptanceIds", "pocIds"], f"Planned task {task_id}", errors, allow_empty=("dependsOn", "sharedPaths", "producesContracts", "consumesContracts", "acceptanceIds", "pocIds"))
        graph[task_id] = task.get("dependsOn", [])
        tasks_by_wave[task.get("wave")].append(task)
        for dependency in task.get("dependsOn", []):
            if dependency not in all_task_ids:
                errors.append(f"Planned task {task_id} depends on unknown task {dependency}")
            elif dependency in task_ids and wave_by_id[next(item["wave"] for item in tasks if item["taskId"] == dependency)]["order"] > wave_by_id[task["wave"]]["order"]:
                errors.append(f"Planned task {task_id} depends on later-wave task {dependency}")
        for requirement_id in task.get("requirementIds", []):
            covered_requirements.add(requirement_id)
            if requirement_id not in requirement_ids:
                errors.append(f"Planned task {task_id} references unknown requirement {requirement_id}")
        for module_id in task.get("moduleIds", []):
            if module_id not in module_ids:
                errors.append(f"Planned task {task_id} references unknown module {module_id}")
        for poc_id in task.get("pocIds", []):
            if poc_id not in poc_ids:
                errors.append(f"Planned task {task_id} references unknown POC {poc_id}")
        for contract in task.get("producesContracts", []):
            if contract in contract_producers:
                errors.append(f"Contract {contract} is produced by both {contract_producers[contract]} and {task_id}")
            contract_producers[contract] = task_id
    if cycle(graph):
        errors.append("Planned task dependency graph contains a cycle")
    ancestor_cache = {}
    for task in tasks:
        task_id = task["taskId"]
        lineage = ancestors(task_id, graph, ancestor_cache)
        for contract in task.get("consumesContracts", []):
            producer = contract_producers.get(contract)
            if not producer:
                errors.append(f"Planned task {task_id} consumes unproduced contract: {contract}")
            elif producer not in lineage:
                errors.append(f"Planned task {task_id} consumes {contract} but producer {producer} is not a dependency ancestor")

    policy = plan.get("parallelPolicy", {})
    for wave_id, wave_tasks in tasks_by_wave.items():
        wave = wave_by_id.get(wave_id, {})
        if len(wave_tasks) > min(wave.get("maxConcurrent", 0), policy.get("maxActiveTasks", 0)):
            errors.append(f"Wave {wave_id} exceeds concurrent task capacity")
        high_tasks = [task for task in wave_tasks if task.get("riskLevel") in {"high", "critical"}]
        if len(high_tasks) > min(wave.get("maxHighRisk", 0), policy.get("maxHighRiskTasks", 0)):
            errors.append(f"Wave {wave_id} exceeds high-risk task capacity")
        if policy.get("criticalStandalone") and any(task.get("riskLevel") == "critical" for task in wave_tasks) and len(wave_tasks) != 1:
            errors.append(f"Wave {wave_id} contains a critical task that is not standalone")
        claims = []
        for task in wave_tasks:
            for path in task.get("outputPaths", []):
                claims.append((task, path, "exclusive"))
            for path in task.get("sharedPaths", []):
                claims.append((task, path, "shared"))
        for index, (left_task, left_path, left_kind) in enumerate(claims):
            for right_task, right_path, right_kind in claims[index + 1 :]:
                if left_task["taskId"] == right_task["taskId"] or not overlaps(left_path, right_path):
                    continue
                coordinated = left_kind == right_kind == "shared" and left_task.get("coordinationGroup") == right_task.get("coordinationGroup") and left_task.get("integrationOrder") != right_task.get("integrationOrder")
                if not coordinated:
                    errors.append(f"Wave {wave_id} output path conflict: {left_task['taskId']}:{left_path} and {right_task['taskId']}:{right_path}")

    uncovered = sorted(requirement_ids - covered_requirements)
    if uncovered:
        errors.append("Requirements without Program Plan coverage: " + ", ".join(uncovered))
    blockers = {blocker.get("id"): blocker for blocker in plan.get("externalBlockers", [])}
    final_task = plan.get("releasePolicy", {}).get("requiredFinalTask")
    if final_task not in task_ids or next((task for task in tasks if task["taskId"] == final_task), {}).get("riskLevel") != "critical":
        errors.append("Release policy final task must exist and be critical")
    if "BRANCH-PROTECTION" not in blockers or final_task not in blockers["BRANCH-PROTECTION"].get("requiredFor", []):
        errors.append("Branch protection blocker must gate the final release task")
    if blockers.get("BRANCH-PROTECTION", {}).get("status") != "resolved":
        warnings.append("GitHub main branch protection/Ruleset remains an external blocker")

    for foundation in foundations:
        task_id, state = foundation.get("taskId"), foundation.get("status")
        specification = task_file(root, task_id)
        if not specification:
            errors.append(f"Foundation task spec does not exist: {task_id}")
        elif state == "completed" and task_front_matter(specification).get("status") not in {"completed", "approved"}:
            errors.append(f"Completed foundation task {task_id} Task Spec is not closed")
    adr_path = os.path.join(root, "adr", "0014-multi-agent-coordination-and-integration.md")
    if os.path.isfile(adr_path) and "Status: Accepted" not in open(adr_path, encoding="utf-8").read():
        errors.append("ADR-0014 must be Accepted after the collaboration mechanism is active")

    for path in ["README.md", "docs/00-guize-engineering-design-baseline.md"]:
        try:
            if "V1 不设置对外 Beta" not in open(os.path.join(root, path), encoding="utf-8").read():
                errors.append(f"Frozen delivery invariant missing from {path}: V1 不设置对外 Beta")
        except OSError:
            errors.append(f"Invariant file missing: {path}")
    baseline = os.path.join(root, "docs", "00-guize-engineering-design-baseline.md")
    try:
        text = open(baseline, encoding="utf-8").read()
        for heading in ["## 7.", "## 8.", "## 9.", "## 10.", "## 13.", "## 14.", "## 16.", "## 18."]:
            if heading not in text:
                errors.append(f"Engineering baseline missing required section prefix: {heading}")
    except OSError:
        errors.append("Engineering baseline is missing")

    contract_gaps = sorted(requirement["id"] for requirement in requirements if requirement.get("machineContractState") not in {"frozen", "implemented"})
    implementation_gaps = sorted(requirement["id"] for requirement in requirements if requirement.get("implementationState") not in {"implemented", "verified"})
    if args.strict_ready and (contract_gaps or implementation_gaps or any(blocker.get("status") == "open" for blocker in blockers.values())):
        errors.append("Strict readiness requested but contract, implementation or external gaps remain")
    else:
        if contract_gaps:
            warnings.append(f"Machine contracts not frozen for {len(contract_gaps)} requirements")
        if implementation_gaps:
            warnings.append(f"Implementation not verified for {len(implementation_gaps)} requirements")

    for error in errors:
        emit("FAIL", error)
    for warning in warnings:
        emit("WARN", warning)
    if errors:
        return 1
    emit("PASS", "Project readiness indexes and Program Plan are structurally consistent", {"requirements": len(requirements), "modules": len(modules), "contractNamespaces": len(namespaces), "plannedTasks": len(tasks), "pocs": len(pocs), "waves": len(waves), "contractGapCount": len(contract_gaps), "implementationGapCount": len(implementation_gaps)})
    return 0


if __name__ == "__main__":
    sys.exit(main())

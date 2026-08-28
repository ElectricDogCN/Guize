#!/usr/bin/env python3
"""Fail-closed validation for Guize multi-agent work reservations."""

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime, timezone

import jsonschema
import yaml

ACTIVE_STATUSES = {"reserved", "in_progress", "blocked", "review", "integration"}
HIGH_RISKS = {"high", "critical"}
TASK_RE = re.compile(r"^[A-Z]+-\d+$")
BRANCH_RE = re.compile(r"^(feat|fix|docs|refactor|chore)/([A-Z]+-\d+)-.+$")
GLOB_CHARS = "*?["


def parse_args():
    parser = argparse.ArgumentParser(description="Validate active multi-agent reservations")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry", default="specs/coordination/active-work.yaml")
    parser.add_argument("--schema", default="specs/coordination/active-work.schema.yaml")
    parser.add_argument("--task", default="")
    parser.add_argument("--now", default="", help="ISO-8601 UTC timestamp for deterministic tests")
    return parser.parse_args()


def report(status, message, details=None):
    payload = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_time(value):
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


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


def parse_front_matter(path):
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    data = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


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
    lp = static_prefix(left)
    rp = static_prefix(right)
    if not lp or not rp:
        return True
    return lp == rp or lp.startswith(rp + "/") or rp.startswith(lp + "/")


def detect_cycle(graph):
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


def validate_task_context(root, task_id, registry, errors, warnings):
    task_path = find_task_file(root, task_id)
    if not task_path:
        errors.append(f"Task spec not found for {task_id}")
        return
    front = parse_front_matter(task_path)
    schema_version = str(front.get("schemaVersion", "1"))
    if schema_version != "2":
        warnings.append(f"{task_id} uses legacy Task Spec schemaVersion {schema_version}; registry linkage not enforced")
        return
    mode = front.get("coordinationMode", "")
    if mode == "bootstrap":
        allowed = registry.get("policy", {}).get("bootstrapTasks", [])
        if task_id not in allowed:
            errors.append(f"Bootstrap task {task_id} is not allowlisted by registry policy")
        return
    if mode != "registry":
        errors.append(f"Unsupported coordinationMode for {task_id}: {mode}")
        return
    entries = [entry for entry in registry.get("tasks", []) if entry.get("taskId") == task_id]
    if len(entries) != 1:
        errors.append(f"Task {task_id} must have exactly one active-work entry")
        return
    entry = entries[0]
    comparisons = {
        "workBranch": "branch",
        "baseBranch": "baseBranch",
        "baseSha": "baseSha",
        "riskLevel": "riskLevel",
        "coordinationGroup": "coordinationGroup",
        "handoffPath": "handoffPath",
        "integrationStrategy": "integrationStrategy",
    }
    for task_key, registry_key in comparisons.items():
        if front.get(task_key, "") != str(entry.get(registry_key, "")):
            errors.append(
                f"Task {task_id} mismatch: front matter {task_key}={front.get(task_key)!r}, "
                f"registry {registry_key}={entry.get(registry_key)!r}"
            )


def main():
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    registry_path = os.path.join(root, args.registry)
    schema_path = os.path.join(root, args.schema)
    errors = []
    warnings = []

    try:
        registry = load_yaml(registry_path)
        schema = load_yaml(schema_path)
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(registry)
    except Exception as exc:
        report("FAIL", f"Cannot validate active-work registry: {exc}")
        sys.exit(1)

    try:
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    except Exception as exc:
        report("ERROR", f"Invalid --now timestamp: {exc}")
        sys.exit(2)

    tasks = registry.get("tasks", [])
    active = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
    policy = registry.get("policy", {})

    if len(active) > policy.get("maxActiveTasks", 0):
        errors.append(f"Active task count {len(active)} exceeds limit {policy.get('maxActiveTasks')}")
    high_count = sum(1 for task in active if task.get("riskLevel") in HIGH_RISKS)
    if high_count > policy.get("maxHighRiskTasks", 0):
        errors.append(f"High/critical active task count {high_count} exceeds limit {policy.get('maxHighRiskTasks')}")

    seen_task_ids = set()
    seen_branches = set()
    seen_handoffs = set()
    active_ids = {task.get("taskId") for task in active}
    graph = {}

    for task in tasks:
        task_id = task.get("taskId", "")
        if task_id in seen_task_ids:
            errors.append(f"Duplicate taskId in registry: {task_id}")
        seen_task_ids.add(task_id)
        branch = task.get("branch", "")
        if branch in seen_branches:
            errors.append(f"Duplicate branch in registry: {branch}")
        seen_branches.add(branch)
        handoff = task.get("handoffPath", "")
        if handoff in seen_handoffs:
            errors.append(f"Duplicate handoffPath in registry: {handoff}")
        seen_handoffs.add(handoff)

        match = BRANCH_RE.fullmatch(branch)
        if not match or match.group(2) != task_id:
            errors.append(f"Branch does not match task ID {task_id}: {branch}")
        if branch == task.get("baseBranch") or branch == "main":
            errors.append(f"Task {task_id} work branch must differ from base/main")
        if task_id in task.get("dependsOn", []):
            errors.append(f"Task {task_id} cannot depend on itself")

        task_path = find_task_file(root, task_id)
        if not task_path:
            errors.append(f"Registry entry has no Task Spec: {task_id}")

        if task.get("status") in ACTIVE_STATUSES:
            try:
                acquired = parse_time(task["lease"]["acquiredAt"])
                expires = parse_time(task["lease"]["expiresAt"])
                if expires <= acquired:
                    errors.append(f"Task {task_id} lease expires before acquisition")
                if expires <= now:
                    errors.append(f"Task {task_id} lease expired at {expires.isoformat()}")
                duration_hours = (expires - acquired).total_seconds() / 3600
                if duration_hours > policy.get("leaseMaxHours", 0):
                    errors.append(f"Task {task_id} lease {duration_hours:.1f}h exceeds maximum")
            except Exception as exc:
                errors.append(f"Task {task_id} has invalid lease: {exc}")
            graph[task_id] = list(task.get("dependsOn", []))

        all_paths = list(task.get("exclusivePaths", [])) + list(task.get("sharedPaths", []))
        if len({normalize_pattern(path) for path in all_paths}) != len(all_paths):
            errors.append(f"Task {task_id} contains duplicate path claims")
        if any(normalize_pattern(path) in {"**", "*", ""} for path in all_paths):
            errors.append(f"Task {task_id} may not reserve the entire repository")

    for task in active:
        for dependency in task.get("dependsOn", []):
            if dependency not in seen_task_ids and not find_task_file(root, dependency):
                errors.append(f"Task {task['taskId']} depends on unknown task {dependency}")
    if detect_cycle(graph):
        errors.append("Active task dependency graph contains a cycle")

    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            for left_path in left.get("exclusivePaths", []):
                for right_path in right.get("exclusivePaths", []) + right.get("sharedPaths", []):
                    if patterns_overlap(left_path, right_path):
                        errors.append(
                            f"Exclusive path conflict: {left['taskId']}:{left_path} overlaps "
                            f"{right['taskId']}:{right_path}"
                        )
            for right_path in right.get("exclusivePaths", []):
                for left_path in left.get("sharedPaths", []):
                    if patterns_overlap(left_path, right_path):
                        errors.append(
                            f"Exclusive path conflict: {right['taskId']}:{right_path} overlaps "
                            f"{left['taskId']}:{left_path}"
                        )
            for left_path in left.get("sharedPaths", []):
                for right_path in right.get("sharedPaths", []):
                    if not patterns_overlap(left_path, right_path):
                        continue
                    same_group = left.get("coordinationGroup") and left.get("coordinationGroup") == right.get("coordinationGroup")
                    distinct_order = left.get("integrationOrder") != right.get("integrationOrder")
                    if not same_group or not distinct_order:
                        errors.append(
                            f"Uncoordinated shared path: {left['taskId']}:{left_path} and "
                            f"{right['taskId']}:{right_path} require same group and distinct integrationOrder"
                        )

    if args.task:
        if not TASK_RE.fullmatch(args.task):
            errors.append(f"Invalid task ID: {args.task}")
        else:
            validate_task_context(root, args.task, registry, errors, warnings)

    for error in errors:
        report("FAIL", error)
    for warning in warnings:
        report("WARN", warning)
    if errors:
        sys.exit(1)
    report(
        "PASS",
        f"Agent coordination valid: {len(active)} active tasks, {high_count} high/critical",
        {"activeTaskIds": sorted(active_ids)},
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fail-closed validation for Guize multi-agent work reservations."""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import jsonschema
import yaml

ACTIVE_STATUSES = {"reserved", "in_progress", "blocked", "review", "integration"}
HIGH_RISKS = {"high", "critical"}
TASK_RE = re.compile(r"^[A-Z]+-\d+$")
BRANCH_RE = re.compile(r"^(feat|fix|docs|refactor|chore)/([A-Z]+-\d+)-.+$")
PLACEHOLDERS = {"", "pending", "tbd", "unknown", "none", "n/a", "na", "unassigned"}
GLOB_CHARS = "*?["


def parse_args():
    parser = argparse.ArgumentParser(description="Validate active multi-agent reservations")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry", default="specs/coordination/active-work.yaml")
    parser.add_argument("--schema", default="specs/coordination/active-work.schema.yaml")
    parser.add_argument("--task", default="")
    parser.add_argument("--now", default="", help="ISO-8601 UTC timestamp for deterministic tests")
    parser.add_argument("--base-ref", default="", help="Current integration base ref, e.g. origin/main")
    parser.add_argument("--head-ref", default="", help="Actual PR head ref, e.g. origin/feat/GZ-101-x")
    parser.add_argument("--branch-name", default="", help="Actual PR branch name without origin/")
    return parser.parse_args()


def report(status, message, details=None):
    payload = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def json_ready(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json_ready(yaml.safe_load(handle))


def parse_time(value):
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


def parse_task(path):
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    data = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, parts[2].strip()


def parse_task_list(value):
    text = str(value or "").strip().strip("[]")
    if text.lower() in PLACEHOLDERS or text.upper() == "NONE":
        return []
    return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]


def extract_section(body, names):
    wanted = [name.lower() for name in names]
    lines = body.splitlines()
    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        title = re.sub(r"^##\s+", "", stripped).strip().lower()
        title = re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", title)
        if any(name in title for name in wanted):
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].strip().startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _looks_like_path_pattern(value):
    value = value.strip()
    if not value or value.lower() in PLACEHOLDERS or value == "无":
        return False
    return (
        "/" in value
        or value.startswith(".")
        or any(token in value for token in ("*", "?", "["))
        or bool(re.search(r"\.[A-Za-z0-9_-]+$", value))
    )


def _bullet_pattern(stripped):
    bullet = re.match(r"[-*]\s+(.+?)\s*$", stripped)
    if not bullet:
        return None
    value = bullet.group(1).strip()
    backticked = re.search(r"`([^`]+)`", value)
    if backticked:
        value = backticked.group(1).strip()
    if not _looks_like_path_pattern(value):
        return None
    return normalize_pattern(value)


def extract_path_patterns(body, names):
    section = extract_section(body, names)
    if section is None:
        return None
    patterns = []
    for line in section.splitlines():
        pattern = _bullet_pattern(line.strip())
        if pattern:
            patterns.append(pattern)
    return patterns


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


def _glob_regex(pattern):
    output = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                output.append(".*")
                index += 2
                continue
            output.append("[^/]*")
        elif char == "?":
            output.append("[^/]")
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end == -1:
                output.append(r"\[")
            else:
                content = pattern[index + 1 : end]
                if content.startswith("!"):
                    content = "^" + content[1:]
                output.append("[" + content + "]")
                index = end
        else:
            output.append(re.escape(char))
        index += 1
    return "".join(output)


def match_pattern(filepath, pattern):
    filepath = normalize_pattern(filepath)
    pattern = normalize_pattern(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return filepath == prefix or filepath.startswith(prefix + "/")
    if any(token in pattern for token in ("*", "?", "[")):
        return re.fullmatch(_glob_regex(pattern), filepath) is not None
    if not os.path.splitext(pattern)[1]:
        return filepath == pattern or filepath.startswith(pattern + "/")
    return filepath == pattern


def run_git(root, args):
    try:
        result = subprocess.run(["git"] + list(args), cwd=root, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def ref_exists(root, ref):
    return run_git(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"]) [0] == 0


def is_ancestor(root, ancestor, descendant):
    return run_git(root, ["merge-base", "--is-ancestor", ancestor, descendant])[0] == 0


def changed_files(root, base_ref, head_ref):
    code, output, _ = run_git(root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
    if code != 0:
        return None
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def clean_branch_name(value):
    name = str(value or "").strip()
    for prefix in ("refs/remotes/origin/", "refs/heads/", "origin/"):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


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


def role_is_placeholder(value):
    return str(value or "").strip().lower() in PLACEHOLDERS


def validate_git_context(root, task_id, front, base_ref, head_ref, errors):
    if not base_ref and not head_ref:
        return
    if not base_ref or not head_ref:
        errors.append("Both --base-ref and --head-ref are required for freshness validation")
        return
    if not ref_exists(root, base_ref):
        errors.append(f"Base ref does not exist: {base_ref}")
        return
    if not ref_exists(root, head_ref):
        errors.append(f"Head ref does not exist: {head_ref}")
        return
    if not is_ancestor(root, base_ref, head_ref):
        errors.append(f"Task {task_id} head {head_ref} does not contain latest base {base_ref}")
    base_sha = front.get("baseSha", "")
    if base_sha:
        if not ref_exists(root, base_sha):
            errors.append(f"Task {task_id} baseSha does not exist: {base_sha}")
        else:
            if not is_ancestor(root, base_sha, head_ref):
                errors.append(f"Task {task_id} baseSha is not an ancestor of {head_ref}")
            if not is_ancestor(root, base_sha, base_ref):
                errors.append(f"Task {task_id} baseSha is not an ancestor of {base_ref}")


def is_coordination_metadata(filepath, task_id, task_path, root):
    task_relative = os.path.relpath(task_path, root).replace("\\", "/")
    return (
        filepath == task_relative
        or filepath == "specs/coordination/active-work.yaml"
        or filepath == f"evidence/{task_id}"
        or filepath.startswith(f"evidence/{task_id}/")
    )


def validate_task_context(root, task_id, registry, errors, warnings, base_ref="", head_ref="", branch_name=""):
    task_path = find_task_file(root, task_id)
    if not task_path:
        errors.append(f"Task spec not found for {task_id}")
        return
    front, body = parse_task(task_path)
    schema_version = str(front.get("schemaVersion", "1"))
    if schema_version != "2":
        warnings.append(f"{task_id} uses legacy Task Spec schemaVersion {schema_version}; registry linkage not enforced")
        return

    validate_git_context(root, task_id, front, base_ref, head_ref, errors)
    mode = front.get("coordinationMode", "")
    actual_branch = clean_branch_name(branch_name or head_ref)
    if mode == "bootstrap":
        allowed = registry.get("policy", {}).get("bootstrapTasks", [])
        if task_id not in allowed:
            errors.append(f"Bootstrap task {task_id} is not allowlisted by registry policy")
        if actual_branch and actual_branch != front.get("workBranch"):
            errors.append(f"Bootstrap task branch mismatch: expected {front.get('workBranch')}, got {actual_branch}")
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
        "status": "status",
        "riskLevel": "riskLevel",
        "taskOwner": "owner",
        "agentRole": "agentRole",
        "coordinator": "coordinator",
        "implementer": "implementer",
        "reviewer": "reviewer",
        "integrator": "integrator",
        "workPackage": "workPackage",
        "coordinationGroup": "coordinationGroup",
        "handoffPath": "handoffPath",
        "integrationStrategy": "integrationStrategy",
    }
    for task_key, registry_key in comparisons.items():
        if str(front.get(task_key, "")) != str(entry.get(registry_key, "")):
            errors.append(
                f"Task {task_id} mismatch: front matter {task_key}={front.get(task_key)!r}, "
                f"registry {registry_key}={entry.get(registry_key)!r}"
            )

    try:
        if int(front.get("integrationOrder", "0")) != int(entry.get("integrationOrder", 0)):
            errors.append(f"Task {task_id} integrationOrder does not match registry")
    except ValueError:
        errors.append(f"Task {task_id} integrationOrder is not an integer")
    try:
        if parse_time(front.get("leaseExpiresAt", "")) != parse_time(entry["lease"]["expiresAt"]):
            errors.append(f"Task {task_id} leaseExpiresAt does not match registry")
    except Exception as exc:
        errors.append(f"Task {task_id} lease comparison failed: {exc}")

    if parse_task_list(front.get("dependsOn")) != list(entry.get("dependsOn", [])):
        errors.append(f"Task {task_id} dependsOn does not match registry ordering/content")

    task_exclusive = extract_path_patterns(body, ["独占写范围", "exclusive write scope"])
    task_shared = extract_path_patterns(body, ["共享修改范围", "shared modification scope"])
    if task_exclusive is None or task_shared is None:
        errors.append(f"Task {task_id} is missing exclusive/shared path sections")
    else:
        registry_exclusive = [normalize_pattern(path) for path in entry.get("exclusivePaths", [])]
        registry_shared = [normalize_pattern(path) for path in entry.get("sharedPaths", [])]
        if task_exclusive != registry_exclusive:
            errors.append(f"Task {task_id} exclusive path claims do not exactly match registry")
        if task_shared != registry_shared:
            errors.append(f"Task {task_id} shared path claims do not exactly match registry")

    if actual_branch:
        match = BRANCH_RE.fullmatch(actual_branch)
        if not match or match.group(2) != task_id:
            errors.append(f"Actual branch does not carry task ID {task_id}: {actual_branch}")
        elif entry.get("status") != "reserved" and actual_branch != entry.get("branch"):
            errors.append(f"Task {task_id} must run on registered branch {entry.get('branch')}, got {actual_branch}")

    if base_ref and head_ref and task_exclusive is not None and task_shared is not None:
        files = changed_files(root, base_ref, head_ref)
        if files is None:
            errors.append(f"Cannot determine changed files for {base_ref}...{head_ref}")
        else:
            claims = list(entry.get("exclusivePaths", [])) + list(entry.get("sharedPaths", []))
            unclaimed = []
            for filepath in files:
                if is_coordination_metadata(filepath, task_id, task_path, root):
                    continue
                if not any(match_pattern(filepath, pattern) for pattern in claims):
                    unclaimed.append(filepath)
            if unclaimed:
                errors.append(f"Task {task_id} changed files outside registered path claims: {unclaimed}")


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
        if not find_task_file(root, task_id):
            errors.append(f"Registry entry has no Task Spec: {task_id}")

        all_paths = list(task.get("exclusivePaths", [])) + list(task.get("sharedPaths", []))
        if len({normalize_pattern(path) for path in all_paths}) != len(all_paths):
            errors.append(f"Task {task_id} contains duplicate path claims")
        if any(normalize_pattern(path) in {"**", "*", ""} for path in all_paths):
            errors.append(f"Task {task_id} may not reserve the entire repository")

        if task.get("status") in ACTIVE_STATUSES:
            if task.get("riskLevel") in HIGH_RISKS:
                implementer = task.get("implementer", "")
                reviewer = task.get("reviewer", "")
                if role_is_placeholder(implementer) or role_is_placeholder(reviewer):
                    errors.append(f"High/critical task {task_id} must assign real implementer and reviewer identities")
                elif implementer == reviewer:
                    errors.append(f"High/critical task {task_id} implementer and reviewer must differ")
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
            validate_task_context(
                root,
                args.task,
                registry,
                errors,
                warnings,
                args.base_ref.strip(),
                args.head_ref.strip(),
                args.branch_name.strip(),
            )

    for error in errors:
        report("FAIL", error)
    for warning in warnings:
        report("WARN", warning)
    if errors:
        sys.exit(1)
    report(
        "PASS",
        f"Agent coordination valid: {len(active)} active tasks, {high_count} high/critical",
        {"activeTaskIds": sorted(task.get("taskId") for task in active)},
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

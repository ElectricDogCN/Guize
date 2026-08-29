#!/usr/bin/env python3
"""Fail-closed validation for Guize multi-agent reservations and completions."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import jsonschema
import yaml

ACTIVE_STATUSES = {"reserved", "in_progress", "blocked", "review", "integration"}
HIGH_RISKS = {"high", "critical"}
COMPLETED_STATUSES = {"completed", "approved"}
TASK_RE = re.compile(r"^[A-Z]+-\d+$")
BRANCH_RE = re.compile(r"^(feat|fix|docs|refactor|chore)/([A-Z]+-\d+)-.+$")
PLACEHOLDERS = {"", "pending", "tbd", "unknown", "none", "n/a", "na", "unassigned"}
GLOB_CHARS = "*?["
CANONICAL_PLAN = "specs/coordination/program-plan.yaml"
CANONICAL_COMPLETIONS = "specs/coordination/task-completions.yaml"
CANONICAL_ACTIVE_WORK = "specs/coordination/active-work.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate active multi-agent reservations")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry", default=CANONICAL_ACTIVE_WORK)
    parser.add_argument("--schema", default="specs/coordination/active-work.schema.yaml")
    parser.add_argument("--task", default="")
    parser.add_argument("--now", default="", help="ISO-8601 UTC timestamp for deterministic tests")
    parser.add_argument("--base-ref", default="", help="Current integration base ref, e.g. origin/main")
    parser.add_argument("--head-ref", default="", help="Actual PR head ref, e.g. HEAD")
    parser.add_argument("--branch-name", default="", help="Actual PR branch name without origin/")
    return parser.parse_args()


def report(status: str, message: str, details: Any | None = None) -> None:
    payload: dict[str, Any] = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def load_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json_ready(yaml.safe_load(handle))


def parse_time(value: Any) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def find_task_file(root: str, task_id: str) -> str | None:
    directory = os.path.join(root, "specs", "tasks")
    exact = os.path.join(directory, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    matches: list[str] = []
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if name.startswith(f"{task_id}-") and name.endswith(".md"):
                matches.append(os.path.join(directory, name))
    return matches[0] if len(matches) == 1 else None


def parse_task(path: str) -> tuple[dict[str, Any], str]:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        document = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, content
    return (json_ready(document) if isinstance(document, dict) else {}), parts[2].strip()


def parse_task_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip().strip("[]")
    if text.lower() in PLACEHOLDERS or text.upper() == "NONE":
        return []
    return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]


def extract_section(body: str, names: list[str]) -> str | None:
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


def normalize_pattern(value: Any) -> str:
    text = str(value).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    text = re.sub(r"/+", "/", text)
    return text.rstrip("/")


def bullet_pattern(stripped: str) -> str | None:
    bullet = re.match(r"[-*]\s+(.+?)\s*$", stripped)
    if not bullet:
        return None
    value = bullet.group(1).strip()
    backticked = re.search(r"`([^`]+)`", value)
    if backticked:
        value = backticked.group(1).strip()
    if not value or value.lower() in PLACEHOLDERS or value in {"无", "无。"}:
        return None
    looks_like_path = (
        "/" in value
        or value.startswith(".")
        or any(token in value for token in ("*", "?", "["))
        or bool(re.search(r"\.[A-Za-z0-9_-]+$", value))
    )
    return normalize_pattern(value) if looks_like_path else None


def extract_path_patterns(body: str, names: list[str]) -> list[str] | None:
    section = extract_section(body, names)
    if section is None:
        return None
    patterns: list[str] = []
    for line in section.splitlines():
        pattern = bullet_pattern(line.strip())
        if pattern:
            patterns.append(pattern)
    return patterns


def static_prefix(pattern: str) -> str:
    pattern = normalize_pattern(pattern)
    indexes = [pattern.find(char) for char in GLOB_CHARS if pattern.find(char) >= 0]
    if not indexes:
        return pattern
    return pattern[: min(indexes)].rstrip("/")


def patterns_overlap(left: str, right: str) -> bool:
    left = normalize_pattern(left)
    right = normalize_pattern(right)
    if not left or not right or left == right:
        return True
    if fnmatch.fnmatch(left, right) or fnmatch.fnmatch(right, left):
        return True
    left_prefix = static_prefix(left)
    right_prefix = static_prefix(right)
    return (
        not left_prefix
        or not right_prefix
        or left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
    )


def glob_regex(pattern: str) -> str:
    output: list[str] = []
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


def match_pattern(filepath: str, pattern: str) -> bool:
    filepath = normalize_pattern(filepath)
    pattern = normalize_pattern(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return filepath == prefix or filepath.startswith(prefix + "/")
    if any(token in pattern for token in ("*", "?", "[")):
        return re.fullmatch(glob_regex(pattern), filepath) is not None
    if not os.path.splitext(pattern)[1]:
        return filepath == pattern or filepath.startswith(pattern + "/")
    return filepath == pattern


def run_git(root: str, arguments: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def ref_exists(root: str, ref: str) -> bool:
    return run_git(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"]) [0] == 0


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return run_git(root, ["merge-base", "--is-ancestor", ancestor, descendant])[0] == 0


def changed_files(root: str, base_ref: str, head_ref: str) -> list[str] | None:
    code, output, _ = run_git(root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
    if code != 0:
        return None
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def yaml_from_ref(root: str, ref: str, relative: str) -> Any | None:
    if not ref_exists(root, ref):
        return None
    code, output, _ = run_git(root, ["show", f"{ref}:{relative}"])
    if code != 0:
        return None
    try:
        return json_ready(yaml.safe_load(output))
    except yaml.YAMLError:
        return None


def clean_branch_name(value: str) -> str:
    name = str(value or "").strip()
    for prefix in ("refs/remotes/origin/", "refs/heads/", "origin/"):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def detect_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
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


def role_is_placeholder(value: Any) -> bool:
    return str(value or "").strip().lower() in PLACEHOLDERS


def validate_git_context(
    root: str,
    task_id: str,
    front: dict[str, Any],
    base_ref: str,
    head_ref: str,
    errors: list[str],
) -> None:
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
    base_sha = str(front.get("baseSha") or "")
    if base_sha:
        if not ref_exists(root, base_sha):
            errors.append(f"Task {task_id} baseSha does not exist: {base_sha}")
        else:
            if not is_ancestor(root, base_sha, head_ref):
                errors.append(f"Task {task_id} baseSha is not an ancestor of {head_ref}")
            if not is_ancestor(root, base_sha, base_ref):
                errors.append(f"Task {task_id} baseSha is not an ancestor of {base_ref}")


def completion_metadata_paths(task_relative: str) -> set[str]:
    return {
        task_relative,
        CANONICAL_ACTIVE_WORK,
        CANONICAL_PLAN,
        CANONICAL_COMPLETIONS,
    }


def is_coordination_metadata(
    filepath: str,
    task_id: str,
    task_path: str,
    root: str,
    completion_mode: bool = False,
) -> bool:
    task_relative = os.path.relpath(task_path, root).replace("\\", "/")
    if (
        filepath == task_relative
        or filepath == CANONICAL_ACTIVE_WORK
        or filepath == f"evidence/{task_id}"
        or filepath.startswith(f"evidence/{task_id}/")
    ):
        return True
    return completion_mode and filepath in completion_metadata_paths(task_relative)


def load_completion_context(
    root: str,
    registry_relative: str,
    current_registry: dict[str, Any],
    task_id: str,
    base_ref: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not base_ref:
        errors.append(f"Completed task {task_id} requires --base-ref to validate the prior reservation")
        return None
    base_registry = yaml_from_ref(root, base_ref, registry_relative)
    if not isinstance(base_registry, dict):
        errors.append(f"Completed task {task_id} cannot read prior Active Work Registry from {base_ref}")
        return None
    entries = [item for item in base_registry.get("tasks", []) if item.get("taskId") == task_id]
    if len(entries) != 1:
        errors.append(
            f"Completed task {task_id} must have exactly one prior active-work entry in {base_ref}"
        )
        return None
    entry = entries[0]
    if entry.get("status") not in ACTIVE_STATUSES:
        errors.append(
            f"Completed task {task_id} prior Registry status must be active, got {entry.get('status')}"
        )
    if current_registry.get("policy") != base_registry.get("policy"):
        errors.append(f"Completed task {task_id} may not change Active Work policy")
    expected_tasks = [item for item in base_registry.get("tasks", []) if item.get("taskId") != task_id]
    if current_registry.get("tasks", []) != expected_tasks:
        errors.append(f"Completed task {task_id} may only remove its own prior Active Work entry")
    return entry


def validate_completion_snapshot(root: str, task_id: str, errors: list[str]) -> None:
    try:
        plan = load_yaml(os.path.join(root, CANONICAL_PLAN))
        ledger = load_yaml(os.path.join(root, CANONICAL_COMPLETIONS))
        active = load_yaml(os.path.join(root, CANONICAL_ACTIVE_WORK))
    except Exception as exc:
        errors.append(f"Completed task {task_id} cannot load completion control files: {exc}")
        return
    tasks = {item.get("taskId"): item for item in plan.get("tasks", [])}
    if tasks.get(task_id, {}).get("status") != "completed":
        errors.append(f"Completed task {task_id} Program Plan status is not completed")
    records = [item for item in ledger.get("records", []) if item.get("taskId") == task_id]
    if len(records) != 1:
        errors.append(f"Completed task {task_id} must have exactly one completion ledger record")
    if any(item.get("taskId") == task_id for item in active.get("tasks", [])):
        errors.append(f"Completed task {task_id} must be removed from Active Work Registry")


def compare_front_list(
    task_id: str,
    front: dict[str, Any],
    entry: dict[str, Any],
    task_key: str,
    registry_key: str,
    errors: list[str],
) -> None:
    if parse_task_list(front.get(task_key)) != list(entry.get(registry_key, [])):
        errors.append(f"Task {task_id} {task_key} does not match registry {registry_key}")


def validate_task_context(
    root: str,
    task_id: str,
    registry: dict[str, Any],
    registry_relative: str,
    errors: list[str],
    warnings: list[str],
    base_ref: str = "",
    head_ref: str = "",
    branch_name: str = "",
) -> None:
    task_path = find_task_file(root, task_id)
    if not task_path:
        errors.append(f"Task spec not found for {task_id}")
        return
    front, body = parse_task(task_path)
    schema_version = str(front.get("schemaVersion", "1"))
    if schema_version != "2":
        warnings.append(
            f"{task_id} uses legacy Task Spec schemaVersion {schema_version}; registry linkage not enforced"
        )
        return

    validate_git_context(root, task_id, front, base_ref, head_ref, errors)
    mode = str(front.get("coordinationMode") or "")
    actual_branch = clean_branch_name(branch_name or head_ref)
    if mode == "bootstrap":
        allowed = registry.get("policy", {}).get("bootstrapTasks", [])
        if task_id not in allowed:
            errors.append(f"Bootstrap task {task_id} is not allowlisted by registry policy")
        if actual_branch and actual_branch != front.get("workBranch"):
            errors.append(
                f"Bootstrap task branch mismatch: expected {front.get('workBranch')}, got {actual_branch}"
            )
        return
    if mode != "registry":
        errors.append(f"Unsupported coordinationMode for {task_id}: {mode}")
        return

    completion_mode = str(front.get("status") or "") in COMPLETED_STATUSES
    current_entries = [entry for entry in registry.get("tasks", []) if entry.get("taskId") == task_id]
    if len(current_entries) == 1:
        entry = current_entries[0]
        if completion_mode:
            errors.append(f"Completed task {task_id} must not remain in Active Work Registry")
    elif len(current_entries) == 0 and completion_mode:
        entry = load_completion_context(
            root, registry_relative, registry, task_id, base_ref, errors
        )
        if entry is None:
            return
        validate_completion_snapshot(root, task_id, errors)
    else:
        errors.append(f"Task {task_id} must have exactly one active-work entry")
        return

    stable_comparisons = {
        "baseBranch": "baseBranch",
        "riskLevel": "riskLevel",
        "taskOwner": "owner",
        "agentRole": "agentRole",
        "coordinator": "coordinator",
        "implementer": "implementer",
        "reviewer": "reviewer",
        "integrator": "integrator",
        "workPackage": "workPackage",
        "programPlan": "programPlan",
        "programTaskId": "programTaskId",
        "wave": "programWave",
        "coordinationGroup": "coordinationGroup",
        "handoffPath": "handoffPath",
        "integrationStrategy": "integrationStrategy",
    }
    comparisons = dict(stable_comparisons)
    if not completion_mode:
        comparisons.update({"workBranch": "branch", "baseSha": "baseSha", "status": "status"})
    for task_key, registry_key in comparisons.items():
        if str(front.get(task_key, "")) != str(entry.get(registry_key, "")):
            errors.append(
                f"Task {task_id} mismatch: front matter {task_key}={front.get(task_key)!r}, "
                f"registry {registry_key}={entry.get(registry_key)!r}"
            )

    for task_key, registry_key in (
        ("dependsOn", "dependsOn"),
        ("requirementIds", "requirementIds"),
        ("moduleIds", "moduleIds"),
        ("producesContracts", "producesContracts"),
        ("consumesContracts", "consumesContracts"),
    ):
        compare_front_list(task_id, front, entry, task_key, registry_key, errors)

    try:
        if int(front.get("integrationOrder", "0")) != int(entry.get("integrationOrder", 0)):
            errors.append(f"Task {task_id} integrationOrder does not match registry")
    except (TypeError, ValueError):
        errors.append(f"Task {task_id} integrationOrder is not an integer")
    if not completion_mode:
        try:
            if parse_time(front.get("leaseExpiresAt", "")) != parse_time(entry["lease"]["expiresAt"]):
                errors.append(f"Task {task_id} leaseExpiresAt does not match registry")
        except Exception as exc:
            errors.append(f"Task {task_id} lease comparison failed: {exc}")

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

    if entry.get("riskLevel") in HIGH_RISKS:
        implementer = entry.get("implementer", "")
        reviewer = entry.get("reviewer", "")
        if role_is_placeholder(implementer) or role_is_placeholder(reviewer):
            errors.append(f"High/critical task {task_id} must assign real implementer and reviewer identities")
        elif implementer == reviewer:
            errors.append(f"High/critical task {task_id} implementer and reviewer must differ")

    if actual_branch:
        match = BRANCH_RE.fullmatch(actual_branch)
        if not match or match.group(2) != task_id:
            errors.append(f"Actual branch does not carry task ID {task_id}: {actual_branch}")
        elif completion_mode:
            if actual_branch != str(front.get("workBranch") or ""):
                errors.append(
                    f"Completed task {task_id} completion branch must equal Task Spec workBranch, got {actual_branch}"
                )
        elif entry.get("status") != "reserved" and actual_branch != entry.get("branch"):
            errors.append(
                f"Task {task_id} must run on registered branch {entry.get('branch')}, got {actual_branch}"
            )

    if base_ref and head_ref and task_exclusive is not None and task_shared is not None:
        files = changed_files(root, base_ref, head_ref)
        if files is None:
            errors.append(f"Cannot determine changed files for {base_ref}...{head_ref}")
        else:
            claims = list(entry.get("exclusivePaths", [])) + list(entry.get("sharedPaths", []))
            unclaimed: list[str] = []
            for filepath in files:
                if is_coordination_metadata(
                    filepath, task_id, task_path, root, completion_mode=completion_mode
                ):
                    continue
                if not any(match_pattern(filepath, pattern) for pattern in claims):
                    unclaimed.append(filepath)
            if unclaimed:
                errors.append(
                    f"Task {task_id} changed files outside registered path claims: {unclaimed}"
                )
            if completion_mode:
                task_relative = os.path.relpath(task_path, root).replace("\\", "/")
                required = {
                    CANONICAL_PLAN,
                    CANONICAL_COMPLETIONS,
                    CANONICAL_ACTIVE_WORK,
                    task_relative,
                }
                missing = sorted(required - set(files))
                if missing:
                    errors.append(
                        f"Completed task {task_id} completion update is missing canonical files: {missing}"
                    )


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    registry_path = os.path.join(root, args.registry)
    schema_path = os.path.join(root, args.schema)
    errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = load_yaml(registry_path)
        schema = load_yaml(schema_path)
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        ).validate(registry)
    except Exception as exc:
        report("FAIL", f"Cannot validate active-work registry: {exc}")
        return 1

    try:
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    except Exception as exc:
        report("ERROR", f"Invalid --now timestamp: {exc}")
        return 2

    tasks = registry.get("tasks", [])
    active = [task for task in tasks if task.get("status") in ACTIVE_STATUSES]
    policy = registry.get("policy", {})
    if len(active) > policy.get("maxActiveTasks", 0):
        errors.append(f"Active task count {len(active)} exceeds limit {policy.get('maxActiveTasks')}")
    high_count = sum(1 for task in active if task.get("riskLevel") in HIGH_RISKS)
    if high_count > policy.get("maxHighRiskTasks", 0):
        errors.append(
            f"High/critical active task count {high_count} exceeds limit {policy.get('maxHighRiskTasks')}"
        )

    seen_task_ids: set[str] = set()
    seen_branches: set[str] = set()
    seen_handoffs: set[str] = set()
    graph: dict[str, list[str]] = {}
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
                    errors.append(
                        f"High/critical task {task_id} must assign real implementer and reviewer identities"
                    )
                elif implementer == reviewer:
                    errors.append(
                        f"High/critical task {task_id} implementer and reviewer must differ"
                    )
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
                    same_group = (
                        left.get("coordinationGroup")
                        and left.get("coordinationGroup") == right.get("coordinationGroup")
                    )
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
                args.registry,
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
        return 1
    report(
        "PASS",
        f"Agent coordination valid: {len(active)} active tasks, {high_count} high/critical",
        {"activeTaskIds": sorted(task.get("taskId") for task in active)},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

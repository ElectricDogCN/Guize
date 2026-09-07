#!/usr/bin/env python3
"""Validate one fail-closed metadata-only Program Task Registration.

Registration is the only legal absent -> planned transition for an ordinary
Program task. It is distinct from Reservation and grants no Lease, Active
Work entry, implementation scope, review/integration authority, result, or
completion authority.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import Counter
from typing import Any, Iterable

import yaml

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
TASK_DIR = "specs/tasks"
TASK_ID_RE = re.compile(r"^[A-Z]+-[0-9]{3}$")
PLACEHOLDERS = {
    "",
    "none",
    "n/a",
    "na",
    "unknown",
    "tbd",
    "pending",
    "self",
    "same-agent",
    "unassigned",
}
TYPE_BY_KIND = {
    "requirements": {"docs", "chore"},
    "contract": {"chore", "docs"},
    "design-contract": {"docs", "chore"},
    "poc-coordination": {"chore"},
    "poc": {"chore"},
    "acceptance": {"chore", "docs"},
    "scaffold": {"chore", "feat"},
    "vertical-slice": {"feat"},
    "release": {"chore"},
    "governance": {"chore", "fix"},
}
CANONICAL_EVIDENCE_ENTRIES = (
    "summary.md",
    "commands.txt",
    "test-results/",
    "screenshots/",
    "api-samples/",
    "migration-report/",
    "performance/",
    "security/",
    "rollback-verification/",
)
SUPPORT_EVIDENCE_FILES = (
    "scope.md",
    "changed-files.md",
    "assumptions.md",
    "risks.md",
    "follow-ups.md",
)
REQUIRED_FRONT_FIELDS = {
    "schemaVersion",
    "id",
    "title",
    "titleZh",
    "type",
    "status",
    "baseBranch",
    "baseSha",
    "workBranch",
    "branchPattern",
    "evidencePath",
    "issue",
    "workPackage",
    "programPlan",
    "programTaskId",
    "wave",
    "requirementIds",
    "moduleIds",
    "producesContracts",
    "consumesContracts",
    "acceptanceIds",
    "pocIds",
    "exitGate",
    "taskOwner",
    "coordinator",
    "implementer",
    "reviewer",
    "integrator",
    "agentRole",
    "riskLevel",
    "coordinationMode",
    "coordinationGroup",
    "dependsOn",
    "handoffPath",
    "integrationStrategy",
    "integrationOrder",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe loader that keeps YAML merge keys and rejects explicit duplicates."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    # Check only keys explicitly present in this mapping before flattening. A
    # legal explicit override of a value inherited through ``<<`` must remain
    # valid, while two explicit occurrences of the same key must fail.
    explicit: set[Any] = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=False)
        try:
            duplicate = key in explicit
            explicit.add(key)
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found unhashable mapping key {key!r}",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate explicit key {key!r}",
                key_node.start_mark,
            )
    loader.flatten_mapping(node)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program Task Registration")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--task", default="")
    parser.add_argument("--branch-name", default="")
    parser.add_argument("--detect-only", action="store_true")
    return parser.parse_args()


def emit(status: str, message: str, details: Any | None = None) -> None:
    payload: dict[str, Any] = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def git(root: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def resolve_ref(root: str, ref: str) -> str | None:
    if not ref:
        return None
    result = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def read_ref(root: str, ref: str, path: str) -> str | None:
    if not ref or not path:
        return None
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def ref_mode(root: str, ref: str, path: str) -> str | None:
    result = git(root, "ls-tree", ref, "--", path)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split(None, 1)[0]


def ref_paths(root: str, ref: str, prefix: str = "") -> list[str]:
    command = ["ls-tree", "-r", "--name-only", ref]
    if prefix:
        command.extend(["--", prefix])
    result = git(root, *command)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def load_yaml_text(text: str | None) -> Any | None:
    if text is None:
        return None
    try:
        return yaml.load(text, Loader=UniqueKeyLoader)
    except yaml.YAMLError:
        return None


def load_ref(root: str, ref: str, path: str) -> Any | None:
    return load_yaml_text(read_ref(root, ref, path))


def task_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in plan.get("tasks") or [] if isinstance(item, dict)]


def foundation_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in plan.get("foundationTasks") or [] if isinstance(item, dict)
    ]


def row_ids(rows: Iterable[dict[str, Any]]) -> list[str]:
    return [str(item.get("taskId") or "") for item in rows]


def duplicate_ids(rows: Iterable[dict[str, Any]]) -> list[str]:
    counts = Counter(item for item in row_ids(rows) if item)
    return sorted(item for item, count in counts.items() if count > 1)


def task_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("taskId")): item
        for item in task_rows(plan)
        if item.get("taskId")
    }


def foundation_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("taskId")): item
        for item in foundation_rows(plan)
        if item.get("taskId")
    }


def changed_paths(
    root: str,
    base_ref: str,
    head_ref: str,
) -> tuple[set[str] | None, list[tuple[str, str, str]]]:
    result = git(
        root,
        "diff",
        "--name-status",
        "-z",
        "-M",
        "-C",
        "--find-copies-harder",
        f"{base_ref}...{head_ref}",
    )
    if result.returncode != 0:
        return None, []
    fields = result.stdout.split("\0")
    paths: set[str] = set()
    records: list[tuple[str, str, str]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not status:
            continue
        if status.startswith(("R", "C")):
            if index + 1 >= len(fields):
                return None, []
            source, destination = fields[index], fields[index + 1]
            index += 2
            paths.update((source, destination))
            records.append((status, source, destination))
        else:
            if index >= len(fields):
                return None, []
            path = fields[index]
            index += 1
            paths.add(path)
            records.append((status, path, path))
    return paths, records


def is_registration_candidate(root: str, base_ref: str, head_ref: str) -> bool:
    if not resolve_ref(root, base_ref) or not resolve_ref(root, head_ref):
        return False
    paths, _ = changed_paths(root, base_ref, head_ref)
    if paths is None or PLAN not in paths:
        return False
    before = load_ref(root, base_ref, PLAN)
    after = load_ref(root, head_ref, PLAN)
    if not isinstance(before, dict) or not isinstance(after, dict):
        # A malformed Program Plan change must enter the fail-closed
        # Registration validator rather than silently falling through to a
        # different lifecycle mode.
        return True
    base_ids = set(row_ids(task_rows(before)))
    return any(task_id not in base_ids for task_id in row_ids(task_rows(after)))


def normalize_path(value: Any) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return re.sub(r"/+", "/", path).rstrip("/")


def safe_repo_path(path: str) -> bool:
    normalized = normalize_path(path)
    return bool(normalized) and not normalized.startswith("/") and all(
        part not in {"", ".", ".."} for part in normalized.split("/")
    )


def static_prefix(pattern: str) -> str:
    normalized = normalize_path(pattern)
    positions = [
        normalized.find(token)
        for token in ("*", "?", "[")
        if normalized.find(token) >= 0
    ]
    return normalized if not positions else normalized[: min(positions)].rstrip("/")


def safe_scope_claim(value: Any) -> bool:
    raw = str(value or "").strip()
    normalized = normalize_path(raw)
    if not safe_repo_path(normalized):
        return False
    if normalized in {"*", "**", "/"}:
        return False
    # Any glob whose non-wildcard prefix is empty is repository-wide or an
    # equivalent root wildcard (for example ./**, **/*, [a-z]*, or ?/**).
    if any(token in normalized for token in ("*", "?", "[")) and not static_prefix(
        normalized
    ):
        return False
    return True


def parse_front(text: str | None) -> tuple[dict[str, Any], str]:
    if not text or not text.startswith("---"):
        return {}, text or ""
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}, text
    try:
        document = yaml.load(parts[1], Loader=UniqueKeyLoader)
    except yaml.YAMLError:
        return {}, parts[2]
    return (document if isinstance(document, dict) else {}), parts[2]


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if not text or text.lower() in PLACEHOLDERS or text.upper() == "NONE":
        return []
    return [
        part.strip().strip("'\"")
        for part in text.strip("[]").split(",")
        if part.strip()
    ]


def extract_section(body: str, titles: tuple[str, ...]) -> str | None:
    lines = body.splitlines()
    wanted = tuple(title.lower() for title in titles)
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        title = re.sub(r"^##\s+", "", stripped).strip().lower()
        title = re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", title)
        if any(item in title for item in wanted):
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


def has_bullet(section: str | None) -> bool:
    return bool(section and re.search(r"(?m)^\s*[-*]\s+\S", section))


def section_paths(body: str, titles: tuple[str, ...]) -> list[str] | None:
    section = extract_section(body, titles)
    if section is None:
        return None
    paths: list[str] = []
    for line in section.splitlines():
        match = re.match(r"\s*[-*]\s+(.+)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        quoted = re.search(r"`([^`]+)`", value)
        if quoted:
            value = quoted.group(1).strip()
        if value in {"无", "无。", "NONE", "none", "N/A", "n/a"}:
            continue
        if quoted or "/" in value or "*" in value or value.startswith("."):
            paths.append(normalize_path(value))
    return paths


def has_validation_command(section: str | None) -> bool:
    if not section:
        return False
    if re.search(
        r"```(?:bash|sh|shell|text)?\s*\n\s*[^`\s][\s\S]*?```",
        section,
        re.I,
    ):
        return True
    return bool(
        re.search(
            r"(?mi)^\s*[-*]\s+`?(?:python|python3|make|git|bash|sh|pytest|npm|pnpm|yarn|mvn|gradle|docker)\b",
            section,
        )
    )


def wave_orders(plan: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {"FOUNDATION": 0}
    for wave in plan.get("waves") or []:
        if isinstance(wave, dict) and wave.get("id") is not None:
            try:
                result[str(wave["id"])] = int(wave["order"])
            except (KeyError, TypeError, ValueError):
                continue
    return result


def dependency_cycle(tasks: dict[str, dict[str, Any]]) -> bool:
    visiting: set[str] = set()
    complete: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return True
        if task_id in complete:
            return False
        visiting.add(task_id)
        for dependency in tasks.get(task_id, {}).get("dependsOn") or []:
            dependency_id = str(dependency)
            if dependency_id in tasks and visit(dependency_id):
                return True
        visiting.remove(task_id)
        complete.add(task_id)
        return False

    return any(visit(task_id) for task_id in tasks)


def dependency_closure(
    task_id: str,
    tasks: dict[str, dict[str, Any]],
) -> set[str]:
    seen: set[str] = set()
    stack = [str(item) for item in tasks.get(task_id, {}).get("dependsOn") or []]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(str(item) for item in tasks.get(current, {}).get("dependsOn") or [])
    return seen


def compare_scalar(
    front: dict[str, Any],
    task: dict[str, Any],
    front_key: str,
    task_key: str,
    errors: list[str],
) -> None:
    if str(front.get(front_key, "")) != str(task.get(task_key, "")):
        errors.append(f"Task Spec {front_key} does not match Program task {task_key}")


def compare_list(
    front: dict[str, Any],
    task: dict[str, Any],
    key: str,
    errors: list[str],
) -> None:
    if as_list(front.get(key)) != [str(item) for item in task.get(key) or []]:
        errors.append(f"Task Spec {key} does not match Program task {key}")


def branch_refs(root: str, branch: str) -> list[tuple[str, str]]:
    candidates = (
        branch,
        f"refs/heads/{branch}",
        f"origin/{branch}",
        f"refs/remotes/origin/{branch}",
    )
    resolved: list[tuple[str, str]] = []
    for candidate in candidates:
        sha = resolve_ref(root, candidate)
        if sha and (candidate, sha) not in resolved:
            resolved.append((candidate, sha))
    return resolved


def commit_parents(root: str, sha: str) -> list[str]:
    result = git(root, "rev-list", "--parents", "-n", "1", sha)
    if result.returncode != 0:
        return []
    parts = result.stdout.strip().split()
    return parts[1:] if parts and parts[0] == sha else []


def validate_branch_provenance(
    root: str,
    base_sha: str,
    head_sha: str,
    work_branch: str,
    task_aware: bool,
    branch_name: str,
    errors: list[str],
) -> None:
    if not work_branch:
        errors.append("Registration Task Spec workBranch is empty")
        return
    refs = branch_refs(root, work_branch)
    if task_aware:
        if not branch_name:
            errors.append("Task-aware Registration requires an authoritative branch name")
        elif branch_name != work_branch:
            errors.append("Registration actual branch does not match Task Spec workBranch")
        if any(sha == head_sha for _, sha in refs):
            return
        # pull_request workflows normally check out refs/pull/<n>/merge rather
        # than the source branch itself. In that case, prove the exact first
        # parent/base and second-parent/source-branch relation instead of
        # comparing the source ref to the synthetic merge SHA.
        parents = commit_parents(root, head_sha)
        if len(parents) != 2 or parents[0] != base_sha:
            errors.append(
                "Task-aware Registration cannot prove candidate HEAD ancestry from the target base"
            )
            return
        if not any(sha == parents[1] for _, sha in refs):
            errors.append(
                "Task-aware Registration workBranch ref does not resolve to the candidate source parent"
            )
        return

    parents = commit_parents(root, head_sha)
    if len(parents) != 2:
        errors.append(
            "Push/no-task Registration must be a two-parent merge commit, not a direct push"
        )
        return
    first_parent, source_parent = parents
    if first_parent != base_sha:
        errors.append(
            "Push/no-task Registration first parent does not equal the exact push base"
        )
    if not any(sha == source_parent for _, sha in refs):
        errors.append(
            "Push/no-task Registration cannot prove a source branch ref matching workBranch"
        )
    tree_check = git(root, "diff", "--quiet", source_parent, head_sha)
    if tree_check.returncode != 0:
        errors.append(
            "Push/no-task Registration merge tree differs from the verified source branch commit"
        )


def parse_compatibility_map(content: str | None) -> dict[str, tuple[str, str]]:
    if not content:
        return {}
    canonical = {entry.rstrip("/"): entry for entry in CANONICAL_EVIDENCE_ENTRIES}
    mappings: dict[str, tuple[str, str]] = {}
    for line in content.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        source = cells[0].strip("`").rstrip("/")
        if source not in canonical:
            continue
        mappings[canonical[source]] = (cells[1].strip().strip("`"), cells[2].strip())
    return mappings


def split_mapping_targets(value: str) -> list[str]:
    return [
        part.strip().strip("`")
        for part in re.split(r"\s*(?:\+|,|，|<br\s*/?>)\s*", value)
        if part.strip()
    ]


def evidence_entry_exists(
    root: str,
    head_ref: str,
    evidence_root: str,
    entry: str,
    all_paths: set[str],
) -> tuple[bool, list[str]]:
    relative = f"{evidence_root}/{entry.rstrip('/')}"
    if entry.endswith("/"):
        prefix = relative + "/"
        matches = sorted(path for path in all_paths if path.startswith(prefix))
        return bool(matches), matches
    content = read_ref(root, head_ref, relative)
    return bool(content), [relative] if content else []


def content_has_executable_steps(content: str) -> bool:
    if "```bash" in content or "```sh" in content or "```shell" in content:
        return True
    return bool(
        re.search(
            r"(?m)^(?:git|rm|cp|mv|python|python3|make|bash|sh|docker|kubectl)\s+",
            content,
        )
    )


def validate_evidence_contract(
    root: str,
    head_ref: str,
    task_id: str,
    errors: list[str],
) -> None:
    evidence_root = f"evidence/{task_id}"
    all_paths = set(ref_paths(root, head_ref, evidence_root))
    compatibility = parse_compatibility_map(
        read_ref(root, head_ref, f"{evidence_root}/EVIDENCE-STRUCTURE.md")
    )
    resolved_entries: dict[str, list[str]] = {}

    for entry in CANONICAL_EVIDENCE_ENTRIES:
        exists, paths = evidence_entry_exists(
            root, head_ref, evidence_root, entry, all_paths
        )
        if exists:
            resolved_entries[entry] = paths
            if not entry.endswith("/"):
                content = read_ref(root, head_ref, paths[0]) or ""
                if task_id not in content:
                    errors.append(
                        f"Canonical Registration Evidence {entry} must identify {task_id}"
                    )
            continue
        mapping = compatibility.get(entry)
        if not mapping:
            errors.append(
                f"Registration Evidence is missing canonical entry or compatibility mapping: {entry}"
            )
            continue
        target, reason = mapping
        normalized = target.upper().replace(" ", "")
        if normalized in {"N/A", "NA", "NOTAPPLICABLE", "不适用"}:
            if len(re.sub(r"[`*_]", "", reason).strip()) < 4:
                errors.append(f"N/A mapping for {entry} must include a reason")
            resolved_entries[entry] = []
            continue
        targets = split_mapping_targets(target)
        if not targets:
            errors.append(f"Compatibility mapping for {entry} has no target")
            continue
        found: list[str] = []
        for target_item in targets:
            candidate = (
                target_item
                if target_item.startswith(evidence_root + "/")
                else f"{evidence_root}/{target_item.lstrip('/')}"
            )
            if target_item.endswith("/"):
                prefix = candidate.rstrip("/") + "/"
                found.extend(sorted(path for path in all_paths if path.startswith(prefix)))
            elif read_ref(root, head_ref, candidate):
                found.append(candidate)
        if not found:
            errors.append(
                f"Compatibility target for {entry} does not exist at candidate ref: {target}"
            )
        else:
            for path in found:
                if not target.endswith("/"):
                    content = read_ref(root, head_ref, path) or ""
                    if task_id not in content:
                        errors.append(
                            f"Compatibility Evidence target must identify {task_id}: {path}"
                        )
            resolved_entries[entry] = found

    for filename in SUPPORT_EVIDENCE_FILES:
        relative = f"{evidence_root}/{filename}"
        content = read_ref(root, head_ref, relative)
        if not content:
            errors.append(f"Registration Evidence support file is missing: {filename}")
        elif task_id not in content:
            errors.append(
                f"Registration Evidence support file must identify {task_id}: {filename}"
            )

    command_paths = resolved_entries.get("commands.txt", [])
    if command_paths:
        commands = read_ref(root, head_ref, command_paths[0]) or ""
        if not re.search(r"命令|command|cmd|\$\s", commands, re.I):
            errors.append("Registration commands Evidence has no command indicator")
        if not re.search(r"退出码|exit.?code|returncode", commands, re.I):
            errors.append("Registration commands Evidence has no exit-code indicator")

    rollback_paths = resolved_entries.get("rollback-verification/", [])
    if rollback_paths:
        if not any(
            content_has_executable_steps(read_ref(root, head_ref, path) or "")
            for path in rollback_paths
        ):
            errors.append(
                "Registration rollback-verification Evidence has no executable steps"
            )


def validate_task_spec(
    root: str,
    base_ref: str,
    head_ref: str,
    base_sha: str,
    head_sha: str,
    task_id: str,
    new_task: dict[str, Any],
    task_hint: str,
    branch_name: str,
    errors: list[str],
) -> tuple[str, dict[str, Any], str]:
    task_path = f"{TASK_DIR}/{task_id}.md"
    matching_specs = sorted(
        path
        for path in ref_paths(root, head_ref, TASK_DIR)
        if path == task_path
        or (path.startswith(f"{TASK_DIR}/{task_id}-") and path.endswith(".md"))
    )
    if len(matching_specs) != 1 or matching_specs[0] != task_path:
        errors.append(
            f"Registration requires exactly one canonical Task Spec {task_path}; got {matching_specs}"
        )
    if read_ref(root, base_ref, task_path) is not None:
        errors.append("Registration Task Spec must be absent from the target base")
    task_text = read_ref(root, head_ref, task_path)
    front, body = parse_front(task_text)
    if not front:
        errors.append(
            "Registration requires one readable schemaVersion 2 Task Spec with unique explicit keys"
        )
        return task_path, {}, body

    missing = sorted(
        key
        for key in REQUIRED_FRONT_FIELDS
        if key not in front or front.get(key) is None or front.get(key) == ""
    )
    if missing:
        errors.append(f"Registration Task Spec is missing fields: {missing}")
    if front.get("schemaVersion") != 2:
        errors.append("Registration Task Spec schemaVersion must be 2")
    if front.get("status") != "planned":
        errors.append("Registration Task Spec status must be planned")
    if front.get("coordinationMode") != "registration":
        errors.append("Registration Task Spec coordinationMode must be registration")
    if front.get("agentRole") != "coordinator":
        errors.append("Registration Task Spec agentRole must be coordinator")
    if "leaseExpiresAt" in front:
        errors.append("Registration Task Spec must not contain leaseExpiresAt")
    if front.get("riskLevel") not in {"high", "critical"}:
        errors.append("Registration Task Spec riskLevel must be high or critical")
    if (
        front.get("programPlan") != PLAN
        or front.get("programTaskId") != task_id
        or front.get("id") != task_id
    ):
        errors.append("Registration Task Spec Program identity is inconsistent")
    if front.get("baseBranch") != "main" or front.get("baseSha") != base_sha:
        errors.append("Registration Task Spec base identity does not match target base")
    if (
        front.get("evidencePath") != f"evidence/{task_id}"
        or front.get("handoffPath") != f"evidence/{task_id}/handoff.md"
    ):
        errors.append("Registration Task Spec Evidence/Handoff identity is inconsistent")
    if front.get("integrationStrategy") != "merge":
        errors.append("Registration integrationStrategy must be merge")

    work_branch = str(front.get("workBranch") or "")
    pattern = str(front.get("branchPattern") or "")
    if (
        pattern != str(new_task.get("branchPattern") or "")
        or not pattern
        or not fnmatch.fnmatchcase(work_branch, pattern)
    ):
        errors.append(
            "Registration Task Spec branchPattern/workBranch does not match Program task"
        )

    compare_scalar(front, new_task, "titleZh", "title", errors)
    for key in (
        "workPackage",
        "riskLevel",
        "wave",
        "integrationOrder",
        "issue",
        "coordinationGroup",
        "exitGate",
    ):
        compare_scalar(front, new_task, key, key, errors)
    for key in (
        "dependsOn",
        "requirementIds",
        "moduleIds",
        "producesContracts",
        "consumesContracts",
        "acceptanceIds",
        "pocIds",
    ):
        compare_list(front, new_task, key, errors)

    if str(front.get("implementer") or "") != str(new_task.get("ownerRole") or ""):
        errors.append(
            "Registration Task Spec implementer does not match Program ownerRole"
        )
    if str(front.get("reviewer") or "") != str(new_task.get("reviewerRole") or ""):
        errors.append(
            "Registration Task Spec reviewer does not match Program reviewerRole"
        )
    allowed_types = TYPE_BY_KIND.get(str(new_task.get("kind") or ""), set())
    if front.get("type") not in allowed_types:
        errors.append(
            "Registration Task Spec type is incompatible with Program task kind"
        )
    for role in (
        "taskOwner",
        "coordinator",
        "implementer",
        "reviewer",
        "integrator",
    ):
        if str(front.get(role) or "").strip().lower() in PLACEHOLDERS:
            errors.append(f"Registration Task Spec {role} must be a concrete identity")
    if front.get("implementer") == front.get("reviewer"):
        errors.append(
            "Registration high-risk implementer and reviewer must be distinct"
        )

    required_sections = (
        (("允许范围", "allowed scope"), "allowed scope"),
        (("禁止范围", "forbidden scope"), "forbidden scope"),
        (
            ("依赖与集成顺序", "dependencies and integration order"),
            "dependencies/integration",
        ),
        (("协作与交接", "collaboration and handoff"), "collaboration/handoff"),
    )
    for titles, label in required_sections:
        section = extract_section(body, titles)
        if not has_bullet(section):
            errors.append(
                f"Registration Task Spec {label} section must contain a bullet"
            )

    acceptance = extract_section(body, ("验收标准", "acceptance criteria"))
    if not acceptance or not re.search(
        r"(?m)^\s*[-*]\s+\[[ xX]\]\s+\S", acceptance
    ):
        errors.append(
            "Registration Task Spec acceptance section must contain a checklist item"
        )
    validation = extract_section(body, ("必须执行的测试", "validation commands"))
    if not has_validation_command(validation):
        errors.append(
            "Registration Task Spec validation section has no executable command"
        )

    exclusive = section_paths(body, ("独占写范围", "exclusive write scope"))
    shared = section_paths(body, ("共享修改范围", "shared modification scope"))
    program_output = [
        normalize_path(item) for item in new_task.get("outputPaths") or []
    ]
    program_shared = [
        normalize_path(item) for item in new_task.get("sharedPaths") or []
    ]
    if exclusive is None or exclusive != program_output:
        errors.append(
            "Registration Task Spec exclusive paths do not match Program outputPaths in order"
        )
    if shared is None or shared != program_shared:
        errors.append(
            "Registration Task Spec shared paths do not match Program sharedPaths in order"
        )
    for claim in program_output + program_shared:
        if not safe_scope_claim(claim):
            errors.append(
                f"Registration contains repository-wide or unsafe path claim: {claim}"
            )

    handoff_path = str(front.get("handoffPath") or "")
    handoff = read_ref(root, head_ref, handoff_path)
    if (
        ref_mode(root, head_ref, handoff_path) not in {"100644", "100755"}
        or not handoff
    ):
        errors.append(
            "Registration handoffPath must be an existing regular file at candidate ref"
        )
    elif task_id not in handoff:
        errors.append("Registration Handoff must identify the Task ID")

    validate_branch_provenance(
        root,
        base_sha,
        head_sha,
        work_branch,
        task_aware=bool(task_hint),
        branch_name=branch_name,
        errors=errors,
    )
    return task_path, front, body


def validate_registration(
    root: str,
    base_ref: str,
    head_ref: str,
    task_hint: str = "",
    branch_name: str = "",
) -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    base_sha = resolve_ref(root, base_ref)
    head_sha = resolve_ref(root, head_ref)
    if not base_sha or not head_sha:
        return 1, {"errors": ["Registration refs are missing"]}

    paths, records = changed_paths(root, base_ref, head_ref)
    if paths is None:
        return 1, {"errors": ["Registration cannot determine exact changed paths"]}

    base_plan = load_ref(root, base_ref, PLAN)
    current_plan = load_ref(root, head_ref, PLAN)
    if not isinstance(base_plan, dict) or not isinstance(current_plan, dict):
        return 1, {
            "errors": [
                "Registration Program Plan snapshots are missing, invalid, or contain duplicate explicit keys"
            ]
        }

    base_rows = task_rows(base_plan)
    current_rows = task_rows(current_plan)
    for label, rows in (
        ("base Program tasks", base_rows),
        ("candidate Program tasks", current_rows),
        ("base Foundation tasks", foundation_rows(base_plan)),
        ("candidate Foundation tasks", foundation_rows(current_plan)),
    ):
        duplicates = duplicate_ids(rows)
        if duplicates:
            errors.append(
                f"Registration {label} contain duplicate task IDs: {duplicates}"
            )

    base_ids = set(row_ids(base_rows))
    current_ids = set(row_ids(current_rows))
    new_rows = [
        item
        for item in current_rows
        if str(item.get("taskId") or "") not in base_ids
    ]
    added_ids = [str(item.get("taskId") or "") for item in new_rows]
    removed = sorted(base_ids - current_ids)
    task_id = added_ids[0] if added_ids else task_hint
    if len(new_rows) != 1:
        errors.append(
            f"Registration must add exactly one Program task row; got {added_ids}"
        )
    if removed:
        errors.append(f"Registration must not remove Program tasks: {removed}")
    if task_hint and task_id and task_hint != task_id:
        errors.append(
            f"Registration task hint {task_hint} does not match new task {task_id}"
        )
    if task_id and not TASK_ID_RE.fullmatch(task_id):
        errors.append(f"Registration task ID is invalid: {task_id}")

    base_tasks = task_map(base_plan)
    current_tasks = task_map(current_plan)
    new_task = current_tasks.get(task_id, {})
    if new_task.get("status") != "planned":
        errors.append("Registration new Program task status must be planned")
    if new_task.get("riskLevel") not in {"high", "critical"}:
        errors.append(
            "Registration Program Plan change must be high or critical risk"
        )

    base_copy = copy.deepcopy(base_plan)
    current_copy = copy.deepcopy(current_plan)
    base_copy["tasks"] = []
    current_copy["tasks"] = []
    if base_copy != current_copy:
        errors.append("Registration must not modify non-task Program Plan sections")

    base_order = row_ids(base_rows)
    current_existing_order = [
        str(item.get("taskId") or "")
        for item in current_rows
        if str(item.get("taskId") or "") in base_ids
    ]
    if base_order != current_existing_order:
        errors.append("Registration must preserve existing Program task order")

    changed_existing: list[str] = []
    orders = wave_orders(current_plan)
    new_wave_order = orders.get(str(new_task.get("wave") or ""))
    if new_wave_order is None:
        errors.append("Registration new task references an unknown Wave")

    for existing_id in base_order:
        before = base_tasks.get(existing_id)
        after = current_tasks.get(existing_id)
        if before is None or after is None or after == before:
            continue
        changed_existing.append(existing_id)
        before_without = copy.deepcopy(before)
        after_without = copy.deepcopy(after)
        before_dependencies = [
            str(item) for item in before_without.pop("dependsOn", [])
        ]
        after_dependencies = [
            str(item) for item in after_without.pop("dependsOn", [])
        ]
        if before_without != after_without:
            errors.append(
                f"Registration may not mutate existing task {existing_id} fields"
            )
        if after.get("status") != "planned":
            errors.append(
                f"Registration dependency attachment target {existing_id} must remain planned"
            )
        if after_dependencies != before_dependencies + [task_id]:
            errors.append(
                f"Registration task {existing_id} dependency change must be one tail append of {task_id}"
            )
        target_order = orders.get(str(after.get("wave") or ""))
        if target_order is None or (
            new_wave_order is not None and target_order < new_wave_order
        ):
            errors.append(
                f"Registration dependency attachment target {existing_id} must be in the same or a later Wave"
            )

    base_active_text = read_ref(root, base_ref, ACTIVE)
    current_active_text = read_ref(root, head_ref, ACTIVE)
    if (
        base_active_text is None
        or current_active_text is None
        or base_active_text != current_active_text
    ):
        errors.append("Registration must leave Active Work byte-identical")

    base_ledger_text = read_ref(root, base_ref, LEDGER)
    current_ledger_text = read_ref(root, head_ref, LEDGER)
    if (
        base_ledger_text is None
        or current_ledger_text is None
        or base_ledger_text != current_ledger_text
    ):
        errors.append("Registration must leave Completion Ledger byte-identical")

    task_path, _, _ = validate_task_spec(
        root,
        base_ref,
        head_ref,
        base_sha,
        head_sha,
        task_id,
        new_task,
        task_hint,
        branch_name,
        errors,
    )

    allowed_exact = {PLAN, task_path}
    invalid_paths = sorted(
        path
        for path in paths
        if path not in allowed_exact
        and path != f"evidence/{task_id}"
        and not path.startswith(f"evidence/{task_id}/")
    )
    if invalid_paths:
        errors.append(
            f"Registration contains implementation or unrelated files: {invalid_paths}"
        )
    if not any(path.startswith(f"evidence/{task_id}/") for path in paths):
        errors.append("Registration must create task-bound Evidence")

    for path in sorted(paths):
        if not safe_repo_path(path):
            errors.append(f"Registration changed path is unsafe: {path}")
        if ref_mode(root, head_ref, path) == "120000":
            errors.append(
                f"Registration must not introduce or modify symlinks: {path}"
            )
    for status, source, destination in records:
        if status.startswith("C"):
            if not (
                source == "specs/tasks/task-template.md"
                and destination == task_path
            ):
                errors.append(
                    f"Registration copy source is not authorized: {source} -> {destination}"
                )
        elif status.startswith("R"):
            source_ok = source in allowed_exact or source.startswith(
                f"evidence/{task_id}/"
            )
            destination_ok = destination in allowed_exact or destination.startswith(
                f"evidence/{task_id}/"
            )
            if not source_ok or not destination_ok:
                errors.append(
                    f"Registration rename escapes task metadata scope: {source} -> {destination}"
                )

    validate_evidence_contract(root, head_ref, task_id, errors)

    all_ids = set(current_tasks) | set(foundation_map(current_plan))
    for dependency in new_task.get("dependsOn") or []:
        dependency_id = str(dependency)
        if dependency_id not in all_ids:
            errors.append(f"Registration dependency does not exist: {dependency_id}")
        elif dependency_id in current_tasks and new_wave_order is not None:
            dependency_order = orders.get(
                str(current_tasks[dependency_id].get("wave") or "")
            )
            if dependency_order is None or dependency_order > new_wave_order:
                errors.append(
                    f"Registration dependency {dependency_id} is in a later Wave"
                )

    if dependency_cycle(current_tasks):
        errors.append("Registration introduces a Program task dependency cycle")

    final_task = str(
        (current_plan.get("releasePolicy") or {}).get("requiredFinalTask") or ""
    )
    if not final_task or final_task not in current_tasks:
        errors.append("Registration cannot resolve the required final Program task")
    elif final_task != task_id and task_id not in dependency_closure(
        final_task, current_tasks
    ):
        errors.append(
            f"Registration task {task_id} is missing from required final-task closure"
        )

    active_document = load_yaml_text(current_active_text)
    if isinstance(active_document, dict) and any(
        item.get("taskId") == task_id
        for item in active_document.get("tasks") or []
        if isinstance(item, dict)
    ):
        errors.append(
            "Registration planned task must not have an Active Work entry"
        )

    details = {
        "taskId": task_id or None,
        "baseSha": base_sha,
        "headSha": head_sha,
        "changedPathCount": len(paths),
        "downstreamAttachments": changed_existing,
        "mode": "task-aware" if task_hint else "push/no-task",
        "errors": errors,
    }
    return (1 if errors else 0), details


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    candidate = is_registration_candidate(root, args.base_ref, args.head_ref)
    if args.detect_only:
        emit(
            "PASS",
            "Registration candidate detection completed",
            {"candidate": candidate},
        )
        return 0
    if not candidate:
        emit(
            "FAIL",
            "Exact diff is not an absent-to-planned Program Task Registration",
        )
        return 1

    code, details = validate_registration(
        root,
        args.base_ref,
        args.head_ref,
        task_hint=args.task,
        branch_name=args.branch_name,
    )
    if code:
        for error in details.get("errors") or []:
            emit("FAIL", error)
        return code
    emit(
        "PASS",
        "Program Task Registration is metadata-only, history-aware, and fail-closed",
        details,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

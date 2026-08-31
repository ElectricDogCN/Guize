#!/usr/bin/env python3
"""Fail-closed lifecycle guard for Program Plan, Registry, Task and Evidence.

This checker is intentionally history-aware and complements the existing
snapshot, transition, history and finalization checkers. It closes lifecycle
scope gaps that are easy to miss when a metadata PR is internally consistent:

* derives affected task IDs even on push-to-main runs without a branch Task ID;
* validates both source and destination paths of renames/copies;
* limits metadata-state PRs to task-bound lifecycle files;
* limits implementation PRs to their registered paths plus task metadata;
* constrains active Foundation leases to governance-owned/audited paths and to
  the exact target base SHA;
* requires task-bound cancellation and completion Evidence;
* rejects completion directly from reserved/blocked/in-progress; and
* requires structured command, exit-code and pass/fail completion results.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from typing import Any

import yaml

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
OWNERSHIP = "specs/designs/module-ownership.yaml"
TASK_DIR = "specs/tasks"
GZ014_COMPLETION_EVIDENCE = "evidence/GZ-014/summary.md"
IMPLEMENTATION_STATES = {"in_progress", "review", "integration"}
METADATA_STATES = {"reserved", "blocked", "cancelled", "completed"}
COMPLETION_BASE_STATES = {"review", "integration"}
GLOB_CHARS = "*?["
TASK_PATH_RE = re.compile(r"^specs/tasks/([A-Z]+-[0-9]+)(?:-[^/]+)?\.md$")

FOUNDATION_SCOPE_EXCEPTIONS: dict[str, tuple[str, ...]] = {
    "GZ-014": (
        "AGENTS.md",
        "README.md",
        "MANIFEST.md",
        "Makefile",
        ".github/**",
        "adr/0014-multi-agent-coordination-and-integration.md",
        "docs/24-requirements-design-readiness-audit.md",
        "docs/25-multi-agent-collaboration-protocol.md",
        "specs/coordination/**",
        "specs/requirements/requirements-index.yaml",
        "specs/designs/module-ownership.yaml",
        "specs/tasks/GZ-003.md",
        "specs/tasks/GZ-014.md",
        "specs/tasks/task-template.md",
        "scripts/**",
        "tests/governance/**",
    )
}

# Exact files of the one-time GZ-003 self-hosting migration.  The authorization
# value is not stored in these files.  It is proven from immutable facts in the
# target-base commit/tree: the base must itself be the GZ-014 Foundation
# Completion PR #33 merge, must newly enter the completed/released GZ-014
# snapshot, and must contain the unchanged GZ-014 completion Evidence outside
# this exempted change set.
GZ003_BOOTSTRAP_MIGRATION_PATHS = frozenset(
    {
        "scripts/check-program-lifecycle-guards.py",
        "tests/governance/test_check_schemas.py",
        "tests/governance/test_program_lifecycle_guards.py",
        "evidence/GZ-003/summary.md",
        "evidence/GZ-003/commands.txt",
        "evidence/GZ-003/handoff.md",
        "evidence/GZ-003/test-results/README.md",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program lifecycle guards")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--task", default="")
    parser.add_argument("--branch-name", default="")
    return parser.parse_args()


def emit(status: str, message: str, details: Any | None = None) -> None:
    payload: dict[str, Any] = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def git(root: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )


def ref_exists(root: str, ref: str) -> bool:
    return bool(ref) and git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").returncode == 0


def resolve_ref(root: str, ref: str) -> str | None:
    result = git(root, "rev-parse", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def read_ref(root: str, ref: str, path: str) -> str | None:
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def load_yaml_text(text: str | None) -> Any | None:
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def load_ref(root: str, ref: str, path: str) -> Any | None:
    return load_yaml_text(read_ref(root, ref, path))


def load_current(root: str, path: str) -> Any:
    with open(os.path.join(root, path), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def mapping(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("taskId")): item
        for item in (items or [])
        if isinstance(item, dict) and item.get("taskId")
    }


def find_task_path(root: str, task_id: str, ref: str | None = None) -> str | None:
    exact = f"{TASK_DIR}/{task_id}.md"
    if ref:
        if read_ref(root, ref, exact) is not None:
            return exact
        tree = git(root, "ls-tree", "-r", "--name-only", ref, TASK_DIR)
        if tree.returncode != 0:
            return None
        matches = sorted(
            path
            for path in tree.stdout.splitlines()
            if path.startswith(f"{TASK_DIR}/{task_id}-") and path.endswith(".md")
        )
        return matches[0] if len(matches) == 1 else None
    if os.path.isfile(os.path.join(root, exact)):
        return exact
    directory = os.path.join(root, TASK_DIR)
    if not os.path.isdir(directory):
        return None
    matches = sorted(
        f"{TASK_DIR}/{name}"
        for name in os.listdir(directory)
        if name.startswith(task_id + "-") and name.endswith(".md")
    )
    return matches[0] if len(matches) == 1 else None


def parse_front(text: str | None) -> dict[str, Any]:
    if not text or not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        value = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return value if isinstance(value, dict) else {}


def normalize_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return re.sub(r"/+", "/", text).rstrip("/")


def static_prefix(pattern: str) -> str:
    pattern = normalize_path(pattern)
    indexes = [pattern.find(char) for char in GLOB_CHARS if pattern.find(char) >= 0]
    return pattern if not indexes else pattern[: min(indexes)].rstrip("/")


def paths_overlap(left: str, right: str) -> bool:
    left = normalize_path(left)
    right = normalize_path(right)
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
                value = pattern[index + 1 : end]
                if value.startswith("!"):
                    value = "^" + value[1:]
                output.append("[" + value + "]")
                index = end
        else:
            output.append(re.escape(char))
        index += 1
    return "".join(output)


def matches_path(path: str, pattern: str) -> bool:
    path = normalize_path(path)
    pattern = normalize_path(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if any(token in pattern for token in GLOB_CHARS):
        return re.fullmatch(glob_regex(pattern), path) is not None
    return path == pattern


def changed_paths(root: str, base_ref: str, head_ref: str) -> set[str] | None:
    result = git(root, "diff", "--name-status", "-M", f"{base_ref}...{head_ref}")
    if result.returncode != 0:
        return None
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            paths.add(normalize_path(parts[1]))
            paths.add(normalize_path(parts[2]))
        elif len(parts) >= 2:
            paths.add(normalize_path(parts[-1]))
    return paths


def task_ids_from_diff(
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    paths: set[str],
) -> set[str]:
    affected: set[str] = set()
    for section in ("foundationTasks", "tasks"):
        before = mapping(base_plan.get(section))
        after = mapping(current_plan.get(section))
        for task_id in set(before) | set(after):
            if before.get(task_id) != after.get(task_id):
                affected.add(task_id)
    before_active = mapping(base_active.get("tasks"))
    after_active = mapping(current_active.get("tasks"))
    for task_id in set(before_active) | set(after_active):
        if before_active.get(task_id) != after_active.get(task_id):
            affected.add(task_id)
    before_records = mapping(base_ledger.get("records"))
    after_records = mapping(current_ledger.get("records"))
    for task_id in set(before_records) | set(after_records):
        if before_records.get(task_id) != after_records.get(task_id):
            affected.add(task_id)
    for path in paths:
        match = TASK_PATH_RE.fullmatch(path)
        if match:
            affected.add(match.group(1))
    return affected


def allowed_metadata_paths(task_id: str, task_path: str, ordinary_completion: bool) -> tuple[set[str], tuple[str, ...]]:
    exact = {PLAN, ACTIVE, task_path}
    if ordinary_completion:
        exact.add(LEDGER)
    prefixes = (f"evidence/{task_id}",)
    return exact, prefixes


def path_allowed(path: str, exact: set[str], prefixes: tuple[str, ...], claims: list[str]) -> bool:
    if path in exact:
        return True
    if any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes):
        return True
    return any(matches_path(path, claim) for claim in claims)


def gz014_completion_snapshot(root: str, ref: str) -> bool:
    plan = load_ref(root, ref, PLAN)
    active = load_ref(root, ref, ACTIVE)
    task_path = find_task_path(root, "GZ-014", ref)
    front = parse_front(read_ref(root, ref, task_path or ""))
    if not isinstance(plan, dict) or not isinstance(active, dict) or not front:
        return False
    foundation = mapping(plan.get("foundationTasks")).get("GZ-014", {})
    has_active = any(
        item.get("taskId") == "GZ-014" for item in active.get("tasks") or []
    )
    return (
        foundation.get("status") == "completed"
        and front.get("status") == "completed"
        and not has_active
    )


def exact_token(message: str, token: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])", message) is not None


def is_gz003_bootstrap_authorized_base(root: str, resolved_base: str) -> bool:
    """Prove the target base is the immutable GZ-014 Completion PR #33 merge.

    Authorization facts all live outside the seven exempted migration paths:
    target-base commit identity/parent, the target-base Program/Task/Registry
    snapshot, and GZ-014's task-bound completion Evidence.
    """
    if not resolved_base or not gz014_completion_snapshot(root, resolved_base):
        return False
    parent = resolve_ref(root, f"{resolved_base}^1")
    if not parent or gz014_completion_snapshot(root, parent):
        return False
    message_result = git(root, "show", "-s", "--format=%B", resolved_base)
    if message_result.returncode != 0:
        return False
    message = message_result.stdout
    if not exact_token(message, "GZ-014") or not re.search(r"(?<!\d)#33(?!\d)", message):
        return False
    evidence = read_ref(root, resolved_base, GZ014_COMPLETION_EVIDENCE) or ""
    return bool(
        re.search(r"(?mi)^Status:\s*COMPLETED\b", evidence)
        and re.search(r"(?<!\d)PR\s*#33(?!\d)", evidence)
    )


def is_one_time_gz003_bootstrap_migration(
    task_id: str,
    base_is_authorized: bool,
    before_status: str,
    after_status: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    paths: set[str],
    task_spec_unchanged: bool,
) -> bool:
    return (
        task_id == "GZ-003"
        and base_is_authorized
        and before_status == "completed"
        and after_status == "completed"
        and base_plan == current_plan
        and base_active == current_active
        and base_ledger == current_ledger
        and task_spec_unchanged
        and paths == set(GZ003_BOOTSTRAP_MIGRATION_PATHS)
    )


def completion_record(ledger: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    records = [
        item
        for item in ledger.get("records") or []
        if isinstance(item, dict) and item.get("taskId") == task_id
    ]
    return records[0] if len(records) == 1 else None


def completion_merge_sha(
    task_id: str,
    current_plan: dict[str, Any],
    current_ledger: dict[str, Any],
) -> str | None:
    foundations = mapping(current_plan.get("foundationTasks"))
    if task_id in foundations:
        value = foundations[task_id].get("mergeCommit")
        return str(value) if value else None
    record = completion_record(current_ledger, task_id)
    value = record.get("mergeCommit") if record else None
    return str(value) if value else None


def validate_structured_completion_evidence(
    root: str,
    task_id: str,
    merge_sha: str,
    paths: set[str],
    errors: list[str],
) -> None:
    required = {
        f"evidence/{task_id}/summary.md",
        f"evidence/{task_id}/commands.txt",
        f"evidence/{task_id}/test-results/README.md",
        f"evidence/{task_id}/handoff.md",
    }
    missing = sorted(required - paths)
    if missing:
        errors.append(
            f"Completion task {task_id} must refresh structured Evidence files: {missing}"
        )
        return
    contents: dict[str, str] = {}
    for relative in required:
        full = os.path.join(root, relative)
        if not os.path.isfile(full):
            errors.append(f"Completion task {task_id} Evidence file is missing: {relative}")
            continue
        with open(full, "r", encoding="utf-8") as handle:
            contents[relative] = handle.read()
    for relative, content in contents.items():
        if task_id not in content or merge_sha not in content:
            errors.append(
                f"Completion Evidence {relative} must identify {task_id} and merge {merge_sha}"
            )
    commands = contents.get(f"evidence/{task_id}/commands.txt", "")
    if not re.search(r"(?mi)^command:\s*\S.+$", commands):
        errors.append(f"Completion task {task_id} commands.txt has no executed command")
    if not re.search(r"(?mi)^exit code:\s*0\s*$", commands):
        errors.append(f"Completion task {task_id} commands.txt has no successful exit code")
    if not re.search(r"(?mi)^result:\s*(PASS|SUCCESS)\b", commands):
        errors.append(f"Completion task {task_id} commands.txt has no explicit PASS result")
    tests = contents.get(f"evidence/{task_id}/test-results/README.md", "")
    if not re.search(r"(?mi)^(status|result):\s*(PASS|SUCCESS)\b", tests):
        errors.append(f"Completion task {task_id} test results have no explicit PASS status")
    for relative in (
        f"evidence/{task_id}/summary.md",
        f"evidence/{task_id}/handoff.md",
    ):
        if relative in contents and not re.search(
            r"(?mi)^(status|result):\s*(COMPLETED|PASS|SUCCESS)\b", contents[relative]
        ):
            errors.append(f"Completion Evidence {relative} has no explicit completed/pass status")


def validate_cancellation_evidence(
    root: str,
    task_id: str,
    before_status: str,
    paths: set[str],
    errors: list[str],
) -> None:
    relative = f"evidence/{task_id}/cancellation.md"
    if relative not in paths:
        errors.append(f"Cancellation task {task_id} must refresh {relative}")
        return
    full = os.path.join(root, relative)
    if not os.path.isfile(full):
        errors.append(f"Cancellation task {task_id} Evidence is missing: {relative}")
        return
    with open(full, "r", encoding="utf-8") as handle:
        content = handle.read()
    requirements = {
        "task": rf"(?mi)^Task:\s*{re.escape(task_id)}\s*$",
        "transition": rf"(?mi)^Transition:\s*{re.escape(before_status)}\s*->\s*cancelled\s*$",
        "reason": r"(?mi)^Reason:\s*\S.+$",
        "retained artifacts": r"(?mi)^Retained Artifacts:\s*\S.+$",
        "validation": r"(?mi)^Validation:\s*(PASS|FAIL|INCONCLUSIVE)\b",
    }
    for label, pattern in requirements.items():
        if not re.search(pattern, content):
            errors.append(
                f"Cancellation Evidence {relative} is missing structured {label} information"
            )


def module_owned_patterns(ownership: dict[str, Any], module_ids: set[str]) -> list[str]:
    patterns: list[str] = []
    for module in ownership.get("modules") or []:
        if isinstance(module, dict) and module.get("id") in module_ids:
            patterns.extend(str(item) for item in module.get("ownedPaths") or [])
    return patterns


def validate_foundation_claims(
    task_id: str,
    entry: dict[str, Any],
    ownership: dict[str, Any],
    resolved_base: str,
    errors: list[str],
) -> None:
    if str(entry.get("baseSha") or "") != resolved_base:
        errors.append(
            f"Active Foundation {task_id} baseSha must equal audited target base {resolved_base}"
        )
    module_patterns = module_owned_patterns(
        ownership, {str(item) for item in entry.get("moduleIds") or []}
    )
    exception_patterns = list(FOUNDATION_SCOPE_EXCEPTIONS.get(task_id, ()))
    for claim in list(entry.get("exclusivePaths") or []) + list(entry.get("sharedPaths") or []):
        if not any(
            paths_overlap(str(claim), pattern)
            for pattern in module_patterns + exception_patterns
        ):
            errors.append(
                f"Active Foundation {task_id} path claim {claim} is outside module ownership and audited repair scope"
            )


def validate_completed_spec_binding(
    root: str,
    task_id: str,
    current_plan: dict[str, Any],
    errors: list[str],
) -> None:
    task_path = find_task_path(root, task_id)
    if not task_path:
        errors.append(f"Completed Program task {task_id} has no Task Spec")
        return
    with open(os.path.join(root, task_path), "r", encoding="utf-8") as handle:
        front = parse_front(handle.read())
    expected_evidence = f"evidence/{task_id}"
    expected_handoff = f"{expected_evidence}/handoff.md"
    if front.get("evidencePath") != expected_evidence:
        errors.append(
            f"Completed Program task {task_id} Task Spec evidencePath must be {expected_evidence}"
        )
    if front.get("handoffPath") != expected_handoff:
        errors.append(
            f"Completed Program task {task_id} Task Spec handoffPath must be {expected_handoff}"
        )


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    if not ref_exists(root, args.base_ref) or not ref_exists(root, args.head_ref):
        emit("FAIL", "Lifecycle guard refs are missing")
        return 1
    resolved_base = resolve_ref(root, args.base_ref)
    if not resolved_base:
        emit("FAIL", "Lifecycle guard target base cannot be resolved")
        return 1
    base_is_bootstrap_authorized = is_gz003_bootstrap_authorized_base(root, resolved_base)
    try:
        base_plan = load_ref(root, args.base_ref, PLAN)
        current_plan = load_current(root, PLAN)
        base_active = load_ref(root, args.base_ref, ACTIVE)
        current_active = load_current(root, ACTIVE)
        base_ledger = load_ref(root, args.base_ref, LEDGER)
        current_ledger = load_current(root, LEDGER)
        ownership = load_current(root, OWNERSHIP)
    except Exception as exc:
        emit("FAIL", f"Cannot load lifecycle guard documents: {exc}")
        return 1
    if base_ledger is None and isinstance(current_ledger, dict) and not (current_ledger.get("records") or []):
        base_ledger = {"records": []}
    if not all(
        isinstance(item, dict)
        for item in (
            base_plan,
            current_plan,
            base_active,
            current_active,
            base_ledger,
            current_ledger,
            ownership,
        )
    ):
        emit("FAIL", "Lifecycle guard documents are missing or invalid")
        return 1
    paths = changed_paths(root, args.base_ref, args.head_ref)
    if paths is None:
        emit("FAIL", "Lifecycle guard cannot determine changed paths")
        return 1
    affected = task_ids_from_diff(
        base_plan,
        current_plan,
        base_active,
        current_active,
        base_ledger,
        current_ledger,
        paths,
    )
    if args.task:
        affected.add(args.task)

    base_tasks = mapping(base_plan.get("tasks"))
    current_tasks = mapping(current_plan.get("tasks"))
    base_foundations = mapping(base_plan.get("foundationTasks"))
    current_foundations = mapping(current_plan.get("foundationTasks"))
    current_entries = mapping(current_active.get("tasks"))

    for task_id, task in current_tasks.items():
        if task.get("status") == "completed":
            validate_completed_spec_binding(root, task_id, current_plan, errors)

    for task_id in sorted(affected):
        ordinary = task_id in current_tasks or task_id in base_tasks
        foundation = task_id in current_foundations or task_id in base_foundations
        before = (base_tasks if ordinary else base_foundations).get(task_id, {})
        after = (current_tasks if ordinary else current_foundations).get(task_id, {})
        before_status = str(before.get("status") or "")
        after_status = str(after.get("status") or "")
        task_path = find_task_path(root, task_id)
        if not task_path:
            errors.append(f"Affected lifecycle task {task_id} has no current Task Spec")
            continue
        entry = current_entries.get(task_id)
        claims: list[str] = []
        if entry:
            claims = [
                str(item)
                for item in list(entry.get("exclusivePaths") or [])
                + list(entry.get("sharedPaths") or [])
            ]
        ordinary_completion = ordinary and after_status == "completed"
        exact, prefixes = allowed_metadata_paths(task_id, task_path, ordinary_completion)
        task_spec_unchanged = read_ref(root, args.base_ref, task_path) == read_ref(
            root, args.head_ref, task_path
        )
        bootstrap_migration = is_one_time_gz003_bootstrap_migration(
            task_id,
            base_is_bootstrap_authorized,
            before_status,
            after_status,
            base_plan,
            current_plan,
            base_active,
            current_active,
            base_ledger,
            current_ledger,
            paths,
            task_spec_unchanged,
        )
        metadata_mode = after_status in METADATA_STATES
        if bootstrap_migration:
            invalid: list[str] = []
        elif metadata_mode:
            invalid = sorted(
                path
                for path in paths
                if not path_allowed(path, exact, prefixes, [])
            )
        else:
            invalid = sorted(
                path
                for path in paths
                if not path_allowed(path, exact, prefixes, claims)
            )
        if invalid:
            errors.append(
                f"Lifecycle task {task_id} changed files outside its {'metadata' if metadata_mode else 'registered'} scope: {invalid}"
            )

        if foundation and entry and after_status in IMPLEMENTATION_STATES | {"reserved", "blocked"}:
            validate_foundation_claims(task_id, entry, ownership, resolved_base, errors)

        if after_status == "cancelled" and before_status != "cancelled":
            validate_cancellation_evidence(root, task_id, before_status, paths, errors)

        if after_status == "completed" and before_status != "completed":
            if before_status not in COMPLETION_BASE_STATES:
                errors.append(
                    f"Lifecycle task {task_id} cannot complete directly from {before_status}; target base must be review or integration"
                )
            merge_sha = completion_merge_sha(task_id, current_plan, current_ledger)
            if not merge_sha:
                errors.append(f"Lifecycle task {task_id} has no unique implementation merge SHA")
            else:
                validate_structured_completion_evidence(
                    root, task_id, merge_sha, paths, errors
                )

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program lifecycle scope, Foundation ownership, rename and Evidence guards passed",
        {
            "affectedTaskIds": sorted(affected),
            "changedPathCount": len(paths),
            "baseRef": args.base_ref,
            "bootstrapBaseAuthorized": base_is_bootstrap_authorized,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

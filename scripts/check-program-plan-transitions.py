#!/usr/bin/env python3
"""Validate Guize Program lifecycle transitions against the integration base.

Snapshot validators prove that the current documents are internally consistent.
This history-aware checker constrains reservation, active, Foundation and
cancellation changes so one task cannot rewrite another task, widen canonical
scope, bypass Program waves, or mix implementation into reservation metadata.
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
from typing import Any

import yaml

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
TASK_DIR = "specs/tasks"
ACTIVE_STATES = {"reserved", "in_progress", "blocked", "review", "integration"}
FINISHED_WAVE_STATES = {"completed", "cancelled"}
ALLOWED_ACTIVE_TRANSITIONS = {
    ("planned", "reserved"),
    ("blocked", "reserved"),
    ("reserved", "in_progress"),
    ("in_progress", "review"),
    ("review", "integration"),
    ("blocked", "in_progress"),
    ("in_progress", "blocked"),
    ("review", "blocked"),
    ("integration", "blocked"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program Plan transitions")
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
        if isinstance(item, dict)
    }


def find_task_path(root: str, task_id: str, ref: str | None = None) -> str | None:
    exact = f"{TASK_DIR}/{task_id}.md"
    if ref:
        if read_ref(root, ref, exact) is not None:
            return exact
        result = git(root, "ls-tree", "-r", "--name-only", ref, TASK_DIR)
        if result.returncode != 0:
            return None
        matches = sorted(
            path
            for path in result.stdout.splitlines()
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


def parse_front_matter(text: str | None) -> tuple[dict[str, Any], str]:
    if not text or not text.startswith("---"):
        return {}, text or ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        document = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, parts[2]
    return (document if isinstance(document, dict) else {}), parts[2]


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if not text or text.upper() == "NONE":
        return []
    return [part.strip() for part in text.strip("[]").split(",") if part.strip()]


def section_paths(body: str, titles: tuple[str, ...]) -> list[str] | None:
    lines = body.splitlines()
    start: int | None = None
    wanted = tuple(value.lower() for value in titles)
    for index, line in enumerate(lines):
        if not line.strip().startswith("## "):
            continue
        title = re.sub(r"^##\s+", "", line.strip()).lower()
        if any(item in title for item in wanted):
            start = index + 1
            break
    if start is None:
        return None
    paths: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        match = re.match(r"[-*]\s+(.+)$", stripped)
        if not match:
            continue
        value = match.group(1).strip()
        quoted = re.search(r"`([^`]+)`", value)
        if quoted:
            value = quoted.group(1).strip()
        if value in {"无", "无。", "NONE", "none"}:
            continue
        if quoted or "/" in value or "*" in value or value.startswith("."):
            value = value.replace("\\", "/")
            while value.startswith("./"):
                value = value[2:]
            paths.append(value.rstrip("/"))
    return paths


def changed_files(root: str, base_ref: str, head_ref: str) -> set[str] | None:
    result = git(root, "diff", "--name-only", f"{base_ref}...{head_ref}")
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def compare_set(
    task_id: str,
    registry: dict[str, Any],
    planned: dict[str, Any],
    registry_key: str,
    planned_key: str,
    errors: list[str],
) -> None:
    left = set(registry.get(registry_key) or [])
    right = set(planned.get(planned_key) or [])
    if left != right:
        errors.append(
            f"Active task {task_id} {registry_key}={sorted(left)} does not match "
            f"Program Plan {planned_key}={sorted(right)}"
        )


def validate_active_program_scope(
    plan: dict[str, Any], active: dict[str, Any], errors: list[str]
) -> None:
    """Bind every ordinary active Registry entry to its complete Program identity."""
    planned = mapping(plan.get("tasks"))
    for entry in active.get("tasks") or []:
        if not isinstance(entry, dict):
            continue
        task_id = str(entry.get("taskId") or "")
        task = planned.get(task_id)
        if not task:
            continue
        scalar_pairs = {
            "title": "title",
            "status": "status",
            "riskLevel": "riskLevel",
            "workPackage": "workPackage",
            "coordinationGroup": "coordinationGroup",
            "integrationOrder": "integrationOrder",
            "programWave": "wave",
        }
        for registry_key, planned_key in scalar_pairs.items():
            if entry.get(registry_key) != task.get(planned_key):
                errors.append(
                    f"Active task {task_id} {registry_key}={entry.get(registry_key)!r} "
                    f"does not match Program Plan {planned_key}={task.get(planned_key)!r}"
                )
        if entry.get("programPlan") != PLAN:
            errors.append(f"Active task {task_id} programPlan must be {PLAN}")
        if entry.get("programTaskId") != task_id:
            errors.append(f"Active task {task_id} programTaskId must equal taskId")
        if task.get("issue") is not None and entry.get("issue") != task.get("issue"):
            errors.append(
                f"Active task {task_id} issue={entry.get('issue')!r} does not match "
                f"Program Plan issue={task.get('issue')!r}"
            )
        branch_pattern = str(task.get("branchPattern") or "")
        if not branch_pattern or not fnmatch.fnmatchcase(
            str(entry.get("branch") or ""), branch_pattern
        ):
            errors.append(
                f"Active task {task_id} branch {entry.get('branch')!r} does not match "
                f"Program Plan branchPattern {branch_pattern!r}"
            )
        for registry_key, planned_key in (
            ("dependsOn", "dependsOn"),
            ("requirementIds", "requirementIds"),
            ("moduleIds", "moduleIds"),
            ("producesContracts", "producesContracts"),
            ("consumesContracts", "consumesContracts"),
            ("exclusivePaths", "outputPaths"),
            ("sharedPaths", "sharedPaths"),
        ):
            compare_set(task_id, entry, task, registry_key, planned_key, errors)


def validate_wave_activation(plan: dict[str, Any], errors: list[str]) -> None:
    """Prevent a later Program wave from opening before every earlier wave closes."""
    wave_order = {
        str(item.get("id")): int(item.get("order"))
        for item in plan.get("waves") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    tasks = [item for item in plan.get("tasks") or [] if isinstance(item, dict)]
    for task in tasks:
        if task.get("status") not in ACTIVE_STATES:
            continue
        task_id = str(task.get("taskId") or "")
        order = wave_order.get(str(task.get("wave") or ""))
        if order is None:
            continue
        blockers = sorted(
            str(other.get("taskId") or "")
            for other in tasks
            if wave_order.get(str(other.get("wave") or ""), order) < order
            and other.get("status") not in FINISHED_WAVE_STATES
        )
        if blockers:
            errors.append(
                f"Program task {task_id} cannot activate in wave {task.get('wave')} while "
                f"earlier-wave tasks remain unfinished: {', '.join(blockers)}"
            )


def only_section_target_changed(
    base: dict[str, Any],
    current: dict[str, Any],
    section: str,
    task_id: str,
    allowed_fields: set[str],
) -> bool:
    base_copy = copy.deepcopy(base)
    current_copy = copy.deepcopy(current)
    base_items = mapping(base_copy.get(section))
    current_items = mapping(current_copy.get(section))
    if set(base_items) != set(current_items) or task_id not in current_items:
        return False
    for other_id in base_items:
        if other_id != task_id and base_items[other_id] != current_items[other_id]:
            return False
    base_target = copy.deepcopy(base_items[task_id])
    current_target = copy.deepcopy(current_items[task_id])
    for field in allowed_fields:
        base_target.pop(field, None)
        current_target.pop(field, None)
    if base_target != current_target:
        return False
    base_copy[section] = []
    current_copy[section] = []
    return base_copy == current_copy


def registry_without_task(document: dict[str, Any], task_id: str) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["tasks"] = [
        item for item in result.get("tasks") or [] if item.get("taskId") != task_id
    ]
    return result


def entry_without_fields(entry: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    result = copy.deepcopy(entry)
    for field in fields:
        result.pop(field, None)
    return result


def validate_active_transition(
    root: str,
    base_ref: str,
    head_ref: str,
    task_id: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    errors: list[str],
) -> None:
    """Allow only the current ordinary or Foundation task's lifecycle transition."""
    base_tasks = mapping(base_plan.get("tasks"))
    current_tasks = mapping(current_plan.get("tasks"))
    base_foundations = mapping(base_plan.get("foundationTasks"))
    current_foundations = mapping(current_plan.get("foundationTasks"))
    section = "tasks" if task_id in current_tasks else "foundationTasks"
    current_map = current_tasks if section == "tasks" else current_foundations
    base_map = base_tasks if section == "tasks" else base_foundations
    current_task = current_map.get(task_id)
    if not current_task or current_task.get("status") not in ACTIVE_STATES:
        return
    base_task = base_map.get(task_id)
    if not base_task:
        errors.append(f"Active transition task {task_id} did not exist in {base_ref}")
        return
    base_status = str(base_task.get("status") or "")
    current_status = str(current_task.get("status") or "")
    transition = (base_status, current_status)
    if transition[0] != transition[1] and transition not in ALLOWED_ACTIVE_TRANSITIONS:
        errors.append(
            f"Program task {task_id} has invalid active transition {base_status} -> {current_status}"
        )
    if not only_section_target_changed(
        base_plan, current_plan, section, task_id, {"status"}
    ):
        errors.append(
            f"Active transition for {task_id} may only change that {section} task's status"
        )

    base_entries = [
        item for item in base_active.get("tasks") or [] if item.get("taskId") == task_id
    ]
    current_entries = [
        item for item in current_active.get("tasks") or [] if item.get("taskId") == task_id
    ]
    if len(current_entries) != 1:
        errors.append(f"Active transition for {task_id} requires one current Registry entry")
        return
    if registry_without_task(base_active, task_id) != registry_without_task(
        current_active, task_id
    ):
        errors.append(
            f"Active transition for {task_id} may not modify Registry policy or another task"
        )

    ordinary_reservation = (
        section == "tasks"
        and current_status == "reserved"
        and base_status in {"planned", "blocked"}
    )
    if ordinary_reservation:
        if base_entries:
            errors.append(f"Reservation transition for {task_id} must introduce its Registry entry")
        task_path = find_task_path(root, task_id)
        files = changed_files(root, base_ref, head_ref)
        if not task_path or files is None:
            errors.append(f"Reservation transition for {task_id} cannot determine its file set")
            return
        allowed_exact = {PLAN, ACTIVE, task_path}
        invalid = sorted(
            path
            for path in files
            if path not in allowed_exact
            and path != f"evidence/{task_id}"
            and not path.startswith(f"evidence/{task_id}/")
        )
        if invalid:
            errors.append(
                f"Reservation transition for {task_id} contains implementation or unrelated files: {invalid}"
            )
    else:
        if len(base_entries) != 1:
            errors.append(
                f"Active transition for {task_id} requires one prior Registry entry in {base_ref}"
            )
            return
        allowed_entry_fields = {"status", "agentRole", "baseSha", "lease"}
        if entry_without_fields(base_entries[0], allowed_entry_fields) != entry_without_fields(
            current_entries[0], allowed_entry_fields
        ):
            errors.append(
                f"Active transition for {task_id} changed stable Registry identity or scope"
            )


def stable_spec_matches(
    task_id: str,
    entry: dict[str, Any],
    front: dict[str, Any],
    body: str,
    errors: list[str],
) -> None:
    scalar_pairs = {
        "id": "taskId",
        "baseBranch": "baseBranch",
        "issue": "issue",
        "workPackage": "workPackage",
        "taskOwner": "owner",
        "coordinator": "coordinator",
        "implementer": "implementer",
        "reviewer": "reviewer",
        "integrator": "integrator",
        "riskLevel": "riskLevel",
        "coordinationGroup": "coordinationGroup",
        "handoffPath": "handoffPath",
        "integrationStrategy": "integrationStrategy",
        "integrationOrder": "integrationOrder",
    }
    for task_key, entry_key in scalar_pairs.items():
        if str(front.get(task_key, "")) != str(entry.get(entry_key, "")):
            errors.append(
                f"{task_id} Task Spec {task_key} does not match Active Work {entry_key}"
            )
    for task_key, entry_key in {
        "dependsOn": "dependsOn",
        "requirementIds": "requirementIds",
        "moduleIds": "moduleIds",
        "producesContracts": "producesContracts",
        "consumesContracts": "consumesContracts",
    }.items():
        if as_list(front.get(task_key)) != list(entry.get(entry_key) or []):
            errors.append(
                f"{task_id} Task Spec {task_key} does not match Active Work {entry_key}"
            )
    exclusive = section_paths(body, ("独占写范围", "exclusive write scope"))
    shared = section_paths(body, ("共享修改范围", "shared modification scope"))
    if set(exclusive or []) != set(entry.get("exclusivePaths") or []):
        errors.append(f"{task_id} Task Spec exclusive paths do not match Active Work")
    if set(shared or []) != set(entry.get("sharedPaths") or []):
        errors.append(f"{task_id} Task Spec shared paths do not match Active Work")


def validate_cancel_transition(
    root: str,
    base_ref: str,
    head_ref: str,
    branch_name: str,
    task_id: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    errors: list[str],
) -> None:
    base_tasks = mapping(base_plan.get("tasks"))
    current_tasks = mapping(current_plan.get("tasks"))
    before = base_tasks.get(task_id)
    after = current_tasks.get(task_id)
    if not before or not after or before.get("status") not in ACTIVE_STATES or after.get("status") != "cancelled":
        errors.append(f"Cancellation task {task_id} has an invalid Program status transition")
        return
    if not only_section_target_changed(base_plan, current_plan, "tasks", task_id, {"status"}):
        errors.append(f"Cancellation task {task_id} may only change its Program status")
    prior_entries = [
        item for item in base_active.get("tasks") or [] if item.get("taskId") == task_id
    ]
    if len(prior_entries) != 1:
        errors.append(f"Cancellation task {task_id} requires one prior Active Work entry")
        return
    if registry_without_task(base_active, task_id) != current_active:
        errors.append(f"Cancellation task {task_id} may only remove its own Active Work entry")
    if current_ledger != base_ledger:
        errors.append(f"Cancellation task {task_id} must not modify the completion ledger")
    task_path = find_task_path(root, task_id, head_ref)
    if not task_path:
        errors.append(f"Cancellation task {task_id} has no Task Spec")
        return
    front, body = parse_front_matter(read_ref(root, head_ref, task_path))
    if front.get("status") != "cancelled":
        errors.append(f"Cancellation task {task_id} Task Spec is not cancelled")
    resolved_base = resolve_ref(root, base_ref)
    if resolved_base and str(front.get("baseSha") or "") != resolved_base:
        errors.append(f"Cancellation task {task_id} Task Spec baseSha must equal target base")
    if branch_name and str(front.get("workBranch") or "") != branch_name:
        errors.append(f"Cancellation task {task_id} Task Spec branch does not match PR branch")
    stable_spec_matches(task_id, prior_entries[0], front, body, errors)
    files = changed_files(root, base_ref, head_ref)
    if files is None:
        errors.append(f"Cancellation task {task_id} cannot determine changed files")
        return
    allowed_exact = {PLAN, ACTIVE, task_path}
    invalid = sorted(
        path
        for path in files
        if path not in allowed_exact
        and path != f"evidence/{task_id}"
        and not path.startswith(f"evidence/{task_id}/")
    )
    if invalid:
        errors.append(f"Cancellation task {task_id} changed unrelated files: {invalid}")


def validate_recorded_reservation_commit(
    root: str, record: dict[str, Any], errors: list[str]
) -> None:
    """Prove that a ledger reservation commit was metadata-only and introduced the lease."""
    task_id = str(record.get("taskId") or "")
    commit = str(record.get("reservationCommit") or "")
    task_path = str(record.get("taskSpec") or "")
    if not commit or not task_path or not ref_exists(root, commit):
        return
    parent_result = git(root, "rev-parse", f"{commit}^1")
    if parent_result.returncode != 0:
        errors.append(f"Reservation commit for {task_id} has no first parent")
        return
    parent = parent_result.stdout.strip()
    diff = git(root, "diff", "--name-only", parent, commit)
    if diff.returncode != 0:
        errors.append(f"Reservation commit for {task_id} changed-file set cannot be read")
        return
    files = {line.strip() for line in diff.stdout.splitlines() if line.strip()}
    allowed_exact = {PLAN, ACTIVE, task_path}
    invalid = sorted(
        path
        for path in files
        if path not in allowed_exact
        and path != f"evidence/{task_id}"
        and not path.startswith(f"evidence/{task_id}/")
    )
    if invalid:
        errors.append(
            f"Reservation commit for {task_id} contains implementation or unrelated files: {invalid}"
        )

    parent_plan = load_ref(root, parent, PLAN)
    commit_plan = load_ref(root, commit, PLAN)
    parent_active = load_ref(root, parent, ACTIVE)
    commit_active = load_ref(root, commit, ACTIVE)
    if not all(
        isinstance(item, dict)
        for item in (parent_plan, commit_plan, parent_active, commit_active)
    ):
        errors.append(f"Reservation commit for {task_id} lacks readable Program/Registry metadata")
        return
    parent_tasks = mapping(parent_plan.get("tasks"))
    commit_tasks = mapping(commit_plan.get("tasks"))
    if (
        task_id not in parent_tasks
        or parent_tasks[task_id].get("status") not in {"planned", "blocked"}
        or commit_tasks.get(task_id, {}).get("status") != "reserved"
        or not only_section_target_changed(parent_plan, commit_plan, "tasks", task_id, {"status"})
    ):
        errors.append(
            f"Reservation commit for {task_id} must only transition that Program task to reserved"
        )
    parent_entries = [
        item for item in parent_active.get("tasks") or [] if item.get("taskId") == task_id
    ]
    commit_entries = [
        item for item in commit_active.get("tasks") or [] if item.get("taskId") == task_id
    ]
    if parent_entries or len(commit_entries) != 1 or commit_entries[0].get("status") != "reserved":
        errors.append(f"Reservation commit for {task_id} did not introduce one reserved lease")
    if registry_without_task(parent_active, task_id) != registry_without_task(
        commit_active, task_id
    ):
        errors.append(
            f"Reservation commit for {task_id} changed Registry policy or another task"
        )


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    if not ref_exists(root, args.base_ref) or not ref_exists(root, args.head_ref):
        emit("FAIL", "Program transition refs are missing")
        return 1
    try:
        base_plan = load_ref(root, args.base_ref, PLAN)
        current_plan = load_current(root, PLAN)
        base_active = load_ref(root, args.base_ref, ACTIVE)
        current_active = load_current(root, ACTIVE)
        base_ledger = load_ref(root, args.base_ref, LEDGER)
        current_ledger = load_current(root, LEDGER)
    except Exception as exc:
        emit("FAIL", f"Cannot load Program transition documents: {exc}")
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
        )
    ):
        emit("FAIL", "Program transition documents are missing or invalid")
        return 1

    validate_active_program_scope(current_plan, current_active, errors)
    validate_wave_activation(current_plan, errors)
    for record in current_ledger.get("records") or []:
        if isinstance(record, dict):
            validate_recorded_reservation_commit(root, record, errors)
    if args.task:
        task_path = find_task_path(root, args.task, args.head_ref)
        front, _ = parse_front_matter(read_ref(root, args.head_ref, task_path or ""))
        if front.get("status") == "cancelled":
            validate_cancel_transition(
                root,
                args.base_ref,
                args.head_ref,
                args.branch_name,
                args.task,
                base_plan,
                current_plan,
                base_active,
                current_active,
                base_ledger,
                current_ledger,
                errors,
            )
        else:
            validate_active_transition(
                root,
                args.base_ref,
                args.head_ref,
                args.task,
                base_plan,
                current_plan,
                base_active,
                current_active,
                errors,
            )

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program reservation scope, wave and lifecycle transitions passed",
        {
            "task": args.task or None,
            "activeTasks": len(current_active.get("tasks") or []),
            "completionRecords": len(current_ledger.get("records") or []),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

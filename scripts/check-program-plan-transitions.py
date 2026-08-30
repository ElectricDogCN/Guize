#!/usr/bin/env python3
"""Validate Guize Program reservation scope and lifecycle transitions.

Snapshot validators prove that the current documents are internally consistent.
This checker compares the proposed branch with the target branch and prevents a
reservation or execution transition from silently rewriting another Program
task, widening its canonical scope, skipping earlier waves, or putting
implementation work into the reservation commit recorded by the completion
ledger.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import os
import subprocess
import sys
from typing import Any

import yaml

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
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
            # Foundation and unknown-task handling remains in Finalization.
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


def plan_only_changes_target_status(
    base: dict[str, Any], current: dict[str, Any], task_id: str
) -> bool:
    base_copy = copy.deepcopy(base)
    current_copy = copy.deepcopy(current)
    base_tasks = mapping(base_copy.get("tasks"))
    current_tasks = mapping(current_copy.get("tasks"))
    if set(base_tasks) != set(current_tasks) or task_id not in current_tasks:
        return False
    for other_id in base_tasks:
        if other_id != task_id and base_tasks[other_id] != current_tasks[other_id]:
            return False
    base_target = copy.deepcopy(base_tasks[task_id])
    current_target = copy.deepcopy(current_tasks[task_id])
    base_target.pop("status", None)
    current_target.pop("status", None)
    if base_target != current_target:
        return False
    base_copy["tasks"] = []
    current_copy["tasks"] = []
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
    """Allow only the current ordinary task's lifecycle transition across the base."""
    base_tasks = mapping(base_plan.get("tasks"))
    current_tasks = mapping(current_plan.get("tasks"))
    if task_id not in current_tasks:
        return  # Foundation transitions are validated by History/Finalization.
    current_status = current_tasks[task_id].get("status")
    if current_status not in ACTIVE_STATES:
        return
    base_task = base_tasks.get(task_id)
    if not base_task:
        errors.append(f"Active transition task {task_id} did not exist in {base_ref}")
        return
    base_status = str(base_task.get("status") or "")
    transition = (base_status, str(current_status))
    if transition[0] != transition[1] and transition not in ALLOWED_ACTIVE_TRANSITIONS:
        errors.append(
            f"Program task {task_id} has invalid active transition {base_status} -> {current_status}"
        )
    if not plan_only_changes_target_status(base_plan, current_plan, task_id):
        errors.append(
            f"Active transition for {task_id} may only change that Program task's status"
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

    if current_status == "reserved" and base_status in {"planned", "blocked"}:
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


def validate_recorded_reservation_commit(
    root: str, record: dict[str, Any], errors: list[str]
) -> None:
    """Prove that a ledger reservation commit was metadata-only and introduced the lease."""
    task_id = str(record.get("taskId") or "")
    commit = str(record.get("reservationCommit") or "")
    task_path = str(record.get("taskSpec") or "")
    if not commit or not task_path or not ref_exists(root, commit):
        return  # Identity/existence failures are emitted by Program Integrity/History.
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
        or not plan_only_changes_target_status(parent_plan, commit_plan, task_id)
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
        ledger = load_current(root, "specs/coordination/task-completions.yaml")
    except Exception as exc:
        emit("FAIL", f"Cannot load Program transition documents: {exc}")
        return 1
    if not all(
        isinstance(item, dict)
        for item in (base_plan, current_plan, base_active, current_active, ledger)
    ):
        emit("FAIL", "Program transition documents are missing or invalid")
        return 1

    validate_active_program_scope(current_plan, current_active, errors)
    validate_wave_activation(current_plan, errors)
    for record in ledger.get("records") or []:
        if isinstance(record, dict):
            validate_recorded_reservation_commit(root, record, errors)
    if args.task:
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
            "completionRecords": len(ledger.get("records") or []),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

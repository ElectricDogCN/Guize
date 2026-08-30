#!/usr/bin/env python3
"""Validate historical Program Plan transitions against the target branch.

The snapshot checker validates the current repository state. This checker
validates transitions against the integration base:

* a recorded reservation commit actually introduced the task lease;
* completed Foundation provenance is immutable;
* Completion PRs modify only the completing task's canonical metadata;
* ordinary tasks append one immutable completion-ledger record;
* Foundation tasks complete without using the ordinary completion ledger.
"""

from __future__ import annotations

import argparse
import copy
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
PR_REF_RE = re.compile(r"^PR-([0-9]+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program Plan history transitions")
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


def git(root: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def ref_exists(root: str, ref: str) -> bool:
    return bool(ref) and git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").returncode == 0


def resolve_ref(root: str, ref: str) -> str | None:
    result = git(root, "rev-parse", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def read_ref(root: str, ref: str, path: str) -> str | None:
    if not path:
        return None
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def load_yaml_text(text: str | None) -> Any | None:
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def load_current(root: str, path: str) -> Any:
    with open(os.path.join(root, path), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_ref(root: str, ref: str, path: str) -> Any | None:
    return load_yaml_text(read_ref(root, ref, path))


def parse_front_matter_text(text: str | None) -> tuple[dict[str, Any], str]:
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


def normalize_list(value: Any) -> list[str]:
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
    values: list[str] = []
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
        if "/" in value or "*" in value or value.startswith("."):
            values.append(value.replace("\\", "/").rstrip("/"))
    return values


def mapping(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {str(item.get("taskId")): item for item in (items or [])}


def only_target_changed(
    base_document: dict[str, Any],
    current_document: dict[str, Any],
    section: str,
    task_id: str,
    allowed_fields: set[str],
) -> bool:
    base_copy = copy.deepcopy(base_document)
    current_copy = copy.deepcopy(current_document)
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


def exact_token(message: str, token: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])", message) is not None


def exact_pr(message: str, reference: str) -> bool:
    match = PR_REF_RE.fullmatch(reference)
    return bool(match and re.search(rf"(?<!\d)#{match.group(1)}(?!\d)", message))


def validate_commit_identity(
    root: str, sha: str, task_id: str, reference: str, label: str, errors: list[str]
) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        errors.append(f"{label} has invalid SHA: {sha!r}")
        return
    if git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        errors.append(f"{label} commit does not exist: {sha}")
        return
    message = git(root, "show", "-s", "--format=%B", sha).stdout
    if not exact_token(message, task_id):
        errors.append(f"{label} commit {sha} does not identify {task_id}")
    if not exact_pr(message, reference):
        errors.append(f"{label} commit {sha} does not identify {reference}")
    if not is_ancestor(root, sha, "HEAD"):
        errors.append(f"{label} commit {sha} is not reachable from HEAD")


def compare_reservation_spec(
    task_id: str,
    entry: dict[str, Any],
    front: dict[str, Any],
    body: str,
    errors: list[str],
) -> None:
    scalar_pairs = {
        "id": "taskId",
        "status": "status",
        "workBranch": "branch",
        "baseBranch": "baseBranch",
        "baseSha": "baseSha",
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
                f"Reservation snapshot {task_id} Task Spec {task_key} does not match Active Work {entry_key}"
            )
    list_pairs = {
        "dependsOn": "dependsOn",
        "requirementIds": "requirementIds",
        "moduleIds": "moduleIds",
        "producesContracts": "producesContracts",
        "consumesContracts": "consumesContracts",
    }
    for task_key, entry_key in list_pairs.items():
        if normalize_list(front.get(task_key)) != list(entry.get(entry_key) or []):
            errors.append(
                f"Reservation snapshot {task_id} Task Spec {task_key} does not match Active Work {entry_key}"
            )
    exclusive = section_paths(body, ("独占写范围", "exclusive write scope"))
    shared = section_paths(body, ("共享修改范围", "shared modification scope"))
    if exclusive != list(entry.get("exclusivePaths") or []):
        errors.append(f"Reservation snapshot {task_id} exclusive paths do not match Active Work")
    if shared != list(entry.get("sharedPaths") or []):
        errors.append(f"Reservation snapshot {task_id} shared paths do not match Active Work")


def compare_completion_spec(
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
                f"Completion Task Spec {task_id} {task_key} does not match prior Active Work {entry_key}"
            )
    for task_key, entry_key in {
        "dependsOn": "dependsOn",
        "requirementIds": "requirementIds",
        "moduleIds": "moduleIds",
        "producesContracts": "producesContracts",
        "consumesContracts": "consumesContracts",
    }.items():
        if normalize_list(front.get(task_key)) != list(entry.get(entry_key) or []):
            errors.append(
                f"Completion Task Spec {task_id} {task_key} does not match prior Active Work {entry_key}"
            )
    exclusive = section_paths(body, ("独占写范围", "exclusive write scope"))
    shared = section_paths(body, ("共享修改范围", "shared modification scope"))
    if exclusive != list(entry.get("exclusivePaths") or []):
        errors.append(f"Completion Task Spec {task_id} exclusive paths do not match prior Active Work")
    if shared != list(entry.get("sharedPaths") or []):
        errors.append(f"Completion Task Spec {task_id} shared paths do not match prior Active Work")


def changed_file_set(root: str, base_ref: str, head_ref: str, errors: list[str]) -> set[str]:
    result = git(root, "diff", "--name-only", f"{base_ref}...{head_ref}")
    if result.returncode != 0:
        errors.append(f"Cannot read changed files for {base_ref}...{head_ref}")
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_changed_scope(
    task_id: str,
    task_path: str,
    files: set[str],
    foundation: bool,
    errors: list[str],
) -> None:
    required = {PLAN, ACTIVE, task_path}
    if not foundation:
        required.add(LEDGER)
    missing = sorted(required - files)
    if missing:
        errors.append(f"Completion task {task_id} is missing canonical files: {missing}")
    allowed_exact = set(required)
    invalid = sorted(
        path
        for path in files
        if path not in allowed_exact
        and path != f"evidence/{task_id}"
        and not path.startswith(f"evidence/{task_id}/")
    )
    if invalid:
        errors.append(f"Completion task {task_id} changed unrelated files: {invalid}")
    if foundation and LEDGER in files:
        errors.append(f"Foundation {task_id} completion must not change {LEDGER}")


def validate_reservation_snapshot(root: str, record: dict[str, Any], errors: list[str]) -> None:
    task_id = str(record.get("taskId") or "")
    commit = str(record.get("reservationCommit") or "")
    active_at_commit = load_ref(root, commit, ACTIVE)
    if not isinstance(active_at_commit, dict):
        errors.append(f"Completion record {task_id} reservation commit has no readable {ACTIVE}")
        return
    entries = [item for item in active_at_commit.get("tasks") or [] if item.get("taskId") == task_id]
    if len(entries) != 1:
        errors.append(
            f"Completion record {task_id} reservation commit must contain exactly one Active Work entry"
        )
        return
    entry = entries[0]
    if entry.get("status") != "reserved":
        errors.append(
            f"Completion record {task_id} reservation snapshot status must be reserved, got {entry.get('status')}"
        )
    parent = resolve_ref(root, f"{commit}^1")
    if not parent:
        errors.append(f"Completion record {task_id} reservation commit has no first parent")
    else:
        prior_active = load_ref(root, parent, ACTIVE)
        if isinstance(prior_active, dict) and any(
            item.get("taskId") == task_id for item in prior_active.get("tasks") or []
        ):
            errors.append(
                f"Completion record {task_id} reservation commit did not introduce the reservation"
            )
    task_path = str(record.get("taskSpec") or "")
    front, body = parse_front_matter_text(read_ref(root, commit, task_path))
    if not front:
        errors.append(f"Completion record {task_id} reservation Task Spec is not readable at commit")
    else:
        compare_reservation_spec(task_id, entry, front, body, errors)
    base_sha = str(entry.get("baseSha") or "")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", base_sha)
        or base_sha == commit
        or not is_ancestor(root, base_sha, commit)
    ):
        errors.append(
            f"Completion record {task_id} reservation baseSha must be a strict ancestor of reservation commit"
        )


def validate_foundation_history(
    root: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    base_ref: str,
    head_ref: str,
    branch_name: str,
    errors: list[str],
) -> None:
    base_foundations = mapping(base_plan.get("foundationTasks"))
    current_foundations = mapping(current_plan.get("foundationTasks"))
    for task_id, prior in base_foundations.items():
        if prior.get("status") == "completed" and current_foundations.get(task_id) != prior:
            errors.append(f"Completed Foundation {task_id} provenance is immutable")
    for task_id, current in current_foundations.items():
        prior = base_foundations.get(task_id)
        if current.get("status") != "completed" or (prior and prior.get("status") == "completed"):
            continue
        if not prior or prior.get("status") not in ACTIVE_STATES:
            errors.append(f"Foundation {task_id} cannot complete without an active base state")
            continue
        prior_entries = [item for item in base_active.get("tasks") or [] if item.get("taskId") == task_id]
        if len(prior_entries) != 1:
            errors.append(f"Foundation {task_id} completion requires one prior Active Work reservation")
            continue
        expected_active = copy.deepcopy(base_active)
        expected_active["tasks"] = [
            item for item in base_active.get("tasks") or [] if item.get("taskId") != task_id
        ]
        if current_active != expected_active:
            errors.append(f"Foundation {task_id} completion may only remove its own Active Work entry")
        if current_ledger != base_ledger:
            errors.append(f"Foundation {task_id} completion must not modify the ordinary completion ledger")
        if not only_target_changed(
            base_plan,
            current_plan,
            "foundationTasks",
            task_id,
            {"status", "completionRef", "mergeCommit"},
        ):
            errors.append(f"Foundation {task_id} completion may only change its completion identity")
        merge_sha = str(current.get("mergeCommit") or "")
        completion_ref = str(current.get("completionRef") or "")
        validate_commit_identity(root, merge_sha, task_id, completion_ref, f"Foundation {task_id}", errors)
        base_sha = str(prior_entries[0].get("baseSha") or "")
        if (
            not re.fullmatch(r"[0-9a-f]{40}", base_sha)
            or merge_sha == base_sha
            or not is_ancestor(root, base_sha, merge_sha)
        ):
            errors.append(
                f"Foundation {task_id} mergeCommit must be a strict descendant of its reservation baseSha"
            )
        task_path = find_task_path(root, task_id)
        if not task_path:
            errors.append(f"Foundation {task_id} completion has no Task Spec")
            continue
        front, body = parse_front_matter_text(read_ref(root, head_ref, task_path))
        if front.get("status") != "completed":
            errors.append(f"Foundation {task_id} Task Spec is not completed")
        resolved_base = resolve_ref(root, base_ref)
        if resolved_base and str(front.get("baseSha") or "") != resolved_base:
            errors.append(f"Foundation {task_id} Task Spec baseSha must equal the target base commit")
        if branch_name and str(front.get("workBranch") or "") != branch_name:
            errors.append(f"Foundation {task_id} Task Spec workBranch does not match the PR branch")
        compare_completion_spec(task_id, prior_entries[0], front, body, errors)
        evidence = str(front.get("evidencePath") or f"evidence/{task_id}")
        handoff = str(front.get("handoffPath") or f"{evidence}/handoff.md")
        if evidence != f"evidence/{task_id}":
            errors.append(f"Foundation {task_id} Evidence path must be task-bound")
        if not os.path.isdir(os.path.join(root, evidence)):
            errors.append(f"Foundation {task_id} Evidence path does not exist")
        if not os.path.isfile(os.path.join(root, handoff)):
            errors.append(f"Foundation {task_id} handoff does not exist")
        validate_changed_scope(
            task_id,
            task_path,
            changed_file_set(root, base_ref, head_ref, errors),
            True,
            errors,
        )


def validate_regular_completion_transition(
    root: str,
    task_id: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    base_ref: str,
    head_ref: str,
    branch_name: str,
    errors: list[str],
) -> None:
    base_tasks = mapping(base_plan.get("tasks"))
    current_tasks = mapping(current_plan.get("tasks"))
    prior = base_tasks.get(task_id)
    current = current_tasks.get(task_id)
    if not prior or not current or current.get("status") != "completed":
        errors.append(f"Completion task {task_id} is not a completed ordinary Program task")
        return
    if prior.get("status") not in ACTIVE_STATES:
        errors.append(f"Completion task {task_id} base Program status is not active")
    if not only_target_changed(base_plan, current_plan, "tasks", task_id, {"status"}):
        errors.append(f"Completion task {task_id} may only change its Program status")
    prior_entries = [item for item in base_active.get("tasks") or [] if item.get("taskId") == task_id]
    if len(prior_entries) != 1:
        errors.append(f"Completion task {task_id} requires one prior Active Work entry")
        return
    expected_active = copy.deepcopy(base_active)
    expected_active["tasks"] = [
        item for item in base_active.get("tasks") or [] if item.get("taskId") != task_id
    ]
    if current_active != expected_active:
        errors.append(f"Completion task {task_id} may only remove its own Active Work entry")
    base_records = base_ledger.get("records") or []
    current_records = current_ledger.get("records") or []
    if len(current_records) != len(base_records) + 1 or current_records[: len(base_records)] != base_records:
        errors.append(f"Completion task {task_id} must append exactly one immutable ledger record")
    elif current_records[-1].get("taskId") != task_id:
        errors.append(f"Completion task {task_id} appended ledger record is bound to another task")
    task_path = find_task_path(root, task_id)
    if not task_path:
        errors.append(f"Completion task {task_id} has no Task Spec")
        return
    front, body = parse_front_matter_text(read_ref(root, head_ref, task_path))
    if front.get("status") != "completed":
        errors.append(f"Completion task {task_id} Task Spec status is not completed")
    resolved_base = resolve_ref(root, base_ref)
    if resolved_base and str(front.get("baseSha") or "") != resolved_base:
        errors.append(f"Completion task {task_id} Task Spec baseSha must equal the target base commit")
    if branch_name and str(front.get("workBranch") or "") != branch_name:
        errors.append(f"Completion task {task_id} Task Spec workBranch does not match the PR branch")
    compare_completion_spec(task_id, prior_entries[0], front, body, errors)
    validate_changed_scope(
        task_id,
        task_path,
        changed_file_set(root, base_ref, head_ref, errors),
        False,
        errors,
    )


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    if not ref_exists(root, args.base_ref) or not ref_exists(root, args.head_ref):
        emit("FAIL", "Program history refs are missing")
        return 1
    try:
        base_plan = load_ref(root, args.base_ref, PLAN)
        current_plan = load_current(root, PLAN)
        base_active = load_ref(root, args.base_ref, ACTIVE)
        current_active = load_current(root, ACTIVE)
        base_ledger = load_ref(root, args.base_ref, LEDGER)
        current_ledger = load_current(root, LEDGER)
    except Exception as exc:
        emit("FAIL", f"Cannot load Program history documents: {exc}")
        return 1
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
        emit("FAIL", "Program history documents are missing or invalid")
        return 1

    validate_foundation_history(
        root,
        base_plan,
        current_plan,
        base_active,
        current_active,
        base_ledger,
        current_ledger,
        args.base_ref,
        args.head_ref,
        args.branch_name,
        errors,
    )
    for record in current_ledger.get("records") or []:
        validate_reservation_snapshot(root, record, errors)

    if args.task:
        task_path = find_task_path(root, args.task)
        front, _ = parse_front_matter_text(read_ref(root, args.head_ref, task_path or ""))
        if front.get("status") == "completed":
            current_foundations = mapping(current_plan.get("foundationTasks"))
            if args.task not in current_foundations:
                validate_regular_completion_transition(
                    root,
                    args.task,
                    base_plan,
                    current_plan,
                    base_active,
                    current_active,
                    base_ledger,
                    current_ledger,
                    args.base_ref,
                    args.head_ref,
                    args.branch_name,
                    errors,
                )

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program Plan history transitions are valid",
        {
            "baseRef": args.base_ref,
            "headRef": args.head_ref,
            "completionRecords": len(current_ledger.get("records") or []),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

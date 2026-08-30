#!/usr/bin/env python3
"""Run the mandatory Program lifecycle guard with exact history semantics."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GUARD_PATH = os.path.join(SCRIPT_DIR, "check-program-lifecycle-guards.py")
SPEC = importlib.util.spec_from_file_location("guize_program_lifecycle_guards", GUARD_PATH)
GUARD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(GUARD)
BLOCKER_OWNER_TASKS = {"BRANCH-PROTECTION": "GZ-018"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run exact Program lifecycle guard")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--task", default="")
    parser.add_argument("--branch-name", default="")
    return parser.parse_args()


def exact_changed_paths(root: str, base_ref: str, head_ref: str) -> set[str] | None:
    """Compare the two exact endpoints and preserve both rename/copy paths."""
    result = GUARD.git(root, "diff", "--name-status", "-M", base_ref, head_ref)
    if result.returncode != 0:
        return None
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if parts[0].startswith(("R", "C")) and len(parts) >= 3:
            paths.add(GUARD.normalize_path(parts[1]))
            paths.add(GUARD.normalize_path(parts[2]))
        elif len(parts) >= 2:
            paths.add(GUARD.normalize_path(parts[-1]))
    return paths


def expanded_task_ids_from_diff(
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    paths: set[str],
) -> set[str]:
    affected = GUARD.task_ids_from_diff(
        base_plan,
        current_plan,
        base_active,
        current_active,
        base_ledger,
        current_ledger,
        paths,
    )
    for section in ("pocs",):
        before = GUARD.mapping(base_plan.get(section))
        after = GUARD.mapping(current_plan.get(section))
        for task_id in set(before) | set(after):
            if before.get(task_id) != after.get(task_id):
                affected.add(task_id)
    before_blockers = GUARD.mapping(base_plan.get("externalBlockers"), key="id")
    after_blockers = GUARD.mapping(current_plan.get("externalBlockers"), key="id")
    for blocker_id in set(before_blockers) | set(after_blockers):
        if before_blockers.get(blocker_id) != after_blockers.get(blocker_id):
            owner = BLOCKER_OWNER_TASKS.get(blocker_id)
            if owner:
                affected.add(owner)
    return affected


def github_issue(number: int) -> dict[str, Any]:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        raise RuntimeError("GITHUB_REPOSITORY is not available")
    base = os.environ.get("GUIZE_GITHUB_API_URL", "https://api.github.com").rstrip("/")
    url = f"{base}/repos/{repository}/issues/{number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "guize-program-lifecycle-gate",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            value = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"GitHub Issue API request failed: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("GitHub Issue API returned a non-object")
    return value


def front_matter_issue(root: str, task_id: str) -> int | None:
    task_path = GUARD.find_task_path(root, task_id)
    if not task_path:
        return None
    with open(os.path.join(root, task_path), "r", encoding="utf-8") as handle:
        front = GUARD.parse_front(handle.read())
    try:
        return int(front.get("issue"))
    except (TypeError, ValueError):
        return None


def completion_transitions(
    base_plan: dict[str, Any], current_plan: dict[str, Any]
) -> set[str]:
    completed: set[str] = set()
    for section in ("foundationTasks", "tasks"):
        before = GUARD.mapping(base_plan.get(section))
        after = GUARD.mapping(current_plan.get(section))
        for task_id, current in after.items():
            if current.get("status") == "completed" and before.get(task_id, {}).get("status") != "completed":
                completed.add(task_id)
    return completed


def validate_completion_issues(
    root: str,
    base_ref: str,
    errors: list[str],
) -> None:
    base_plan = GUARD.load_ref(root, base_ref, GUARD.PLAN)
    current_plan = GUARD.load_current(root, GUARD.PLAN)
    if not isinstance(base_plan, dict) or not isinstance(current_plan, dict):
        errors.append("Completion Issue validation cannot load Program Plan snapshots")
        return
    for task_id in sorted(completion_transitions(base_plan, current_plan)):
        issue_number = front_matter_issue(root, task_id)
        if not issue_number:
            errors.append(f"Completion task {task_id} has no numeric Issue identity")
            continue
        try:
            issue = github_issue(issue_number)
        except RuntimeError as exc:
            errors.append(f"Completion task {task_id} Issue #{issue_number} cannot be verified: {exc}")
            continue
        if issue.get("state") != "closed" or issue.get("state_reason") != "completed":
            errors.append(
                f"Completion task {task_id} requires Issue #{issue_number} closed with state_reason=completed"
            )


def main() -> int:
    args = parse_args()
    # Reuse the complete lifecycle scope/Evidence implementation, replacing
    # only the two history-sensitive extension points.
    GUARD.changed_paths = exact_changed_paths
    GUARD.task_ids_from_diff = expanded_task_ids_from_diff
    original_argv = sys.argv
    sys.argv = [
        GUARD_PATH,
        "--repo-root",
        args.repo_root,
        "--base-ref",
        args.base_ref,
        "--head-ref",
        args.head_ref,
        "--task",
        args.task,
        "--branch-name",
        args.branch_name,
    ]
    try:
        result = GUARD.main()
    finally:
        sys.argv = original_argv
    if result != 0:
        return result
    errors: list[str] = []
    validate_completion_issues(os.path.abspath(args.repo_root), args.base_ref, errors)
    if errors:
        for error in errors:
            GUARD.emit("FAIL", error)
        return 1
    GUARD.emit("PASS", "Exact lifecycle diff and Completion Issue verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

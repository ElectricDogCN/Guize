#!/usr/bin/env python3
"""Run mandatory Task Scope validation for implementation and lifecycle PRs.

A planned Registration is metadata-only and is checked by the shared
history-aware Registration validator. It never receives ordinary implementation
scope. Reservation and later lifecycle metadata retain their existing paths.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

import yaml

IMPLEMENTATION_TASK_STATES = {"in_progress", "review", "integration"}
REGISTRATION_TASK_STATES = {"planned"}
METADATA_TASK_STATES = {"reserved", "blocked", "cancelled", "completed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch the Task Scope gate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--branch-name", default="")
    parser.add_argument(
        "--scope-script",
        default="scripts/check-task-scope.py",
        help="Override only for isolated dispatcher tests",
    )
    parser.add_argument(
        "--registration-script",
        default="scripts/check-program-task-registration.py",
        help="Override only for isolated dispatcher tests",
    )
    return parser.parse_args()


def find_task_file(root: str, task_id: str) -> str | None:
    directory = os.path.join(root, "specs", "tasks")
    exact = os.path.join(directory, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    if not os.path.isdir(directory):
        return None
    matches = sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.startswith(task_id + "-") and name.endswith(".md")
    )
    return matches[0] if len(matches) == 1 else None


def task_document(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if not content.startswith("---"):
        raise ValueError("Task Spec has no YAML front matter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Task Spec front matter is not terminated")
    document: Any = yaml.safe_load(parts[1])
    if not isinstance(document, dict):
        raise ValueError("Task Spec front matter is not a mapping")
    return document


def resolve_script(root: str, value: str) -> str:
    return value if os.path.isabs(value) else os.path.join(root, value)


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    path = find_task_file(root, args.task)
    if not path:
        print(f"FAIL: Task Spec not found for {args.task}")
        return 2
    try:
        document = task_document(path)
        status = str(document.get("status") or "")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"FAIL: Cannot read Task Spec status for {args.task}: {exc}")
        return 2

    if status in REGISTRATION_TASK_STATES:
        if document.get("coordinationMode") != "registration":
            print("FAIL: planned Task requires coordinationMode registration")
            return 2
        registration_script = resolve_script(root, args.registration_script)
        if not os.path.isfile(registration_script):
            print(
                f"FAIL: Registration checker does not exist: {registration_script}"
            )
            return 2
        branch_name = args.branch_name or str(document.get("workBranch") or "")
        command = [
            sys.executable,
            registration_script,
            "--repo-root",
            root,
            "--base-ref",
            args.base,
            "--head-ref",
            args.head_ref,
            "--task",
            args.task,
        ]
        if branch_name:
            command += ["--branch-name", branch_name]
        return subprocess.run(command, cwd=root, check=False).returncode

    if status in METADATA_TASK_STATES:
        label = {
            "reserved": "Reservation PR",
            "blocked": "Blocked-state metadata PR",
            "cancelled": "Cancellation PR",
            "completed": "Completion PR",
        }[status]
        print(
            f"INFO: {args.task} is a {label}; exact changed-file scope is owned by Program History and Program Transitions against the target branch."
        )
        return 0

    if status not in IMPLEMENTATION_TASK_STATES:
        print(f"FAIL: Unsupported Task status for scope dispatch: {status!r}")
        return 2

    scope_script = resolve_script(root, args.scope_script)
    if not os.path.isfile(scope_script):
        print(f"FAIL: Scope checker does not exist: {scope_script}")
        return 2
    return subprocess.run(
        [
            sys.executable,
            scope_script,
            "--repo-root",
            root,
            "--task",
            args.task,
            "--base",
            args.base,
        ],
        cwd=root,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())

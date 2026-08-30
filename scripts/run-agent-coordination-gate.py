#!/usr/bin/env python3
"""Run the mandatory Agent Coordination mode for the current Task.

Active/reservation work is validated against its current Active Work entry by
``check-agent-coordination.py --task``. A Completion PR intentionally removes
that entry, so task-specific completion semantics are owned by the mandatory
Program History checker. For completed Task Specs this dispatcher therefore
runs the global Registry validation only; the workflow and ``make verify`` run
Program Integrity/History immediately before this command.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

import yaml

ACTIVE_TASK_STATES = {"reserved", "in_progress", "blocked", "review", "integration"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch the Agent Coordination gate")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--task", default="")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--branch-name", default="")
    parser.add_argument(
        "--coordination-script",
        default="scripts/check-agent-coordination.py",
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


def task_status(path: str) -> str:
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
    return str(document.get("status") or "")


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    script = args.coordination_script
    if not os.path.isabs(script):
        script = os.path.join(root, script)
    if not os.path.isfile(script):
        print(f"FAIL: Coordination checker does not exist: {script}")
        return 2

    command = [sys.executable, script, "--repo-root", root]
    if args.task:
        path = find_task_file(root, args.task)
        if not path:
            print(f"FAIL: Task Spec not found for {args.task}")
            return 2
        try:
            status = task_status(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"FAIL: Cannot read Task Spec status for {args.task}: {exc}")
            return 2
        if status in ACTIVE_TASK_STATES:
            command += ["--task", args.task]
            if args.base_ref:
                command += ["--base-ref", args.base_ref]
            if args.head_ref:
                command += ["--head-ref", args.head_ref]
            if args.branch_name:
                command += ["--branch-name", args.branch_name]
        elif status == "completed":
            print(
                f"INFO: {args.task} is a Completion PR; task-specific transition "
                "validation is provided by the mandatory Program History gate."
            )
        else:
            print(f"FAIL: Unsupported Task status for coordination dispatch: {status!r}")
            return 2

    result = subprocess.run(command, cwd=root, check=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

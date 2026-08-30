#!/usr/bin/env python3
"""Run the mandatory Agent Coordination mode for the current Task.

Active/reservation work is validated against its current Active Work entry by
``check-agent-coordination.py --task``. A Completion PR intentionally removes
that entry, so task-specific completion semantics are owned by the mandatory
Program History checker. For completed Task Specs this dispatcher therefore
runs the global Registry validation only; the workflow and ``make verify`` run
Program Integrity/History immediately before this command.

The dispatcher also performs a repository-wide lifecycle guard: every ordinary
Program task whose Program Plan state is ``completed`` must retain a Task Spec
whose completion state and stable Program identity exactly match the canonical
plan. Legacy Foundation tasks are intentionally excluded because their older
Task Specs may use the historical ``approved`` state and are governed by
Foundation provenance checks instead.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

import yaml

ACTIVE_TASK_STATES = {"reserved", "in_progress", "blocked", "review", "integration"}
PROGRAM_PLAN = "specs/coordination/program-plan.yaml"
NONE_VALUES = {"", "NONE", "none", "null", "N/A", "n/a"}


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


def task_status(path: str) -> str:
    return str(task_document(path).get("status") or "")


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if text in NONE_VALUES:
        return []
    return [part.strip() for part in text.strip("[]").split(",") if part.strip()]


def validate_completed_program_specs(root: str) -> list[str]:
    """Reject completed Program tasks whose Task Spec identity has drifted."""
    path = os.path.join(root, PROGRAM_PLAN)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            plan: Any = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        return [f"Cannot read canonical Program Plan lifecycle state: {exc}"]
    if not isinstance(plan, dict):
        return ["Canonical Program Plan is not a mapping"]

    errors: list[str] = []
    scalar_pairs = {
        "title": "titleZh",
        "workPackage": "workPackage",
        "riskLevel": "riskLevel",
        "coordinationGroup": "coordinationGroup",
        "wave": "wave",
        "integrationOrder": "integrationOrder",
        "exitGate": "exitGate",
    }
    list_fields = (
        "dependsOn",
        "requirementIds",
        "moduleIds",
        "producesContracts",
        "consumesContracts",
    )

    for task in plan.get("tasks") or []:
        if not isinstance(task, dict) or task.get("status") != "completed":
            continue
        task_id = str(task.get("taskId") or "")
        spec = find_task_file(root, task_id)
        if not spec:
            errors.append(f"Completed Program task {task_id} has no unique Task Spec")
            continue
        try:
            document = task_document(spec)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"Completed Program task {task_id} Task Spec is unreadable: {exc}")
            continue

        if document.get("status") != "completed":
            errors.append(
                f"Completed Program task {task_id} Task Spec status must be exactly completed, "
                f"got {document.get('status')!r}"
            )
        if document.get("programPlan") != PROGRAM_PLAN:
            errors.append(
                f"Completed Program task {task_id} Task Spec programPlan must be {PROGRAM_PLAN}"
            )
        if document.get("programTaskId") != task_id or document.get("id") != task_id:
            errors.append(
                f"Completed Program task {task_id} Task Spec identity does not match its Program task"
            )
        if document.get("coordinationMode") != "registry":
            errors.append(
                f"Completed Program task {task_id} Task Spec coordinationMode must remain registry"
            )

        for plan_field, spec_field in scalar_pairs.items():
            if str(document.get(spec_field, "")) != str(task.get(plan_field, "")):
                errors.append(
                    f"Completed Program task {task_id} Task Spec {spec_field} does not match "
                    f"Program Plan {plan_field}"
                )
        if task.get("issue") is not None and str(document.get("issue", "")) != str(
            task.get("issue")
        ):
            errors.append(
                f"Completed Program task {task_id} Task Spec issue does not match Program Plan"
            )
        for field in list_fields:
            if as_list(document.get(field)) != [str(item) for item in task.get(field) or []]:
                errors.append(
                    f"Completed Program task {task_id} Task Spec {field} does not match Program Plan"
                )
    return errors


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    script = args.coordination_script
    if not os.path.isabs(script):
        script = os.path.join(root, script)
    if not os.path.isfile(script):
        print(f"FAIL: Coordination checker does not exist: {script}")
        return 2

    lifecycle_errors = validate_completed_program_specs(root)
    if lifecycle_errors:
        for error in lifecycle_errors:
            print(f"FAIL: {error}")
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

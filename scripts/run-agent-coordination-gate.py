#!/usr/bin/env python3
"""Run the mandatory Agent Coordination mode for the current Task.

Implementation work is validated against Active Work path claims. Registration
is metadata-only and is always validated by the canonical history-aware
Registration checker; callers cannot replace that checker. Non-Registration
fixtures do not need to vendor the Registration checker merely to exercise the
existing dispatcher modes.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from typing import Any

import yaml

IMPLEMENTATION_TASK_STATES = {"in_progress", "review", "integration"}
REGISTRATION_TASK_STATES = {"planned"}
METADATA_TASK_STATES = {"reserved", "blocked", "cancelled", "completed"}
PROGRAM_PLAN = "specs/coordination/program-plan.yaml"
REGISTRATION_SCRIPT = "scripts/check-program-task-registration.py"
NONE_VALUES = {"", "NONE", "none", "null", "N/A", "n/a"}
ZERO_SHA = "0" * 40


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
        help="Override only for isolated non-Registration dispatcher tests",
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


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if text in NONE_VALUES:
        return []
    return [part.strip() for part in text.strip("[]").split(",") if part.strip()]


def load_program_plan(root: str) -> tuple[dict[str, Any] | None, list[str]]:
    path = os.path.join(root, PROGRAM_PLAN)
    if not os.path.isfile(path):
        return None, []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            plan: Any = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        return None, [f"Cannot read canonical Program Plan lifecycle state: {exc}"]
    if not isinstance(plan, dict):
        return None, ["Canonical Program Plan is not a mapping"]
    return plan, []


def validate_completed_foundation_specs(root: str, plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for foundation in plan.get("foundationTasks") or []:
        if not isinstance(foundation, dict) or foundation.get("status") != "completed":
            continue
        task_id = str(foundation.get("taskId") or "")
        spec = find_task_file(root, task_id)
        if not spec:
            errors.append(f"Completed Foundation task {task_id} has no unique Task Spec")
            continue
        try:
            document = task_document(spec)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"Completed Foundation task {task_id} Task Spec is unreadable: {exc}")
            continue
        schema_version = document.get("schemaVersion")
        status = document.get("status")
        if schema_version is None:
            if status not in {"approved", "completed"}:
                errors.append(
                    f"Legacy completed Foundation task {task_id} Task Spec has invalid status {status!r}"
                )
        elif status != "completed":
            errors.append(
                f"schemaVersion {schema_version} completed Foundation task {task_id} Task Spec status must remain completed, got {status!r}"
            )
    return errors


def validate_completed_program_specs(root: str, plan: dict[str, Any]) -> list[str]:
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
                f"Completed Program task {task_id} Task Spec status must be exactly completed, got {document.get('status')!r}"
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
                    f"Completed Program task {task_id} Task Spec {spec_field} does not match Program Plan {plan_field}"
                )
        if task.get("issue") is not None and str(document.get("issue", "")) != str(task.get("issue")):
            errors.append(
                f"Completed Program task {task_id} Task Spec issue does not match Program Plan"
            )
        for field in list_fields:
            if as_list(document.get(field)) != [str(item) for item in task.get(field) or []]:
                errors.append(
                    f"Completed Program task {task_id} Task Spec {field} does not match Program Plan"
                )
    return errors


def resolve_script(root: str, value: str) -> str:
    return value if os.path.isabs(value) else os.path.join(root, value)


def registration_script_path(root: str) -> str:
    return os.path.join(root, REGISTRATION_SCRIPT)


def load_registration_module(root: str):
    path = registration_script_path(root)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Registration checker does not exist: {path}")
    spec = importlib.util.spec_from_file_location("guize_program_task_registration", path)
    if not spec or not spec.loader:
        raise RuntimeError("Cannot load canonical Registration checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_ref_exists(root: str, ref: str) -> bool:
    if not ref:
        return False
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def program_plan_changed(root: str, base_ref: str, head_ref: str) -> bool | None:
    if not base_ref or not head_ref:
        return False
    result = subprocess.run(
        ["git", "diff", "--quiet", f"{base_ref}...{head_ref}", "--", PROGRAM_PLAN],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    return None


def global_history_context(args: argparse.Namespace, root: str) -> tuple[str, str, str]:
    if args.base_ref and args.head_ref:
        return args.base_ref, args.head_ref, args.branch_name
    event = os.environ.get("EVENT_NAME") or os.environ.get("GITHUB_EVENT_NAME") or ""
    before = os.environ.get("PUSH_BEFORE") or os.environ.get("GITHUB_EVENT_BEFORE") or ""
    branch = args.branch_name or os.environ.get("GITHUB_REF_NAME") or "main"
    if event == "push" and before and before != ZERO_SHA and git_ref_exists(root, before):
        return before, args.head_ref or "HEAD", branch
    return "", "", branch


def run_registration(
    module: Any,
    root: str,
    base_ref: str,
    head_ref: str,
    task: str,
    branch_name: str,
) -> int:
    code, details = module.validate_registration(
        root,
        base_ref,
        head_ref,
        task_hint=task,
        branch_name=branch_name,
    )
    if code:
        for error in details.get("errors") or []:
            module.emit("FAIL", error)
        return code
    module.emit(
        "PASS",
        "Agent Coordination accepted metadata-only Program Task Registration",
        details,
    )
    return 0


def validate_global_program_specs(root: str) -> int | None:
    plan, lifecycle_errors = load_program_plan(root)
    if plan is not None:
        lifecycle_errors.extend(validate_completed_foundation_specs(root, plan))
        lifecycle_errors.extend(validate_completed_program_specs(root, plan))
    if lifecycle_errors:
        for error in lifecycle_errors:
            print(f"FAIL: {error}")
        return 2
    return None


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    coordination_script = resolve_script(root, args.coordination_script)
    if not os.path.isfile(coordination_script):
        print(f"FAIL: Coordination checker does not exist: {coordination_script}")
        return 2

    # Resolve task-aware Registration before running repository-wide completed
    # Task consistency. The Registration validator proves the whole base/head
    # metadata transition and must not require unrelated completed-task files in
    # an isolated behavioral fixture.
    task_document_value: dict[str, Any] | None = None
    task_status = ""
    if args.task:
        path = find_task_file(root, args.task)
        if not path:
            print(f"FAIL: Task Spec not found for {args.task}")
            return 2
        try:
            task_document_value = task_document(path)
            task_status = str(task_document_value.get("status") or "")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"FAIL: Cannot read Task Spec status for {args.task}: {exc}")
            return 2
        if task_status in REGISTRATION_TASK_STATES:
            if task_document_value.get("coordinationMode") != "registration":
                print("FAIL: planned Task requires coordinationMode registration")
                return 2
            if not args.base_ref or not args.head_ref or not args.branch_name:
                print(
                    "FAIL: Task-aware Registration coordination requires exact base/head refs and an authoritative branch name"
                )
                return 2
            try:
                registration = load_registration_module(root)
            except (OSError, RuntimeError) as exc:
                print(f"FAIL: {exc}")
                return 2
            return run_registration(
                registration,
                root,
                args.base_ref,
                args.head_ref,
                task=args.task,
                branch_name=args.branch_name,
            )

    # In push/no-task mode, load the canonical validator only when the current
    # repository actually has it. An isolated non-Registration fixture may omit
    # the new checker; however, any Program Plan change with no checker fails
    # closed rather than falling through to ordinary coordination.
    if not args.task:
        base_ref, head_ref, branch_name = global_history_context(args, root)
        if base_ref and head_ref:
            changed = program_plan_changed(root, base_ref, head_ref)
            if changed is None:
                print("FAIL: Cannot determine Program Plan change in no-task mode")
                return 2
            path = registration_script_path(root)
            if os.path.isfile(path):
                try:
                    registration = load_registration_module(root)
                except (OSError, RuntimeError) as exc:
                    print(f"FAIL: {exc}")
                    return 2
                if registration.is_registration_candidate(root, base_ref, head_ref):
                    return run_registration(
                        registration,
                        root,
                        base_ref,
                        head_ref,
                        task="",
                        branch_name=branch_name,
                    )
            elif changed:
                print(
                    f"FAIL: Program Plan changed but canonical Registration checker is missing: {path}"
                )
                return 2

    global_result = validate_global_program_specs(root)
    if global_result is not None:
        return global_result

    command = [sys.executable, coordination_script, "--repo-root", root]
    if args.task:
        status = task_status
        if status in IMPLEMENTATION_TASK_STATES:
            command += ["--task", args.task]
            if args.base_ref:
                command += ["--base-ref", args.base_ref]
            if args.head_ref:
                command += ["--head-ref", args.head_ref]
            if args.branch_name:
                command += ["--branch-name", args.branch_name]
        elif status in METADATA_TASK_STATES:
            label = {
                "reserved": "Reservation PR",
                "blocked": "Blocked-state metadata PR",
                "cancelled": "Cancellation PR",
                "completed": "Completion PR",
            }[status]
            print(
                f"INFO: {args.task} is a {label}; exact target-base lifecycle and file scope are validated by the mandatory Program History/Transitions/Finalization gates."
            )
        else:
            print(f"FAIL: Unsupported Task status for coordination dispatch: {status!r}")
            return 2

    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())

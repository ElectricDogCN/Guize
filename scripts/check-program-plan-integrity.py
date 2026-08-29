#!/usr/bin/env python3
"""Validate Guize Program Plan execution and completion integrity.

This checker complements structural JSON Schema validation. It enforces the
cross-file invariants that make the Program Plan, Active Work Registry, Task
Specs, module ownership, Git history and completion ledger one auditable
coordination control plane.
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

import jsonschema
import yaml

CANONICAL_PLAN = "specs/coordination/program-plan.yaml"
CANONICAL_ACTIVE_WORK = "specs/coordination/active-work.yaml"
CANONICAL_MODULE_OWNERSHIP = "specs/designs/module-ownership.yaml"
CANONICAL_COMPLETIONS = "specs/coordination/task-completions.yaml"
CANONICAL_COMPLETION_SCHEMA = "specs/coordination/task-completions.schema.yaml"
CANONICAL_AUTHORITY = {
    "requirements": "specs/requirements/product-requirements.md",
    "requirementIndex": "specs/requirements/requirements-index.yaml",
    "moduleOwnership": "specs/designs/module-ownership.yaml",
    "collaborationProtocol": "docs/25-multi-agent-collaboration-protocol.md",
}
EXECUTION_STATUSES = {"reserved", "in_progress", "review", "integration", "completed"}
ACTIVE_LEASE_STATUSES = {"reserved", "in_progress", "review", "integration", "blocked"}
GLOB_CHARS = "*?["
PR_REF_RE = re.compile(r"^PR-([0-9]+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program Plan execution integrity")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan", default=CANONICAL_PLAN)
    parser.add_argument("--active-work", default=CANONICAL_ACTIVE_WORK)
    parser.add_argument("--modules", default=CANONICAL_MODULE_OWNERSHIP)
    parser.add_argument("--completions", default=CANONICAL_COMPLETIONS)
    parser.add_argument("--completion-schema", default=CANONICAL_COMPLETION_SCHEMA)
    return parser.parse_args()


def emit(status: str, message: str, details: Any | None = None) -> None:
    payload: dict[str, Any] = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def load_yaml(root: str, relative: str) -> Any:
    path = os.path.join(root, relative)
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_front_matter(path: str) -> dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def find_task_spec(root: str, task_id: str) -> str | None:
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


def normalize_path(pattern: str) -> str:
    value = str(pattern or "").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return re.sub(r"/+", "/", value).rstrip("/")


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


def git(root: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
    )


def commit_identity_errors(
    root: str,
    sha: str,
    task_id: str,
    completion_ref: str,
    label: str,
) -> list[str]:
    errors: list[str] = []
    if not re.fullmatch(r"[0-9a-f]{40}", str(sha or "")):
        return [f"{label} has invalid commit SHA: {sha!r}"]
    exists = git(root, "cat-file", "-e", f"{sha}^{{commit}}")
    if exists.returncode != 0:
        return [f"{label} commit {sha} does not exist in the repository"]
    reachable = git(root, "merge-base", "--is-ancestor", sha, "HEAD")
    if reachable.returncode != 0:
        errors.append(f"{label} commit {sha} is not reachable from HEAD")
    message_result = git(root, "show", "-s", "--format=%B", sha)
    if message_result.returncode != 0:
        errors.append(f"{label} commit {sha} message could not be read")
        return errors
    message = message_result.stdout
    if task_id not in message:
        errors.append(f"{label} commit {sha} message does not identify {task_id}")
    match = PR_REF_RE.fullmatch(str(completion_ref or ""))
    if not match:
        errors.append(f"{label} completionRef must use PR-<number>: {completion_ref!r}")
    elif f"#{match.group(1)}" not in message:
        errors.append(
            f"{label} commit {sha} message does not identify {completion_ref}"
        )
    return errors


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def validate_completion_ledger(
    root: str,
    plan_tasks: dict[str, dict[str, Any]],
    ledger: dict[str, Any],
    errors: list[str],
) -> None:
    records = ledger.get("records") or []
    by_task: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = record.get("taskId")
        if task_id in by_task:
            errors.append(f"Completion ledger has duplicate record for {task_id}")
        by_task[task_id] = record

    for task_id, task in plan_tasks.items():
        if task.get("status") != "completed":
            if task_id in by_task:
                errors.append(
                    f"Completion ledger records {task_id}, but Program Plan status is {task.get('status')}"
                )
            continue
        record = by_task.get(task_id)
        if not record:
            errors.append(f"Completed Program task {task_id} has no completion ledger record")
            continue

        task_spec = str(record.get("taskSpec") or "")
        evidence_path = str(record.get("evidencePath") or "")
        handoff_path = str(record.get("handoffPath") or "")
        spec_path = os.path.join(root, task_spec)
        evidence_full = os.path.join(root, evidence_path)
        handoff_full = os.path.join(root, handoff_path)
        if not os.path.isfile(spec_path):
            errors.append(f"Completed Program task {task_id} Task Spec does not exist: {task_spec}")
        else:
            front = parse_front_matter(spec_path)
            if front.get("id") != task_id:
                errors.append(f"Completed Program task {task_id} Task Spec id does not match")
            if front.get("status") not in {"completed", "approved"}:
                errors.append(f"Completed Program task {task_id} Task Spec is not completed")
        if not os.path.isdir(evidence_full):
            errors.append(f"Completed Program task {task_id} Evidence path does not exist: {evidence_path}")
        if not handoff_path.startswith(evidence_path.rstrip("/") + "/"):
            errors.append(f"Completed Program task {task_id} handoff is outside Evidence path")
        if not os.path.isfile(handoff_full):
            errors.append(f"Completed Program task {task_id} handoff does not exist: {handoff_path}")

        reservation_sha = str(record.get("reservationCommit") or "")
        merge_sha = str(record.get("mergeCommit") or "")
        errors.extend(
            commit_identity_errors(
                root,
                reservation_sha,
                task_id,
                str(record.get("reservationRef") or ""),
                f"Completion record {task_id} reservation",
            )
        )
        errors.extend(
            commit_identity_errors(
                root,
                merge_sha,
                task_id,
                str(record.get("completionRef") or ""),
                f"Completion record {task_id} merge",
            )
        )
        if (
            re.fullmatch(r"[0-9a-f]{40}", reservation_sha)
            and re.fullmatch(r"[0-9a-f]{40}", merge_sha)
            and not is_ancestor(root, reservation_sha, merge_sha)
        ):
            errors.append(
                f"Completion record {task_id} reservationCommit is not an ancestor of mergeCommit"
            )

    unknown = sorted(set(by_task) - set(plan_tasks))
    if unknown:
        errors.append("Completion ledger references unknown Program tasks: " + ", ".join(unknown))


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    try:
        plan = load_yaml(root, args.plan)
        active_work = load_yaml(root, args.active_work)
        ownership = load_yaml(root, args.modules)
        completions = load_yaml(root, args.completions)
        completion_schema = load_yaml(root, args.completion_schema)
        jsonschema.Draft202012Validator.check_schema(completion_schema)
        jsonschema.Draft202012Validator(completion_schema).validate(completions)
    except Exception as exc:
        emit("FAIL", f"Cannot load or validate Program Plan integrity inputs: {exc}")
        return 1

    if plan.get("sourceOfTruth") != CANONICAL_PLAN:
        errors.append(f"Program Plan sourceOfTruth must be {CANONICAL_PLAN}")
    authority = plan.get("authority") or {}
    for key, canonical in CANONICAL_AUTHORITY.items():
        if authority.get(key) != canonical:
            errors.append(
                f"Program Plan authority.{key} must be {canonical}, got {authority.get(key)!r}"
            )

    foundation_tasks = {
        item.get("taskId"): item for item in (plan.get("foundationTasks") or [])
    }
    plan_tasks = {item.get("taskId"): item for item in (plan.get("tasks") or [])}
    active_tasks = {
        item.get("taskId"): item for item in (active_work.get("tasks") or [])
    }
    all_tasks = {**foundation_tasks, **plan_tasks}

    for task_id, foundation in foundation_tasks.items():
        if foundation.get("status") != "completed":
            continue
        errors.extend(
            commit_identity_errors(
                root,
                str(foundation.get("mergeCommit") or ""),
                task_id,
                str(foundation.get("completionRef") or ""),
                f"Foundation task {task_id}",
            )
        )

    for task_id, task in plan_tasks.items():
        if task.get("status") not in EXECUTION_STATUSES:
            continue
        for dependency in task.get("dependsOn") or []:
            dependency_task = all_tasks.get(dependency)
            if not dependency_task:
                errors.append(f"Program task {task_id} depends on unknown task {dependency}")
            elif dependency_task.get("status") != "completed":
                errors.append(
                    f"Program task {task_id} cannot be {task.get('status')} while dependency "
                    f"{dependency} is {dependency_task.get('status')}"
                )

    for task_id, registry in active_tasks.items():
        for dependency in registry.get("dependsOn") or []:
            dependency_task = all_tasks.get(dependency)
            if not dependency_task or dependency_task.get("status") != "completed":
                errors.append(
                    f"Active task {task_id} has incomplete dependency {dependency}"
                )
        if task_id in plan_tasks:
            planned = plan_tasks[task_id]
            spec_path = find_task_spec(root, task_id)
            if not spec_path:
                errors.append(f"Active Program task {task_id} has no unique Task Spec")
            else:
                front = parse_front_matter(spec_path)
                exit_gate = front.get("exitGate")
                if not exit_gate:
                    errors.append(f"Active Program task {task_id} Task Spec has no exitGate")
                elif exit_gate != str(planned.get("exitGate") or ""):
                    errors.append(
                        f"Active Program task {task_id} Task Spec exitGate does not match Program Plan"
                    )

    blockers = plan.get("externalBlockers") or []
    for blocker in blockers:
        if blocker.get("status") == "resolved":
            continue
        blocker_id = blocker.get("id")
        for task_id in blocker.get("requiredFor") or []:
            task = plan_tasks.get(task_id)
            if task and task.get("status") in EXECUTION_STATUSES:
                errors.append(
                    f"Program task {task_id} cannot be {task.get('status')} while external "
                    f"blocker {blocker_id} is {blocker.get('status')}"
                )

    module_paths: list[tuple[str, str]] = []
    for module in ownership.get("modules") or []:
        module_id = module.get("id")
        for path in module.get("ownedPaths") or []:
            module_paths.append((module_id, path))
    namespaces = ownership.get("contractNamespaces") or []

    for task_id, task in plan_tasks.items():
        task_modules = set(task.get("moduleIds") or [])
        for claim_kind in ("outputPaths", "sharedPaths"):
            for claimed_path in task.get(claim_kind) or []:
                for owner_module, owned_path in module_paths:
                    if paths_overlap(claimed_path, owned_path) and owner_module not in task_modules:
                        errors.append(
                            f"Program task {task_id} {claim_kind} claim {claimed_path} overlaps "
                            f"{owner_module}:{owned_path} without declaring {owner_module}"
                        )
                for namespace in namespaces:
                    namespace_pattern = namespace.get("pattern") or ""
                    if not paths_overlap(claimed_path, namespace_pattern):
                        continue
                    writers = {namespace.get("ownerModule")} | set(
                        namespace.get("sharedWriterModules") or []
                    )
                    if not task_modules.intersection(writers):
                        errors.append(
                            f"Program task {task_id} {claim_kind} claim {claimed_path} overlaps "
                            f"contract namespace {namespace.get('id')} without an owner/shared-writer module"
                        )

    final_task_id = plan.get("releasePolicy", {}).get("requiredFinalTask")
    final_task = plan_tasks.get(final_task_id)
    wave_order = {
        item.get("id"): item.get("order") for item in (plan.get("waves") or [])
    }
    maximum_wave = max(wave_order.values(), default=0)
    if final_task_id != "GZ-020":
        errors.append("releasePolicy.requiredFinalTask must be canonical task GZ-020")
    if not final_task:
        errors.append("Canonical final task GZ-020 does not exist")
    else:
        if final_task.get("kind") != "release":
            errors.append("Canonical final task GZ-020 must have kind=release")
        if final_task.get("riskLevel") != "critical":
            errors.append("Canonical final task GZ-020 must have riskLevel=critical")
        if wave_order.get(final_task.get("wave")) != maximum_wave:
            errors.append("Canonical final task GZ-020 must be in the last Program wave")
        dependents = [
            task_id
            for task_id, task in plan_tasks.items()
            if final_task_id in (task.get("dependsOn") or [])
        ]
        if dependents:
            errors.append(
                "No Program task may depend on final release task GZ-020: "
                + ", ".join(sorted(dependents))
            )

    validate_completion_ledger(root, plan_tasks, completions, errors)

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program Plan execution and completion integrity passed",
        {
            "foundationTasks": len(foundation_tasks),
            "programTasks": len(plan_tasks),
            "activeTasks": len(active_tasks),
            "completionRecords": len(completions.get("records") or []),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

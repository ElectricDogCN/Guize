#!/usr/bin/env python3
"""Validate workflow YAML, schemas, instances, Task Specs, and Program Plan activation semantics."""

from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import sys
from typing import Any

import jsonschema
import yaml

CANONICAL_PROGRAM_PLAN = "specs/coordination/program-plan.yaml"
ACTIVE_PROGRAM_STATUSES = {"reserved", "in_progress", "review", "integration", "blocked"}
NONE_VALUES = {"", "none", "n/a", "na", "unknown", "tbd", "pending"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Guize YAML/JSON schemas and contract documents")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    return parser.parse_args()


def load_document(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        if path.endswith(".json"):
            return json.load(handle)
        return yaml.safe_load(handle)


def parse_front_matter(path: str) -> dict[str, str]:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict[str, str] = {}
    for line in parts[1].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def parse_front_list(value: Any) -> list[str]:
    text = str(value or "").strip().strip("[]")
    if text.lower() in NONE_VALUES:
        return []
    return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]


def find_task_spec(root: str, task_id: str) -> str | None:
    base = os.path.join(root, "specs", "tasks")
    exact = os.path.join(base, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    candidates = sorted(
        path
        for path in glob.glob(os.path.join(base, f"{task_id}-*.md"))
        if os.path.isfile(path)
    )
    return candidates[0] if len(candidates) == 1 else None


def validate_schema_document(path: str, root: str, errors: list[str]) -> None:
    relpath = os.path.relpath(path, root)
    try:
        document = load_document(path)
        if not isinstance(document, dict):
            raise ValueError("schema root must be a mapping")
        validator_cls = jsonschema.validators.validator_for(document)
        validator_cls.check_schema(document)
        print(f"OK JSON-SCHEMA: {relpath}")
    except Exception as exc:
        errors.append(f"{relpath}: {exc}")


def validate_instance(instance_path: str, schema_path: str, root: str, errors: list[str]) -> None:
    rel_instance = os.path.relpath(instance_path, root)
    rel_schema = os.path.relpath(schema_path, root)
    try:
        instance = load_document(instance_path)
        schema = load_document(schema_path)
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema, format_checker=jsonschema.FormatChecker())
        failures = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
        if failures:
            for failure in failures:
                location = "/".join(str(part) for part in failure.absolute_path) or "<root>"
                errors.append(f"{rel_instance} violates {rel_schema} at {location}: {failure.message}")
        else:
            print(f"OK SCHEMA INSTANCE: {rel_instance} <- {rel_schema}")
    except Exception as exc:
        errors.append(f"{rel_instance} / {rel_schema}: {exc}")


def compare_scalar(
    task_id: str,
    registry: dict[str, Any],
    planned: dict[str, Any],
    registry_key: str,
    plan_key: str,
    errors: list[str],
) -> None:
    if registry.get(registry_key) != planned.get(plan_key):
        errors.append(
            f"Active task {task_id} {registry_key}={registry.get(registry_key)!r} "
            f"does not match Program Plan {plan_key}={planned.get(plan_key)!r}"
        )


def compare_set(
    task_id: str,
    registry: dict[str, Any],
    planned: dict[str, Any],
    registry_key: str,
    plan_key: str,
    errors: list[str],
) -> None:
    registry_values = set(registry.get(registry_key) or [])
    plan_values = set(planned.get(plan_key) or [])
    if registry_values != plan_values:
        errors.append(
            f"Active task {task_id} {registry_key}={sorted(registry_values)} "
            f"does not match Program Plan {plan_key}={sorted(plan_values)}"
        )


def validate_task_registry(root: str, task_id: str, registry: dict[str, Any], errors: list[str]) -> None:
    """Cross-check Task Spec front matter against the active registry lease."""
    path = find_task_spec(root, task_id)
    if not path:
        errors.append(f"Active task {task_id} has no unique Task Spec")
        return
    try:
        front = parse_front_matter(path)
    except OSError as exc:
        errors.append(f"Cannot read Task Spec for active task {task_id}: {exc}")
        return

    scalar_pairs = [
        ("id", "taskId"),
        ("titleZh", "title"),
        ("status", "status"),
        ("baseBranch", "baseBranch"),
        ("baseSha", "baseSha"),
        ("workBranch", "branch"),
        ("issue", "issue"),
        ("workPackage", "workPackage"),
        ("programPlan", "programPlan"),
        ("programTaskId", "programTaskId"),
        ("wave", "programWave"),
        ("taskOwner", "owner"),
        ("coordinator", "coordinator"),
        ("implementer", "implementer"),
        ("reviewer", "reviewer"),
        ("integrator", "integrator"),
        ("agentRole", "agentRole"),
        ("riskLevel", "riskLevel"),
        ("coordinationGroup", "coordinationGroup"),
        ("handoffPath", "handoffPath"),
        ("integrationStrategy", "integrationStrategy"),
        ("integrationOrder", "integrationOrder"),
    ]
    for task_key, registry_key in scalar_pairs:
        task_value = str(front.get(task_key, ""))
        registry_value = str(registry.get(registry_key, ""))
        if task_value != registry_value:
            errors.append(
                f"Task Spec {task_id} {task_key}={task_value!r} does not match "
                f"Active Work {registry_key}={registry_value!r}"
            )

    lease_expires = str((registry.get("lease") or {}).get("expiresAt", ""))
    if front.get("leaseExpiresAt", "") != lease_expires:
        errors.append(
            f"Task Spec {task_id} leaseExpiresAt={front.get('leaseExpiresAt')!r} "
            f"does not match Active Work lease.expiresAt={lease_expires!r}"
        )

    list_pairs = [
        ("dependsOn", "dependsOn"),
        ("requirementIds", "requirementIds"),
        ("moduleIds", "moduleIds"),
        ("producesContracts", "producesContracts"),
        ("consumesContracts", "consumesContracts"),
    ]
    for task_key, registry_key in list_pairs:
        task_values = set(parse_front_list(front.get(task_key)))
        registry_values = set(registry.get(registry_key) or [])
        if task_values != registry_values:
            errors.append(
                f"Task Spec {task_id} {task_key}={sorted(task_values)} does not match "
                f"Active Work {registry_key}={sorted(registry_values)}"
            )
    print(f"OK TASK REGISTRY LINK: {task_id}")


def validate_program_activation(root: str, active_work: dict[str, Any], program_plan: dict[str, Any], errors: list[str]) -> None:
    """Ensure every active lease is the exact activation of one canonical planned task."""
    planned_tasks = {item.get("taskId"): item for item in program_plan.get("tasks", [])}
    foundation_tasks = {item.get("taskId"): item for item in program_plan.get("foundationTasks", [])}
    active_tasks = {item.get("taskId"): item for item in active_work.get("tasks", [])}

    active_policy = active_work.get("policy", {})
    plan_policy = program_plan.get("parallelPolicy", {})
    for key in ("maxActiveTasks", "maxHighRiskTasks"):
        if active_policy.get(key) != plan_policy.get(key):
            errors.append(
                f"Active Work policy {key}={active_policy.get(key)!r} does not match "
                f"Program Plan parallelPolicy {key}={plan_policy.get(key)!r}"
            )

    for task_id, registry in active_tasks.items():
        validate_task_registry(root, task_id, registry, errors)
        if registry.get("programPlan") != CANONICAL_PROGRAM_PLAN:
            errors.append(
                f"Active task {task_id} programPlan must be {CANONICAL_PROGRAM_PLAN}, "
                f"got {registry.get('programPlan')!r}"
            )
        if registry.get("programTaskId") != task_id:
            errors.append(
                f"Active task {task_id} programTaskId must equal taskId, "
                f"got {registry.get('programTaskId')!r}"
            )

        if task_id in planned_tasks:
            planned = planned_tasks[task_id]
            compare_scalar(task_id, registry, planned, "title", "title", errors)
            compare_scalar(task_id, registry, planned, "status", "status", errors)
            compare_scalar(task_id, registry, planned, "riskLevel", "riskLevel", errors)
            compare_scalar(task_id, registry, planned, "workPackage", "workPackage", errors)
            compare_scalar(task_id, registry, planned, "programWave", "wave", errors)
            compare_scalar(task_id, registry, planned, "coordinationGroup", "coordinationGroup", errors)
            compare_scalar(task_id, registry, planned, "integrationOrder", "integrationOrder", errors)
            compare_set(task_id, registry, planned, "dependsOn", "dependsOn", errors)
            compare_set(task_id, registry, planned, "requirementIds", "requirementIds", errors)
            compare_set(task_id, registry, planned, "moduleIds", "moduleIds", errors)
            compare_set(task_id, registry, planned, "producesContracts", "producesContracts", errors)
            compare_set(task_id, registry, planned, "consumesContracts", "consumesContracts", errors)
            compare_set(task_id, registry, planned, "sharedPaths", "sharedPaths", errors)

            planned_issue = planned.get("issue")
            if planned_issue is not None and registry.get("issue") != planned_issue:
                errors.append(
                    f"Active task {task_id} issue={registry.get('issue')!r} "
                    f"does not match Program Plan issue={planned_issue!r}"
                )

            pattern = planned.get("branchPattern", "")
            branch = registry.get("branch", "")
            if not pattern or not fnmatch.fnmatchcase(branch, pattern):
                errors.append(
                    f"Active task {task_id} branch {branch!r} does not match Program Plan "
                    f"branchPattern {pattern!r}"
                )

            claims = set(registry.get("exclusivePaths") or []) | set(registry.get("sharedPaths") or [])
            for output_path in planned.get("outputPaths", []):
                if output_path not in claims:
                    errors.append(
                        f"Active task {task_id} does not reserve Program Plan output path: {output_path}"
                    )
            print(f"OK PROGRAM ACTIVATION: {task_id} <- {planned.get('wave')}")
        elif task_id in foundation_tasks:
            foundation = foundation_tasks[task_id]
            if registry.get("programWave") != "FOUNDATION":
                errors.append(
                    f"Foundation active task {task_id} programWave must be FOUNDATION, "
                    f"got {registry.get('programWave')!r}"
                )
            if registry.get("status") != foundation.get("status"):
                errors.append(
                    f"Foundation active task {task_id} status={registry.get('status')!r} "
                    f"does not match Program Plan status={foundation.get('status')!r}"
                )
            print(f"OK FOUNDATION ACTIVATION: {task_id}")
        else:
            errors.append(f"Active task {task_id} does not exist in canonical Program Plan")

    expected_active = {
        task_id
        for task_id, task in planned_tasks.items()
        if task.get("status") in ACTIVE_PROGRAM_STATUSES
    }
    expected_active |= {
        task_id
        for task_id, task in foundation_tasks.items()
        if task.get("status") in ACTIVE_PROGRAM_STATUSES
    }
    missing = sorted(expected_active - set(active_tasks))
    if missing:
        errors.append(
            "Program Plan marks tasks active but Active Work Registry has no lease: "
            + ", ".join(missing)
        )


def main() -> None:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []

    workflow_files = glob.glob(os.path.join(root, ".github", "workflows", "*.yml"))
    workflow_files += glob.glob(os.path.join(root, ".github", "workflows", "*.yaml"))
    for path in sorted(workflow_files):
        try:
            load_document(path)
            print(f"OK YAML: {os.path.relpath(path, root)}")
        except Exception as exc:
            errors.append(f"{os.path.relpath(path, root)}: {exc}")

    contract_files = glob.glob(os.path.join(root, "contracts", "**", "*.json"), recursive=True)
    contract_files += glob.glob(os.path.join(root, "contracts", "**", "*.yaml"), recursive=True)
    contract_files += glob.glob(os.path.join(root, "contracts", "**", "*.yml"), recursive=True)
    for path in sorted(set(contract_files)):
        relpath = os.path.relpath(path, root)
        try:
            document = load_document(path)
            if isinstance(document, dict) and "$schema" in document:
                validator_cls = jsonschema.validators.validator_for(document)
                validator_cls.check_schema(document)
                print(f"OK JSON-SCHEMA: {relpath}")
            else:
                print(f"OK CONTRACT DOCUMENT: {relpath}")
        except Exception as exc:
            errors.append(f"{relpath}: {exc}")

    coordination_dir = os.path.join(root, "specs", "coordination")
    coordination_schemas = glob.glob(os.path.join(coordination_dir, "*.schema.yaml"))
    coordination_schemas += glob.glob(os.path.join(coordination_dir, "*.schema.yml"))
    coordination_schemas += glob.glob(os.path.join(coordination_dir, "*.schema.json"))
    for path in sorted(set(coordination_schemas)):
        validate_schema_document(path, root, errors)

    active_path = os.path.join(coordination_dir, "active-work.yaml")
    active_schema_path = os.path.join(coordination_dir, "active-work.schema.yaml")
    program_path = os.path.join(coordination_dir, "program-plan.yaml")
    program_schema_path = os.path.join(coordination_dir, "program-plan.schema.yaml")
    declared_instances = [
        (active_path, active_schema_path),
        (program_path, program_schema_path),
    ]
    for instance_path, schema_path in declared_instances:
        if not os.path.isfile(instance_path):
            errors.append(f"{os.path.relpath(instance_path, root)}: instance file is missing")
            continue
        if not os.path.isfile(schema_path):
            errors.append(f"{os.path.relpath(schema_path, root)}: schema file is missing")
            continue
        validate_instance(instance_path, schema_path, root, errors)

    if os.path.isfile(active_path) and os.path.isfile(program_path):
        try:
            validate_program_activation(
                root,
                load_document(active_path),
                load_document(program_path),
                errors,
            )
        except Exception as exc:
            errors.append(f"Program Plan / Active Work / Task Spec semantic validation failed: {exc}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        sys.exit(1)

    print("OK: Schema, Task Spec, Active Work and Program Plan validation completed")
    sys.exit(0)


if __name__ == "__main__":
    main()

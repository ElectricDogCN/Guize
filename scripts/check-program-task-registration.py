#!/usr/bin/env python3
"""Validate one metadata-only absent-to-planned Program Task Registration.

Registration is distinct from Reservation: it adds exactly one high-risk
ordinary Program task and a matching schemaVersion 2 Task Spec, keeps Active
Work and the Completion Ledger byte-identical, and grants no implementation
scope or Lease.
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
TASK_ID_RE = re.compile(r"^[A-Z]+-[0-9]{3}$")
PLACEHOLDERS = {"", "none", "n/a", "na", "unknown", "tbd", "pending", "self", "same-agent", "unassigned"}
TYPE_BY_KIND = {
    "requirements": {"docs", "chore"},
    "contract": {"chore", "docs"},
    "design-contract": {"docs", "chore"},
    "poc-coordination": {"chore"},
    "poc": {"chore"},
    "acceptance": {"chore", "docs"},
    "scaffold": {"chore", "feat"},
    "vertical-slice": {"feat"},
    "release": {"chore"},
    "governance": {"chore", "fix"},
}


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program Task Registration")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--task", default="")
    parser.add_argument("--branch-name", default="")
    parser.add_argument("--detect-only", action="store_true")
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


def resolve_ref(root: str, ref: str) -> str | None:
    result = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def read_ref(root: str, ref: str, path: str) -> str | None:
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def load_yaml_text(text: str | None) -> Any | None:
    if text is None:
        return None
    try:
        return yaml.load(text, Loader=UniqueKeyLoader)
    except yaml.YAMLError:
        return None


def load_ref(root: str, ref: str, path: str) -> Any | None:
    return load_yaml_text(read_ref(root, ref, path))


def task_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("taskId")): item
        for item in plan.get("tasks") or []
        if isinstance(item, dict) and item.get("taskId")
    }


def foundation_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("taskId")): item
        for item in plan.get("foundationTasks") or []
        if isinstance(item, dict) and item.get("taskId")
    }


def changed_paths(root: str, base_ref: str, head_ref: str) -> tuple[set[str] | None, list[tuple[str, str, str]]]:
    result = git(root, "diff", "--name-status", "-M", base_ref, head_ref)
    if result.returncode != 0:
        return None, []
    paths: set[str] = set()
    records: list[tuple[str, str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            source, destination = parts[1].strip(), parts[2].strip()
            paths.update({source, destination})
            records.append((status, source, destination))
        elif len(parts) >= 2:
            path = parts[-1].strip()
            paths.add(path)
            records.append((status, path, path))
    return paths, records


def is_registration_candidate(root: str, base_ref: str, head_ref: str) -> bool:
    if not resolve_ref(root, base_ref) or not resolve_ref(root, head_ref):
        return False
    before = load_ref(root, base_ref, PLAN)
    after = load_ref(root, head_ref, PLAN)
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    return bool(set(task_map(after)) - set(task_map(before)))


def normalize_path(value: Any) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return re.sub(r"/+", "/", path).rstrip("/")


def safe_repo_path(path: str) -> bool:
    path = normalize_path(path)
    return bool(path) and not path.startswith("/") and all(
        part not in {"", ".", ".."} for part in path.split("/")
    )


def ref_mode(root: str, ref: str, path: str) -> str | None:
    result = git(root, "ls-tree", ref, "--", path)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split(None, 1)[0]


def parse_front(text: str | None) -> tuple[dict[str, Any], str]:
    if not text or not text.startswith("---"):
        return {}, text or ""
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}, text
    try:
        document = yaml.load(parts[1], Loader=UniqueKeyLoader)
    except yaml.YAMLError:
        return {}, parts[2]
    return (document if isinstance(document, dict) else {}), parts[2]


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if not text or text.lower() in PLACEHOLDERS or text.upper() == "NONE":
        return []
    return [part.strip().strip("'\"") for part in text.strip("[]").split(",") if part.strip()]


def section_paths(body: str, titles: tuple[str, ...]) -> list[str] | None:
    lines = body.splitlines()
    wanted = tuple(title.lower() for title in titles)
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        title = re.sub(r"^##\s+", "", stripped).strip().lower()
        title = re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", title)
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
            paths.append(normalize_path(value))
    return paths


def wave_orders(plan: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {"FOUNDATION": 0}
    for wave in plan.get("waves") or []:
        if isinstance(wave, dict) and wave.get("id") is not None:
            try:
                result[str(wave["id"])] = int(wave["order"])
            except (KeyError, TypeError, ValueError):
                continue
    return result


def dependency_cycle(tasks: dict[str, dict[str, Any]]) -> bool:
    visiting: set[str] = set()
    complete: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return True
        if task_id in complete:
            return False
        visiting.add(task_id)
        for dependency in tasks.get(task_id, {}).get("dependsOn") or []:
            if dependency in tasks and visit(str(dependency)):
                return True
        visiting.remove(task_id)
        complete.add(task_id)
        return False

    return any(visit(task_id) for task_id in tasks)


def dependency_closure(task_id: str, tasks: dict[str, dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    stack = [str(item) for item in tasks.get(task_id, {}).get("dependsOn") or []]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(
            str(item) for item in tasks.get(current, {}).get("dependsOn") or []
        )
    return seen


def compare_scalar(front: dict[str, Any], task: dict[str, Any], front_key: str, task_key: str, errors: list[str]) -> None:
    if str(front.get(front_key, "")) != str(task.get(task_key, "")):
        errors.append(f"Task Spec {front_key} does not match Program task {task_key}")


def compare_list(front: dict[str, Any], task: dict[str, Any], key: str, errors: list[str]) -> None:
    if as_list(front.get(key)) != [str(item) for item in task.get(key) or []]:
        errors.append(f"Task Spec {key} does not match Program task {key}")


def validate_registration(
    root: str,
    base_ref: str,
    head_ref: str,
    task_hint: str = "",
    branch_name: str = "",
) -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    base_sha = resolve_ref(root, base_ref)
    head_sha = resolve_ref(root, head_ref)
    if not base_sha or not head_sha:
        return 1, {"errors": ["Registration refs are missing"]}

    base_plan = load_ref(root, base_ref, PLAN)
    current_plan = load_ref(root, head_ref, PLAN)
    if not isinstance(base_plan, dict) or not isinstance(current_plan, dict):
        return 1, {
            "errors": [
                "Registration Program Plan snapshots are missing, invalid, or contain duplicate keys"
            ]
        }

    base_tasks = task_map(base_plan)
    current_tasks = task_map(current_plan)
    added = sorted(set(current_tasks) - set(base_tasks))
    removed = sorted(set(base_tasks) - set(current_tasks))
    task_id = added[0] if added else task_hint
    if len(added) != 1:
        errors.append(f"Registration must add exactly one Program task; got {added}")
    if removed:
        errors.append(f"Registration must not remove Program tasks: {removed}")
    if task_hint and task_id and task_hint != task_id:
        errors.append(
            f"Registration task hint {task_hint} does not match new task {task_id}"
        )
    if task_id and not TASK_ID_RE.fullmatch(task_id):
        errors.append(f"Registration task ID is invalid: {task_id}")

    new_task = current_tasks.get(task_id, {})
    if new_task.get("status") != "planned":
        errors.append("Registration new Program task status must be planned")
    if new_task.get("riskLevel") not in {"high", "critical"}:
        errors.append("Registration Program Plan change must be high or critical risk")

    base_copy = copy.deepcopy(base_plan)
    current_copy = copy.deepcopy(current_plan)
    base_copy["tasks"] = []
    current_copy["tasks"] = []
    if base_copy != current_copy:
        errors.append("Registration must not modify non-task Program Plan sections")

    base_order = [
        str(item.get("taskId")) for item in base_plan.get("tasks") or []
    ]
    current_existing_order = [
        str(item.get("taskId"))
        for item in current_plan.get("tasks") or []
        if item.get("taskId") in base_tasks
    ]
    if base_order != current_existing_order:
        errors.append("Registration must preserve existing Program task order")

    changed_existing: list[str] = []
    orders = wave_orders(current_plan)
    new_wave_order = orders.get(str(new_task.get("wave") or ""))
    if new_wave_order is None:
        errors.append("Registration new task references an unknown Wave")

    for existing_id in base_order:
        before = base_tasks[existing_id]
        after = current_tasks.get(existing_id)
        if after == before:
            continue
        changed_existing.append(existing_id)
        if not isinstance(after, dict):
            errors.append(f"Registration changed task {existing_id} is missing")
            continue
        before_without = copy.deepcopy(before)
        after_without = copy.deepcopy(after)
        before_dependencies = [
            str(item) for item in before_without.pop("dependsOn", [])
        ]
        after_dependencies = [
            str(item) for item in after_without.pop("dependsOn", [])
        ]
        if before_without != after_without:
            errors.append(
                f"Registration may not mutate existing task {existing_id} fields"
            )
        if after.get("status") != "planned":
            errors.append(
                f"Registration dependency attachment target {existing_id} must remain planned"
            )
        if after_dependencies != before_dependencies + [task_id]:
            errors.append(
                f"Registration task {existing_id} dependency change must be one tail append of {task_id}"
            )
        target_order = orders.get(str(after.get("wave") or ""))
        if target_order is None or (
            new_wave_order is not None and target_order < new_wave_order
        ):
            errors.append(
                f"Registration dependency attachment target {existing_id} must be in the same or a later Wave"
            )

    base_active_text = read_ref(root, base_ref, ACTIVE)
    current_active_text = read_ref(root, head_ref, ACTIVE)
    if (
        base_active_text is None
        or current_active_text is None
        or base_active_text != current_active_text
    ):
        errors.append("Registration must leave Active Work byte-identical")

    base_ledger_text = read_ref(root, base_ref, LEDGER)
    current_ledger_text = read_ref(root, head_ref, LEDGER)
    if (
        base_ledger_text is None
        or current_ledger_text is None
        or base_ledger_text != current_ledger_text
    ):
        errors.append("Registration must leave Completion Ledger byte-identical")

    task_path = f"{TASK_DIR}/{task_id}.md" if task_id else ""
    task_text = read_ref(root, head_ref, task_path) if task_path else None
    if task_path and read_ref(root, base_ref, task_path) is not None:
        errors.append("Registration Task Spec must be absent from the target base")
    front, body = parse_front(task_text)
    if not front:
        errors.append(
            "Registration requires one readable schemaVersion 2 Task Spec with unique keys"
        )
    else:
        required_front = {
            "schemaVersion",
            "id",
            "title",
            "titleZh",
            "type",
            "status",
            "baseBranch",
            "baseSha",
            "workBranch",
            "branchPattern",
            "evidencePath",
            "issue",
            "workPackage",
            "programPlan",
            "programTaskId",
            "wave",
            "requirementIds",
            "moduleIds",
            "producesContracts",
            "consumesContracts",
            "acceptanceIds",
            "pocIds",
            "exitGate",
            "taskOwner",
            "coordinator",
            "implementer",
            "reviewer",
            "integrator",
            "agentRole",
            "riskLevel",
            "coordinationMode",
            "coordinationGroup",
            "dependsOn",
            "handoffPath",
            "integrationStrategy",
            "integrationOrder",
        }
        missing = sorted(
            key
            for key in required_front
            if key not in front or front.get(key) is None or front.get(key) == ""
        )
        if missing:
            errors.append(f"Registration Task Spec is missing fields: {missing}")
        if front.get("schemaVersion") != 2:
            errors.append("Registration Task Spec schemaVersion must be 2")
        if front.get("status") != "planned":
            errors.append("Registration Task Spec status must be planned")
        if front.get("coordinationMode") != "registration":
            errors.append(
                "Registration Task Spec coordinationMode must be registration"
            )
        if front.get("agentRole") != "coordinator":
            errors.append("Registration Task Spec agentRole must be coordinator")
        if "leaseExpiresAt" in front:
            errors.append("Registration Task Spec must not contain leaseExpiresAt")
        if front.get("riskLevel") not in {"high", "critical"}:
            errors.append(
                "Registration Task Spec riskLevel must be high or critical"
            )
        if (
            front.get("programPlan") != PLAN
            or front.get("programTaskId") != task_id
            or front.get("id") != task_id
        ):
            errors.append("Registration Task Spec Program identity is inconsistent")
        if front.get("baseBranch") != "main" or front.get("baseSha") != base_sha:
            errors.append(
                "Registration Task Spec base identity does not match target base"
            )
        if (
            front.get("evidencePath") != f"evidence/{task_id}"
            or front.get("handoffPath") != f"evidence/{task_id}/handoff.md"
        ):
            errors.append(
                "Registration Task Spec Evidence/Handoff identity is inconsistent"
            )
        if front.get("integrationStrategy") != "merge":
            errors.append("Registration integrationStrategy must be merge")

        work_branch = str(front.get("workBranch") or "")
        pattern = str(front.get("branchPattern") or "")
        if (
            pattern != str(new_task.get("branchPattern") or "")
            or not pattern
            or not fnmatch.fnmatchcase(work_branch, pattern)
        ):
            errors.append(
                "Registration Task Spec branchPattern/workBranch does not match Program task"
            )
        if branch_name and branch_name != work_branch:
            errors.append(
                "Registration actual branch does not match Task Spec workBranch"
            )

        compare_scalar(front, new_task, "titleZh", "title", errors)
        for key in (
            "workPackage",
            "riskLevel",
            "wave",
            "integrationOrder",
            "issue",
            "coordinationGroup",
            "exitGate",
        ):
            compare_scalar(front, new_task, key, key, errors)
        for key in (
            "dependsOn",
            "requirementIds",
            "moduleIds",
            "producesContracts",
            "consumesContracts",
            "acceptanceIds",
            "pocIds",
        ):
            compare_list(front, new_task, key, errors)

        if str(front.get("implementer") or "") != str(
            new_task.get("ownerRole") or ""
        ):
            errors.append(
                "Registration Task Spec implementer does not match Program ownerRole"
            )
        if str(front.get("reviewer") or "") != str(
            new_task.get("reviewerRole") or ""
        ):
            errors.append(
                "Registration Task Spec reviewer does not match Program reviewerRole"
            )
        allowed_types = TYPE_BY_KIND.get(str(new_task.get("kind") or ""), set())
        if front.get("type") not in allowed_types:
            errors.append(
                "Registration Task Spec type is incompatible with Program task kind"
            )
        for role in (
            "taskOwner",
            "coordinator",
            "implementer",
            "reviewer",
            "integrator",
        ):
            if str(front.get(role) or "").strip().lower() in PLACEHOLDERS:
                errors.append(
                    f"Registration Task Spec {role} must be a concrete identity"
                )
        if front.get("implementer") == front.get("reviewer"):
            errors.append(
                "Registration high-risk implementer and reviewer must be distinct"
            )

        exclusive = section_paths(
            body, ("独占写范围", "exclusive write scope")
        )
        shared = section_paths(
            body, ("共享修改范围", "shared modification scope")
        )
        if exclusive is None or exclusive != [
            normalize_path(item) for item in new_task.get("outputPaths") or []
        ]:
            errors.append(
                "Registration Task Spec exclusive paths do not match Program outputPaths in order"
            )
        if shared is None or shared != [
            normalize_path(item) for item in new_task.get("sharedPaths") or []
        ]:
            errors.append(
                "Registration Task Spec shared paths do not match Program sharedPaths in order"
            )

    paths, records = changed_paths(root, base_ref, head_ref)
    if paths is None:
        errors.append("Registration cannot determine exact changed paths")
        paths = set()
    allowed_exact = {PLAN, task_path}
    invalid_paths = sorted(
        path
        for path in paths
        if path not in allowed_exact
        and path != f"evidence/{task_id}"
        and not path.startswith(f"evidence/{task_id}/")
    )
    if invalid_paths:
        errors.append(
            f"Registration contains implementation or unrelated files: {invalid_paths}"
        )
    if not any(path.startswith(f"evidence/{task_id}/") for path in paths):
        errors.append("Registration must create task-bound Evidence")

    for path in sorted(paths):
        if not safe_repo_path(path):
            errors.append(f"Registration changed path is unsafe: {path}")
        if ref_mode(root, head_ref, path) == "120000":
            errors.append(
                f"Registration must not introduce or modify symlinks: {path}"
            )
    for status, source, destination in records:
        if status.startswith(("R", "C")):
            source_ok = source in allowed_exact or source.startswith(
                f"evidence/{task_id}/"
            )
            destination_ok = destination in allowed_exact or destination.startswith(
                f"evidence/{task_id}/"
            )
            if not source_ok or not destination_ok:
                errors.append(
                    f"Registration rename/copy escapes task metadata scope: {source} -> {destination}"
                )

    all_ids = set(current_tasks) | set(foundation_map(current_plan))
    for dependency in new_task.get("dependsOn") or []:
        if dependency not in all_ids:
            errors.append(f"Registration dependency does not exist: {dependency}")
        elif dependency in current_tasks and new_wave_order is not None:
            dependency_order = orders.get(
                str(current_tasks[dependency].get("wave") or "")
            )
            if dependency_order is None or dependency_order > new_wave_order:
                errors.append(
                    f"Registration dependency {dependency} is in a later Wave"
                )

    if dependency_cycle(current_tasks):
        errors.append("Registration introduces a Program task dependency cycle")

    final_task = str(
        (current_plan.get("releasePolicy") or {}).get("requiredFinalTask") or ""
    )
    if not final_task or final_task not in current_tasks:
        errors.append("Registration cannot resolve the required final Program task")
    elif final_task != task_id and task_id not in dependency_closure(
        final_task, current_tasks
    ):
        errors.append(
            f"Registration task {task_id} is missing from required final-task closure"
        )

    active_document = load_yaml_text(current_active_text)
    if isinstance(active_document, dict) and any(
        item.get("taskId") == task_id
        for item in active_document.get("tasks") or []
        if isinstance(item, dict)
    ):
        errors.append(
            "Registration planned task must not have an Active Work entry"
        )

    details = {
        "taskId": task_id or None,
        "baseSha": base_sha,
        "headSha": head_sha,
        "changedPathCount": len(paths),
        "downstreamAttachments": changed_existing,
        "errors": errors,
    }
    return (1 if errors else 0), details


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    candidate = is_registration_candidate(root, args.base_ref, args.head_ref)
    if args.detect_only:
        emit(
            "PASS",
            "Registration candidate detection completed",
            {"candidate": candidate},
        )
        return 0
    if not candidate:
        emit(
            "FAIL",
            "Exact diff is not an absent-to-planned Program Task Registration",
        )
        return 1

    code, details = validate_registration(
        root,
        args.base_ref,
        args.head_ref,
        task_hint=args.task,
        branch_name=args.branch_name,
    )
    if code:
        for error in details.get("errors") or []:
            emit("FAIL", error)
        return code
    emit(
        "PASS",
        "Program Task Registration is metadata-only, history-aware, and fail-closed",
        details,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Dispatch Program lifecycle validation to Registration, audited completed-
Foundation maintenance, or the byte-identical preserved lifecycle core.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import os
import re
import sys
from typing import Any

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(SCRIPT_DIR, "check-program-lifecycle-guards-core.py")
REGISTRATION_PATH = os.path.join(SCRIPT_DIR, "check-program-task-registration.py")
MAINTENANCE_MODE = "completed-foundation-maintenance"


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


CORE = _load(CORE_PATH, "guize_program_lifecycle_guards_core")
REGISTRATION = _load(
    REGISTRATION_PATH, "guize_program_task_registration_for_lifecycle"
)
for _name, _value in vars(CORE).items():
    if not _name.startswith("__"):
        globals().setdefault(_name, _value)


def _maintenance_path(task_id: str) -> str:
    return f"evidence/{task_id}/foundation-maintenance.yaml"


def _load_yaml_ref(root: str, ref: str, path: str) -> Any | None:
    return REGISTRATION.load_yaml_text(REGISTRATION.read_ref(root, ref, path))


def _task_path(root: str, ref: str, task_id: str) -> str | None:
    exact = f"specs/tasks/{task_id}.md"
    paths = REGISTRATION.ref_paths(root, ref, "specs/tasks")
    matches = [
        path
        for path in paths
        if path == exact
        or (path.startswith(f"specs/tasks/{task_id}-") and path.endswith(".md"))
    ]
    return matches[0] if len(matches) == 1 else None


def _front_and_body(
    root: str, ref: str, task_id: str
) -> tuple[dict[str, Any], str, str | None]:
    path = _task_path(root, ref, task_id)
    if not path:
        return {}, "", None
    front, body = REGISTRATION.parse_front(REGISTRATION.read_ref(root, ref, path))
    return front, body, path


def _normalize(value: Any) -> str:
    return REGISTRATION.normalize_path(value)


def _glob_regex(pattern: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                output.append(".*")
                index += 2
                continue
            output.append("[^/]*")
        elif char == "?":
            output.append("[^/]")
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end == -1:
                output.append(r"\[")
            else:
                value = pattern[index + 1 : end]
                if value.startswith("!"):
                    value = "^" + value[1:]
                output.append("[" + value + "]")
                index = end
        else:
            output.append(re.escape(char))
        index += 1
    return "".join(output)


def _matches(path: str, pattern: str) -> bool:
    path = _normalize(path)
    pattern = _normalize(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if any(token in pattern for token in ("*", "?", "[")):
        return re.fullmatch(_glob_regex(pattern), path) is not None
    return path == pattern


def _module_patterns(ownership: dict[str, Any], module_ids: set[str]) -> list[str]:
    patterns: list[str] = []
    for module in ownership.get("modules") or []:
        if isinstance(module, dict) and str(module.get("id") or "") in module_ids:
            patterns.extend(str(value) for value in module.get("ownedPaths") or [])
    return patterns


def _maintenance_task_from_diff(
    root: str, base_ref: str, head_ref: str, task_hint: str
) -> str:
    if task_hint and REGISTRATION.read_ref(
        root, head_ref, _maintenance_path(task_hint)
    ):
        return task_hint
    paths, _ = REGISTRATION.changed_paths(root, base_ref, head_ref)
    if paths is None:
        return ""
    candidates = sorted(
        match.group(1)
        for path in paths
        for match in [
            re.fullmatch(
                r"evidence/([A-Z]+-[0-9]+)/foundation-maintenance\.yaml", path
            )
        ]
        if match
    )
    return candidates[0] if len(candidates) == 1 else ""


def _validate_completed_foundation_maintenance(
    root: str,
    base_ref: str,
    head_ref: str,
    task_id: str,
    branch_name: str,
) -> tuple[int, dict[str, Any]]:
    errors: list[str] = []
    base_sha = REGISTRATION.resolve_ref(root, base_ref)
    head_sha = REGISTRATION.resolve_ref(root, head_ref)
    if not base_sha or not head_sha:
        return 1, {"errors": ["Completed-Foundation maintenance refs are missing"]}

    base_plan = _load_yaml_ref(root, base_ref, REGISTRATION.PLAN)
    head_plan = _load_yaml_ref(root, head_ref, REGISTRATION.PLAN)
    base_active = REGISTRATION.read_ref(root, base_ref, REGISTRATION.ACTIVE)
    head_active = REGISTRATION.read_ref(root, head_ref, REGISTRATION.ACTIVE)
    base_ledger = REGISTRATION.read_ref(root, base_ref, REGISTRATION.LEDGER)
    head_ledger = REGISTRATION.read_ref(root, head_ref, REGISTRATION.LEDGER)
    ownership = _load_yaml_ref(root, head_ref, "specs/designs/module-ownership.yaml")
    manifest = _load_yaml_ref(root, head_ref, _maintenance_path(task_id))
    if not isinstance(base_plan, dict) or not isinstance(head_plan, dict):
        errors.append(
            "Completed-Foundation maintenance Program Plan snapshots are invalid"
        )
        base_plan = {}
        head_plan = {}
    if not isinstance(ownership, dict):
        errors.append("Completed-Foundation maintenance module ownership is invalid")
        ownership = {}
    if not isinstance(manifest, dict):
        errors.append("Completed-Foundation maintenance manifest is missing or invalid")
        manifest = {}

    base_foundations = REGISTRATION.foundation_map(base_plan)
    head_foundations = REGISTRATION.foundation_map(head_plan)
    before = base_foundations.get(task_id)
    after = head_foundations.get(task_id)
    if (
        not before
        or not after
        or before != after
        or after.get("status") != "completed"
    ):
        errors.append(
            "Completed-Foundation maintenance must preserve one identical completed Foundation row"
        )
    if REGISTRATION.read_ref(
        root, base_ref, REGISTRATION.PLAN
    ) != REGISTRATION.read_ref(root, head_ref, REGISTRATION.PLAN):
        errors.append(
            "Completed-Foundation maintenance must leave Program Plan byte-identical"
        )
    if base_active is None or base_active != head_active:
        errors.append(
            "Completed-Foundation maintenance must leave Active Work byte-identical"
        )
    if base_ledger is None or base_ledger != head_ledger:
        errors.append(
            "Completed-Foundation maintenance must leave Completion Ledger byte-identical"
        )

    front, _, task_path = _front_and_body(root, head_ref, task_id)
    if not task_path:
        errors.append("Completed-Foundation maintenance has no unique Task Spec")
    elif REGISTRATION.read_ref(
        root, base_ref, task_path
    ) != REGISTRATION.read_ref(root, head_ref, task_path):
        errors.append(
            "Completed-Foundation maintenance must not rewrite the completed Task Spec"
        )
    if front.get("schemaVersion") != 2 or front.get("id") != task_id:
        errors.append("Completed-Foundation maintenance Task Spec identity is invalid")
    if front.get("status") != "completed":
        errors.append("Completed-Foundation maintenance Task Spec must remain completed")
    if front.get("riskLevel") not in {"high", "critical"}:
        errors.append(
            "Completed-Foundation maintenance must remain high or critical risk"
        )
    if not REGISTRATION.as_list(front.get("moduleIds")):
        errors.append(
            "Completed-Foundation maintenance Task Spec has no owning module"
        )
    if front.get("implementer") == front.get("reviewer"):
        errors.append("Completed-Foundation maintenance requires independent review")

    required_manifest = {
        "schemaVersion": 1,
        "mode": MAINTENANCE_MODE,
        "taskId": task_id,
        "baseSha": base_sha,
        "riskLevel": front.get("riskLevel"),
        "independentReviewRequired": True,
        "postMergeGateRequired": True,
    }
    for key, expected in required_manifest.items():
        if manifest.get(key) != expected:
            errors.append(
                f"Completed-Foundation maintenance manifest {key} must equal {expected!r}"
            )
    if not isinstance(manifest.get("issue"), int) or int(
        manifest.get("issue", 0)
    ) < 1:
        errors.append(
            "Completed-Foundation maintenance manifest requires a tracking issue"
        )
    if not str(manifest.get("purpose") or "").strip():
        errors.append("Completed-Foundation maintenance manifest requires a purpose")

    manifest_branch = str(manifest.get("workBranch") or "")
    if not manifest_branch or not fnmatch.fnmatchcase(
        manifest_branch, f"fix/{task_id}-*"
    ):
        errors.append(
            f"Completed-Foundation maintenance branch must match fix/{task_id}-*"
        )
    refs = REGISTRATION.branch_refs(root, manifest_branch)
    parents = REGISTRATION.commit_parents(root, head_sha)
    if branch_name:
        if branch_name != manifest_branch:
            errors.append(
                "Completed-Foundation maintenance actual branch does not match manifest workBranch"
            )
        if not any(sha == head_sha for _, sha in refs):
            if (
                len(parents) != 2
                or parents[0] != base_sha
                or not any(sha == parents[1] for _, sha in refs)
            ):
                errors.append(
                    "Completed-Foundation maintenance cannot prove PR source branch provenance"
                )
    else:
        if len(parents) != 2 or parents[0] != base_sha:
            errors.append(
                "Completed-Foundation maintenance push must be a two-parent merge with the exact base first"
            )
        elif not any(sha == parents[1] for _, sha in refs):
            errors.append(
                "Completed-Foundation maintenance push cannot prove the manifest source branch"
            )

    authorized = manifest.get("authorizedPaths") or []
    if not isinstance(authorized, list) or not authorized:
        errors.append(
            "Completed-Foundation maintenance manifest authorizedPaths is empty"
        )
        authorized = []
    normalized_authorized: list[str] = []
    for claim in authorized:
        normalized = _normalize(claim)
        if not REGISTRATION.safe_scope_claim(normalized):
            errors.append(
                f"Completed-Foundation maintenance has unsafe authorized path: {claim}"
            )
        normalized_authorized.append(normalized)

    module_patterns = _module_patterns(
        ownership, set(REGISTRATION.as_list(front.get("moduleIds")))
    )
    for claim in normalized_authorized:
        if claim.startswith(f"evidence/{task_id}"):
            continue
        if claim == "specs/designs/module-ownership.yaml":
            # The ownership registry is the canonical file that records its
            # own governance ownership; maintenance may change it only when
            # explicitly enumerated in the manifest.
            continue
        if not any(
            _matches(claim, pattern) or _matches(pattern, claim)
            for pattern in module_patterns
        ):
            errors.append(
                f"Completed-Foundation maintenance authorized path is outside module ownership: {claim}"
            )

    paths, records = REGISTRATION.changed_paths(root, base_ref, head_ref)
    if paths is None:
        errors.append(
            "Completed-Foundation maintenance cannot determine changed paths"
        )
        paths = set()
    required_manifest_path = _maintenance_path(task_id)
    if required_manifest_path not in paths:
        errors.append(
            "Completed-Foundation maintenance must add or refresh its manifest"
        )
    forbidden_exact = {
        REGISTRATION.PLAN,
        REGISTRATION.ACTIVE,
        REGISTRATION.LEDGER,
        task_path or "",
    }
    for path in sorted(paths):
        if path in forbidden_exact:
            errors.append(
                f"Completed-Foundation maintenance changed forbidden state file: {path}"
            )
        if path.endswith(".tmp") or os.path.basename(path).startswith(
            ".ops008-controller"
        ):
            errors.append(
                f"Completed-Foundation maintenance contains temporary residue: {path}"
            )
        if not REGISTRATION.safe_repo_path(path):
            errors.append(
                f"Completed-Foundation maintenance changed unsafe path: {path}"
            )
        if REGISTRATION.ref_mode(root, head_ref, path) == "120000":
            errors.append(
                f"Completed-Foundation maintenance must not add symlinks: {path}"
            )
        if not any(_matches(path, claim) for claim in normalized_authorized):
            errors.append(
                f"Completed-Foundation maintenance changed unauthorized path: {path}"
            )
    for status, source, destination in records:
        if status.startswith(("R", "C")) and not (
            any(_matches(source, claim) for claim in normalized_authorized)
            and any(_matches(destination, claim) for claim in normalized_authorized)
        ):
            errors.append(
                f"Completed-Foundation maintenance rename/copy escapes authorization: {source} -> {destination}"
            )

    details = {
        "taskId": task_id,
        "baseSha": base_sha,
        "headSha": head_sha,
        "branch": manifest_branch,
        "manifest": required_manifest_path,
        "changedPathCount": len(paths),
        "authorizedPathCount": len(normalized_authorized),
        "errors": errors,
    }
    return (1 if errors else 0), details


def main() -> int:
    args = CORE.parse_args()
    root = os.path.abspath(args.repo_root)
    if REGISTRATION.is_registration_candidate(
        root, args.base_ref, args.head_ref
    ):
        code, details = REGISTRATION.validate_registration(
            root,
            args.base_ref,
            args.head_ref,
            task_hint=args.task,
            branch_name=args.branch_name,
        )
        if code:
            for error in details.get("errors") or []:
                REGISTRATION.emit("FAIL", error)
            return code
        REGISTRATION.emit(
            "PASS", "Program Task Registration lifecycle scope passed", details
        )
        return 0

    maintenance_task = _maintenance_task_from_diff(
        root, args.base_ref, args.head_ref, args.task
    )
    if maintenance_task:
        code, details = _validate_completed_foundation_maintenance(
            root,
            args.base_ref,
            args.head_ref,
            maintenance_task,
            args.branch_name,
        )
        if code:
            for error in details.get("errors") or []:
                REGISTRATION.emit("FAIL", error)
            return code
        REGISTRATION.emit(
            "PASS",
            "Completed Foundation maintenance is explicit, owned, state-preserving, and fail-closed",
            details,
        )
        return 0

    # run-program-lifecycle-gate.py monkey-patches these exported hooks. Copy
    # the current wrapper values into the preserved core before delegation.
    CORE.changed_paths = globals().get("changed_paths", CORE.changed_paths)
    CORE.task_ids_from_diff = globals().get(
        "task_ids_from_diff", CORE.task_ids_from_diff
    )
    return CORE.main()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Dispatch Program lifecycle validation to Registration, audited completed-
Foundation maintenance, or the byte-identical preserved lifecycle core.
"""

from __future__ import annotations

import copy
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
OWNERSHIP_PATH = "specs/designs/module-ownership.yaml"
PROTOCOL_PATH = "docs/25-multi-agent-collaboration-protocol.md"


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


def _expected_ownership_text(base_text: str, module_id: str, path: str) -> str | None:
    """Return the only permitted byte-level ownership edit: one tail append."""
    lines = base_text.splitlines(keepends=True)
    module_start: int | None = None
    module_end = len(lines)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == f"- id: {module_id}":
            module_start = index
            break
    if module_start is None:
        return None
    for index in range(module_start + 1, len(lines)):
        if lines[index].startswith("- id: "):
            module_end = index
            break

    paths_start: int | None = None
    paths_end: int | None = None
    for index in range(module_start + 1, module_end):
        if lines[index].rstrip("\r\n") == "  ownedPaths:":
            paths_start = index
            continue
        if paths_start is not None and index > paths_start:
            stripped = lines[index].rstrip("\r\n")
            if stripped.startswith("  ") and not stripped.startswith("  - "):
                paths_end = index
                break
    if paths_start is None or paths_end is None:
        return None
    existing = [
        line.strip()[2:].strip()
        for line in lines[paths_start + 1 : paths_end]
        if line.strip().startswith("- ")
    ]
    if path in existing:
        return None
    newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    lines.insert(paths_end, f"  - {path}{newline}")
    return "".join(lines)


def _validate_ownership_delta(
    base_text: str | None,
    head_text: str | None,
    base_ownership: dict[str, Any],
    head_ownership: dict[str, Any],
    manifest: dict[str, Any],
    errors: list[str],
) -> set[str]:
    expected_delta = {
        "moduleId": "MOD-GOV",
        "field": "ownedPaths",
        "operation": "tail-append",
        "paths": [PROTOCOL_PATH],
    }
    if manifest.get("ownershipDelta") != expected_delta:
        errors.append(
            "Completed-Foundation maintenance ownershipDelta must declare the exact MOD-GOV protocol tail append"
        )
    if not base_text or head_text is None:
        errors.append("Completed-Foundation maintenance ownership text is missing")
        return {PROTOCOL_PATH}
    expected_text = _expected_ownership_text(base_text, "MOD-GOV", PROTOCOL_PATH)
    if expected_text is None:
        errors.append(
            "Completed-Foundation maintenance cannot derive the one permitted ownership tail append"
        )
    elif head_text != expected_text:
        errors.append(
            "Completed-Foundation maintenance ownership change must be the exact byte-preserving MOD-GOV protocol tail append"
        )

    expected_document = copy.deepcopy(base_ownership)
    modules = [
        module
        for module in expected_document.get("modules") or []
        if isinstance(module, dict) and module.get("id") == "MOD-GOV"
    ]
    if len(modules) != 1:
        errors.append("Target-base ownership must contain exactly one MOD-GOV module")
    else:
        owned = modules[0].get("ownedPaths")
        if not isinstance(owned, list) or PROTOCOL_PATH in owned:
            errors.append(
                "Target-base MOD-GOV ownership cannot accept the declared one-time protocol append"
            )
        else:
            owned.append(PROTOCOL_PATH)
            if head_ownership != expected_document:
                errors.append(
                    "Completed-Foundation maintenance changed ownership outside the declared protocol append"
                )
    return {PROTOCOL_PATH}


def _residue_name(path: str) -> bool:
    basename = os.path.basename(path).lower()
    suffixes = (".tmp", ".temp", ".placeholder", ".marker")
    if basename.endswith(suffixes):
        return True
    if basename.startswith((".controller-probe", ".ops008-controller")):
        return True
    tokens = [token for token in re.split(r"[^a-z0-9]+", basename) if token]
    return "probe" in tokens or "placeholder" in tokens or "marker" in tokens


def _placeholder_only(content: str | None) -> bool:
    if content is None:
        return False
    compact = " ".join(content.strip().lower().split())
    if not compact or len(compact) > 512:
        return False
    if compact in {
        "placeholder",
        "test",
        "do-not-commit",
        "controller probe",
        "pending controller validation upload",
    }:
        return True
    words = set(re.findall(r"[a-z0-9-]+", compact))
    if "do-not-commit" in words:
        return True
    if "placeholder" in words and len(words) <= 30:
        return True
    return "controller" in words and "probe" in words and len(words) <= 30


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

    manifest_path = _maintenance_path(task_id)
    base_plan = _load_yaml_ref(root, base_ref, REGISTRATION.PLAN)
    head_plan = _load_yaml_ref(root, head_ref, REGISTRATION.PLAN)
    base_active = REGISTRATION.read_ref(root, base_ref, REGISTRATION.ACTIVE)
    head_active = REGISTRATION.read_ref(root, head_ref, REGISTRATION.ACTIVE)
    base_ledger = REGISTRATION.read_ref(root, base_ref, REGISTRATION.LEDGER)
    head_ledger = REGISTRATION.read_ref(root, head_ref, REGISTRATION.LEDGER)
    base_ownership_text = REGISTRATION.read_ref(root, base_ref, OWNERSHIP_PATH)
    head_ownership_text = REGISTRATION.read_ref(root, head_ref, OWNERSHIP_PATH)
    base_ownership = REGISTRATION.load_yaml_text(base_ownership_text)
    head_ownership = REGISTRATION.load_yaml_text(head_ownership_text)
    manifest = _load_yaml_ref(root, head_ref, manifest_path)

    if REGISTRATION.read_ref(root, base_ref, manifest_path) is not None:
        errors.append(
            "Completed-Foundation maintenance manifest must be absent from the target base; this one-time maintenance cannot be reused"
        )
    if not isinstance(base_plan, dict) or not isinstance(head_plan, dict):
        errors.append(
            "Completed-Foundation maintenance Program Plan snapshots are invalid"
        )
        base_plan = {}
        head_plan = {}
    if not isinstance(base_ownership, dict):
        errors.append("Completed-Foundation maintenance target-base ownership is invalid")
        base_ownership = {}
    if not isinstance(head_ownership, dict):
        errors.append("Completed-Foundation maintenance candidate ownership is invalid")
        head_ownership = {}
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
    module_ids = set(REGISTRATION.as_list(front.get("moduleIds")))
    if not module_ids:
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
        "oneTime": True,
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

    delta_paths = _validate_ownership_delta(
        base_ownership_text,
        head_ownership_text,
        base_ownership,
        head_ownership,
        manifest,
        errors,
    )

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
        if any(sha == head_sha for _, sha in refs):
            if REGISTRATION.merge_base(root, base_sha, head_sha) != base_sha:
                errors.append(
                    "Completed-Foundation maintenance target base must be the exact merge base of branch HEAD"
                )
        elif (
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

    module_patterns = _module_patterns(base_ownership, module_ids)
    for claim in normalized_authorized:
        if claim.startswith(f"evidence/{task_id}"):
            continue
        if claim == OWNERSHIP_PATH:
            continue
        if claim in delta_paths:
            continue
        if not any(
            _matches(claim, pattern) or _matches(pattern, claim)
            for pattern in module_patterns
        ):
            errors.append(
                f"Completed-Foundation maintenance authorized path is outside target-base module ownership: {claim}"
            )

    paths, records = REGISTRATION.changed_paths(root, base_ref, head_ref)
    if paths is None:
        errors.append(
            "Completed-Foundation maintenance cannot determine changed paths"
        )
        paths = set()
    if manifest_path not in paths:
        errors.append(
            "Completed-Foundation maintenance must add its one-time manifest"
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
        if _residue_name(path):
            errors.append(
                f"Completed-Foundation maintenance contains probe/temp/placeholder residue: {path}"
            )
        if not REGISTRATION.safe_repo_path(path):
            errors.append(
                f"Completed-Foundation maintenance changed unsafe path: {path}"
            )
        mode = REGISTRATION.ref_mode(root, head_ref, path)
        if mode == "120000":
            errors.append(
                f"Completed-Foundation maintenance must not add symlinks: {path}"
            )
        if mode in {"100644", "100755"} and _placeholder_only(
            REGISTRATION.read_ref(root, head_ref, path)
        ):
            errors.append(
                f"Completed-Foundation maintenance contains placeholder-only content: {path}"
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
        "manifest": manifest_path,
        "changedPathCount": len(paths),
        "authorizedPathCount": len(normalized_authorized),
        "oneTime": manifest.get("oneTime"),
        "ownershipDelta": manifest.get("ownershipDelta"),
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
            "Completed Foundation maintenance is one-time, owned, state-preserving, and fail-closed",
            details,
        )
        return 0

    CORE.changed_paths = globals().get("changed_paths", CORE.changed_paths)
    CORE.task_ids_from_diff = globals().get(
        "task_ids_from_diff", CORE.task_ids_from_diff
    )
    return CORE.main()


if __name__ == "__main__":
    sys.exit(main())

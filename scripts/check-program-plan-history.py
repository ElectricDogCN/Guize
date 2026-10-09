#!/usr/bin/env python3
"""Validate Program Plan transitions against the integration base.

This checker is deliberately history-aware. It proves that reservations were
real repository states, completed provenance is immutable, and Completion PRs
modify only the completing task's canonical metadata.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml

RECOVERY_SPEC = importlib.util.spec_from_file_location(
    "guize_history_recovery", os.path.join(os.path.dirname(__file__), "check-program-lifecycle-guards.py")
)
RECOVERY = importlib.util.module_from_spec(RECOVERY_SPEC)
assert RECOVERY_SPEC and RECOVERY_SPEC.loader
RECOVERY_SPEC.loader.exec_module(RECOVERY)

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
TASK_DIR = "specs/tasks"
ACTIVE_STATES = {"reserved", "in_progress", "blocked", "review", "integration"}
PR_REF_RE = re.compile(r"^PR-([0-9]+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program Plan history transitions")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--task", default="")
    parser.add_argument("--branch-name", default="")
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


def ref_exists(root: str, ref: str) -> bool:
    return bool(ref) and git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").returncode == 0


def resolve_ref(root: str, ref: str) -> str | None:
    result = git(root, "rev-parse", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def read_ref(root: str, ref: str, path: str) -> str | None:
    if not path:
        return None
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def load_yaml_text(text: str | None) -> Any | None:
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def load_current(root: str, path: str) -> Any:
    with open(os.path.join(root, path), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_ref(root: str, ref: str, path: str) -> Any | None:
    return load_yaml_text(read_ref(root, ref, path))


def parse_front_matter(text: str | None) -> tuple[dict[str, Any], str]:
    if not text or not text.startswith("---"):
        return {}, text or ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        document = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, parts[2]
    return (document if isinstance(document, dict) else {}), parts[2]


def find_task_path(root: str, task_id: str, ref: str = "HEAD") -> str | None:
    exact = f"{TASK_DIR}/{task_id}.md"
    if read_ref(root, ref, exact) is not None:
        return exact
    tree = git(root, "ls-tree", "-r", "--name-only", ref, TASK_DIR)
    if tree.returncode != 0:
        return None
    matches = sorted(
        path
        for path in tree.stdout.splitlines()
        if path.startswith(f"{TASK_DIR}/{task_id}-") and path.endswith(".md")
    )
    return matches[0] if len(matches) == 1 else None


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if not text or text.upper() == "NONE":
        return []
    return [part.strip() for part in text.strip("[]").split(",") if part.strip()]


def section_paths(body: str, titles: tuple[str, ...]) -> list[str] | None:
    lines = body.splitlines()
    start: int | None = None
    wanted = tuple(value.lower() for value in titles)
    for index, line in enumerate(lines):
        if not line.strip().startswith("## "):
            continue
        title = re.sub(r"^##\s+", "", line.strip()).lower()
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
            value = value.replace("\\", "/")
            while value.startswith("./"):
                value = value[2:]
            paths.append(value.rstrip("/"))
    return paths


def mapping(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {str(item.get("taskId")): item for item in (items or [])}


def exact_token(message: str, token: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])", message) is not None


def exact_pr(message: str, reference: str) -> bool:
    match = PR_REF_RE.fullmatch(reference)
    return bool(match and re.search(rf"(?<!\d)#{match.group(1)}(?!\d)", message))


def validate_commit(
    root: str, sha: str, task_id: str, reference: str, label: str, errors: list[str]
) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        errors.append(f"{label} has invalid SHA: {sha!r}")
        return
    if git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        errors.append(f"{label} commit does not exist: {sha}")
        return
    message = git(root, "show", "-s", "--format=%B", sha).stdout
    if not exact_token(message, task_id):
        errors.append(f"{label} commit {sha} does not identify {task_id}")
    if not exact_pr(message, reference):
        errors.append(f"{label} commit {sha} does not identify {reference}")
    if not is_ancestor(root, sha, "HEAD"):
        errors.append(f"{label} commit {sha} is not reachable from HEAD")


def stable_spec_matches(
    task_id: str,
    entry: dict[str, Any],
    front: dict[str, Any],
    body: str,
    errors: list[str],
    reservation: bool,
) -> None:
    scalar_pairs = {
        "id": "taskId",
        "baseBranch": "baseBranch",
        "issue": "issue",
        "workPackage": "workPackage",
        "taskOwner": "owner",
        "coordinator": "coordinator",
        "implementer": "implementer",
        "reviewer": "reviewer",
        "integrator": "integrator",
        "riskLevel": "riskLevel",
        "coordinationGroup": "coordinationGroup",
        "handoffPath": "handoffPath",
        "integrationStrategy": "integrationStrategy",
        "integrationOrder": "integrationOrder",
    }
    if reservation:
        scalar_pairs.update(
            {"status": "status", "workBranch": "branch", "baseSha": "baseSha"}
        )
    for task_key, entry_key in scalar_pairs.items():
        if str(front.get(task_key, "")) != str(entry.get(entry_key, "")):
            errors.append(
                f"{task_id} Task Spec {task_key} does not match Active Work {entry_key}"
            )
    for task_key, entry_key in {
        "dependsOn": "dependsOn",
        "requirementIds": "requirementIds",
        "moduleIds": "moduleIds",
        "producesContracts": "producesContracts",
        "consumesContracts": "consumesContracts",
    }.items():
        if as_list(front.get(task_key)) != list(entry.get(entry_key) or []):
            errors.append(
                f"{task_id} Task Spec {task_key} does not match Active Work {entry_key}"
            )
    exclusive = section_paths(body, ("独占写范围", "exclusive write scope"))
    shared = section_paths(body, ("共享修改范围", "shared modification scope"))
    if set(exclusive or []) != set(entry.get("exclusivePaths") or []):
        errors.append(f"{task_id} Task Spec exclusive paths do not match Active Work")
    if set(shared or []) != set(entry.get("sharedPaths") or []):
        errors.append(f"{task_id} Task Spec shared paths do not match Active Work")


def changed_files(root: str, base_ref: str, head_ref: str, errors: list[str]) -> set[str]:
    result = git(root, "diff", "--name-only", f"{base_ref}...{head_ref}")
    if result.returncode != 0:
        errors.append(f"Cannot read changed files for {base_ref}...{head_ref}")
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_completion_scope(
    task_id: str,
    task_path: str,
    files: set[str],
    foundation: bool,
    errors: list[str],
) -> None:
    required = {PLAN, ACTIVE, task_path}
    if not foundation:
        required.add(LEDGER)
    missing = sorted(required - files)
    if missing:
        errors.append(f"Completion task {task_id} is missing canonical files: {missing}")
    invalid = sorted(
        path
        for path in files
        if path not in required
        and path != f"evidence/{task_id}"
        and not path.startswith(f"evidence/{task_id}/")
    )
    if invalid:
        errors.append(f"Completion task {task_id} changed unrelated files: {invalid}")
    if foundation and LEDGER in files:
        errors.append(f"Foundation {task_id} completion must not change {LEDGER}")


def only_task_removed(
    base_active: dict[str, Any], current_active: dict[str, Any], task_id: str
) -> bool:
    expected = copy.deepcopy(base_active)
    expected["tasks"] = [
        item for item in base_active.get("tasks") or [] if item.get("taskId") != task_id
    ]
    return current_active == expected


def only_plan_target_changed(
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    section: str,
    task_id: str,
    fields: set[str],
) -> bool:
    base_copy = copy.deepcopy(base_plan)
    current_copy = copy.deepcopy(current_plan)
    base_items = mapping(base_copy.get(section))
    current_items = mapping(current_copy.get(section))
    if set(base_items) != set(current_items) or task_id not in current_items:
        return False
    for other_id in base_items:
        if other_id != task_id and base_items[other_id] != current_items[other_id]:
            return False
    base_target = copy.deepcopy(base_items[task_id])
    current_target = copy.deepcopy(current_items[task_id])
    for field in fields:
        base_target.pop(field, None)
        current_target.pop(field, None)
    if base_target != current_target:
        return False
    base_copy[section] = []
    current_copy[section] = []
    return base_copy == current_copy


def validate_reservation_snapshot(
    root: str, record: dict[str, Any], errors: list[str]
) -> None:
    task_id = str(record.get("taskId") or "")
    commit = str(record.get("reservationCommit") or "")
    active = load_ref(root, commit, ACTIVE)
    if not isinstance(active, dict):
        errors.append(f"Completion record {task_id} reservation commit has no readable {ACTIVE}")
        return
    entries = [item for item in active.get("tasks") or [] if item.get("taskId") == task_id]
    if len(entries) != 1 or entries[0].get("status") != "reserved":
        errors.append(
            f"Completion record {task_id} reservation commit must contain one reserved Active Work entry"
        )
        return
    parent = resolve_ref(root, f"{commit}^1")
    if not parent:
        errors.append(f"Completion record {task_id} reservation commit has no first parent")
    else:
        previous = load_ref(root, parent, ACTIVE)
        if isinstance(previous, dict) and any(
            item.get("taskId") == task_id for item in previous.get("tasks") or []
        ):
            errors.append(
                f"Completion record {task_id} reservation commit did not introduce the reservation"
            )
    task_path = str(record.get("taskSpec") or "")
    front, body = parse_front_matter(read_ref(root, commit, task_path))
    if not front:
        errors.append(f"Completion record {task_id} reservation Task Spec is unreadable")
    else:
        stable_spec_matches(task_id, entries[0], front, body, errors, reservation=True)
    base_sha = str(entries[0].get("baseSha") or "")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", base_sha)
        or base_sha == commit
        or not is_ancestor(root, base_sha, commit)
    ):
        errors.append(
            f"Completion record {task_id} reservation baseSha must be a strict ancestor of reservation commit"
        )


def validate_regular_completion(
    root: str,
    task_id: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    base_ref: str,
    head_ref: str,
    branch_name: str,
    errors: list[str],
) -> None:
    before = mapping(base_plan.get("tasks")).get(task_id)
    after = mapping(current_plan.get("tasks")).get(task_id)
    if not before or not after or before.get("status") not in ACTIVE_STATES or after.get("status") != "completed":
        errors.append(f"Completion task {task_id} has an invalid Program status transition")
        return
    if not only_plan_target_changed(
        base_plan, current_plan, "tasks", task_id, {"status"}
    ):
        errors.append(f"Completion task {task_id} may only change its Program status")
    prior_entries = [
        item for item in base_active.get("tasks") or [] if item.get("taskId") == task_id
    ]
    if len(prior_entries) != 1:
        errors.append(f"Completion task {task_id} requires one prior Active Work entry")
        return
    if not only_task_removed(base_active, current_active, task_id):
        errors.append(f"Completion task {task_id} may only remove its own Active Work entry")
    base_records = base_ledger.get("records") or []
    current_records = current_ledger.get("records") or []
    if (
        len(current_records) != len(base_records) + 1
        or current_records[: len(base_records)] != base_records
        or current_records[-1].get("taskId") != task_id
    ):
        errors.append(
            f"Completion task {task_id} must append exactly one immutable task-bound ledger record"
        )
    task_path = find_task_path(root, task_id, head_ref)
    if not task_path:
        errors.append(f"Completion task {task_id} has no Task Spec")
        return
    front, body = parse_front_matter(read_ref(root, head_ref, task_path))
    if front.get("status") != "completed":
        errors.append(f"Completion task {task_id} Task Spec is not completed")
    resolved_base = resolve_ref(root, base_ref)
    if resolved_base and str(front.get("baseSha") or "") != resolved_base:
        errors.append(f"Completion task {task_id} Task Spec baseSha must equal target base")
    if branch_name and str(front.get("workBranch") or "") != branch_name:
        errors.append(f"Completion task {task_id} Task Spec branch does not match PR branch")
    stable_spec_matches(task_id, prior_entries[0], front, body, errors, reservation=False)
    validate_completion_scope(
        task_id,
        task_path,
        changed_files(root, base_ref, head_ref, errors),
        False,
        errors,
    )


def foundation_reservation(
    root: str,
    task_id: str,
    base_ref: str,
    current_entry: dict[str, Any],
    errors: list[str],
) -> tuple[str, dict[str, Any], set[str]] | None:
    """Prove the original reservation on the audited integration history.

    Active Work baseSha changes when a Foundation enters Review or is rebased.
    It cannot stand in for the original reservation's immutable Git snapshot.
    Walk only the target base's first-parent chain, without path simplification:
    a candidate or an archived side parent cannot manufacture that history.
    """
    history = git(root, "rev-list", "--first-parent", "--reverse", base_ref)
    if history.returncode != 0:
        errors.append(f"Foundation {task_id} cannot read audited reservation history")
        return None
    commits = history.stdout.splitlines()
    introductions: list[tuple[str, dict[str, Any]]] = []
    snapshots: list[tuple[str, dict[str, Any]]] = []
    present = False
    for commit in commits:
        text = read_ref(root, commit, ACTIVE)
        active = load_yaml_text(text)
        if text is not None and (
            not isinstance(active, dict) or not isinstance(active.get("tasks"), list)
        ):
            errors.append(f"Foundation {task_id} has unreadable historical Registry at {commit}")
            return None
        entries = [
            item for item in (active or {}).get("tasks", [])
            if isinstance(item, dict) and item.get("taskId") == task_id
        ]
        if len(entries) > 1:
            errors.append(f"Foundation {task_id} has duplicate historical Registry entries")
            return None
        if entries and not present:
            introductions.append((commit, entries[0]))
        if entries:
            snapshots.append((commit, entries[0]))
        present = bool(entries)
    if len(introductions) != 1 or not present:
        errors.append(f"Foundation {task_id} requires exactly one original reservation on audited first-parent history")
        return None
    commit, entry = introductions[0]
    parent = resolve_ref(root, f"{commit}^1")
    plan = load_ref(root, commit, PLAN)
    previous_plan = load_ref(root, parent, PLAN) if parent else None
    previous_active = load_ref(root, parent, ACTIVE) if parent else None
    if not parent or not isinstance(plan, dict) or not isinstance(previous_plan, dict) or not isinstance(previous_active, dict):
        errors.append(f"Foundation {task_id} reservation has no readable integration parent")
        return None
    def historical_time(value: Any) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Historical timestamps require an explicit timezone")
        return parsed.astimezone(timezone.utc)
    try:
        observed = datetime.fromtimestamp(int(git(root, "show", "-s", "--format=%ct", commit).stdout.strip()), timezone.utc)
        acquired = historical_time(entry["lease"]["acquiredAt"])
        expires = historical_time(entry["lease"]["expiresAt"])
        maximum = min(168, int(previous_active["policy"]["leaseMaxHours"]))
        # Git records whole seconds; do not reject legitimate same-second
        # subsecond timestamps as if it recorded a more precise chronology.
        if not acquired < observed + timedelta(seconds=1) or not observed < expires or not 0 < (expires - acquired).total_seconds() <= maximum * 3600:
            raise ValueError("Reservation lease is invalid at its integration commit time")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        errors.append(f"Foundation {task_id} original reservation lease is invalid: {exc}")
        observed = None
    ownership = load_ref(root, commit, RECOVERY.OWNERSHIP)
    if not isinstance(ownership, dict):
        errors.append(f"Foundation {task_id} original reservation ownership snapshot is unreadable")
    else:
        RECOVERY.validate_foundation_claims(task_id, entry, ownership, parent, errors)
        audited_legacy = RECOVERY.FOUNDATION_SCOPE_EXCEPTIONS.get(task_id, ())
        if any(not RECOVERY.governance_claim_subset(str(path), ownership) and str(path) not in audited_legacy for path in entry.get("exclusivePaths") or []):
            errors.append(f"Foundation {task_id} original reservation claims are outside governance ownership subsets")
    if entry.get("sharedPaths") or not entry.get("exclusivePaths"):
        errors.append(f"Foundation {task_id} original reservation requires exclusive governance claims")
    if any(str(path).strip() in {"", "*", "**"} for path in list(entry.get("exclusivePaths") or []) + list(entry.get("sharedPaths") or [])):
        errors.append(f"Foundation {task_id} original reservation may not claim the entire repository")
    foundations = [item for item in plan.get("foundationTasks", []) if item.get("taskId") == task_id]
    if (
        len(foundations) != 1 or foundations[0].get("status") != "reserved"
        or foundations[0].get("title") != entry.get("title")
        or foundations[0].get("completionRef") != f"ISSUE-{entry.get('issue')}"
        or foundations[0].get("mergeCommit") is not None
        or entry.get("status") != "reserved"
        or entry.get("agentRole") != "coordinator"
        or entry.get("riskLevel") != "high"
        or entry.get("moduleIds") != ["MOD-GOV"]
        or entry.get("programWave") != "FOUNDATION"
        or entry.get("programTaskId") != task_id
        or entry.get("programPlan") != PLAN
        or not entry.get("implementer") or not entry.get("reviewer")
        or entry.get("implementer") == entry.get("reviewer")
    ):
        errors.append(f"Foundation {task_id} original reservation identity is invalid")
        return None
    without_target = copy.deepcopy(plan)
    without_target["foundationTasks"] = [item for item in plan.get("foundationTasks", []) if item.get("taskId") != task_id]
    registry = load_ref(root, commit, ACTIVE)
    without_entry = copy.deepcopy(registry)
    without_entry["tasks"] = [item for item in registry.get("tasks", []) if item.get("taskId") != task_id]
    if (
        previous_plan.get("status") == "active" and plan.get("status") == "frozen"
        and RECOVERY.recovery_owner(plan) == task_id
    ):
        # The existing recovery validator reads current files and the Ledger.
        # Give it the real historical checkout, never the later Completion tree.
        freeze_errors: list[str] = []
        try:
            if observed is None or historical_time(plan["recovery"]["frozenAt"]) >= observed + timedelta(seconds=1):
                raise ValueError("Original freeze occurred after its integration commit")
        except (KeyError, TypeError, ValueError) as exc:
            freeze_errors.append(str(exc))
        try:
            with tempfile.TemporaryDirectory(prefix="guize-foundation-reservation-") as temporary:
                snapshot = os.path.join(temporary, "snapshot")
                clone = git(root, "clone", "--shared", "--no-checkout", "--quiet", "--", root, snapshot)
                checkout = git(snapshot, "checkout", "--detach", "--quiet", commit) if clone.returncode == 0 else None
                if not checkout or checkout.returncode != 0 or resolve_ref(snapshot, "HEAD") != commit:
                    freeze_errors.append("Cannot reconstruct original freeze snapshot")
                elif RECOVERY.validate_recovery_transition(snapshot, parent, commit, freeze_errors) != task_id:
                    freeze_errors.append("Original freeze owner does not match reservation")
        except OSError as exc:
            freeze_errors.append(f"Cannot verify original freeze snapshot: {exc}")
        if freeze_errors:
            errors.extend(f"Foundation {task_id} original atomic freeze rejected: {error}" for error in freeze_errors)
        else:
            previous_plan = copy.deepcopy(previous_plan)
            for document in (without_target, previous_plan):
                document.pop("status", None)
                document.pop("recovery", None)
    if without_target != previous_plan or without_entry != previous_active:
        errors.append(f"Foundation {task_id} original reservation changed another identity or policy")
    mutable = {"status", "agentRole", "baseSha", "branch", "exclusivePaths", "sharedPaths", "lease"}
    stable = {k: v for k, v in entry.items() if k not in mutable}
    for snapshot_commit, snapshot_entry in snapshots:
        if {k: v for k, v in snapshot_entry.items() if k not in mutable} != stable:
            errors.append(f"Foundation {task_id} changed stable identity in audited history at {snapshot_commit}")
        if not snapshot_entry.get("implementer") or snapshot_entry.get("implementer") == snapshot_entry.get("reviewer"):
            errors.append(f"Foundation {task_id} lost independent roles in audited history at {snapshot_commit}")
    if {k: v for k, v in entry.items() if k not in mutable} != {k: v for k, v in current_entry.items() if k not in mutable}:
        errors.append(f"Foundation {task_id} original reservation does not match current stable identity")
    task_path = find_task_path(root, task_id, commit)
    front, body = parse_front_matter(read_ref(root, commit, task_path or ""))
    if (
        front.get("schemaVersion") != 2 or front.get("status") != "reserved"
        or front.get("wave") != "FOUNDATION" or front.get("agentRole") != "coordinator"
        or front.get("titleZh") != entry.get("title")
    ):
        errors.append(f"Foundation {task_id} original reservation Task Spec is invalid")
    else:
        stable_spec_matches(task_id, entry, front, body, errors, reservation=True)
    if (
        front.get("coordinationMode") != "registry" or front.get("programPlan") != PLAN
        or front.get("programTaskId") != task_id
        or front.get("evidencePath") != f"evidence/{task_id}"
        or front.get("handoffPath") != f"evidence/{task_id}/handoff.md"
    ):
        errors.append(f"Foundation {task_id} original reservation Task Spec canonical binding is invalid")
    try:
        if historical_time(front.get("leaseExpiresAt")) != historical_time(entry["lease"]["expiresAt"]):
            raise ValueError("Task Spec leaseExpiresAt does not match original Registry")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"Foundation {task_id} original reservation Task Spec lease is invalid: {exc}")
    try:
        with tempfile.TemporaryDirectory(prefix="guize-foundation-task-") as temporary:
            snapshot = os.path.join(temporary, "snapshot")
            clone = git(root, "clone", "--shared", "--no-checkout", "--quiet", "--", root, snapshot)
            checkout = git(snapshot, "checkout", "--detach", "--quiet", commit) if clone.returncode == 0 else None
            if not checkout or checkout.returncode != 0 or resolve_ref(snapshot, "HEAD") != commit:
                errors.append(f"Foundation {task_id} cannot reconstruct original Task Spec snapshot")
            else:
                task_errors: list[str] = []
                validation = subprocess.run(
                    [sys.executable, os.path.join(os.path.dirname(__file__), "check-task-file.py"), "--repo-root", snapshot, "--task", task_id],
                    cwd=snapshot, capture_output=True, text=True, check=False,
                )
                if validation.returncode != 0:
                    task_errors.append("Historical Task file validation failed: " + validation.stdout.strip() + validation.stderr.strip())
                evidence = str(front.get("evidencePath") or "")
                if not os.path.isdir(os.path.join(snapshot, evidence)) or read_ref(root, commit, f"evidence/{task_id}/handoff.md") is None:
                    task_errors.append("Original reservation Evidence/handoff does not exist")
                errors.extend(f"Foundation {task_id} original reservation Task Spec: {error}" for error in task_errors)
    except OSError as exc:
        errors.append(f"Foundation {task_id} cannot validate original Task Spec: {exc}")
    base_sha = str(entry.get("baseSha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha) or base_sha == commit or not is_ancestor(root, base_sha, commit):
        errors.append(f"Foundation {task_id} original reservation baseSha must be a strict ancestor")
    if base_sha != parent:
        errors.append(f"Foundation {task_id} original reservation baseSha must equal integration parent")
    files = RECOVERY.changed_paths(root, parent, commit)
    if files is None:
        errors.append(f"Foundation {task_id} cannot read exact original reservation paths")
        files = set()
    allowed = {PLAN, ACTIVE, task_path}
    if not {PLAN, ACTIVE, task_path}.issubset(files) or any(
        path not in allowed and not path.startswith(f"evidence/{task_id}/")
        for path in files
    ):
        errors.append(f"Foundation {task_id} original reservation must be metadata-only")
    return commit, entry, set(commits)


def validate_foundations(
    root: str,
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    base_ref: str,
    head_ref: str,
    branch_name: str,
    errors: list[str],
) -> None:
    before_map = mapping(base_plan.get("foundationTasks"))
    after_map = mapping(current_plan.get("foundationTasks"))
    for task_id, before in before_map.items():
        after = after_map.get(task_id)
        if before.get("status") == "completed" and after != before:
            errors.append(f"Completed Foundation {task_id} provenance is immutable")
    for task_id, after in after_map.items():
        before = before_map.get(task_id)
        if after.get("status") != "completed" or (before and before.get("status") == "completed"):
            continue
        if not before or before.get("status") not in ACTIVE_STATES:
            errors.append(f"Foundation {task_id} cannot complete without an active base state")
            continue
        prior_entries = [
            item for item in base_active.get("tasks") or [] if item.get("taskId") == task_id
        ]
        if len(prior_entries) != 1:
            errors.append(f"Foundation {task_id} requires one prior Active Work entry")
            continue
        if not only_task_removed(base_active, current_active, task_id):
            errors.append(f"Foundation {task_id} may only remove its own Active Work entry")
        if current_ledger != base_ledger:
            errors.append(f"Foundation {task_id} must not modify the ordinary ledger")
        if not only_plan_target_changed(
            base_plan,
            current_plan,
            "foundationTasks",
            task_id,
            {"status", "completionRef", "mergeCommit"},
        ):
            errors.append(f"Foundation {task_id} may only change completion identity fields")
        merge_sha = str(after.get("mergeCommit") or "")
        completion_ref = str(after.get("completionRef") or "")
        validate_commit(root, merge_sha, task_id, completion_ref, f"Foundation {task_id}", errors)
        reservation = foundation_reservation(root, task_id, base_ref, prior_entries[0], errors)
        if reservation:
            reservation_commit, reserved_entry, audited_commits = reservation
            reservation_base = str(reserved_entry.get("baseSha") or "")
            if merge_sha == reservation_base or not is_ancestor(root, reservation_base, merge_sha):
                errors.append(f"Foundation {task_id} mergeCommit must strictly descend from reservation baseSha")
            if merge_sha == reservation_commit or not is_ancestor(root, reservation_commit, merge_sha):
                errors.append(f"Foundation {task_id} implementation must strictly follow original reservation")
            if merge_sha not in audited_commits:
                errors.append(f"Foundation {task_id} implementation is not integrated on audited first-parent history")
        task_path = find_task_path(root, task_id, head_ref)
        if not task_path:
            errors.append(f"Foundation {task_id} has no Task Spec")
            continue
        front, body = parse_front_matter(read_ref(root, head_ref, task_path))
        if front.get("status") != "completed":
            errors.append(f"Foundation {task_id} Task Spec is not completed")
        resolved_base = resolve_ref(root, base_ref)
        if resolved_base and str(front.get("baseSha") or "") != resolved_base:
            errors.append(f"Foundation {task_id} Task Spec baseSha must equal target base")
        if branch_name and str(front.get("workBranch") or "") != branch_name:
            errors.append(f"Foundation {task_id} Task Spec branch does not match PR branch")
        stable_spec_matches(task_id, prior_entries[0], front, body, errors, reservation=False)
        evidence = str(front.get("evidencePath") or "")
        handoff = str(front.get("handoffPath") or "")
        if evidence != f"evidence/{task_id}" or handoff != f"evidence/{task_id}/handoff.md":
            errors.append(f"Foundation {task_id} Evidence/Handoff must be task-bound")
        if not os.path.isdir(os.path.join(root, evidence)) or not os.path.isfile(
            os.path.join(root, handoff)
        ):
            errors.append(f"Foundation {task_id} Evidence/Handoff does not exist")
        validate_completion_scope(
            task_id,
            task_path,
            changed_files(root, base_ref, head_ref, errors),
            True,
            errors,
        )


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    if not ref_exists(root, args.base_ref) or not ref_exists(root, args.head_ref):
        emit("FAIL", "Program history refs are missing")
        return 1
    try:
        base_plan = load_ref(root, args.base_ref, PLAN)
        current_plan = load_current(root, PLAN)
        base_active = load_ref(root, args.base_ref, ACTIVE)
        current_active = load_current(root, ACTIVE)
        base_ledger = load_ref(root, args.base_ref, LEDGER)
        current_ledger = load_current(root, LEDGER)
    except Exception as exc:
        emit("FAIL", f"Cannot load Program history documents: {exc}")
        return 1

    # GZ-014 is the migration that introduces an empty ledger. A missing base
    # ledger is valid only while the current ledger is still empty.
    if base_ledger is None:
        if isinstance(current_ledger, dict) and not (current_ledger.get("records") or []):
            base_ledger = {"records": []}
        else:
            errors.append("A non-empty completion ledger cannot be introduced without base history")
            base_ledger = {"records": []}

    documents = (
        base_plan,
        current_plan,
        base_active,
        current_active,
        base_ledger,
        current_ledger,
    )
    if not all(isinstance(item, dict) for item in documents):
        emit("FAIL", "Program history documents are missing or invalid")
        return 1

    validate_foundations(
        root,
        base_plan,
        current_plan,
        base_active,
        current_active,
        base_ledger,
        current_ledger,
        args.base_ref,
        args.head_ref,
        args.branch_name,
        errors,
    )
    for record in current_ledger.get("records") or []:
        validate_reservation_snapshot(root, record, errors)

    paths = RECOVERY.changed_paths(root, args.base_ref, args.head_ref) or set()
    repair_tasks = RECOVERY.evidence_task_ids(paths)
    if args.task:
        repair_tasks.add(args.task)
    repairs: set[str] = set()
    for task_id in sorted(repair_tasks):
        if RECOVERY.completed_evidence_candidate(base_plan, current_plan, task_id):
            RECOVERY.validate_evidence_repair(root, args.base_ref, args.head_ref, task_id, args.branch_name, errors)
            repairs.add(task_id)
    if args.task and args.task not in repairs:
        task_path = find_task_path(root, args.task, args.head_ref)
        front, _ = parse_front_matter(read_ref(root, args.head_ref, task_path or ""))
        if front.get("status") == "completed" and args.task not in mapping(
            current_plan.get("foundationTasks")
        ):
            validate_regular_completion(
                root,
                args.task,
                base_plan,
                current_plan,
                base_active,
                current_active,
                base_ledger,
                current_ledger,
                args.base_ref,
                args.head_ref,
                args.branch_name,
                errors,
            )

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program Plan history transitions are valid",
        {
            "baseRef": args.base_ref,
            "headRef": args.head_ref,
            "completionRecords": len(current_ledger.get("records") or []),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

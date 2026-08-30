#!/usr/bin/env python3
"""Validate Program/Registry lifecycle and completion finalization invariants.

This mandatory supplemental checker covers invariants that require the current
snapshot, target-branch state, changed-file set, task Evidence, and (when an
external blocker is declared resolved) live GitHub state at the same time.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

import yaml

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
TASK_DIR = "specs/tasks"
ACTIVE_STATES = {"reserved", "in_progress", "blocked", "review", "integration"}
COMPLETION_TOKENS = ("completion", "completed", "complete", "完成", "收口", "合并")
REQUIRED_COMPLETION_EVIDENCE = (
    "handoff.md",
    "summary.md",
    "commands.txt",
    "test-results/README.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program finalization invariants")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--task", default="")
    return parser.parse_args()


def emit(status: str, message: str, details: Any | None = None) -> None:
    payload: dict[str, Any] = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def load_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git(root: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )


def ref_exists(root: str, ref: str) -> bool:
    return bool(ref) and git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").returncode == 0


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def read_ref(root: str, ref: str, path: str) -> str | None:
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def load_ref(root: str, ref: str, path: str) -> Any | None:
    text = read_ref(root, ref, path)
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def mapping(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {str(item.get("taskId")): item for item in (items or []) if isinstance(item, dict)}


def find_task_path(root: str, task_id: str) -> str | None:
    exact = f"{TASK_DIR}/{task_id}.md"
    if os.path.isfile(os.path.join(root, exact)):
        return exact
    directory = os.path.join(root, TASK_DIR)
    if not os.path.isdir(directory):
        return None
    matches = sorted(
        f"{TASK_DIR}/{name}"
        for name in os.listdir(directory)
        if name.startswith(task_id + "-") and name.endswith(".md")
    )
    return matches[0] if len(matches) == 1 else None


def parse_front(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        document = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return document if isinstance(document, dict) else {}


def changed_files(root: str, base_ref: str, head_ref: str) -> set[str] | None:
    result = git(root, "diff", "--name-only", f"{base_ref}...{head_ref}")
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_execution_mapping(
    plan: dict[str, Any], active: dict[str, Any], errors: list[str]
) -> None:
    """Require one Active Work lease for every executing Program/Foundation task."""
    planned = mapping(plan.get("tasks"))
    foundations = mapping(plan.get("foundationTasks"))
    active_entries: dict[str, list[dict[str, Any]]] = {}
    for entry in active.get("tasks") or []:
        task_id = str(entry.get("taskId") or "")
        active_entries.setdefault(task_id, []).append(entry)

    for task_id, task in {**foundations, **planned}.items():
        status = task.get("status")
        entries = active_entries.get(task_id, [])
        if status in ACTIVE_STATES:
            if len(entries) != 1:
                errors.append(
                    f"Executing task {task_id} must have exactly one Active Work entry; got {len(entries)}"
                )
            elif entries[0].get("status") != status:
                errors.append(
                    f"Executing task {task_id} Program status {status!r} does not match "
                    f"Active Work status {entries[0].get('status')!r}"
                )
        elif entries:
            errors.append(
                f"Non-executing task {task_id} with Program status {status!r} must not have an Active Work entry"
            )

    for task_id, entries in active_entries.items():
        if task_id not in planned and task_id not in foundations:
            errors.append(f"Active Work task {task_id} does not exist in the canonical Program Plan")
        if len(entries) != 1:
            errors.append(f"Active Work task {task_id} is duplicated")


def validate_foundation_specs(
    root: str, plan: dict[str, Any], errors: list[str]
) -> None:
    """Allow historical approved specs only for pre-schema legacy Foundations."""
    for foundation in plan.get("foundationTasks") or []:
        if not isinstance(foundation, dict) or foundation.get("status") != "completed":
            continue
        task_id = str(foundation.get("taskId") or "")
        path = find_task_path(root, task_id)
        if not path:
            errors.append(f"Completed Foundation {task_id} has no unique Task Spec")
            continue
        front = parse_front(os.path.join(root, path))
        schema_version = front.get("schemaVersion")
        status = front.get("status")
        if schema_version is None:
            if status not in {"approved", "completed"}:
                errors.append(
                    f"Legacy completed Foundation {task_id} Task Spec has invalid status {status!r}"
                )
        elif status != "completed":
            errors.append(
                f"schemaVersion {schema_version} completed Foundation {task_id} Task Spec "
                f"status must remain completed, got {status!r}"
            )


def completion_merge_sha(
    task_id: str, plan: dict[str, Any], ledger: dict[str, Any]
) -> str | None:
    foundations = mapping(plan.get("foundationTasks"))
    if task_id in foundations:
        value = foundations[task_id].get("mergeCommit")
        return str(value) if value else None
    records = [
        item
        for item in ledger.get("records") or []
        if isinstance(item, dict) and item.get("taskId") == task_id
    ]
    if len(records) != 1:
        return None
    value = records[0].get("mergeCommit")
    return str(value) if value else None


def validate_completion_evidence(
    root: str,
    base_ref: str,
    head_ref: str,
    task_id: str,
    plan: dict[str, Any],
    ledger: dict[str, Any],
    errors: list[str],
) -> None:
    path = find_task_path(root, task_id)
    if not path:
        return
    front = parse_front(os.path.join(root, path))
    if front.get("status") != "completed":
        return

    merge_sha = completion_merge_sha(task_id, plan, ledger)
    if not merge_sha:
        errors.append(f"Completed task {task_id} has no unique implementation merge commit")
        return
    if not re.fullmatch(r"[0-9a-f]{40}", merge_sha):
        errors.append(f"Completed task {task_id} merge commit is invalid: {merge_sha!r}")
    elif not is_ancestor(root, merge_sha, base_ref):
        errors.append(
            f"Completed task {task_id} implementation merge {merge_sha} is not present in target base {base_ref}"
        )

    files = changed_files(root, base_ref, head_ref)
    if files is None:
        errors.append(f"Cannot read completion changed files for {base_ref}...{head_ref}")
        return
    evidence_root = f"evidence/{task_id}"
    for relative in REQUIRED_COMPLETION_EVIDENCE:
        evidence_path = f"{evidence_root}/{relative}"
        if evidence_path not in files:
            errors.append(
                f"Completed task {task_id} must refresh completion Evidence file: {evidence_path}"
            )
            continue
        full = os.path.join(root, evidence_path)
        if not os.path.isfile(full):
            errors.append(f"Completed task {task_id} Evidence file is missing: {evidence_path}")
            continue
        with open(full, "r", encoding="utf-8") as handle:
            content = handle.read()
        lowered = content.lower()
        if task_id not in content:
            errors.append(f"Completed task {task_id} Evidence file does not identify the task: {evidence_path}")
        if merge_sha not in content:
            errors.append(
                f"Completed task {task_id} Evidence file does not record implementation merge {merge_sha}: "
                f"{evidence_path}"
            )
        if not any(token in lowered for token in COMPLETION_TOKENS):
            errors.append(
                f"Completed task {task_id} Evidence file does not describe completion: {evidence_path}"
            )


def ref_matches(pattern: str, ref: str) -> bool:
    if pattern == "~DEFAULT_BRANCH":
        return ref == "refs/heads/main"
    return fnmatch.fnmatchcase(ref, pattern)


def ruleset_applies_to_main(ruleset: dict[str, Any]) -> bool:
    if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
        return False
    condition = ((ruleset.get("conditions") or {}).get("ref_name") or {})
    includes = condition.get("include") or []
    excludes = condition.get("exclude") or []
    main_ref = "refs/heads/main"
    return any(ref_matches(str(item), main_ref) for item in includes) and not any(
        ref_matches(str(item), main_ref) for item in excludes
    )


def ruleset_satisfies_policy(ruleset: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if ruleset.get("bypass_actors"):
        failures.append("ruleset has bypass actors")
    rules = {rule.get("type"): rule for rule in ruleset.get("rules") or []}
    pull_request = rules.get("pull_request")
    if not pull_request:
        failures.append("pull_request rule is missing")
    else:
        parameters = pull_request.get("parameters") or {}
        if int(parameters.get("required_approving_review_count") or 0) < 1:
            failures.append("at least one approving review is not required")
        if parameters.get("dismiss_stale_reviews_on_push") is not True:
            failures.append("stale approval dismissal is not required")
        if parameters.get("require_code_owner_review") is not True:
            failures.append("CODEOWNERS review is not required")
        if parameters.get("required_review_thread_resolution") is not True:
            failures.append("review thread resolution is not required")
    status_rule = rules.get("required_status_checks")
    status_parameters = (status_rule or {}).get("parameters") or {}
    contexts = {
        str(item.get("context") or "")
        for item in status_parameters.get("required_status_checks") or []
    }
    if "Governance Checks" not in contexts and "Governance Gate / Governance Checks" not in contexts:
        failures.append("Governance Checks is not a required status check")
    if status_parameters.get("strict_required_status_checks_policy") is not True:
        failures.append("pull requests are not required to test against the latest target branch")
    if "deletion" not in rules:
        failures.append("branch deletion is not blocked")
    if "non_fast_forward" not in rules:
        failures.append("force push/non-fast-forward updates are not blocked")
    return not failures, failures


def github_json(path: str) -> Any:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        raise RuntimeError("GITHUB_REPOSITORY is not available")
    base = os.environ.get("GUIZE_GITHUB_API_URL", "https://api.github.com").rstrip("/")
    url = f"{base}/repos/{repository}/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "guize-program-finalization",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"GitHub API request failed for {path}: {exc}") from exc


def validate_resolved_blockers(plan: dict[str, Any], errors: list[str]) -> None:
    for blocker in plan.get("externalBlockers") or []:
        if not isinstance(blocker, dict) or blocker.get("status") != "resolved":
            continue
        blocker_id = blocker.get("id")
        if blocker_id != "BRANCH-PROTECTION":
            errors.append(
                f"Resolved external blocker {blocker_id} has no supported live verification provider"
            )
            continue
        try:
            issue = github_json(f"issues/{blocker.get('issue')}")
            if issue.get("state") != "closed":
                errors.append(f"Resolved blocker {blocker_id} issue is not closed")
            branch = github_json("branches/main")
            if branch.get("protected") is not True:
                errors.append(f"Resolved blocker {blocker_id} main.protected is not true")
            summaries = github_json("rulesets")
            accepted = False
            reasons: list[str] = []
            for summary in summaries if isinstance(summaries, list) else []:
                ruleset_id = summary.get("id")
                if ruleset_id is None:
                    continue
                detail = github_json(f"rulesets/{ruleset_id}")
                if not ruleset_applies_to_main(detail):
                    continue
                valid, failures = ruleset_satisfies_policy(detail)
                if valid:
                    accepted = True
                    break
                reasons.extend(failures)
            if not accepted:
                detail = "; ".join(sorted(set(reasons))) or "no qualifying active ruleset applies to main"
                errors.append(f"Resolved blocker {blocker_id} lacks verified enforcement: {detail}")
        except RuntimeError as exc:
            errors.append(f"Resolved blocker {blocker_id} cannot be live-verified: {exc}")


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    if not ref_exists(root, args.base_ref) or not ref_exists(root, args.head_ref):
        emit("FAIL", "Program finalization refs are missing")
        return 1
    try:
        plan = load_yaml(os.path.join(root, PLAN))
        active = load_yaml(os.path.join(root, ACTIVE))
        ledger = load_yaml(os.path.join(root, LEDGER))
    except Exception as exc:
        emit("FAIL", f"Cannot load Program finalization documents: {exc}")
        return 1
    if not all(isinstance(item, dict) for item in (plan, active, ledger)):
        emit("FAIL", "Program finalization documents must be mappings")
        return 1

    validate_execution_mapping(plan, active, errors)
    validate_foundation_specs(root, plan, errors)
    validate_resolved_blockers(plan, errors)
    if args.task:
        validate_completion_evidence(
            root,
            args.base_ref,
            args.head_ref,
            args.task,
            plan,
            ledger,
            errors,
        )

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program finalization invariants passed",
        {
            "activeTasks": len(active.get("tasks") or []),
            "completedFoundations": sum(
                1
                for item in plan.get("foundationTasks") or []
                if isinstance(item, dict) and item.get("status") == "completed"
            ),
            "task": args.task or None,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

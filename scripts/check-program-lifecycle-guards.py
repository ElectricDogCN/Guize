#!/usr/bin/env python3
"""Fail-closed lifecycle guard for Program Plan, Registry, Task and Evidence.

This checker is intentionally history-aware and complements the existing
snapshot, transition, history and finalization checkers. It closes lifecycle
scope gaps that are easy to miss when a metadata PR is internally consistent:

* derives affected task IDs even on push-to-main runs without a branch Task ID;
* validates both source and destination paths of renames/copies;
* limits metadata-state PRs to task-bound lifecycle files;
* limits implementation PRs to their registered paths plus task metadata;
* constrains active Foundation leases to governance-owned/audited paths and to
  the exact target base SHA;
* requires task-bound cancellation and completion Evidence;
* rejects completion directly from reserved/blocked/in-progress; and
* requires structured command, exit-code and pass/fail completion results.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any

import yaml

PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
LEDGER = "specs/coordination/task-completions.yaml"
OWNERSHIP = "specs/designs/module-ownership.yaml"
TASK_DIR = "specs/tasks"
IMPLEMENTATION_STATES = {"in_progress", "review", "integration"}
METADATA_STATES = {"reserved", "blocked", "cancelled", "completed"}
COMPLETION_BASE_STATES = {"review", "integration"}
GLOB_CHARS = "*?["
TASK_PATH_RE = re.compile(r"^specs/tasks/([A-Z]+-[0-9]+)(?:-[^/]+)?\.md$")

# GZ-014 predates explicit governance ownership for several root documents.
# These are the audited repair surfaces recorded in its Task Spec and Registry;
# business implementation, business contracts and deployment remain excluded.
FOUNDATION_SCOPE_EXCEPTIONS: dict[str, tuple[str, ...]] = {
    "GZ-014": (
        "AGENTS.md",
        "README.md",
        "MANIFEST.md",
        "Makefile",
        ".github/**",
        "adr/0014-multi-agent-coordination-and-integration.md",
        "docs/24-requirements-design-readiness-audit.md",
        "docs/25-multi-agent-collaboration-protocol.md",
        "specs/coordination/**",
        "specs/requirements/requirements-index.yaml",
        "specs/designs/module-ownership.yaml",
        "specs/tasks/GZ-003.md",
        "specs/tasks/GZ-014.md",
        "specs/tasks/task-template.md",
        "scripts/**",
        "tests/governance/**",
    )
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Program lifecycle guards")
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


def read_ref(root: str, ref: str, path: str) -> str | None:
    result = git(root, "show", f"{ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def load_yaml_text(text: str | None) -> Any | None:
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def load_ref(root: str, ref: str, path: str) -> Any | None:
    return load_yaml_text(read_ref(root, ref, path))


def load_current(root: str, path: str) -> Any:
    with open(os.path.join(root, path), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def mapping(items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("taskId")): item
        for item in (items or [])
        if isinstance(item, dict) and item.get("taskId")
    }


def find_task_path(root: str, task_id: str, ref: str | None = None) -> str | None:
    exact = f"{TASK_DIR}/{task_id}.md"
    if ref:
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


def parse_front(text: str | None) -> dict[str, Any]:
    if not text or not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        value = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return value if isinstance(value, dict) else {}


def normalize_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return re.sub(r"/+", "/", text).rstrip("/")


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


def glob_regex(pattern: str) -> str:
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


def matches_path(path: str, pattern: str) -> bool:
    path = normalize_path(path)
    pattern = normalize_path(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if any(token in pattern for token in GLOB_CHARS):
        return re.fullmatch(glob_regex(pattern), path) is not None
    return path == pattern


def changed_paths(root: str, base_ref: str, head_ref: str) -> set[str] | None:
    """Return every changed path, including both sides of rename/copy records."""
    result = git(root, "diff", "--name-status", "-M", base_ref, head_ref)
    if result.returncode != 0:
        return None
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            paths.add(normalize_path(parts[1]))
            paths.add(normalize_path(parts[2]))
        elif len(parts) >= 2:
            paths.add(normalize_path(parts[-1]))
    return paths


def task_ids_from_diff(
    base_plan: dict[str, Any],
    current_plan: dict[str, Any],
    base_active: dict[str, Any],
    current_active: dict[str, Any],
    base_ledger: dict[str, Any],
    current_ledger: dict[str, Any],
    paths: set[str],
) -> set[str]:
    affected: set[str] = set()
    for section in ("foundationTasks", "tasks"):
        before = mapping(base_plan.get(section))
        after = mapping(current_plan.get(section))
        for task_id in set(before) | set(after):
            if before.get(task_id) != after.get(task_id):
                affected.add(task_id)
    before_active = mapping(base_active.get("tasks"))
    after_active = mapping(current_active.get("tasks"))
    for task_id in set(before_active) | set(after_active):
        if before_active.get(task_id) != after_active.get(task_id):
            affected.add(task_id)
    before_records = mapping(base_ledger.get("records"))
    after_records = mapping(current_ledger.get("records"))
    for task_id in set(before_records) | set(after_records):
        if before_records.get(task_id) != after_records.get(task_id):
            affected.add(task_id)
    for path in paths:
        match = TASK_PATH_RE.fullmatch(path)
        if match:
            affected.add(match.group(1))
    return affected


def allowed_metadata_paths(task_id: str, task_path: str, ordinary_completion: bool) -> tuple[set[str], tuple[str, ...]]:
    exact = {PLAN, ACTIVE, task_path}
    if ordinary_completion:
        exact.add(LEDGER)
    prefixes = (f"evidence/{task_id}",)
    return exact, prefixes


def path_allowed(path: str, exact: set[str], prefixes: tuple[str, ...], claims: list[str]) -> bool:
    if path in exact:
        return True
    if any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes):
        return True
    return any(matches_path(path, claim) for claim in claims)


def completion_record(ledger: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    records = [
        item
        for item in ledger.get("records") or []
        if isinstance(item, dict) and item.get("taskId") == task_id
    ]
    return records[0] if len(records) == 1 else None


def completion_merge_sha(
    task_id: str,
    current_plan: dict[str, Any],
    current_ledger: dict[str, Any],
) -> str | None:
    foundations = mapping(current_plan.get("foundationTasks"))
    if task_id in foundations:
        value = foundations[task_id].get("mergeCommit")
        return str(value) if value else None
    record = completion_record(current_ledger, task_id)
    value = record.get("mergeCommit") if record else None
    return str(value) if value else None


def validate_structured_completion_evidence(
    root: str,
    task_id: str,
    merge_sha: str,
    paths: set[str],
    errors: list[str],
) -> None:
    required = {
        f"evidence/{task_id}/summary.md",
        f"evidence/{task_id}/commands.txt",
        f"evidence/{task_id}/test-results/README.md",
        f"evidence/{task_id}/handoff.md",
    }
    missing = sorted(required - paths)
    if missing:
        errors.append(
            f"Completion task {task_id} must refresh structured Evidence files: {missing}"
        )
        return
    contents: dict[str, str] = {}
    for relative in required:
        full = os.path.join(root, relative)
        if not os.path.isfile(full):
            errors.append(f"Completion task {task_id} Evidence file is missing: {relative}")
            continue
        with open(full, "r", encoding="utf-8") as handle:
            contents[relative] = handle.read()
    for relative, content in contents.items():
        if task_id not in content or merge_sha not in content:
            errors.append(
                f"Completion Evidence {relative} must identify {task_id} and merge {merge_sha}"
            )
    commands = contents.get(f"evidence/{task_id}/commands.txt", "")
    if not re.search(r"(?mi)^command:\s*\S.+$", commands):
        errors.append(f"Completion task {task_id} commands.txt has no executed command")
    if not re.search(r"(?mi)^exit code:\s*0\s*$", commands):
        errors.append(f"Completion task {task_id} commands.txt has no successful exit code")
    if not re.search(r"(?mi)^result:\s*(PASS|SUCCESS)\b", commands):
        errors.append(f"Completion task {task_id} commands.txt has no explicit PASS result")
    tests = contents.get(f"evidence/{task_id}/test-results/README.md", "")
    if not re.search(r"(?mi)^(status|result):\s*(PASS|SUCCESS)\b", tests):
        errors.append(f"Completion task {task_id} test results have no explicit PASS status")
    for relative in (
        f"evidence/{task_id}/summary.md",
        f"evidence/{task_id}/handoff.md",
    ):
        if relative in contents and not re.search(
            r"(?mi)^(status|result):\s*(COMPLETED|PASS|SUCCESS)\b", contents[relative]
        ):
            errors.append(f"Completion Evidence {relative} has no explicit completed/pass status")


def validate_cancellation_evidence(
    root: str,
    task_id: str,
    before_status: str,
    paths: set[str],
    errors: list[str],
) -> None:
    relative = f"evidence/{task_id}/cancellation.md"
    if relative not in paths:
        errors.append(f"Cancellation task {task_id} must refresh {relative}")
        return
    full = os.path.join(root, relative)
    if not os.path.isfile(full):
        errors.append(f"Cancellation task {task_id} Evidence is missing: {relative}")
        return
    with open(full, "r", encoding="utf-8") as handle:
        content = handle.read()
    requirements = {
        "task": rf"(?mi)^Task:\s*{re.escape(task_id)}\s*$",
        "transition": rf"(?mi)^Transition:\s*{re.escape(before_status)}\s*->\s*cancelled\s*$",
        "reason": r"(?mi)^Reason:\s*\S.+$",
        "retained artifacts": r"(?mi)^Retained Artifacts:\s*\S.+$",
        "validation": r"(?mi)^Validation:\s*(PASS|FAIL|INCONCLUSIVE)\b",
    }
    for label, pattern in requirements.items():
        if not re.search(pattern, content):
            errors.append(
                f"Cancellation Evidence {relative} is missing structured {label} information"
            )


def module_owned_patterns(ownership: dict[str, Any], module_ids: set[str]) -> list[str]:
    patterns: list[str] = []
    for module in ownership.get("modules") or []:
        if isinstance(module, dict) and module.get("id") in module_ids:
            patterns.extend(str(item) for item in module.get("ownedPaths") or [])
    return patterns


def validate_foundation_claims(
    task_id: str,
    entry: dict[str, Any],
    ownership: dict[str, Any],
    resolved_base: str,
    errors: list[str],
) -> None:
    if str(entry.get("baseSha") or "") != resolved_base:
        errors.append(
            f"Active Foundation {task_id} baseSha must equal audited target base {resolved_base}"
        )
    module_patterns = module_owned_patterns(
        ownership, {str(item) for item in entry.get("moduleIds") or []}
    )
    exception_patterns = list(FOUNDATION_SCOPE_EXCEPTIONS.get(task_id, ()))
    for claim in list(entry.get("exclusivePaths") or []) + list(entry.get("sharedPaths") or []):
        if entry.get("moduleIds") == ["MOD-GOV"] and task_id not in FOUNDATION_SCOPE_EXCEPTIONS:
            if not governance_claim_subset(str(claim), ownership):
                errors.append(f"Active Foundation {task_id} path claim {claim} is outside governance ownership subsets")
            continue
        if not any(
            paths_overlap(str(claim), pattern)
            for pattern in module_patterns + exception_patterns
        ):
            errors.append(
                f"Active Foundation {task_id} path claim {claim} is outside module ownership and audited repair scope"
            )
    if entry.get("moduleIds") == ["MOD-GOV"] and task_id not in FOUNDATION_SCOPE_EXCEPTIONS and entry.get("sharedPaths"):
        errors.append(f"Active Foundation {task_id} requires exclusive governance claims")


def validate_completed_spec_binding(
    root: str,
    task_id: str,
    current_plan: dict[str, Any],
    errors: list[str],
) -> None:
    task_path = find_task_path(root, task_id)
    if not task_path:
        errors.append(f"Completed Program task {task_id} has no Task Spec")
        return
    with open(os.path.join(root, task_path), "r", encoding="utf-8") as handle:
        front = parse_front(handle.read())
    expected_evidence = f"evidence/{task_id}"
    expected_handoff = f"{expected_evidence}/handoff.md"
    if front.get("evidencePath") != expected_evidence:
        errors.append(
            f"Completed Program task {task_id} Task Spec evidencePath must be {expected_evidence}"
        )
    if front.get("handoffPath") != expected_handoff:
        errors.append(
            f"Completed Program task {task_id} Task Spec handoffPath must be {expected_handoff}"
        )


def metadata_paths(task_id: str, task_path: str) -> tuple[set[str], str]:
    return {PLAN, ACTIVE, task_path}, f"evidence/{task_id}/"


def safe_evidence_path(path: str, task_id: str) -> bool:
    return (
        isinstance(path, str)
        and path.startswith(f"evidence/{task_id}/")
        and "\\" not in path
        and all(part not in {"", ".", ".."} for part in path.split("/"))
    )


def unchanged_bytes(root: str, base_ref: str, paths: list[str], head_ref: str = "HEAD") -> bool:
    for path in paths:
        previous = subprocess.run(["git", "show", f"{base_ref}:{path}"], cwd=root, capture_output=True)
        proposed = subprocess.run(["git", "show", f"{head_ref}:{path}"], cwd=root, capture_output=True)
        try:
            current = Path(root, path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return False
        if previous.returncode or proposed.returncode or previous.stdout != proposed.stdout:
            return False
        if proposed.stdout.decode("utf-8").replace("\r\n", "\n") != current:
            return False
    return True


def evidence_task_ids(paths: set[str]) -> set[str]:
    return {
        match.group(1)
        for path in paths
        if (match := re.match(r"^evidence/([A-Z]+-[0-9]+)/", path))
    }


def completed_evidence_candidate(
    base_plan: dict[str, Any], current_plan: dict[str, Any], task_id: str
) -> bool:
    before = mapping(base_plan.get("tasks")).get(task_id, {})
    after = mapping(current_plan.get("tasks")).get(task_id, {})
    return before.get("status") == after.get("status") == "completed"


def github_issue(number: int) -> dict[str, Any]:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        raise RuntimeError("GITHUB_REPOSITORY is not available")
    base = os.environ.get("GUIZE_GITHUB_API_URL", "https://api.github.com").rstrip("/")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "guize-program-lifecycle-gate", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{base}/repos/{repository}/issues/{number}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            value = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"GitHub Issue API request failed: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("GitHub Issue API returned a non-object")
    return value


def validate_evidence_repair(
    root: str, base_ref: str, head_ref: str, task_id: str,
    branch_name: str, errors: list[str],
) -> None:
    initial_errors = len(errors)
    base_plan = load_ref(root, base_ref, PLAN)
    current_plan = load_current(root, PLAN)
    task_path = find_task_path(root, task_id)
    paths = changed_paths(root, base_ref, head_ref)
    if not task_path or paths is None or not paths:
        errors.append(f"Evidence repair {task_id} requires a Task and a non-empty exact diff")
        return
    if not completed_evidence_candidate(base_plan, current_plan, task_id):
        errors.append(f"Evidence repair {task_id} requires completed at both endpoints")
    if base_plan.get("status") == "frozen" or current_plan.get("status") == "frozen":
        errors.append(f"Evidence repair {task_id} cannot run while Program is frozen")
    if not unchanged_bytes(root, base_ref, [PLAN, ACTIVE, LEDGER, task_path], head_ref):
        errors.append(f"Evidence repair {task_id} must preserve Program/Registry/Ledger/Task bytes")
    if any(not safe_evidence_path(path, task_id) for path in paths):
        errors.append(f"Evidence repair {task_id} changed files outside its own Evidence")
    if branch_name and branch_name != "main" and not re.fullmatch(
        rf"(?:chore|fix|docs)/{re.escape(task_id)}-.+", branch_name
    ):
        errors.append(f"Evidence repair {task_id} branch must carry the same Task ID")
    ledger = load_current(root, LEDGER)
    if len([r for r in ledger.get("records") or [] if r.get("taskId") == task_id]) != 1:
        errors.append(f"Evidence repair {task_id} requires its immutable completion record")
    if len(errors) == initial_errors:
        front = parse_front(Path(root, task_path).read_text(encoding="utf-8"))
        number = front.get("issue")
        if type(number) is not int or number <= 0:
            errors.append(f"Evidence repair {task_id} has no numeric Issue identity")
            return
        try:
            issue = github_issue(number)
            if issue.get("number") != number or "pull_request" in issue or issue.get("state") != "closed" or issue.get("state_reason") != "completed":
                errors.append(f"Evidence repair {task_id} requires Issue #{number} closed with state_reason=completed")
        except RuntimeError as exc:
            errors.append(f"Evidence repair {task_id} Issue #{number} cannot be verified: {exc}")


def governance_claim_subset(claim: str, ownership: dict[str, Any]) -> bool:
    if "\\" in claim or any(p in {"", ".", ".."} for p in claim.split("/")):
        return False
    owned = module_owned_patterns(ownership, {"MOD-GOV"})
    return any(
        claim == path or (path.endswith("/**") and claim.startswith(path[:-2]))
        for path in owned
    )


def recovery_owner(plan: dict[str, Any]) -> str:
    recovery = plan.get("recovery")
    return str(recovery.get("taskId") or "") if isinstance(recovery, dict) else ""


def validate_frozen_snapshot(root: str, plan: dict[str, Any], errors: list[str]) -> None:
    if plan.get("status") != "frozen":
        return
    try:
        recovery = plan["recovery"]
        if not isinstance(recovery, dict) or set(recovery) != {"taskId", "reason", "affectedTasks", "sourceCommit", "frozenAt", "verificationPath"}:
            raise ValueError("Frozen Program has an invalid recovery descriptor")
        task_id = recovery_owner(plan)
        foundation = mapping(plan.get("foundationTasks"))[task_id]
        entry = mapping(load_current(root, ACTIVE).get("tasks"))[task_id]
        if foundation.get("status") not in {"reserved", "in_progress", "review", "integration", "blocked"} or foundation.get("status") != entry.get("status") or entry.get("moduleIds") != ["MOD-GOV"]:
            raise ValueError("Frozen Program must retain a matching active governance recovery owner")
        task_path = find_task_path(root, task_id)
        front = parse_front(Path(root, task_path).read_text(encoding="utf-8"))
        if front.get("id") != task_id or front.get("status") != entry.get("status") or front.get("issue") != entry.get("issue") or foundation.get("completionRef") != f"ISSUE-{entry.get('issue')}":
            raise ValueError("Frozen recovery owner Task/Issue identity does not match its lease")
        source = recovery["sourceCommit"]
        if not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{40}", source) or not is_ancestor(root, source, "HEAD"):
            raise ValueError("Frozen source must be an actual current ancestor")
        original = load_ref(root, source, PLAN)
        if not isinstance(original, dict) or original.get("status") != "active":
            raise ValueError("Frozen source must contain the preceding active Program")
        all_tasks = {**mapping(plan.get("tasks")), **mapping(plan.get("foundationTasks"))}
        prior = {**mapping(original.get("tasks")), **mapping(original.get("foundationTasks"))}
        affected = recovery["affectedTasks"]
        if not isinstance(affected, list) or not affected or any(not isinstance(t, str) for t in affected) or len(set(affected)) != len(affected) or any(all_tasks.get(t, {}).get("status") != "completed" or prior.get(t, {}).get("status") != "completed" for t in affected):
            raise ValueError("Frozen affected tasks must retain their completed source identities")
        if not isinstance(recovery["reason"], str) or len(recovery["reason"].strip()) < 12 or not safe_evidence_path(recovery["verificationPath"], task_id) or not recovery["verificationPath"].endswith(".json"):
            raise ValueError("Frozen reason and verification path are invalid")
        frozen_at = datetime.fromisoformat(recovery["frozenAt"].replace("Z", "+00:00"))
        acquired = datetime.fromisoformat(entry["lease"]["acquiredAt"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(entry["lease"]["expiresAt"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if frozen_at.tzinfo is None or frozen_at.utcoffset().total_seconds() != 0 or frozen_at > now or acquired.tzinfo is None or expires.tzinfo is None or not acquired <= now < expires or not 0 < (expires - acquired).total_seconds() <= 168 * 3600:
            raise ValueError("Frozen timestamp or recovery lease is invalid")
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        errors.append(f"Frozen Program snapshot rejected: {exc}")


def recovery_log(root: str, ref: str, path: str, task_id: str) -> bytes:
    if not safe_evidence_path(path, task_id):
        raise ValueError("Recovery evidence path escapes its task")
    tree = git(root, "ls-tree", ref, "--", path)
    if tree.returncode or not tree.stdout.startswith("100644 blob "):
        raise ValueError("Recovery evidence must be a tracked regular file")
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True)
    if result.returncode:
        raise ValueError("Recovery evidence cannot be read at the target base")
    return result.stdout


def validate_recovery_command(root: str, command: str, label: str, source: str, task_id: str, recovery: dict[str, Any]) -> None:
    tokens = shlex.split(command)
    executable = os.path.basename(tokens[0]) if tokens else ""
    checks = {
        "programIntegrity": "scripts/check-program-plan-integrity.py",
        "lifecycle": "scripts/run-program-lifecycle-gate.py",
        "coordination": "scripts/run-agent-coordination-gate.py",
    }
    if label == "verify":
        if tokens[:2] != ["make", "verify"] or len(tokens) != 6:
            raise ValueError("Recovery verify must run the complete make verify target")
        arguments = dict(token.split("=", 1) for token in tokens[2:])
        if set(arguments) != {"TASK", "BASE", "HEAD_REF", "BRANCH"} or arguments["TASK"] != task_id or arguments["HEAD_REF"] != source:
            raise ValueError("Recovery verify does not bind the owner and validated HEAD")
        base = arguments["BASE"]
        branch = arguments["BRANCH"]
    elif label == "governance":
        if executable not in {"python", "python3"} or tokens[1:5] != ["-m", "pytest", "tests/governance", "-q"] or len(tokens) != 6 or not tokens[5].startswith("--junitxml="):
            raise ValueError("Recovery governance must run the complete governance suite")
        if not safe_evidence_path(tokens[5].split("=", 1)[1], task_id):
            raise ValueError("Recovery JUnit output must belong to its task")
        return
    else:
        if executable not in {"python", "python3"} or len(tokens) < 4 or tokens[1] != checks[label]:
            raise ValueError(f"Recovery {label} has the wrong executable or script")
        expected = {"--base-ref"} if label == "programIntegrity" else {"--base-ref", "--head-ref", "--task", "--branch-name"}
        arguments = dict(zip(tokens[2::2], tokens[3::2]))
        if len(tokens) != 2 + 2 * len(expected) or set(arguments) != expected:
            raise ValueError(f"Recovery {label} has incomplete or unsupported arguments")
        if label != "programIntegrity" and (arguments["--head-ref"] != source or arguments["--task"] != task_id):
            raise ValueError(f"Recovery {label} does not bind the owner and validated HEAD")
        base = arguments["--base-ref"]
        branch = arguments.get("--branch-name", f"chore/{task_id}-recovery")
    if not re.fullmatch(r"[0-9a-f]{40}", base) or not is_ancestor(root, base, source):
        raise ValueError("Recovery command base must be an actual repair ancestor")
    plan = load_ref(root, base, PLAN)
    if not isinstance(plan, dict) or plan.get("status") != "frozen" or plan.get("recovery") != recovery:
        raise ValueError("Recovery command base does not belong to this frozen event")
    if not re.fullmatch(rf"(?:chore|fix|docs)/{re.escape(task_id)}-.+", branch):
        raise ValueError("Recovery command branch does not carry its owner Task ID")


def validate_thaw_proof(
    root: str, base_ref: str, recovery: dict[str, Any], errors: list[str]
) -> None:
    task_id = str(recovery.get("taskId") or "")
    try:
        proof = json.loads(recovery_log(root, base_ref, recovery.get("verificationPath"), task_id))
        if set(proof) != {"taskId", "frozenSourceCommit", "validatedCommit", "commands", "junitPath", "junitSha256"}:
            raise ValueError("Recovery proof has missing or unknown fields")
        source = proof["validatedCommit"]
        frozen_source = recovery["sourceCommit"]
        if proof["taskId"] != task_id or proof["frozenSourceCommit"] != frozen_source:
            raise ValueError("Recovery proof belongs to another task or freeze event")
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not is_ancestor(root, source, base_ref):
            raise ValueError("Validated repair commit has not merged into the target base")
        if source == frozen_source or not is_ancestor(root, frozen_source, source):
            raise ValueError("Validated repair commit must follow the frozen source")
        validated_plan = load_ref(root, source, PLAN)
        if not isinstance(validated_plan, dict) or validated_plan.get("status") != "frozen" or validated_plan.get("recovery") != recovery:
            raise ValueError("Validated commit does not contain this exact frozen event")
        archival = changed_paths(root, source, base_ref)
        if archival is None or any(not safe_evidence_path(p, task_id) for p in archival):
            raise ValueError("Code or control metadata changed after repair validation")
        commands = proof["commands"]
        required = {
            "programIntegrity": "check-program-plan-integrity.py",
            "lifecycle": "run-program-lifecycle-gate.py",
            "coordination": "run-agent-coordination-gate.py",
            "governance": "pytest",
            "verify": "make verify",
        }
        if set(commands) != set(required):
            raise ValueError("Recovery proof does not cover all mandatory checks")
        log_texts: dict[str, str] = {}
        for label, token in required.items():
            item = commands[label]
            if set(item) != {"command", "exitCode", "logPath", "sha256"} or type(item["exitCode"]) is not int or item["exitCode"] != 0:
                raise ValueError(f"Recovery check {label} is not a successful recorded command")
            if token not in item["command"]:
                raise ValueError(f"Recovery check {label} has the wrong command")
            validate_recovery_command(root, item["command"], label, source, task_id, recovery)
            raw = recovery_log(root, base_ref, item["logPath"], task_id)
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError(f"Recovery log {label} hash does not match")
            text = raw.decode("utf-8")
            log_texts[label] = text
            if not text.startswith(f"Source Commit: {source}\nCommand: {item['command']}\n") or not text.rstrip().endswith("Exit Code: 0"):
                raise ValueError(f"Recovery log {label} does not bind its command and exit code")
        raw = recovery_log(root, base_ref, proof["junitPath"], task_id)
        if hashlib.sha256(raw).hexdigest() != proof["junitSha256"]:
            raise ValueError("Recovery JUnit hash does not match")
        xml = ET.fromstring(raw)
        suites = [xml] if xml.tag == "testsuite" else list(xml.findall("testsuite"))
        if not suites or sum(int(s.get("tests", 0)) for s in suites) <= 0:
            raise ValueError("Recovery JUnit is empty")
        if any(int(s.get(k, 0)) != 0 for s in suites for k in ("failures", "errors", "skipped")):
            raise ValueError("Recovery JUnit contains failures, errors or skips")
        if any(int(s.get("tests", 0)) != len(s.findall("testcase")) for s in suites) or any(next(xml.iter(tag), None) is not None for tag in ("failure", "error", "skipped")):
            raise ValueError("Recovery JUnit testcase counts or failure nodes contradict its summary")
        junit_command = commands["governance"]["command"]
        if shlex.split(junit_command)[-1] != f"--junitxml={proof['junitPath']}":
            raise ValueError("Recovery governance command and archived JUnit path differ")
        expected_messages = {
            "programIntegrity": ["Program Plan execution and completion integrity passed"],
            "lifecycle": ["Program lifecycle scope, Foundation ownership, rename and Evidence guards passed", "Exact lifecycle diff and Completion Issue verification passed"],
            "coordination": ["Agent coordination valid:"],
        }
        for label, messages in expected_messages.items():
            results = []
            for line in log_texts[label].splitlines()[2:-1]:
                if line.startswith("{"):
                    results.append(json.loads(line))
            if any(result.get("status") == "FAIL" for result in results) or any(not any(result.get("status") == "PASS" and message in result.get("message", "") for result in results) for message in messages):
                raise ValueError(f"Recovery {label} log has no actual successful checker output")
        total = sum(len(s.findall("testcase")) for s in suites)
        for label in ("governance", "verify"):
            counts = re.findall(r"(?m)^.*?\b([0-9]+) passed(?: in |,)", log_texts[label])
            if not counts or int(counts[-1]) != total or re.search(r"\b[1-9][0-9]* (?:failed|errors?|skipped)\b", log_texts[label]):
                raise ValueError(f"Recovery {label} pytest output does not match its zero-skip JUnit")
        if any(marker not in log_texts["verify"] for marker in ("=== docs-check", "=== schema-check", "=== secret-scan", "=== task-verify", "=== governance-test")) or re.search(r'"status":\s*"FAIL"|^MISSING:', log_texts["verify"], re.MULTILINE):
            raise ValueError("Recovery verify log does not contain the successful complete target chain")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, ET.ParseError) as exc:
        errors.append(f"Program thaw proof rejected: {exc}")


def validate_recovery_transition(
    root: str, base_ref: str, head_ref: str, errors: list[str]
) -> str:
    before = load_ref(root, base_ref, PLAN)
    after = load_current(root, PLAN)
    if (before.get("status"), before.get("recovery")) == (after.get("status"), after.get("recovery")):
        return ""
    pair = (before.get("status"), after.get("status"))
    if pair not in {("active", "frozen"), ("frozen", "active")}:
        errors.append("Program recovery metadata may only change in freeze/thaw transitions")
        return ""
    recovery = after.get("recovery")
    if not isinstance(recovery, dict):
        errors.append("Program freeze/thaw requires structured recovery metadata")
        return ""
    task_id = recovery_owner(after)
    task_path = find_task_path(root, task_id)
    paths = changed_paths(root, base_ref, head_ref)
    entry = mapping(load_current(root, ACTIVE).get("tasks")).get(task_id, {})
    foundation = mapping(after.get("foundationTasks")).get(task_id, {})
    if not task_path or not entry or entry.get("moduleIds") != ["MOD-GOV"] or foundation.get("status") not in {"reserved", "in_progress", "review", "integration", "blocked"}:
        errors.append("Program freeze/thaw requires a registered governance Foundation owner")
        return task_id
    exact, prefix = metadata_paths(task_id, task_path)
    if paths is None or any(p not in exact and not safe_evidence_path(p, task_id) for p in paths):
        errors.append("Program freeze/thaw must be metadata-only for its recovery owner")
    left, right = copy.deepcopy(before), copy.deepcopy(after)
    for document in (left, right):
        document.pop("status", None)
        document.pop("recovery", None)
    # A first reserved Foundation may freeze atomically, without implementation.
    old_foundations = mapping(left.get("foundationTasks"))
    if task_id not in old_foundations and foundation.get("status") == "reserved":
        right["foundationTasks"] = [x for x in right["foundationTasks"] if x["taskId"] != task_id]
    if left != right:
        errors.append("Program freeze/thaw changed unrelated Program identities")
    base_active = load_ref(root, base_ref, ACTIVE)
    current_active = load_current(root, ACTIVE)
    for document in (base_active, current_active):
        document["tasks"] = [x for x in document.get("tasks") or [] if x.get("taskId") != task_id]
    if base_active != current_active or not unchanged_bytes(root, base_ref, [LEDGER]):
        errors.append("Program freeze/thaw changed another lease, policy or Ledger")
    try:
        if set(recovery) != {"taskId", "reason", "affectedTasks", "sourceCommit", "frozenAt", "verificationPath"}:
            raise ValueError("Unexpected recovery fields")
        if not isinstance(recovery["reason"], str) or len(recovery["reason"].strip()) < 12:
            raise ValueError("Recovery reason must explain the incident")
        if not safe_evidence_path(recovery["verificationPath"], task_id) or not recovery["verificationPath"].endswith(".json"):
            raise ValueError("Recovery verificationPath must be task-bound JSON")
        timestamp = datetime.fromisoformat(recovery["frozenAt"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0 or timestamp > datetime.now(timezone.utc):
            raise ValueError("Recovery frozenAt must be an actual UTC timestamp")
        affected = recovery["affectedTasks"]
        all_tasks = {**mapping(before.get("tasks")), **mapping(before.get("foundationTasks"))}
        if not isinstance(affected, list) or not affected or len(set(affected)) != len(affected) or any(all_tasks.get(t, {}).get("status") != "completed" for t in affected):
            raise ValueError("Recovery affectedTasks must identify existing completed tasks")
        if pair == ("active", "frozen"):
            if recovery["sourceCommit"] != resolve_ref(root, base_ref):
                raise ValueError("Freeze sourceCommit must equal the actual target base")
        else:
            if recovery != before.get("recovery"):
                raise ValueError("Thaw must preserve the exact freeze event")
            validate_thaw_proof(root, base_ref, recovery, errors)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f"Program recovery metadata rejected: {exc}")
    return task_id


def validate_frozen_changes(root: str, base_ref: str, head_ref: str, errors: list[str]) -> None:
    before, after = load_ref(root, base_ref, PLAN), load_current(root, PLAN)
    if before.get("status") != "frozen" and after.get("status") != "frozen":
        return
    validate_frozen_snapshot(root, after, errors)
    paths = changed_paths(root, base_ref, head_ref)
    if paths is None:
        errors.append("Frozen Program cannot determine exact changes")
        return
    if before.get("status") != after.get("status"):
        # The recovery-transition validator enforces the narrower metadata diff.
        validate_recovery_transition(root, base_ref, head_ref, errors)
        return
    if {k: v for k, v in before.items() if k not in {"tasks", "foundationTasks", "pocs"}} != {k: v for k, v in after.items() if k not in {"tasks", "foundationTasks", "pocs"}}:
        errors.append("Frozen Program cannot change root authority, policy or recovery metadata")
    previous_tasks, current_tasks = mapping(before.get("tasks")), mapping(after.get("tasks"))
    if set(previous_tasks) != set(current_tasks):
        errors.append("Frozen Program cannot add or remove ordinary tasks")
    old_pocs, new_pocs = copy.deepcopy(before.get("pocs") or []), copy.deepcopy(after.get("pocs") or [])
    for pocs in (old_pocs, new_pocs):
        for poc in pocs:
            task_id = poc.get("taskId")
            if previous_tasks.get(task_id) != current_tasks.get(task_id) and current_tasks.get(task_id, {}).get("status") in {"blocked", "cancelled"}:
                poc.pop("status", None)
    if old_pocs != new_pocs:
        errors.append("Frozen Program cannot change unrelated POC identities or results")
    old_active, new_active = load_ref(root, base_ref, ACTIVE), load_current(root, ACTIVE)
    if {k: v for k, v in old_active.items() if k != "tasks"} != {k: v for k, v in new_active.items() if k != "tasks"}:
        errors.append("Frozen Program cannot change Registry policy")
    entries = mapping(load_current(root, ACTIVE).get("tasks"))
    foundations = mapping(after.get("foundationTasks"))
    ordinary = mapping(after.get("tasks"))
    owner = recovery_owner(after)
    if after.get("status") == "frozen" and (
        owner not in entries or owner not in foundations or entries[owner].get("moduleIds") != ["MOD-GOV"]
    ):
        errors.append("Frozen Program must retain its active governance recovery owner")
    allowed_exact: set[str] = set()
    allowed_patterns: list[str] = []
    for task_id, entry in entries.items():
        path = find_task_path(root, task_id)
        if not path:
            continue
        if task_id in foundations and entry.get("moduleIds") == ["MOD-GOV"]:
            ownership = load_current(root, OWNERSHIP)
            if entry.get("sharedPaths") or any(not governance_claim_subset(str(p), ownership) for p in entry.get("exclusivePaths") or []):
                errors.append(f"Frozen recovery Foundation {task_id} claims must be governance subsets")
                continue
            allowed_exact.update({PLAN, ACTIVE, path})
            allowed_patterns.append(f"evidence/{task_id}/**")
            if entry.get("status") in IMPLEMENTATION_STATES:
                allowed_patterns.extend(entry.get("exclusivePaths") or [])
        elif ordinary.get(task_id, {}).get("status") == "blocked":
            allowed_exact.update({PLAN, ACTIVE, path})
            allowed_patterns.append(f"evidence/{task_id}/**")
    for task_id, task in ordinary.items():
        if task.get("status") == "cancelled":
            path = find_task_path(root, task_id)
            if path:
                allowed_exact.update({PLAN, ACTIVE, path})
                allowed_patterns.append(f"evidence/{task_id}/**")
    if any(p not in allowed_exact and not any(fnmatch.fnmatchcase(p, pattern) for pattern in allowed_patterns) for p in paths):
        errors.append("Frozen Program rejects ordinary implementation, completion and Evidence repair")
    previous = mapping(before.get("tasks"))
    for task_id, task in ordinary.items():
        if task != previous.get(task_id) and task.get("status") not in {"blocked", "cancelled"}:
            errors.append(f"Frozen Program rejects ordinary task activation or completion: {task_id}")
        elif task != previous.get(task_id) and {
            k: v for k, v in task.items() if k != "status"
        } != {k: v for k, v in previous.get(task_id, {}).items() if k != "status"}:
            errors.append(f"Frozen Program cannot change ordinary task identity or scope: {task_id}")
        if task != previous.get(task_id) and task.get("status") in {"blocked", "cancelled"}:
            path = find_task_path(root, task_id)
            front = parse_front(Path(root, path).read_text(encoding="utf-8")) if path else {}
            if front.get("status") != task.get("status"):
                errors.append(f"Frozen ordinary task {task_id} Task Spec must match blocked/cancelled status")


def frozen_repair_task_ids(root: str, base_ref: str, head_ref: str) -> set[str]:
    plan = load_current(root, PLAN)
    if plan.get("status") != "frozen":
        return set()
    paths = (changed_paths(root, base_ref, head_ref) or set()) - {PLAN, ACTIVE, LEDGER}
    foundations = mapping(plan.get("foundationTasks"))
    result: set[str] = set()
    for entry in load_current(root, ACTIVE).get("tasks") or []:
        task_id = entry.get("taskId")
        if task_id not in foundations or entry.get("moduleIds") != ["MOD-GOV"]:
            continue
        task_path = find_task_path(root, task_id)
        if any(path == task_path or safe_evidence_path(path, task_id) or any(matches_path(path, str(claim)) for claim in entry.get("exclusivePaths") or []) for path in paths):
            result.add(task_id)
    return result


def is_ancestor(root: str, before: str, after: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", before, after).returncode == 0


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []
    if not ref_exists(root, args.base_ref) or not ref_exists(root, args.head_ref):
        emit("FAIL", "Lifecycle guard refs are missing")
        return 1
    resolved_base = resolve_ref(root, args.base_ref)
    if not resolved_base:
        emit("FAIL", "Lifecycle guard target base cannot be resolved")
        return 1
    try:
        base_plan = load_ref(root, args.base_ref, PLAN)
        current_plan = load_current(root, PLAN)
        base_active = load_ref(root, args.base_ref, ACTIVE)
        current_active = load_current(root, ACTIVE)
        base_ledger = load_ref(root, args.base_ref, LEDGER)
        current_ledger = load_current(root, LEDGER)
        ownership = load_current(root, OWNERSHIP)
    except Exception as exc:
        emit("FAIL", f"Cannot load lifecycle guard documents: {exc}")
        return 1
    if base_ledger is None and isinstance(current_ledger, dict) and not (current_ledger.get("records") or []):
        base_ledger = {"records": []}
    if not all(
        isinstance(item, dict)
        for item in (
            base_plan,
            current_plan,
            base_active,
            current_active,
            base_ledger,
            current_ledger,
            ownership,
        )
    ):
        emit("FAIL", "Lifecycle guard documents are missing or invalid")
        return 1
    paths = changed_paths(root, args.base_ref, args.head_ref)
    if paths is None:
        emit("FAIL", "Lifecycle guard cannot determine changed paths")
        return 1
    validate_frozen_changes(root, args.base_ref, args.head_ref, errors)
    recovery_task = validate_recovery_transition(root, args.base_ref, args.head_ref, errors)
    affected = task_ids_from_diff(
        base_plan,
        current_plan,
        base_active,
        current_active,
        base_ledger,
        current_ledger,
        paths,
    )
    if args.task:
        affected.add(args.task)
    affected.update(evidence_task_ids(paths))
    affected.update(frozen_repair_task_ids(root, args.base_ref, args.head_ref))
    if recovery_task:
        affected.add(recovery_task)

    base_tasks = mapping(base_plan.get("tasks"))
    current_tasks = mapping(current_plan.get("tasks"))
    base_foundations = mapping(base_plan.get("foundationTasks"))
    current_foundations = mapping(current_plan.get("foundationTasks"))
    base_entries = mapping(base_active.get("tasks"))
    current_entries = mapping(current_active.get("tasks"))

    for task_id, task in current_tasks.items():
        if task.get("status") == "completed":
            validate_completed_spec_binding(root, task_id, current_plan, errors)

    for task_id in sorted(affected):
        ordinary = task_id in current_tasks or task_id in base_tasks
        foundation = task_id in current_foundations or task_id in base_foundations
        before = (base_tasks if ordinary else base_foundations).get(task_id, {})
        after = (current_tasks if ordinary else current_foundations).get(task_id, {})
        before_status = str(before.get("status") or "")
        after_status = str(after.get("status") or "")
        if ordinary and before_status == after_status == "completed":
            validate_evidence_repair(
                root, args.base_ref, args.head_ref, task_id, args.branch_name, errors
            )
        task_path = find_task_path(root, task_id)
        if not task_path:
            errors.append(f"Affected lifecycle task {task_id} has no current Task Spec")
            continue
        entry = current_entries.get(task_id)
        claims: list[str] = []
        if entry:
            claims = [
                str(item)
                for item in list(entry.get("exclusivePaths") or [])
                + list(entry.get("sharedPaths") or [])
            ]
        ordinary_completion = ordinary and after_status == "completed"
        exact, prefixes = allowed_metadata_paths(task_id, task_path, ordinary_completion)
        metadata_mode = after_status in METADATA_STATES
        if metadata_mode:
            invalid = sorted(
                path
                for path in paths
                if not path_allowed(path, exact, prefixes, [])
            )
        else:
            invalid = sorted(
                path
                for path in paths
                if not path_allowed(path, exact, prefixes, claims)
            )
        if invalid:
            errors.append(
                f"Lifecycle task {task_id} changed files outside its {'metadata' if metadata_mode else 'registered'} scope: {invalid}"
            )

        if foundation and entry and after_status in IMPLEMENTATION_STATES | {"reserved", "blocked"}:
            validate_foundation_claims(task_id, entry, ownership, resolved_base, errors)

        if after_status == "cancelled" and before_status != "cancelled":
            validate_cancellation_evidence(root, task_id, before_status, paths, errors)

        if after_status == "completed" and before_status != "completed":
            if before_status not in COMPLETION_BASE_STATES:
                errors.append(
                    f"Lifecycle task {task_id} cannot complete directly from {before_status}; target base must be review or integration"
                )
            merge_sha = completion_merge_sha(task_id, current_plan, current_ledger)
            if not merge_sha:
                errors.append(f"Lifecycle task {task_id} has no unique implementation merge SHA")
            else:
                validate_structured_completion_evidence(
                    root, task_id, merge_sha, paths, errors
                )

    if errors:
        for error in errors:
            emit("FAIL", error)
        return 1
    emit(
        "PASS",
        "Program lifecycle scope, Foundation ownership, rename and Evidence guards passed",
        {
            "affectedTaskIds": sorted(affected),
            "changedPathCount": len(paths),
            "baseRef": args.base_ref,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate Guize Program Plan execution and completion integrity.

This checker complements structural JSON Schema validation. It enforces the
cross-file and Git-history invariants that make the Program Plan, Active Work
Registry, Task Specs, module ownership, completion ledger, external blockers
and final release one fail-closed coordination control plane.
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
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help=(
            "Integration base used for append-only and activation-order checks; "
            "pass an empty string only in isolated fixtures."
        ),
    )
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


def parse_front_matter(path: str) -> dict[str, Any]:
    """Parse delimited Task front matter with the same YAML semantics as Tasks."""
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
    try:
        document = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return document if isinstance(document, dict) else {}


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
        check=False,
    )


def git_ref_exists(root: str, ref: str) -> bool:
    if not ref:
        return False
    return git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").returncode == 0


def load_yaml_from_ref(root: str, ref: str, relative: str) -> Any | None:
    if not ref or not git_ref_exists(root, ref):
        return None
    result = git(root, "show", f"{ref}:{relative}")
    if result.returncode != 0:
        return None
    try:
        return yaml.safe_load(result.stdout)
    except yaml.YAMLError:
        return None


def exact_identifier(message: str, value: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(value)}(?![A-Z0-9])", message) is not None


def exact_pr_token(message: str, number: str) -> bool:
    return re.search(rf"(?<!\d)#{re.escape(number)}(?!\d)", message) is not None


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
    if not exact_identifier(message, task_id):
        errors.append(f"{label} commit {sha} message does not identify {task_id}")
    match = PR_REF_RE.fullmatch(str(completion_ref or ""))
    if not match:
        errors.append(f"{label} completionRef must use PR-<number>: {completion_ref!r}")
    elif not exact_pr_token(message, match.group(1)):
        errors.append(f"{label} commit {sha} message does not identify {completion_ref}")
    return errors


def is_ancestor(root: str, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def dependency_closure(task_id: str, tasks: dict[str, dict[str, Any]]) -> set[str]:
    closure: set[str] = set()
    stack = list(tasks.get(task_id, {}).get("dependsOn") or [])
    while stack:
        dependency = stack.pop()
        if dependency in closure:
            continue
        closure.add(dependency)
        if dependency in tasks:
            stack.extend(tasks[dependency].get("dependsOn") or [])
    return closure


def completion_records(ledger: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in (ledger or {}).get("records") or []:
        task_id = record.get("taskId")
        if task_id not in result:
            result[task_id] = record
    return result


def completion_merge_sha(
    task_id: str,
    foundation_tasks: dict[str, dict[str, Any]],
    plan_tasks: dict[str, dict[str, Any]],
    ledger_records: dict[str, dict[str, Any]],
) -> str | None:
    if task_id in foundation_tasks:
        value = foundation_tasks[task_id].get("mergeCommit")
        return str(value) if value else None
    if task_id in plan_tasks:
        record = ledger_records.get(task_id)
        value = record.get("mergeCommit") if record else None
        return str(value) if value else None
    return None


def validate_completion_ledger(
    root: str,
    plan_tasks: dict[str, dict[str, Any]],
    ledger: dict[str, Any],
    errors: list[str],
    base_plan_tasks: dict[str, dict[str, Any]] | None = None,
    base_ledger: dict[str, Any] | None = None,
) -> None:
    records = ledger.get("records") or []
    by_task: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = record.get("taskId")
        if task_id in by_task:
            errors.append(f"Completion ledger has duplicate record for {task_id}")
        by_task[task_id] = record

    previous = completion_records(base_ledger)
    for task_id, prior_record in previous.items():
        current_record = by_task.get(task_id)
        if current_record is None:
            errors.append(f"Completion ledger record for {task_id} is append-only and may not be removed")
        elif current_record != prior_record:
            errors.append(f"Completion ledger record for {task_id} is immutable and may not be modified")

    for task_id, prior_task in (base_plan_tasks or {}).items():
        if prior_task.get("status") == "completed":
            current_task = plan_tasks.get(task_id)
            if not current_task or current_task.get("status") != "completed":
                errors.append(f"Completed Program task {task_id} may not regress from completed")

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

        expected_spec = find_task_spec(root, task_id)
        expected_spec_relative = (
            os.path.relpath(expected_spec, root).replace("\\", "/") if expected_spec else None
        )
        expected_evidence = f"evidence/{task_id}"
        expected_handoff = f"{expected_evidence}/handoff.md"
        task_spec = str(record.get("taskSpec") or "")
        evidence_path = str(record.get("evidencePath") or "")
        handoff_path = str(record.get("handoffPath") or "")

        if expected_spec_relative is None:
            errors.append(f"Completed Program task {task_id} has no unique Task Spec")
        elif task_spec != expected_spec_relative:
            errors.append(
                f"Completed Program task {task_id} taskSpec must be {expected_spec_relative}, got {task_spec}"
            )
        if evidence_path != expected_evidence:
            errors.append(
                f"Completed Program task {task_id} evidencePath must be {expected_evidence}, got {evidence_path}"
            )
        if handoff_path != expected_handoff:
            errors.append(
                f"Completed Program task {task_id} handoffPath must be {expected_handoff}, got {handoff_path}"
            )

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
            if str(front.get("exitGate") or "") != str(task.get("exitGate") or ""):
                errors.append(
                    f"Completed Program task {task_id} Task Spec exitGate does not match Program Plan"
                )
        if not os.path.isdir(evidence_full):
            errors.append(f"Completed Program task {task_id} Evidence path does not exist: {evidence_path}")
        if not os.path.isfile(handoff_full):
            errors.append(f"Completed Program task {task_id} handoff does not exist: {handoff_path}")

        reservation_ref = str(record.get("reservationRef") or "")
        completion_ref = str(record.get("completionRef") or "")
        reservation_sha = str(record.get("reservationCommit") or "")
        merge_sha = str(record.get("mergeCommit") or "")
        if reservation_ref == completion_ref:
            errors.append(f"Completion record {task_id} reservationRef and completionRef must differ")
        if reservation_sha == merge_sha:
            errors.append(f"Completion record {task_id} reservationCommit and mergeCommit must differ")
        errors.extend(
            commit_identity_errors(
                root,
                reservation_sha,
                task_id,
                reservation_ref,
                f"Completion record {task_id} reservation",
            )
        )
        errors.extend(
            commit_identity_errors(
                root,
                merge_sha,
                task_id,
                completion_ref,
                f"Completion record {task_id} merge",
            )
        )
        if (
            re.fullmatch(r"[0-9a-f]{40}", reservation_sha)
            and re.fullmatch(r"[0-9a-f]{40}", merge_sha)
            and (
                reservation_sha == merge_sha
                or not is_ancestor(root, reservation_sha, merge_sha)
            )
        ):
            errors.append(
                f"Completion record {task_id} reservationCommit must be a strict ancestor of mergeCommit"
            )

    unknown = sorted(set(by_task) - set(plan_tasks))
    if unknown:
        errors.append("Completion ledger references unknown Program tasks: " + ", ".join(unknown))


def github_json(path: str) -> Any:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repository:
        raise RuntimeError("GITHUB_REPOSITORY is not available")
    base = os.environ.get("GUIZE_GITHUB_API_URL", "https://api.github.com").rstrip("/")
    url = f"{base}/repos/{repository}/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "guize-program-plan-integrity",
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


def ruleset_applies_to_main(ruleset: dict[str, Any]) -> bool:
    if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
        return False
    include = (((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or [])
    return "~DEFAULT_BRANCH" in include or "refs/heads/main" in include


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
    contexts: set[str] = set()
    if status_rule:
        contexts = {
            str(item.get("context") or "")
            for item in (status_rule.get("parameters") or {}).get("required_status_checks") or []
        }
    if "Governance Checks" not in contexts and "Governance Gate / Governance Checks" not in contexts:
        failures.append("Governance Checks is not a required status check")
    if "deletion" not in rules:
        failures.append("branch deletion is not blocked")
    if "non_fast_forward" not in rules:
        failures.append("force push/non-fast-forward updates are not blocked")
    return not failures, failures


def verify_branch_protection(blocker: dict[str, Any], errors: list[str]) -> None:
    blocker_id = blocker.get("id")
    issue_number = blocker.get("issue")
    try:
        issue = github_json(f"issues/{issue_number}")
        if issue.get("state") != "closed":
            errors.append(f"External blocker {blocker_id} issue #{issue_number} is not closed")
        branch = github_json("branches/main")
        if branch.get("protected") is not True:
            errors.append(f"External blocker {blocker_id} cannot be resolved: main.protected is not true")
        summaries = github_json("rulesets")
        candidates: list[dict[str, Any]] = []
        for summary in summaries if isinstance(summaries, list) else []:
            ruleset_id = summary.get("id")
            if ruleset_id is None:
                continue
            detail = github_json(f"rulesets/{ruleset_id}")
            if ruleset_applies_to_main(detail):
                candidates.append(detail)
        accepted = False
        reasons: list[str] = []
        for candidate in candidates:
            valid, failures = ruleset_satisfies_policy(candidate)
            if valid:
                accepted = True
                break
            reasons.extend(failures)
        if not accepted:
            detail = "; ".join(sorted(set(reasons))) or "no active ruleset applies to main"
            errors.append(
                f"External blocker {blocker_id} lacks an API-confirmed protected Ruleset: {detail}"
            )
    except RuntimeError as exc:
        errors.append(f"External blocker {blocker_id} resolution cannot be verified: {exc}")


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

    if args.base_ref and not git_ref_exists(root, args.base_ref):
        emit("FAIL", f"Program Plan base ref does not exist: {args.base_ref}")
        return 1

    base_plan = load_yaml_from_ref(root, args.base_ref, args.plan) if args.base_ref else None
    base_completions = (
        load_yaml_from_ref(root, args.base_ref, args.completions) if args.base_ref else None
    )

    if plan.get("sourceOfTruth") != CANONICAL_PLAN:
        errors.append(f"Program Plan sourceOfTruth must be {CANONICAL_PLAN}")
    authority = plan.get("authority") or {}
    for key, canonical in CANONICAL_AUTHORITY.items():
        if authority.get(key) != canonical:
            errors.append(
                f"Program Plan authority.{key} must be {canonical}, got {authority.get(key)!r}"
            )

    foundation_tasks = {item.get("taskId"): item for item in (plan.get("foundationTasks") or [])}
    plan_tasks = {item.get("taskId"): item for item in (plan.get("tasks") or [])}
    active_tasks = {item.get("taskId"): item for item in (active_work.get("tasks") or [])}
    all_tasks = {**foundation_tasks, **plan_tasks}

    base_foundations = {
        item.get("taskId"): item for item in (base_plan or {}).get("foundationTasks") or []
    }
    base_plan_tasks = {item.get("taskId"): item for item in (base_plan or {}).get("tasks") or []}
    base_all_tasks = {**base_foundations, **base_plan_tasks}
    base_ledger_records = completion_records(base_completions)

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
            if args.base_ref:
                base_dependency = base_all_tasks.get(dependency)
                if not base_dependency or base_dependency.get("status") != "completed":
                    errors.append(
                        f"Program task {task_id} cannot activate in the same change that completes "
                        f"dependency {dependency}; it was not completed in {args.base_ref}"
                    )

    for task_id, registry in active_tasks.items():
        for dependency in registry.get("dependsOn") or []:
            dependency_task = all_tasks.get(dependency)
            if not dependency_task or dependency_task.get("status") != "completed":
                errors.append(f"Active task {task_id} has incomplete dependency {dependency}")
                continue
            if args.base_ref:
                base_dependency = base_all_tasks.get(dependency)
                if not base_dependency or base_dependency.get("status") != "completed":
                    errors.append(
                        f"Active task {task_id} dependency {dependency} was not completed in {args.base_ref}"
                    )
                    continue
                dependency_merge = completion_merge_sha(
                    dependency,
                    base_foundations,
                    base_plan_tasks,
                    base_ledger_records,
                )
                base_sha = str(registry.get("baseSha") or "")
                if not dependency_merge:
                    errors.append(
                        f"Active task {task_id} dependency {dependency} has no verified completion merge identity"
                    )
                elif not re.fullmatch(r"[0-9a-f]{40}", base_sha):
                    errors.append(f"Active task {task_id} has invalid baseSha {base_sha!r}")
                elif not is_ancestor(root, dependency_merge, base_sha):
                    errors.append(
                        f"Active task {task_id} dependency {dependency} merge {dependency_merge} "
                        f"is not an ancestor of reservation baseSha {base_sha}"
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
                elif str(exit_gate) != str(planned.get("exitGate") or ""):
                    errors.append(
                        f"Active Program task {task_id} Task Spec exitGate does not match Program Plan"
                    )

    blockers = plan.get("externalBlockers") or []
    for blocker in blockers:
        blocker_id = blocker.get("id")
        if blocker.get("status") == "resolved":
            if blocker_id == "BRANCH-PROTECTION":
                verify_branch_protection(blocker, errors)
            else:
                errors.append(
                    f"External blocker {blocker_id} is resolved but has no supported live verification provider"
                )
            continue
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
    wave_order = {item.get("id"): item.get("order") for item in (plan.get("waves") or [])}
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
        closure = dependency_closure(final_task_id, plan_tasks)
        missing_predecessors = sorted(set(plan_tasks) - {final_task_id} - closure)
        if missing_predecessors:
            errors.append(
                "Final release task GZ-020 does not transitively depend on all Program tasks: "
                + ", ".join(missing_predecessors)
            )

    validate_completion_ledger(
        root,
        plan_tasks,
        completions,
        errors,
        base_plan_tasks=base_plan_tasks if base_plan else None,
        base_ledger=base_completions,
    )

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
            "baseRef": args.base_ref or None,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

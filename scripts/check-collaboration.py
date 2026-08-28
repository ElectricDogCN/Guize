#!/usr/bin/env python3
"""Validate Guize multi-agent task coordination and handoff contracts."""

from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import jsonschema
import yaml


ACTIVE_RESERVATION_STATUSES = {"planned", "active", "blocked"}
REQUIRED_HANDOFF_SECTIONS = (
    "baseline",
    "delivered outputs",
    "validation",
    "integration notes",
    "known gaps",
    "rollback",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate multi-agent coordination metadata and changed-path ownership."
    )
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-003")
    parser.add_argument(
        "--base", required=True, help="Base ref used to determine changed files, e.g. origin/main"
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument(
        "--skip-diff",
        action="store_true",
        help="Skip changed-file ownership validation; intended only for focused unit tests.",
    )
    return parser.parse_args()


def report(status: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def run_git(repo_root: Path, args: Sequence[str]) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except OSError as exc:
        return -1, "", str(exc)


def find_task_file(repo_root: Path, task_id: str) -> Optional[Path]:
    task_dir = repo_root / "specs" / "tasks"
    preferred = [
        task_dir / f"{task_id}.md",
        task_dir / f"{task_id}-repository-baseline.md",
    ]
    for candidate in preferred:
        if candidate.is_file():
            return candidate
    matches = sorted(task_dir.glob(f"{task_id}-*.md"))
    return matches[0] if matches else None


def parse_front_matter(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    parsed = yaml.safe_load(parts[1])
    return parsed if isinstance(parsed, dict) else {}


def as_task_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return data


def validate_schema(descriptor: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    try:
        validator_class = jsonschema.validators.validator_for(schema)
        validator_class.check_schema(schema)
        validator = validator_class(schema)
        for error in sorted(validator.iter_errors(descriptor), key=lambda item: list(item.path)):
            location = ".".join(str(item) for item in error.path) or "<root>"
            errors.append(f"Descriptor schema violation at {location}: {error.message}")
    except Exception as exc:  # schema errors must fail closed
        errors.append(f"Cannot validate coordination schema: {exc}")
    return errors


def normalize_repo_path(value: str) -> str:
    return value.replace("\\", "/").strip().lstrip("./").rstrip("/")


def pattern_matches(path: str, pattern: str) -> bool:
    path = normalize_repo_path(path)
    pattern = normalize_repo_path(pattern)
    if not pattern:
        return False
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if any(token in pattern for token in ("*", "?", "[")):
        return fnmatch.fnmatchcase(path, pattern)
    if Path(pattern).suffix:
        return path == pattern
    return path == pattern or path.startswith(pattern + "/")


def static_prefix(pattern: str) -> str:
    normalized = normalize_repo_path(pattern)
    indices = [
        index
        for token in ("*", "?", "[")
        if (index := normalized.find(token)) >= 0
    ]
    if indices:
        normalized = normalized[: min(indices)]
    return normalized.rstrip("/")


def patterns_may_overlap(left: str, right: str) -> bool:
    left_normalized = normalize_repo_path(left)
    right_normalized = normalize_repo_path(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    left_prefix = static_prefix(left_normalized)
    right_prefix = static_prefix(right_normalized)
    if not left_prefix or not right_prefix:
        return True
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
    )


def get_changed_files(repo_root: Path, base: str) -> Optional[List[str]]:
    rc, _, _ = run_git(repo_root, ["rev-parse", "--verify", f"{base}^{{commit}}"])
    if rc != 0:
        return None
    rc, stdout, _ = run_git(repo_root, ["diff", "--name-only", f"{base}...HEAD"])
    if rc != 0:
        return None
    return [normalize_repo_path(line) for line in stdout.splitlines() if line.strip()]


def path_exists_or_glob(repo_root: Path, value: str) -> bool:
    normalized = normalize_repo_path(value)
    if any(token in normalized for token in ("*", "?", "[")):
        return bool(glob.glob(str(repo_root / normalized), recursive=True))
    return (repo_root / normalized).exists()


def validate_handoff(path: Path) -> List[str]:
    if not path.is_file():
        return [f"Handoff file does not exist: {path}"]
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return [f"Handoff file is empty: {path}"]
    headings = {
        re.sub(r"^#+\s*", "", line.strip()).strip().lower()
        for line in text.splitlines()
        if line.strip().startswith("#")
    }
    errors = []
    for required in REQUIRED_HANDOFF_SECTIONS:
        if not any(required in heading for heading in headings):
            errors.append(f"Handoff missing section: {required}")
    return errors


def descriptor_paths(descriptor: Dict[str, Any], key: str) -> List[str]:
    paths = descriptor.get("paths", {})
    if not isinstance(paths, dict):
        return []
    values = paths.get(key, [])
    return [str(value) for value in values] if isinstance(values, list) else []


def validate_descriptor_overlap(
    repo_root: Path, task_id: str, current: Dict[str, Any]
) -> List[str]:
    errors: List[str] = []
    current_exclusive = descriptor_paths(current, "exclusive")
    current_shared = descriptor_paths(current, "shared")
    descriptor_dir = repo_root / "specs" / "collaboration" / "tasks"

    for path in sorted(descriptor_dir.glob("*.yaml")):
        try:
            other = load_yaml(path)
        except Exception as exc:
            errors.append(f"Cannot load coordination descriptor {path}: {exc}")
            continue
        other_task = str(other.get("taskId", ""))
        if not other_task or other_task == task_id:
            continue
        if str(other.get("status", "")) not in ACTIVE_RESERVATION_STATUSES:
            continue
        other_exclusive = descriptor_paths(other, "exclusive")
        other_shared = descriptor_paths(other, "shared")

        for left in current_exclusive:
            for right in [*other_exclusive, *other_shared]:
                if patterns_may_overlap(left, right):
                    errors.append(
                        f"Exclusive path conflict with {other_task}: '{left}' overlaps '{right}'"
                    )
        for left in current_shared:
            for right in other_exclusive:
                if patterns_may_overlap(left, right):
                    errors.append(
                        f"Shared path conflicts with {other_task} exclusive path: "
                        f"'{left}' overlaps '{right}'"
                    )
    return errors


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_id = args.task.strip()
    base = args.base.strip()
    errors: List[str] = []
    info: Dict[str, Any] = {"task": task_id, "base": base}

    if not re.fullmatch(r"[A-Z]+-[0-9]+", task_id):
        report("ERROR", f"Invalid task ID: {task_id}")
        return 2
    if not (repo_root / ".git").exists():
        report("ERROR", f"Repository root is not a Git worktree: {repo_root}")
        return 2

    task_file = find_task_file(repo_root, task_id)
    if task_file is None:
        report("ERROR", f"Task file not found for {task_id}")
        return 2
    front_matter = parse_front_matter(task_file)

    required_front_matter = (
        "coordinationMode",
        "ownerRole",
        "reviewRole",
        "baseCommit",
        "coordinationPath",
        "handoffPath",
        "dependsOn",
    )
    for field in required_front_matter:
        if field not in front_matter or front_matter[field] in (None, ""):
            errors.append(f"Task front matter missing collaboration field: {field}")

    coordination_path = repo_root / str(front_matter.get("coordinationPath", ""))
    schema_path = repo_root / "specs" / "collaboration" / "task-coordination.schema.yaml"
    descriptor: Dict[str, Any] = {}
    if not coordination_path.is_file():
        errors.append(f"Coordination descriptor does not exist: {coordination_path}")
    else:
        try:
            descriptor = load_yaml(coordination_path)
        except Exception as exc:
            errors.append(f"Cannot load coordination descriptor: {exc}")

    if not schema_path.is_file():
        errors.append(f"Coordination schema does not exist: {schema_path}")
    elif descriptor:
        try:
            schema = load_yaml(schema_path)
            errors.extend(validate_schema(descriptor, schema))
        except Exception as exc:
            errors.append(f"Cannot load coordination schema: {exc}")

    if descriptor:
        cross_checks = (
            ("taskId", task_id),
            ("mode", str(front_matter.get("coordinationMode", ""))),
            ("baseCommit", str(front_matter.get("baseCommit", ""))),
        )
        for field, expected in cross_checks:
            actual = str(descriptor.get(field, ""))
            if actual != expected:
                errors.append(
                    f"Task/descriptor mismatch for {field}: expected '{expected}', got '{actual}'"
                )

        roles = descriptor.get("roles", {}) if isinstance(descriptor.get("roles"), dict) else {}
        owner = str(roles.get("owner", ""))
        reviewer = str(roles.get("reviewer", ""))
        if owner != str(front_matter.get("ownerRole", "")):
            errors.append("ownerRole does not match descriptor roles.owner")
        if reviewer != str(front_matter.get("reviewRole", "")):
            errors.append("reviewRole does not match descriptor roles.reviewer")
        if owner and reviewer and owner == reviewer:
            errors.append("Owner and final reviewer must be different execution roles")

        task_dependencies = set(as_task_list(front_matter.get("dependsOn")))
        descriptor_dependencies = {
            str(value) for value in descriptor.get("dependencies", [])
        }
        if task_dependencies != descriptor_dependencies:
            errors.append(
                "dependsOn does not match descriptor dependencies: "
                f"task={sorted(task_dependencies)}, descriptor={sorted(descriptor_dependencies)}"
            )
        if task_id in descriptor_dependencies:
            errors.append("Task cannot depend on itself")

        handoff = descriptor.get("handoff", {}) if isinstance(descriptor.get("handoff"), dict) else {}
        handoff_path_value = str(front_matter.get("handoffPath", ""))
        if str(handoff.get("path", "")) != handoff_path_value:
            errors.append("handoffPath does not match descriptor handoff.path")
        if bool(handoff.get("required", False)):
            errors.extend(validate_handoff(repo_root / handoff_path_value))

        base_commit = str(descriptor.get("baseCommit", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", base_commit):
            errors.append(f"Invalid baseCommit format: {base_commit}")
        else:
            rc, _, _ = run_git(repo_root, ["cat-file", "-e", f"{base_commit}^{{commit}}"])
            if rc != 0:
                errors.append(f"baseCommit does not exist in Git history: {base_commit}")
            else:
                rc, _, _ = run_git(
                    repo_root, ["merge-base", "--is-ancestor", base_commit, "HEAD"]
                )
                if rc != 0:
                    errors.append(f"baseCommit is not an ancestor of HEAD: {base_commit}")

        contracts = descriptor.get("contracts", {}) if isinstance(descriptor.get("contracts"), dict) else {}
        for input_path in contracts.get("inputs", []):
            if not path_exists_or_glob(repo_root, str(input_path)):
                errors.append(f"Declared contract input does not exist: {input_path}")

        errors.extend(validate_descriptor_overlap(repo_root, task_id, descriptor))

        if not args.skip_diff:
            changed_files = get_changed_files(repo_root, base)
            if changed_files is None:
                errors.append(f"Cannot determine changed files from base: {base}")
            else:
                info["changedFiles"] = changed_files
                declared = [
                    *descriptor_paths(descriptor, "exclusive"),
                    *descriptor_paths(descriptor, "shared"),
                ]
                undeclared = [
                    path
                    for path in changed_files
                    if not any(pattern_matches(path, pattern) for pattern in declared)
                ]
                if undeclared:
                    errors.append(
                        "Changed files are outside coordination path ownership: "
                        + ", ".join(undeclared)
                    )

    if errors:
        for error in errors:
            report("FAIL", error)
        report("FAIL", f"Collaboration contract failed for {task_id}", info)
        return 1

    report(
        "PASS",
        f"Collaboration contract passed for {task_id}",
        {
            **info,
            "coordinationPath": str(coordination_path.relative_to(repo_root)),
            "handoffPath": str(front_matter.get("handoffPath", "")),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

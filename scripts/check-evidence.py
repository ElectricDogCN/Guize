#!/usr/bin/env python3
"""Validate task Evidence against the canonical AGENTS.md evidence contract."""

import argparse
import json
import os
import re
import sys


CANONICAL_ENTRIES = [
    "summary.md",
    "commands.txt",
    "test-results/",
    "screenshots/",
    "api-samples/",
    "migration-report/",
    "performance/",
    "security/",
    "rollback-verification/",
]

SUPPORT_FILES = [
    "scope.md",
    "changed-files.md",
    "assumptions.md",
    "risks.md",
    "follow-ups.md",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check task evidence directory content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-001")
    parser.add_argument(
        "--evidence-dir",
        default="evidence",
        help="Base evidence directory (default: evidence)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: .)",
    )
    return parser.parse_args()


def report(status, message, details=None):
    obj = {"status": status, "message": message}
    if details is not None:
        obj["details"] = details
    print(json.dumps(obj, ensure_ascii=False))


def file_contains_task_id(path, task_id):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return task_id in handle.read()
    except Exception:
        return False


def has_command_indicators(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except Exception:
        return False
    has_cmd = bool(re.search(r"命令|command|cmd|\$\s", content, re.I))
    has_exit = bool(re.search(r"退出码|exit.?code|returncode", content, re.I))
    return has_cmd and has_exit


def has_executable_steps(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except Exception:
        return False
    if "```bash" in content or "```sh" in content:
        return True
    return bool(
        re.search(
            r"(?m)^(?:git\s|rm\s|cp\s|mv\s|docker\s|kubectl\s|make\s|python\s|bash\s)",
            content,
        )
    )


def _entry_exists(task_evidence, entry):
    path = os.path.join(task_evidence, entry.rstrip("/"))
    if entry.endswith("/"):
        if not os.path.isdir(path):
            return False
        return any(True for _ in os.scandir(path))
    return os.path.isfile(path) and os.path.getsize(path) > 0


def _clean_cell(value):
    return value.strip().strip("`").strip()


def parse_compatibility_map(task_evidence):
    """Parse explicit canonical-to-compatible mappings from EVIDENCE-STRUCTURE.md."""
    path = os.path.join(task_evidence, "EVIDENCE-STRUCTURE.md")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return {}

    mappings = {}
    canonical_names = {entry.rstrip("/"): entry for entry in CANONICAL_ENTRIES}
    for line in lines:
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        source = _clean_cell(cells[0]).rstrip("/")
        if source not in canonical_names:
            continue
        target = _clean_cell(cells[1])
        explanation = cells[2].strip()
        mappings[canonical_names[source]] = (target, explanation)
    return mappings


def validate_compatibility(task_evidence, task_id, entry, mapping):
    target, explanation = mapping
    normalized = target.strip().upper().replace(" ", "")
    if normalized in {"N/A", "NA", "NOTAPPLICABLE", "不适用"}:
        if len(re.sub(r"[`*_]", "", explanation).strip()) < 4:
            return False, f"N/A mapping for {entry} must include a reason."
        return True, None

    # A compatibility cell may name multiple alternatives joined by + or comma.
    candidates = [
        part.strip().strip("`")
        for part in re.split(r"\s*(?:\+|,|，|<br\s*/?>)\s*", target)
        if part.strip()
    ]
    if not candidates:
        return False, f"Compatibility mapping for {entry} has no target."

    existing = []
    for candidate in candidates:
        candidate_path = os.path.join(task_evidence, candidate.rstrip("/"))
        if candidate.endswith("/"):
            valid = os.path.isdir(candidate_path) and any(True for _ in os.scandir(candidate_path))
        else:
            valid = os.path.isfile(candidate_path) and os.path.getsize(candidate_path) > 0
        if valid:
            existing.append(candidate_path)

    if not existing:
        return False, f"Compatibility target for {entry} does not exist: {target}"
    for path in existing:
        if os.path.isfile(path) and not file_contains_task_id(path, task_id):
            return False, f"Compatibility target does not contain task ID {task_id}: {os.path.basename(path)}"
    return True, None


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    task_id = args.task.strip()
    if not task_id:
        report("ERROR", "Task ID must not be empty.")
        sys.exit(2)

    task_evidence = os.path.join(repo_root, args.evidence_dir, task_id)
    if not os.path.isdir(task_evidence):
        report("ERROR", f"Evidence directory not found: {task_evidence}")
        sys.exit(1)

    errors = []
    warnings = []
    compatibility = parse_compatibility_map(task_evidence)

    for entry in CANONICAL_ENTRIES:
        if _entry_exists(task_evidence, entry):
            path = os.path.join(task_evidence, entry.rstrip("/"))
            if os.path.isfile(path) and not file_contains_task_id(path, task_id):
                errors.append(f"Canonical evidence does not contain task ID {task_id}: {entry}")
            continue
        mapping = compatibility.get(entry)
        if not mapping:
            errors.append(f"Missing canonical evidence or explicit compatibility reference: {entry}")
            continue
        valid, error = validate_compatibility(task_evidence, task_id, entry, mapping)
        if not valid:
            errors.append(error)

    for filename in SUPPORT_FILES:
        filepath = os.path.join(task_evidence, filename)
        if not os.path.isfile(filepath) or os.path.getsize(filepath) == 0:
            errors.append(f"Missing or empty support evidence file: {filename}")
        elif not file_contains_task_id(filepath, task_id):
            errors.append(f"Support evidence does not contain task ID {task_id}: {filename}")

    command_path = os.path.join(task_evidence, "commands.txt")
    if not os.path.isfile(command_path):
        mapped = compatibility.get("commands.txt")
        if mapped and mapped[0].strip().upper() not in {"N/A", "NA"}:
            command_path = os.path.join(task_evidence, mapped[0].strip().strip("`"))
    if os.path.isfile(command_path) and not has_command_indicators(command_path):
        warnings.append("Command evidence may be missing command/exit-code indicators.")

    rollback_path = os.path.join(task_evidence, "rollback-verification")
    if not os.path.isdir(rollback_path):
        mapped = compatibility.get("rollback-verification/")
        if mapped and mapped[0].strip().upper() not in {"N/A", "NA"}:
            rollback_path = os.path.join(task_evidence, mapped[0].split("+")[0].strip().strip("`"))
    if os.path.isfile(rollback_path) and not has_executable_steps(rollback_path):
        warnings.append("Rollback evidence may be missing executable verification/rollback steps.")

    for error in errors:
        report("FAIL", error)
    for warning in warnings:
        report("WARN", warning)

    if errors:
        sys.exit(1)
    if warnings:
        report("PASS", f"Evidence contract passed with warnings for {task_id}.")
        sys.exit(0)
    report("PASS", f"Evidence contract passed for {task_id}.")
    sys.exit(0)


if __name__ == "__main__":
    main()

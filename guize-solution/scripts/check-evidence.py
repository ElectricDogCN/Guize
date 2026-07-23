#!/usr/bin/env python3
"""Check evidence directory content."""

import argparse
import json
import os
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check task evidence directory content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task ID, e.g. GZ-001",
    )
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
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return task_id in content
    except Exception:
        return False


def has_command_indicators(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False
    # Look for command and exit code indicators
    has_cmd = bool(re.search(r"命令|command|cmd|\$\s", content, re.I))
    has_exit = bool(re.search(r"退出码|exit.?code|returncode", content, re.I))
    return has_cmd and has_exit


def has_executable_steps(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False
    # Look for bash code blocks or command-like lines
    if "```bash" in content or "```sh" in content:
        return True
    # Lines starting with common command indicators
    if re.search(r"(?m)^(?:git\s|rm\s|cp\s|mv\s|docker\s|kubectl\s|make\s|python\s|bash\s)", content):
        return True
    return False


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    task_id = args.task.strip()

    if not task_id:
        report("ERROR", "Task ID must not be empty.")
        sys.exit(2)

    evidence_base = os.path.join(repo_root, args.evidence_dir)
    task_evidence = os.path.join(evidence_base, task_id)

    if not os.path.isdir(task_evidence):
        report("ERROR", f"Evidence directory not found: {task_evidence}")
        sys.exit(1)

    required_files = [
        "README.md",
        "scope.md",
        "changed-files.md",
        "commands.md",
        "test-results.md",
        "assumptions.md",
        "risks.md",
        "rollback.md",
        "follow-ups.md",
    ]

    errors = []
    warnings = []

    for filename in required_files:
        filepath = os.path.join(task_evidence, filename)
        if not os.path.isfile(filepath):
            errors.append(f"Missing required file: {filename}")
            continue
        size = os.path.getsize(filepath)
        if size == 0:
            errors.append(f"File is empty: {filename}")
        if not file_contains_task_id(filepath, task_id):
            errors.append(f"File does not contain task ID {task_id}: {filename}")

        # Specific checks
        if filename == "test-results.md" and os.path.isfile(filepath):
            if not has_command_indicators(filepath):
                warnings.append(f"test-results.md may be missing command/exit code indicators.")
        if filename == "rollback.md" and os.path.isfile(filepath):
            if not has_executable_steps(filepath):
                warnings.append(f"rollback.md may be missing executable steps.")

    if errors:
        for err in errors:
            report("FAIL", err)
    if warnings:
        for warn in warnings:
            report("WARN", warn)

    if errors:
        sys.exit(1)
    if warnings:
        report("PASS", f"Evidence checks passed with warnings for {task_id}.")
        sys.exit(0)
    report("PASS", f"Evidence checks passed for {task_id}.")
    sys.exit(0)


if __name__ == "__main__":
    main()

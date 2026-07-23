#!/usr/bin/env python3
"""Validate a task specification file."""

import argparse
import json
import os
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate a Guize task specification file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task ID, e.g. GZ-001",
    )
    parser.add_argument(
        "--spec-dir",
        default="specs/tasks",
        help="Directory containing task spec files (default: specs/tasks)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: .)",
    )
    return parser.parse_args()


def find_task_file(repo_root, spec_dir, task_id):
    """Find task file using preferred naming or fallback."""
    base = os.path.join(repo_root, spec_dir)
    candidates = [
        os.path.join(base, f"{task_id}-repository-baseline.md"),
        os.path.join(base, f"{task_id}.md"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def parse_front_matter(text):
    """Parse simple YAML front matter; returns (dict, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text = parts[1].strip()
    body = parts[2].strip()
    data = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, body


def report(status, message, details=None):
    obj = {"status": status, "message": message}
    if details is not None:
        obj["details"] = details
    print(json.dumps(obj, ensure_ascii=False))


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    task_id = args.task.strip()

    if not task_id:
        report("ERROR", "Task ID must not be empty.")
        sys.exit(2)

    task_path = find_task_file(repo_root, args.spec_dir, task_id)
    if not task_path:
        report("ERROR", f"Task file not found for {task_id}.", {"searched": [
            os.path.join(repo_root, args.spec_dir, f"{task_id}-repository-baseline.md"),
            os.path.join(repo_root, args.spec_dir, f"{task_id}.md"),
        ]})
        sys.exit(2)

    try:
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        report("ERROR", f"Cannot read task file: {exc}")
        sys.exit(2)

    front_matter, body = parse_front_matter(content)

    required_fields = [
        "id",
        "title",
        "titleZh",
        "type",
        "status",
        "baseBranch",
        "workBranch",
        "evidencePath",
    ]
    errors = []
    warnings = []

    for field in required_fields:
        if field not in front_matter or not front_matter[field]:
            errors.append(f"Missing or empty front matter field: {field}")

    # Task ID format
    if not re.fullmatch(r"[A-Z]+-\d+", task_id):
        errors.append(f"Task ID format invalid: {task_id}")
    else:
        if front_matter.get("id") != task_id:
            errors.append(
                f"Front matter id mismatch: expected {task_id}, got {front_matter.get('id')}"
            )

    # Branch name pattern
    work_branch = front_matter.get("workBranch", "")
    expected_prefix = f"{front_matter.get('type', 'chore')}/{task_id}"
    if not work_branch.startswith(expected_prefix):
        errors.append(
            f"workBranch '{work_branch}' does not start with expected prefix '{expected_prefix}'"
        )

    # Evidence path exists
    evidence_path = front_matter.get("evidencePath", "")
    if evidence_path:
        full_evidence = os.path.join(repo_root, evidence_path)
        if not os.path.isdir(full_evidence):
            errors.append(f"Evidence path does not exist: {evidence_path}")
    else:
        errors.append("evidencePath is empty.")

    # Allowed scope and forbidden scope sections exist
    lower_body = body.lower()
    if "## 允许范围" not in body and "## allowed scope" not in lower_body:
        errors.append("Missing allowed scope section.")
    if "## 禁止范围" not in body and "## forbidden scope" not in lower_body:
        errors.append("Missing forbidden scope section.")

    # Acceptance criteria exist
    if "## 验收标准" not in body and "## acceptance criteria" not in lower_body:
        errors.append("Missing acceptance criteria section.")
    else:
        # Look for at least one checklist item or bullet
        if not re.search(r"[-*]\s+\[.\]", body):
            warnings.append("No checklist items found in acceptance criteria.")

    # Validation commands exist
    if "## 必须执行的测试" not in body and "## validation commands" not in lower_body:
        errors.append("Missing validation commands section.")
    else:
        if not re.search(r"```", body):
            warnings.append("No code blocks found in validation commands section.")

    if errors:
        for err in errors:
            report("FAIL", err)
    if warnings:
        for warn in warnings:
            report("WARN", warn)

    if errors:
        sys.exit(1)
    if warnings:
        report("PASS", f"Task file valid with warnings: {task_path}")
        sys.exit(0)
    report("PASS", f"Task file valid: {task_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()

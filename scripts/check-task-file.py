#!/usr/bin/env python3
"""Validate a Guize task specification file."""

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
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-001")
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
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, body


def report(status, message, details=None):
    obj = {"status": status, "message": message}
    if details is not None:
        obj["details"] = details
    print(json.dumps(obj, ensure_ascii=False))


def extract_section(body, names):
    """Return the body of a level-2 Markdown section by Chinese/English names."""
    wanted = [name.lower() for name in names]
    lines = body.splitlines()
    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        title = re.sub(r"^##\s+", "", stripped).strip().lower()
        title = re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", title)
        if any(name in title for name in wanted):
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].strip().startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    task_id = args.task.strip()

    if not task_id:
        report("ERROR", "Task ID must not be empty.")
        sys.exit(2)

    task_path = find_task_file(repo_root, args.spec_dir, task_id)
    if not task_path:
        report(
            "ERROR",
            f"Task file not found for {task_id}.",
            {
                "searched": [
                    os.path.join(repo_root, args.spec_dir, f"{task_id}-repository-baseline.md"),
                    os.path.join(repo_root, args.spec_dir, f"{task_id}.md"),
                ]
            },
        )
        sys.exit(2)

    try:
        with open(task_path, "r", encoding="utf-8") as handle:
            content = handle.read()
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

    if not re.fullmatch(r"[A-Z]+-\d+", task_id):
        errors.append(f"Task ID format invalid: {task_id}")
    elif front_matter.get("id") != task_id:
        errors.append(
            f"Front matter id mismatch: expected {task_id}, got {front_matter.get('id')}"
        )

    work_branch = front_matter.get("workBranch", "")
    expected_prefix = f"{front_matter.get('type', 'chore')}/{task_id}"
    if not work_branch.startswith(expected_prefix):
        errors.append(
            f"workBranch '{work_branch}' does not start with expected prefix '{expected_prefix}'"
        )

    evidence_path = front_matter.get("evidencePath", "")
    if evidence_path:
        full_evidence = os.path.join(repo_root, evidence_path)
        if not os.path.isdir(full_evidence):
            errors.append(f"Evidence path does not exist: {evidence_path}")
    else:
        errors.append("evidencePath is empty.")

    allowed = extract_section(body, ["允许范围", "allowed scope"])
    forbidden = extract_section(body, ["禁止范围", "forbidden scope"])
    acceptance = extract_section(body, ["验收标准", "acceptance criteria"])
    validation = extract_section(body, ["必须执行的测试", "validation commands"])

    if allowed is None:
        errors.append("Missing allowed scope section.")
    elif not re.search(r"(?m)^\s*[-*]\s+\S", allowed):
        errors.append("Allowed scope section has no scope entries.")

    if forbidden is None:
        errors.append("Missing forbidden scope section.")
    elif not re.search(r"(?m)^\s*[-*]\s+\S", forbidden):
        errors.append("Forbidden scope section has no entries.")

    if acceptance is None:
        errors.append("Missing acceptance criteria section.")
    elif not re.search(r"(?m)^\s*[-*]\s+\[[ xX]\]\s+\S", acceptance):
        errors.append("Acceptance criteria section must contain at least one checklist item.")

    if validation is None:
        errors.append("Missing validation commands section.")
    elif not re.search(r"```(?:bash|sh|shell|text)?\s*\n[^`\n]+", validation, re.I):
        errors.append("Validation commands section must contain a non-empty code block.")

    for error in errors:
        report("FAIL", error)
    for warning in warnings:
        report("WARN", warning)

    if errors:
        sys.exit(1)
    if warnings:
        report("PASS", f"Task file valid with warnings: {task_path}")
        sys.exit(0)
    report("PASS", f"Task file valid: {task_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()

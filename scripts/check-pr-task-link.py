#!/usr/bin/env python3
"""Validate PR/branch linkage to task."""

import argparse
import json
import os
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate branch/PR linkage to a Guize task.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch name, e.g. chore/GZ-001-repository-baseline",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="PR title (or set PR_TITLE env var)",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="PR body (or set PR_BODY env var)",
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


def get_branch(args):
    branch = (args.branch or os.environ.get("GITHUB_HEAD_REF", "")).strip()
    if not branch:
        # Try git command
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=args.repo_root,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass
    return branch


def extract_task_id(branch):
    """Extract task ID from branch name like chore/GZ-001-xxx."""
    # Remove remote prefix if present
    if "/" in branch and not branch.startswith(("feature/", "chore/", "fix/", "bugfix/")):
        parts = branch.split("/")
        # e.g. origin/chore/GZ-001-xxx -> chore/GZ-001-xxx
        if len(parts) > 1:
            branch = "/".join(parts[1:])
    match = re.search(r"([A-Z]+-\d+)", branch)
    if match:
        return match.group(1)
    return None


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
    branch = get_branch(args)
    title = (args.title or os.environ.get("PR_TITLE", "")).strip()
    body_text = (args.body or os.environ.get("PR_BODY", "")).strip()

    if not branch:
        report("ERROR", "Branch name is required. Provide --branch or set GITHUB_HEAD_REF.")
        sys.exit(2)

    task_id = extract_task_id(branch)
    if not task_id:
        report("ERROR", f"Could not extract task ID from branch: {branch}")
        sys.exit(1)

    errors = []
    warnings = []

    # Verify task file exists
    task_path = find_task_file(repo_root, args.spec_dir, task_id)
    if not task_path:
        errors.append(f"Task file not found for {task_id}.")
    else:
        try:
            with open(task_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            report("ERROR", f"Cannot read task file: {exc}")
            sys.exit(2)

        front_matter, _ = parse_front_matter(content)
        work_branch = front_matter.get("workBranch", "")
        if work_branch and work_branch != branch:
            warnings.append(
                f"Branch mismatch: task file says '{work_branch}', actual '{branch}'"
            )

        evidence_path = front_matter.get("evidencePath", "")
        if evidence_path:
            full_evidence = os.path.join(repo_root, evidence_path)
            if not os.path.isdir(full_evidence):
                errors.append(f"Evidence path does not exist: {evidence_path}")
        else:
            warnings.append("Task file has no evidencePath.")

    # Check title and body for task ID mention
    if title and task_id not in title:
        warnings.append(f"PR title does not mention task ID {task_id}.")
    if body_text and task_id not in body_text:
        warnings.append(f"PR body does not mention task ID {task_id}.")

    if errors:
        for err in errors:
            report("FAIL", err)
    if warnings:
        for warn in warnings:
            report("WARN", warn)

    if errors:
        sys.exit(1)
    if warnings:
        report("PASS", f"PR/branch linkage valid with warnings for {task_id}.")
        sys.exit(0)
    report("PASS", f"PR/branch linkage valid for {task_id}.")
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate git diff against task allowed/forbidden scope."""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate changed files against task allowed scope.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task ID, e.g. GZ-001",
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Base branch or commit to diff against, e.g. main",
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


def extract_allowed_patterns(body):
    """Extract allowed scope patterns from bullet list under allowed scope section."""
    patterns = []
    in_allowed = False
    for line in body.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        # Section headers
        if stripped.startswith("## "):
            if "允许范围" in stripped or "allowed scope" in lower:
                in_allowed = True
                continue
            if "禁止范围" in stripped or "forbidden scope" in lower:
                in_allowed = False
                continue
            # Another section ends allowed scope
            if in_allowed:
                in_allowed = False
            continue
        if in_allowed:
            # Bullet items like `- `path`` or `- path`
            match = re.match(r"[-*]\s+`?([^`]+)`?\s*", stripped)
            if match:
                patterns.append(match.group(1).strip())
    return patterns


def match_pattern(filepath, pattern):
    """Match a filepath against a pattern supporting ** wildcards."""
    # Normalize separators
    filepath = filepath.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatch(filepath, pattern):
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if filepath.startswith(prefix + "/") or filepath == prefix:
            return True
    if pattern.endswith("/"):
        prefix = pattern[:-1]
        if filepath.startswith(prefix + "/") or filepath == prefix:
            return True
    # Directory match: pattern is a directory and filepath is inside it
    if not pattern.endswith("/**") and not pattern.endswith("/") and not os.path.splitext(pattern)[1]:
        if filepath.startswith(pattern + "/") or filepath == pattern:
            return True
    return False


def _repo_subpath_prefix(repo_root):
    """Return prefix to strip from git output when repo_root is inside a larger git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode == 0:
            git_root = result.stdout.strip()
            rel = os.path.relpath(repo_root, git_root).replace("\\", "/")
            if rel and rel != ".":
                return rel + "/"
    except Exception:
        pass
    return ""


def get_changed_files(repo_root, base):
    """Get changed file list via git diff."""
    env = os.environ.copy()
    git_dir = os.path.join(repo_root, ".git")
    if os.path.isdir(git_dir):
        env["GIT_DIR"] = git_dir
        env["GIT_WORK_TREE"] = repo_root

    prefix = _repo_subpath_prefix(repo_root)

    # Try merge-base diff first
    cmds = [
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only", base],
    ]
    for cmd in cmds:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_root,
                env=env,
            )
            if result.returncode == 0:
                files = []
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if prefix and line.startswith(prefix):
                        line = line[len(prefix):]
                    files.append(line)
                if files:
                    return files
        except Exception:
            continue
    # Fallback to git status if no base
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode == 0:
            files = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if len(line) > 3 and line[2] == " ":
                    filepath = line[3:].strip()
                    # Skip directory entries from git status
                    if filepath.endswith("/") or filepath.endswith("\\"):
                        continue
                    files.append(filepath)
            return files
    except Exception:
        pass
    return None


def report(status, message, details=None):
    obj = {"status": status, "message": message}
    if details is not None:
        obj["details"] = details
    print(json.dumps(obj, ensure_ascii=False))


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    task_id = args.task.strip()
    base = args.base.strip()

    if not task_id:
        report("ERROR", "Task ID must not be empty.")
        sys.exit(2)
    if not base:
        report("ERROR", "Base branch must not be empty.")
        sys.exit(2)

    task_path = find_task_file(repo_root, args.spec_dir, task_id)
    if not task_path:
        report("ERROR", f"Task file not found for {task_id}.")
        sys.exit(2)

    try:
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        report("ERROR", f"Cannot read task file: {exc}")
        sys.exit(2)

    _, body = parse_front_matter(content)
    patterns = extract_allowed_patterns(body)
    if not patterns:
        report("ERROR", "No allowed scope patterns found in task file.")
        sys.exit(2)

    changed_files = get_changed_files(repo_root, base)
    if changed_files is None:
        report("ERROR", "Failed to determine changed files from git.")
        sys.exit(2)

    allowed = []
    out_of_scope = []

    for filepath in changed_files:
        matched = any(match_pattern(filepath, p) for p in patterns)
        if matched:
            allowed.append(filepath)
        else:
            out_of_scope.append(filepath)

    report("INFO", f"Changed files: {len(changed_files)}, Allowed: {len(allowed)}, Out-of-scope: {len(out_of_scope)}")
    if allowed:
        report("PASS", "Allowed files", {"files": allowed})
    if out_of_scope:
        report("FAIL", "Out-of-scope files found", {"files": out_of_scope})
        sys.exit(1)

    report("PASS", "All changed files are within allowed scope.")
    sys.exit(0)


if __name__ == "__main__":
    main()

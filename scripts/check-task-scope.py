#!/usr/bin/env python3
"""Validate git diff against task allowed/forbidden scope."""

import argparse
import json
import os
import re
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate changed files against task allowed/forbidden scope.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-001")
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
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, body


def _looks_like_path_pattern(value):
    """Return True when a bullet value can be enforced as a repository path."""
    value = value.strip()
    if not value:
        return False
    return (
        "/" in value
        or value.startswith(".")
        or any(token in value for token in ("*", "?", "["))
        or bool(re.search(r"\.[A-Za-z0-9_-]+$", value))
    )


def _bullet_pattern(stripped):
    """Extract the path/pattern portion of a Markdown bullet, if present."""
    bullet = re.match(r"[-*]\s+(.+?)\s*$", stripped)
    if not bullet:
        return None
    value = bullet.group(1).strip()
    backticked = re.search(r"`([^`]+)`", value)
    if backticked:
        value = backticked.group(1).strip()
    if not _looks_like_path_pattern(value):
        return None
    return value


def extract_scope_patterns(body, section):
    """Extract path patterns from the allowed or forbidden scope section."""
    if section not in {"allowed", "forbidden"}:
        raise ValueError("section must be 'allowed' or 'forbidden'")

    patterns = []
    active = False
    for line in body.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if stripped.startswith("## "):
            is_allowed = "允许范围" in stripped or "allowed scope" in lower
            is_forbidden = "禁止范围" in stripped or "forbidden scope" in lower
            if section == "allowed" and is_allowed:
                active = True
                continue
            if section == "forbidden" and is_forbidden:
                active = True
                continue
            if active:
                active = False
            continue
        if active:
            pattern = _bullet_pattern(stripped)
            if pattern:
                patterns.append(pattern)
    return patterns


def _glob_regex(pattern):
    """Translate a repository glob so only ** may cross path separators."""
    out = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(r"\[")
            else:
                content = pattern[i + 1 : end]
                if content.startswith("!"):
                    content = "^" + content[1:]
                out.append("[" + content + "]")
                i = end
        else:
            out.append(re.escape(char))
        i += 1
    return "".join(out)


def match_pattern(filepath, pattern):
    """Match repository paths; * stays in one segment and ** crosses segments."""
    filepath = filepath.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/").lstrip("./")

    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return filepath == prefix or filepath.startswith(prefix + "/")
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return filepath == prefix or filepath.startswith(prefix + "/")

    has_glob = any(token in pattern for token in ("*", "?", "["))
    if has_glob:
        return re.fullmatch(_glob_regex(pattern), filepath) is not None

    # A non-glob path without a file extension is treated as a directory root.
    if not os.path.splitext(pattern)[1]:
        return filepath == pattern or filepath.startswith(pattern + "/")
    return filepath == pattern


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
    """Get changed file list via git diff; invalid bases fail closed."""
    env = os.environ.copy()
    git_dir = os.path.join(repo_root, ".git")
    if os.path.isdir(git_dir):
        env["GIT_DIR"] = git_dir
        env["GIT_WORK_TREE"] = repo_root

    prefix = _repo_subpath_prefix(repo_root)
    try:
        base_check = subprocess.run(
            ["git", "rev-parse", "--verify", f"{base}^{{commit}}"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
        )
        if base_check.returncode != 0:
            return None
    except Exception:
        return None

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
                        line = line[len(prefix) :]
                    files.append(line)
                if files:
                    return files
        except Exception:
            continue

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
                if len(line) < 4:
                    continue
                filepath = line[3:].strip()
                if filepath and not filepath.endswith(("/", "\\")):
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
        with open(task_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        report("ERROR", f"Cannot read task file: {exc}")
        sys.exit(2)

    _, body = parse_front_matter(content)
    allowed_patterns = extract_scope_patterns(body, "allowed")
    forbidden_patterns = extract_scope_patterns(body, "forbidden")
    if not allowed_patterns:
        report("ERROR", "No allowed scope patterns found in task file.")
        sys.exit(2)

    changed_files = get_changed_files(repo_root, base)
    if changed_files is None:
        report("ERROR", "Cannot determine changed files; scope validation fails closed.")
        sys.exit(2)

    allowed = []
    forbidden = []
    out_of_scope = []
    for filepath in changed_files:
        if any(match_pattern(filepath, pattern) for pattern in forbidden_patterns):
            forbidden.append(filepath)
        elif any(match_pattern(filepath, pattern) for pattern in allowed_patterns):
            allowed.append(filepath)
        else:
            out_of_scope.append(filepath)

    report(
        "INFO",
        (
            f"Changed files: {len(changed_files)}, Allowed: {len(allowed)}, "
            f"Forbidden: {len(forbidden)}, Out-of-scope: {len(out_of_scope)}"
        ),
    )
    if allowed:
        report("PASS", "Allowed files", {"files": allowed})
    if forbidden:
        report("FAIL", "Forbidden-scope files found", {"files": forbidden})
    if out_of_scope:
        report("FAIL", "Out-of-scope files found", {"files": out_of_scope})
    if forbidden or out_of_scope:
        sys.exit(1)

    report("PASS", "All changed files are within allowed scope and outside forbidden scope.")
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check spec synchronization based on changed files."""

import argparse
import json
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check spec synchronization based on changed files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base",
        default="main",
        help="Base branch or commit to diff against (default: main)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: .)",
    )
    return parser.parse_args()


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
    env = os.environ.copy()
    git_dir = os.path.join(repo_root, ".git")
    if os.path.isdir(git_dir):
        env["GIT_DIR"] = git_dir
        env["GIT_WORK_TREE"] = repo_root

    prefix = _repo_subpath_prefix(repo_root)

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
    # Fallback to git status
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
    return []


def file_changed(changed_files, prefix):
    return any(f.startswith(prefix) for f in changed_files)


def any_file_matches(changed_files, prefixes):
    for f in changed_files:
        for p in prefixes:
            if f.startswith(p):
                return True
    return False


def report(status, message, details=None):
    obj = {"status": status, "message": message}
    if details is not None:
        obj["details"] = details
    print(json.dumps(obj, ensure_ascii=False))


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    base = args.base.strip()

    changed_files = get_changed_files(repo_root, base)
    if changed_files is None:
        report("ERROR", "Failed to determine changed files from git.")
        sys.exit(2)

    warnings = []
    errors = []

    # contracts/openapi/** -> warn if no test or doc update
    if file_changed(changed_files, "contracts/openapi/"):
        has_test = any_file_matches(changed_files, ["tests/", "test/"])
        has_doc = any_file_matches(changed_files, ["docs/", "specs/"])
        if not has_test and not has_doc:
            warnings.append(
                "contracts/openapi/ changed but no corresponding test or doc update found."
            )

    # contracts/events/** -> warn if no event version note
    if file_changed(changed_files, "contracts/events/"):
        has_note = any_file_matches(changed_files, ["docs/", "specs/", "adr/"])
        if not has_note:
            warnings.append(
                "contracts/events/ changed but no event version note found in docs/specs/adr."
            )

    # deployment/** -> warn if no deployment/rollback doc update
    if file_changed(changed_files, "deployment/"):
        has_doc = any_file_matches(changed_files, ["docs/", "specs/"])
        if not has_doc:
            warnings.append(
                "deployment/ changed but no deployment/rollback doc update found."
            )

    # rules/never-rules.md -> check rules/never-rules-changelog.md modified
    if file_changed(changed_files, "rules/never-rules.md"):
        if not file_changed(changed_files, "rules/never-rules-changelog.md"):
            errors.append(
                "rules/never-rules.md changed but rules/never-rules-changelog.md was not updated."
            )

    # adr/** -> check there is an index or new ADR referenced
    if file_changed(changed_files, "adr/"):
        has_index = any_file_matches(changed_files, ["adr/index", "docs/"])
        if not has_index:
            warnings.append(
                "adr/ changed but no index or doc reference update found."
            )

    # .github/workflows/** -> note CI change
    if file_changed(changed_files, ".github/workflows/"):
        warnings.append(
            "CI workflow files changed. Ensure syntax validation and manual review."
        )

    if warnings:
        for w in warnings:
            report("WARN", w)
    if errors:
        for e in errors:
            report("FAIL", e)

    if errors:
        sys.exit(1)
    if warnings:
        report("PASS", "Spec sync check passed with warnings.")
        sys.exit(0)
    report("PASS", "Spec sync check passed. No synchronization issues detected.")
    sys.exit(0)


if __name__ == "__main__":
    main()

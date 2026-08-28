#!/usr/bin/env python3
import os
import re
import sys
from urllib.parse import unquote, urlsplit

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def check_file(filepath):
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except Exception as exc:
        return [(0, f"Cannot read file: {exc}")]

    for index, line in enumerate(lines, 1):
        content = line.rstrip("\n\r")
        if content.endswith(" ") or content.endswith("\t"):
            issues.append((index, "trailing whitespace"))

        for raw_target in LINK_PATTERN.findall(content):
            target = raw_target.strip().split()[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(("#", "mailto:")):
                continue
            path = unquote(parsed.path)
            if not path or not path.lower().endswith(".md"):
                continue
            resolved = path if os.path.isabs(path) else os.path.join(os.path.dirname(filepath), path)
            if not os.path.isfile(os.path.normpath(resolved)):
                issues.append((index, f"broken internal link: {target}"))

    return issues


def find_markdown_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune only the Git metadata directory. `.github` is repository content
        # and must remain subject to Markdown validation.
        dirnames[:] = [dirname for dirname in dirnames if dirname != ".git"]
        for filename in filenames:
            if filename.endswith(".md"):
                files.append(os.path.join(dirpath, filename))
    return sorted(files)


def main():
    root = "."
    all_issues = []
    md_files = find_markdown_files(root)
    print(f"Checking {len(md_files)} Markdown files...")

    for filepath in md_files:
        for line_num, message in check_file(filepath):
            all_issues.append(f"{filepath}:{line_num}: {message}")

    if all_issues:
        print("\nERRORS:")
        for issue in all_issues:
            print(f"  - {issue}")
        print("\nFAIL: Issues found")
        sys.exit(1)

    print("\nOK: No issues found")
    sys.exit(0)


if __name__ == "__main__":
    main()

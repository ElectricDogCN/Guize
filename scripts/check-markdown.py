#!/usr/bin/env python3
import os
import re
import sys

def check_file(filepath):
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return [(0, f"Cannot read file: {e}")]

    for i, line in enumerate(lines, 1):
        content = line.rstrip("\n\r")
        if content.endswith(" ") or content.endswith("\t"):
            issues.append((i, "trailing whitespace"))

    return issues

def find_markdown_files(root):
    files = []
    for dirpath, _, filenames in os.walk(root):
        if ".git" in dirpath:
            continue
        for fname in filenames:
            if fname.endswith(".md"):
                files.append(os.path.join(dirpath, fname))
    return sorted(files)

def main():
    root = "."
    all_issues = []
    md_files = find_markdown_files(root)
    print(f"Checking {len(md_files)} Markdown files...")

    for filepath in md_files:
        issues = check_file(filepath)
        for line_num, msg in issues:
            all_issues.append(f"{filepath}:{line_num}: {msg}")

    if all_issues:
        print("\nERRORS:")
        for issue in all_issues:
            print(f"  - {issue}")
        print("\nFAIL: Issues found")
        sys.exit(1)
    else:
        print("\nOK: No issues found")
        sys.exit(0)

if __name__ == "__main__":
    main()

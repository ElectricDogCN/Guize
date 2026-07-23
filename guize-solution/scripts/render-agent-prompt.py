#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render agent prompt from task spec and template.

Substitutes {{VARIABLE}} placeholders in a template using CLI arguments
and metadata extracted from the task specification file.
"""

import argparse
import os
import re
import sys


def find_task_file(task_id, specs_dir="specs/tasks"):
    """Find task spec file by task ID.

    Looks for exact match first (e.g., GZ-001.md), then prefix match
    (e.g., GZ-001-repository-baseline.md).
    """
    exact = os.path.join(specs_dir, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact

    if os.path.isdir(specs_dir):
        matches = []
        for name in os.listdir(specs_dir):
            if name.startswith(f"{task_id}-") and name.endswith(".md"):
                matches.append(os.path.join(specs_dir, name))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(
                f"Error: Multiple task files found for {task_id}: {matches}",
                file=sys.stderr,
            )
            sys.exit(1)

    return None


def extract_yaml_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    return None


def parse_yaml_line(line):
    """Parse a simple key: value line from YAML frontmatter."""
    if ":" not in line:
        return None, None
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def extract_section(content, heading):
    """Extract content of a markdown section by heading."""
    pattern = (
        rf"(?:^|\n)(#{{1,3}}\s*{re.escape(heading)}\s*\n)"
        rf"(.*?)"
        rf"(?=(?:\n#{{1,3}}\s)|\Z)"
    )
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(2).strip()
    return None


def extract_metadata(task_file_path):
    """Extract metadata from task spec file."""
    with open(task_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    metadata = {
        "id": None,
        "title": None,
        "evidencePath": None,
        "allowed_scope": None,
        "forbidden_scope": None,
        "acceptance_criteria": None,
    }

    frontmatter = extract_yaml_frontmatter(content)
    if frontmatter:
        for line in frontmatter.splitlines():
            key, value = parse_yaml_line(line)
            if key == "id":
                metadata["id"] = value
            elif key == "title":
                metadata["title"] = value
            elif key == "evidencePath":
                metadata["evidencePath"] = value

    metadata["allowed_scope"] = extract_section(content, "允许范围")
    metadata["forbidden_scope"] = extract_section(content, "禁止范围")
    metadata["acceptance_criteria"] = extract_section(content, "验收标准")

    return metadata


def render_template(template_path, variables):
    """Render template with variable substitution.

    Replaces {{KEY}} placeholders with values. Unknown placeholders
    are left unchanged.
    """
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Sort by length descending to avoid partial replacements
    for key, value in sorted(variables.items(), key=lambda x: len(x[0]), reverse=True):
        placeholder = f"{{{{{key}}}}}"
        if placeholder in content:
            content = content.replace(placeholder, str(value))

    return content


def main():
    parser = argparse.ArgumentParser(
        description="Render agent prompt from task spec and template."
    )
    parser.add_argument("--task", required=True, help="Task ID (e.g., GZ-001)")
    parser.add_argument(
        "--branch", required=True, help="Working branch name"
    )
    parser.add_argument("--base", required=True, help="Base branch name")
    parser.add_argument(
        "--mode", required=True, help="Execution mode (e.g., implement, review)"
    )
    parser.add_argument("--issue", required=True, help="Issue reference")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument(
        "--template",
        default="prompts/templates/task-execution.md",
        help="Template file path (default: prompts/templates/task-execution.md)",
    )
    parser.add_argument(
        "--specs-dir",
        default="specs/tasks",
        help="Directory containing task spec files (default: specs/tasks)",
    )

    args = parser.parse_args()

    # Validate template exists
    if not os.path.isfile(args.template):
        print(f"Error: Template not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    # Find and validate task file
    task_file = find_task_file(args.task, args.specs_dir)
    if not task_file:
        print(
            f"Error: Task file not found for task {args.task}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Extract metadata
    metadata = extract_metadata(task_file)

    # Validate required fields
    required_fields = [
        "id",
        "title",
        "evidencePath",
        "allowed_scope",
        "forbidden_scope",
        "acceptance_criteria",
    ]
    missing = [f for f in required_fields if not metadata.get(f)]
    if missing:
        print(
            f"Error: Task file missing required fields: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate consistency
    if metadata["id"] != args.task:
        print(
            f"Error: Task file ID '{metadata['id']}' does not match "
            f"--task '{args.task}'",
            file=sys.stderr,
        )
        sys.exit(1)

    # Build substitution variables
    variables = {
        "TASK_ID": args.task,
        "TASK_FILE": task_file,
        "ISSUE_REFERENCE": args.issue,
        "BRANCH_NAME": args.branch,
        "BASE_BRANCH": args.base,
        "EXECUTION_MODE": args.mode,
        "TASK_TITLE": metadata["title"] or "",
        "EVIDENCE_PATH": metadata["evidencePath"] or "",
    }

    # Render
    rendered = render_template(args.template, variables)

    # Warn about unsubstituted variables
    leftover = re.findall(r"\{\{[A-Za-z0-9_]+\}\}", rendered)
    if leftover:
        print(
            f"Warning: Unsubstituted template variables: {', '.join(sorted(set(leftover)))}",
            file=sys.stderr,
        )

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rendered)

    # Generation summary to stderr
    print(f"Generated prompt: {args.output}", file=sys.stderr)
    print(
        f"  Task: {metadata['id']} - {metadata['title']}",
        file=sys.stderr,
    )
    print(f"  Task file: {task_file}", file=sys.stderr)
    print(f"  Template: {args.template}", file=sys.stderr)
    print(
        f"  Evidence path: {metadata['evidencePath']}",
        file=sys.stderr,
    )
    print(f"  Branch: {args.branch} -> {args.base}", file=sys.stderr)
    print(f"  Mode: {args.mode}", file=sys.stderr)


if __name__ == "__main__":
    main()

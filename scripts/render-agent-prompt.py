#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render an agent prompt from a Guize task spec and template."""

import argparse
import os
import re
import sys


def find_task_file(task_id, specs_dir="specs/tasks"):
    exact = os.path.join(specs_dir, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    matches = []
    if os.path.isdir(specs_dir):
        for name in os.listdir(specs_dir):
            if name.startswith(f"{task_id}-") and name.endswith(".md"):
                matches.append(os.path.join(specs_dir, name))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Error: Multiple task files found for {task_id}: {matches}", file=sys.stderr)
        sys.exit(1)
    return None


def extract_yaml_frontmatter(content):
    pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else None


def parse_yaml_line(line):
    if ":" not in line:
        return None, None
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def extract_section(content, heading):
    pattern = rf"(?:^|\n)(#{{1,3}}\s*{re.escape(heading)}\s*\n)(.*?)(?=(?:\n#{{1,3}}\s)|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(2).strip() if match else None


def extract_metadata(task_file_path):
    with open(task_file_path, "r", encoding="utf-8") as handle:
        content = handle.read()

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
            if key:
                metadata[key] = value

    metadata["allowed_scope"] = extract_section(content, "允许范围")
    metadata["forbidden_scope"] = extract_section(content, "禁止范围")
    metadata["acceptance_criteria"] = extract_section(content, "验收标准")
    metadata["dependencies"] = extract_section(content, "依赖与集成顺序")
    metadata["exclusive_scope"] = extract_section(content, "独占写范围")
    metadata["shared_scope"] = extract_section(content, "共享修改范围")
    metadata["handoff"] = extract_section(content, "协作与交接")
    return metadata


def render_template(template_path, variables):
    with open(template_path, "r", encoding="utf-8") as handle:
        content = handle.read()
    for key, value in sorted(variables.items(), key=lambda item: len(item[0]), reverse=True):
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


def main():
    parser = argparse.ArgumentParser(description="Render agent prompt from task spec and template.")
    parser.add_argument("--task", required=True, help="Task ID (e.g., GZ-001)")
    parser.add_argument("--branch", required=True, help="Working branch name")
    parser.add_argument("--base", required=True, help="Base branch name")
    parser.add_argument("--mode", required=True, help="Execution mode (implement, review, handoff, integrate)")
    parser.add_argument("--issue", required=True, help="Issue reference")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--template", default="prompts/templates/task-execution.md")
    parser.add_argument("--specs-dir", default="specs/tasks")
    args = parser.parse_args()

    if not os.path.isfile(args.template):
        print(f"Error: Template not found: {args.template}", file=sys.stderr)
        sys.exit(1)

    task_file = find_task_file(args.task, args.specs_dir)
    if not task_file:
        print(f"Error: Task file not found for task {args.task}", file=sys.stderr)
        sys.exit(1)

    metadata = extract_metadata(task_file)
    required_fields = ["id", "title", "evidencePath", "allowed_scope", "forbidden_scope", "acceptance_criteria"]
    missing = [field for field in required_fields if not metadata.get(field)]
    if missing:
        print(f"Error: Task file missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    if metadata["id"] != args.task:
        print(f"Error: Task file ID '{metadata['id']}' does not match --task '{args.task}'", file=sys.stderr)
        sys.exit(1)

    variables = {
        "TASK_ID": args.task,
        "TASK_FILE": task_file,
        "ISSUE_REFERENCE": args.issue,
        "BRANCH_NAME": args.branch,
        "BASE_BRANCH": args.base,
        "EXECUTION_MODE": args.mode,
        "TASK_TITLE": metadata.get("title", ""),
        "EVIDENCE_PATH": metadata.get("evidencePath", ""),
        "SCHEMA_VERSION": metadata.get("schemaVersion", "1"),
        "WORK_PACKAGE": metadata.get("workPackage", ""),
        "TASK_OWNER": metadata.get("taskOwner", ""),
        "AGENT_ROLE": metadata.get("agentRole", ""),
        "RISK_LEVEL": metadata.get("riskLevel", ""),
        "COORDINATION_MODE": metadata.get("coordinationMode", "legacy"),
        "COORDINATION_GROUP": metadata.get("coordinationGroup", ""),
        "DEPENDS_ON": metadata.get("dependsOn", ""),
        "BASE_SHA": metadata.get("baseSha", ""),
        "HANDOFF_PATH": metadata.get("handoffPath", ""),
        "INTEGRATION_STRATEGY": metadata.get("integrationStrategy", ""),
        "ALLOWED_SCOPE": metadata.get("allowed_scope", ""),
        "FORBIDDEN_SCOPE": metadata.get("forbidden_scope", ""),
        "ACCEPTANCE_CRITERIA": metadata.get("acceptance_criteria", ""),
        "DEPENDENCIES_AND_ORDER": metadata.get("dependencies", ""),
        "EXCLUSIVE_SCOPE": metadata.get("exclusive_scope", ""),
        "SHARED_SCOPE": metadata.get("shared_scope", ""),
        "HANDOFF_RULES": metadata.get("handoff", ""),
    }

    rendered = render_template(args.template, variables)
    leftover = re.findall(r"\{\{[A-Za-z0-9_]+\}\}", rendered)
    if leftover:
        print(f"Warning: Unsubstituted template variables: {', '.join(sorted(set(leftover)))}", file=sys.stderr)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(rendered)

    print(f"Generated prompt: {args.output}", file=sys.stderr)
    print(f"  Task: {metadata['id']} - {metadata['title']}", file=sys.stderr)
    print(f"  Task file: {task_file}", file=sys.stderr)
    print(f"  Template: {args.template}", file=sys.stderr)
    print(f"  Evidence path: {metadata['evidencePath']}", file=sys.stderr)
    print(f"  Branch: {args.branch} -> {args.base}", file=sys.stderr)
    print(f"  Base SHA: {metadata.get('baseSha', 'legacy')}", file=sys.stderr)
    print(f"  Role/Risk: {metadata.get('agentRole', 'legacy')}/{metadata.get('riskLevel', 'legacy')}", file=sys.stderr)
    print(f"  Mode: {args.mode}", file=sys.stderr)


if __name__ == "__main__":
    main()

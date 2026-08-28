#!/usr/bin/env python3
"""Validate a Guize task specification file."""

import argparse
import json
import os
import re
import sys


V2_REQUIRED_FIELDS = [
    "schemaVersion",
    "workPackage",
    "taskOwner",
    "agentRole",
    "riskLevel",
    "coordinationMode",
    "coordinationGroup",
    "dependsOn",
    "baseSha",
    "handoffPath",
    "integrationStrategy",
]
V2_ROLES = {"coordinator", "implementer", "reviewer", "integrator"}
V2_RISKS = {"low", "medium", "high", "critical"}
V2_MODES = {"bootstrap", "registry"}
V2_INTEGRATION = {"merge", "squash", "rebase"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate a Guize task specification file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-001")
    parser.add_argument("--spec-dir", default="specs/tasks", help="Directory containing task spec files (default: specs/tasks)")
    parser.add_argument("--repo-root", default=".", help="Repository root path (default: .)")
    return parser.parse_args()


def find_task_file(repo_root, spec_dir, task_id):
    base = os.path.join(repo_root, spec_dir)
    exact = os.path.join(base, f"{task_id}.md")
    if os.path.isfile(exact):
        return exact
    candidates = []
    if os.path.isdir(base):
        for name in os.listdir(base):
            if name.startswith(f"{task_id}-") and name.endswith(".md"):
                candidates.append(os.path.join(base, name))
    if len(candidates) == 1:
        return candidates[0]
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


def has_validation_command(section):
    """Accept a non-empty fenced block or a structured list containing command text."""
    if not section:
        return False
    if re.search(r"```(?:bash|sh|shell|text)?\s*\n\s*[^`\s][\s\S]*?```", section, re.I):
        return True
    for line in section.splitlines():
        stripped = line.strip()
        if not re.match(r"^(?:[-*]|\d+[.)])\s+", stripped):
            continue
        if re.search(r"`[^`]+`", stripped):
            return True
        text = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", stripped)
        if re.match(r"(?:python|python3|make|git|bash|sh|pytest|npm|pnpm|yarn|mvn|gradle|docker)\b", text):
            return True
    return False


def has_list_entry(section):
    return bool(section and re.search(r"(?m)^\s*[-*]\s+\S", section))


def validate_v2(front_matter, body, repo_root, evidence_path, errors):
    if str(front_matter.get("schemaVersion")) != "2":
        errors.append("schemaVersion must be 2 when the field is present.")
        return
    for field in V2_REQUIRED_FIELDS:
        if field not in front_matter or front_matter[field] == "":
            errors.append(f"Missing or empty schemaVersion 2 field: {field}")

    if front_matter.get("agentRole") not in V2_ROLES:
        errors.append(f"Invalid agentRole: {front_matter.get('agentRole')}")
    if front_matter.get("riskLevel") not in V2_RISKS:
        errors.append(f"Invalid riskLevel: {front_matter.get('riskLevel')}")
    if front_matter.get("coordinationMode") not in V2_MODES:
        errors.append(f"Invalid coordinationMode: {front_matter.get('coordinationMode')}")
    if front_matter.get("integrationStrategy") not in V2_INTEGRATION:
        errors.append(f"Invalid integrationStrategy: {front_matter.get('integrationStrategy')}")

    base_sha = front_matter.get("baseSha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        errors.append("baseSha must be a 40-character lowercase Git commit SHA.")

    handoff_path = front_matter.get("handoffPath", "")
    if handoff_path:
        normalized_evidence = evidence_path.rstrip("/") + "/"
        if not handoff_path.startswith(normalized_evidence):
            errors.append("handoffPath must be inside evidencePath.")
        if not os.path.isfile(os.path.join(repo_root, handoff_path)):
            errors.append(f"handoffPath does not exist: {handoff_path}")

    required_sections = [
        (["依赖与集成顺序", "dependencies and integration order"], "Missing dependencies/integration section."),
        (["独占写范围", "exclusive write scope"], "Missing exclusive write scope section."),
        (["共享修改范围", "shared modification scope"], "Missing shared modification scope section."),
        (["协作与交接", "collaboration and handoff"], "Missing collaboration/handoff section."),
    ]
    for names, message in required_sections:
        section = extract_section(body, names)
        if section is None:
            errors.append(message)
        elif not has_list_entry(section):
            errors.append(f"{message.rstrip('.')} must contain at least one bullet.")


def main():
    args = parse_args()
    repo_root = os.path.abspath(args.repo_root)
    task_id = args.task.strip()
    if not task_id:
        report("ERROR", "Task ID must not be empty.")
        sys.exit(2)

    task_path = find_task_file(repo_root, args.spec_dir, task_id)
    if not task_path:
        report("ERROR", f"Task file not found or ambiguous for {task_id}.")
        sys.exit(2)

    try:
        with open(task_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        report("ERROR", f"Cannot read task file: {exc}")
        sys.exit(2)

    front_matter, body = parse_front_matter(content)
    required_fields = ["id", "title", "titleZh", "type", "status", "baseBranch", "workBranch", "evidencePath"]
    errors = []
    warnings = []
    for field in required_fields:
        if field not in front_matter or not front_matter[field]:
            errors.append(f"Missing or empty front matter field: {field}")

    if not re.fullmatch(r"[A-Z]+-\d+", task_id):
        errors.append(f"Task ID format invalid: {task_id}")
    elif front_matter.get("id") != task_id:
        errors.append(f"Front matter id mismatch: expected {task_id}, got {front_matter.get('id')}")

    work_branch = front_matter.get("workBranch", "")
    expected_prefix = f"{front_matter.get('type', 'chore')}/{task_id}"
    if not work_branch.startswith(expected_prefix):
        errors.append(f"workBranch '{work_branch}' does not start with expected prefix '{expected_prefix}'")

    evidence_path = front_matter.get("evidencePath", "")
    if evidence_path:
        if not os.path.isdir(os.path.join(repo_root, evidence_path)):
            errors.append(f"Evidence path does not exist: {evidence_path}")
    else:
        errors.append("evidencePath is empty.")

    allowed = extract_section(body, ["允许范围", "allowed scope"])
    forbidden = extract_section(body, ["禁止范围", "forbidden scope"])
    acceptance = extract_section(body, ["验收标准", "acceptance criteria"])
    validation = extract_section(body, ["必须执行的测试", "validation commands"])

    if allowed is None:
        errors.append("Missing allowed scope section.")
    elif not has_list_entry(allowed):
        errors.append("Allowed scope section has no scope entries.")
    if forbidden is None:
        errors.append("Missing forbidden scope section.")
    elif not has_list_entry(forbidden):
        errors.append("Forbidden scope section has no entries.")
    if acceptance is None:
        errors.append("Missing acceptance criteria section.")
    elif not re.search(r"(?m)^\s*[-*]\s+\[[ xX]\]\s+\S", acceptance):
        errors.append("Acceptance criteria section must contain at least one checklist item.")
    if validation is None:
        errors.append("Missing validation commands section.")
    elif not has_validation_command(validation):
        errors.append("Validation commands section must contain at least one executable command.")

    if "schemaVersion" in front_matter:
        validate_v2(front_matter, body, repo_root, evidence_path, errors)
    else:
        warnings.append("Legacy Task Spec schemaVersion 1; multi-agent metadata is not enforced.")

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

#!/usr/bin/env python3
"""Validate a Guize task specification file."""

import argparse
import json
import os
import re
import sys
from datetime import datetime


V2_COMMON_FIELDS = [
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
V2_REGISTRY_FIELDS = [
    "coordinator",
    "implementer",
    "reviewer",
    "integrator",
    "integrationOrder",
    "leaseExpiresAt",
]
V2_ROLES = {"coordinator", "implementer", "reviewer", "integrator"}
V2_RISKS = {"low", "medium", "high", "critical"}
V2_MODES = {"bootstrap", "registry"}
V2_INTEGRATION = {"merge", "squash", "rebase"}
V2_REGISTRY_STATUSES = {"reserved", "in_progress", "blocked", "review", "integration", "completed", "cancelled"}
PLACEHOLDERS = {"", "pending", "tbd", "unknown", "none", "n/a", "na", "unassigned"}


def parse_args():
    parser = argparse.ArgumentParser(description="Validate a Guize task specification file.")
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-001")
    parser.add_argument("--spec-dir", default="specs/tasks")
    parser.add_argument("--repo-root", default=".")
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
    return candidates[0] if len(candidates) == 1 else None


def parse_front_matter(text):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    data = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, parts[2].strip()


def report(status, message, details=None):
    payload = {"status": status, "message": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False))


def extract_section(body, names):
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


def valid_datetime(value):
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed.tzinfo is not None
    except Exception:
        return False


def role_placeholder(value):
    return str(value or "").strip().lower() in PLACEHOLDERS


def validate_v2(front, body, repo_root, evidence_path, errors):
    if str(front.get("schemaVersion")) != "2":
        errors.append("schemaVersion must be 2 when the field is present.")
        return
    for field in V2_COMMON_FIELDS:
        if field not in front or front[field] == "":
            errors.append(f"Missing or empty schemaVersion 2 field: {field}")

    if front.get("agentRole") not in V2_ROLES:
        errors.append(f"Invalid agentRole: {front.get('agentRole')}")
    if front.get("riskLevel") not in V2_RISKS:
        errors.append(f"Invalid riskLevel: {front.get('riskLevel')}")
    if front.get("coordinationMode") not in V2_MODES:
        errors.append(f"Invalid coordinationMode: {front.get('coordinationMode')}")
    if front.get("integrationStrategy") not in V2_INTEGRATION:
        errors.append(f"Invalid integrationStrategy: {front.get('integrationStrategy')}")
    if not re.fullmatch(r"[0-9a-f]{40}", front.get("baseSha", "")):
        errors.append("baseSha must be a 40-character lowercase Git commit SHA.")

    handoff_path = front.get("handoffPath", "")
    if handoff_path:
        evidence_prefix = evidence_path.rstrip("/") + "/"
        if not handoff_path.startswith(evidence_prefix):
            errors.append("handoffPath must be inside evidencePath.")
        if not os.path.isfile(os.path.join(repo_root, handoff_path)):
            errors.append(f"handoffPath does not exist: {handoff_path}")

    mode = front.get("coordinationMode")
    if mode == "registry":
        for field in V2_REGISTRY_FIELDS:
            if field not in front or front[field] == "":
                errors.append(f"Missing or empty registry coordination field: {field}")
        if front.get("status") not in V2_REGISTRY_STATUSES:
            errors.append(f"Registry task has invalid status: {front.get('status')}")
        try:
            if int(front.get("integrationOrder", "0")) < 1:
                errors.append("integrationOrder must be a positive integer.")
        except ValueError:
            errors.append("integrationOrder must be a positive integer.")
        if not valid_datetime(front.get("leaseExpiresAt", "")):
            errors.append("leaseExpiresAt must be an ISO-8601 timestamp with timezone.")
        if front.get("riskLevel") in {"high", "critical"}:
            implementer = front.get("implementer", "")
            reviewer = front.get("reviewer", "")
            if role_placeholder(implementer) or role_placeholder(reviewer):
                errors.append("High/critical registry tasks require assigned implementer and reviewer identities.")
            elif implementer == reviewer:
                errors.append("High/critical registry tasks require different implementer and reviewer identities.")

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

    front, body = parse_front_matter(content)
    required_fields = ["id", "title", "titleZh", "type", "status", "baseBranch", "workBranch", "evidencePath"]
    errors = []
    warnings = []
    for field in required_fields:
        if field not in front or not front[field]:
            errors.append(f"Missing or empty front matter field: {field}")

    if not re.fullmatch(r"[A-Z]+-\d+", task_id):
        errors.append(f"Task ID format invalid: {task_id}")
    elif front.get("id") != task_id:
        errors.append(f"Front matter id mismatch: expected {task_id}, got {front.get('id')}")
    expected_prefix = f"{front.get('type', 'chore')}/{task_id}"
    if not front.get("workBranch", "").startswith(expected_prefix):
        errors.append(f"workBranch '{front.get('workBranch')}' does not start with expected prefix '{expected_prefix}'")

    evidence_path = front.get("evidencePath", "")
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

    if "schemaVersion" in front:
        validate_v2(front, body, repo_root, evidence_path, errors)
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

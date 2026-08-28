#!/usr/bin/env python3
"""Render a role-specific Guize multi-agent prompt from repository truth."""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import yaml


MAX_FILE_CHARS = 30_000
MAX_TOTAL_CONTEXT_CHARS = 140_000
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt"}

ROLE_RESPONSIBILITIES = {
    "integration-agent": (
        "Control dependency readiness, shared paths, integration order and full regression. "
        "Do not replace independent review or silently expand scope."
    ),
    "independent-review-agent": (
        "Review requirements, contracts, path ownership, tests, Evidence, Handoff and rollback. "
        "Do not act as implementation Owner for this task."
    ),
    "security-review-agent": (
        "Review authorization, public access, secrets, external connectivity, parser sandbox, "
        "audit and abuse cases."
    ),
    "operations-review-agent": (
        "Review deployment, observability, SLO, alerting, backup, recovery and rollback evidence."
    ),
    "requirements-agent": (
        "Freeze requirements, NFR, constraints, acceptance and traceability without inventing "
        "implementation details."
    ),
    "api-contract-agent": (
        "Define machine-valid OpenAPI, errors, examples, idempotency and compatibility before code."
    ),
    "event-contract-agent": (
        "Define event payloads, ownership, compatibility, replay and consumer idempotency."
    ),
    "data-contract-agent": (
        "Define PostgreSQL schema, constraints, migrations and recovery verification."
    ),
    "workflow-contract-agent": (
        "Define Temporal, LiteFlow, Task, Worker and failure semantics as executable contracts."
    ),
    "implementation-agent": (
        "Consume approved contracts, write only owned paths and stop when an upstream contract is "
        "missing or contradictory."
    ),
    "qa-agent": (
        "Derive independent positive, negative, permission, idempotency, fault and recovery tests."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Guize multi-agent task prompt")
    parser.add_argument("--task", required=True, help="Task ID, e.g. GZ-003")
    parser.add_argument("--role", default=None, help="Role from the task coordination descriptor")
    parser.add_argument("--output", required=True, help="Output Markdown path")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    return parser.parse_args()


def find_task_file(repo_root: Path, task_id: str) -> Optional[Path]:
    task_dir = repo_root / "specs" / "tasks"
    for candidate in (
        task_dir / f"{task_id}.md",
        task_dir / f"{task_id}-repository-baseline.md",
    ):
        if candidate.is_file():
            return candidate
    matches = sorted(task_dir.glob(f"{task_id}-*.md"))
    return matches[0] if matches else None


def parse_front_matter(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else {}


def load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return data


def bullets(values: Iterable[Any]) -> str:
    normalized = [str(value) for value in values]
    return "\n".join(f"- `{value}`" for value in normalized) if normalized else "- None"


def expand_paths(repo_root: Path, patterns: Sequence[str]) -> List[Path]:
    found: List[Path] = []
    seen: Set[Path] = set()
    for pattern in patterns:
        normalized = pattern.replace("\\", "/").lstrip("./")
        has_glob = any(token in normalized for token in ("*", "?", "["))
        candidates = (
            [Path(value) for value in glob.glob(str(repo_root / normalized), recursive=True)]
            if has_glob
            else [repo_root / normalized]
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            if not resolved.is_file() or resolved in seen:
                continue
            try:
                resolved.relative_to(repo_root)
            except ValueError:
                continue
            if resolved.suffix.lower() not in TEXT_SUFFIXES:
                continue
            seen.add(resolved)
            found.append(resolved)
    return sorted(found)


def read_context_file(repo_root: Path, path: Path) -> str:
    relative = path.relative_to(repo_root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > MAX_FILE_CHARS
    body = text[:MAX_FILE_CHARS]
    if truncated:
        body += "\n\n[TRUNCATED BY PROMPT RENDERER; read the repository file for the remainder.]"
    return f'<context path="{relative}">\n{body}\n</context>'


def dependency_context(repo_root: Path, dependencies: Sequence[str]) -> List[str]:
    contexts: List[str] = []
    for dependency in dependencies:
        path = repo_root / "evidence" / dependency / "handoff.md"
        if path.is_file():
            contexts.append(read_context_file(repo_root, path))
        else:
            contexts.append(
                f'<context path="evidence/{dependency}/handoff.md">\n'
                "NOT AVAILABLE. This dependency predates the multi-agent handoff contract or has "
                "not produced its handoff. Read its Task, PR and Evidence directly.\n</context>"
            )
    return contexts


def choose_role(descriptor: Dict[str, Any], requested: Optional[str]) -> str:
    roles = descriptor.get("roles", {})
    if not isinstance(roles, dict):
        raise ValueError("Coordination descriptor roles must be an object")
    allowed = {str(value) for value in roles.values() if str(value).strip()}
    if requested:
        if requested not in allowed:
            raise ValueError(
                f"Role '{requested}' is not declared by the coordination descriptor: {sorted(allowed)}"
            )
        return requested
    owner = str(roles.get("owner", "")).strip()
    if not owner:
        raise ValueError("Coordination descriptor does not declare roles.owner")
    return owner


def role_responsibility(role: str) -> str:
    return ROLE_RESPONSIBILITIES.get(
        role,
        "Follow the declared role boundary, repository authority order, Task Scope, Coordination "
        "Descriptor and Handoff contract. Do not infer missing authority.",
    )


def render(template: str, replacements: Dict[str, str]) -> str:
    output = template
    for key, value in replacements.items():
        output = output.replace("{{" + key + "}}", value)
    unresolved = sorted(
        token for token in set(part.split("}}", 1)[0] for part in output.split("{{")[1:]) if token
    )
    if unresolved:
        raise ValueError(f"Unresolved template placeholders: {unresolved}")
    return output


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_id = args.task.strip()
    task_file = find_task_file(repo_root, task_id)
    if task_file is None:
        print(f"ERROR: Task file not found for {task_id}", file=sys.stderr)
        return 2

    front_matter = parse_front_matter(task_file)
    coordination_value = str(front_matter.get("coordinationPath", "")).strip()
    if not coordination_value:
        print("ERROR: Task does not declare coordinationPath", file=sys.stderr)
        return 2
    coordination_path = repo_root / coordination_value
    if not coordination_path.is_file():
        print(f"ERROR: Coordination descriptor not found: {coordination_path}", file=sys.stderr)
        return 2

    try:
        descriptor = load_yaml(coordination_path)
        role = choose_role(descriptor, args.role)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    template_path = repo_root / "prompts" / "templates" / "multi-agent-task-execution.md"
    if not template_path.is_file():
        print(f"ERROR: Prompt template not found: {template_path}", file=sys.stderr)
        return 2

    paths = descriptor.get("paths", {}) if isinstance(descriptor.get("paths"), dict) else {}
    contracts = (
        descriptor.get("contracts", {}) if isinstance(descriptor.get("contracts"), dict) else {}
    )
    dependencies = [str(value) for value in descriptor.get("dependencies", [])]

    mandatory_paths = [
        repo_root / "AGENTS.md",
        repo_root / "rules" / "never-rules.md",
        task_file,
        repo_root / "specs" / "collaboration" / "README.md",
        coordination_path,
    ]
    input_paths = expand_paths(repo_root, [str(value) for value in contracts.get("inputs", [])])

    contexts: List[str] = []
    total_chars = 0
    seen: Set[Path] = set()
    for path in [*mandatory_paths, *input_paths]:
        resolved = path.resolve()
        if not resolved.is_file() or resolved in seen:
            continue
        seen.add(resolved)
        block = read_context_file(repo_root, resolved)
        if total_chars + len(block) > MAX_TOTAL_CONTEXT_CHARS:
            contexts.append(
                f'<context path="{resolved.relative_to(repo_root).as_posix()}">\n'
                "OMITTED BY CONTEXT BUDGET. Read this repository file before modifying its domain.\n"
                "</context>"
            )
            continue
        contexts.append(block)
        total_chars += len(block)

    for block in dependency_context(repo_root, dependencies):
        if total_chars + len(block) > MAX_TOTAL_CONTEXT_CHARS:
            break
        contexts.append(block)
        total_chars += len(block)

    replacements = {
        "TASK_ID": task_id,
        "ROLE": role,
        "BASE_COMMIT": str(descriptor.get("baseCommit", "")),
        "WORK_BRANCH": str(front_matter.get("workBranch", "")),
        "COORDINATION_MODE": str(descriptor.get("mode", "")),
        "EXCLUSIVE_PATHS": bullets(paths.get("exclusive", [])),
        "SHARED_PATHS": bullets(paths.get("shared", [])),
        "DEPENDENCIES": bullets(dependencies),
        "CONTRACT_INPUTS": bullets(contracts.get("inputs", [])),
        "CONTRACT_OUTPUTS": bullets(contracts.get("outputs", [])),
        "ROLE_RESPONSIBILITY": role_responsibility(role),
        "HANDOFF_PATH": str(descriptor.get("handoff", {}).get("path", "")),
        "EMBEDDED_CONTEXT": "\n\n".join(contexts),
    }

    try:
        rendered = render(template_path.read_text(encoding="utf-8"), replacements)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = (repo_root / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered.rstrip() + "\n", encoding="utf-8")
    print(
        f"OK: rendered {task_id} role={role} to {output_path} "
        f"with {len(contexts)} context blocks"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

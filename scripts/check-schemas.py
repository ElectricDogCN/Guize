#!/usr/bin/env python3
"""Validate workflow YAML, JSON/YAML schemas and declared schema instances."""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any

import jsonschema
import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Guize YAML/JSON schemas and contract documents")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    return parser.parse_args()


def load_document(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        if path.endswith(".json"):
            return json.load(handle)
        return yaml.safe_load(handle)


def validate_schema_document(path: str, root: str, errors: list[str]) -> None:
    relpath = os.path.relpath(path, root)
    try:
        document = load_document(path)
        if not isinstance(document, dict):
            raise ValueError("schema root must be a mapping")
        validator_cls = jsonschema.validators.validator_for(document)
        validator_cls.check_schema(document)
        print(f"OK JSON-SCHEMA: {relpath}")
    except Exception as exc:
        errors.append(f"{relpath}: {exc}")


def validate_instance(instance_path: str, schema_path: str, root: str, errors: list[str]) -> None:
    rel_instance = os.path.relpath(instance_path, root)
    rel_schema = os.path.relpath(schema_path, root)
    try:
        instance = load_document(instance_path)
        schema = load_document(schema_path)
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        failures = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
        if failures:
            for failure in failures:
                location = "/".join(str(part) for part in failure.absolute_path) or "<root>"
                errors.append(f"{rel_instance} violates {rel_schema} at {location}: {failure.message}")
        else:
            print(f"OK SCHEMA INSTANCE: {rel_instance} <- {rel_schema}")
    except Exception as exc:
        errors.append(f"{rel_instance} / {rel_schema}: {exc}")


def main() -> None:
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors: list[str] = []

    workflow_files = glob.glob(os.path.join(root, ".github", "workflows", "*.yml"))
    workflow_files += glob.glob(os.path.join(root, ".github", "workflows", "*.yaml"))
    for path in sorted(workflow_files):
        try:
            load_document(path)
            print(f"OK YAML: {os.path.relpath(path, root)}")
        except Exception as exc:
            errors.append(f"{os.path.relpath(path, root)}: {exc}")

    contract_files = glob.glob(os.path.join(root, "contracts", "**", "*.json"), recursive=True)
    contract_files += glob.glob(os.path.join(root, "contracts", "**", "*.yaml"), recursive=True)
    contract_files += glob.glob(os.path.join(root, "contracts", "**", "*.yml"), recursive=True)
    for path in sorted(set(contract_files)):
        relpath = os.path.relpath(path, root)
        try:
            document = load_document(path)
            if isinstance(document, dict) and "$schema" in document:
                validator_cls = jsonschema.validators.validator_for(document)
                validator_cls.check_schema(document)
                print(f"OK JSON-SCHEMA: {relpath}")
            else:
                print(f"OK CONTRACT DOCUMENT: {relpath}")
        except Exception as exc:
            errors.append(f"{relpath}: {exc}")

    coordination_dir = os.path.join(root, "specs", "coordination")
    coordination_schemas = glob.glob(os.path.join(coordination_dir, "*.schema.yaml"))
    coordination_schemas += glob.glob(os.path.join(coordination_dir, "*.schema.yml"))
    coordination_schemas += glob.glob(os.path.join(coordination_dir, "*.schema.json"))
    for path in sorted(set(coordination_schemas)):
        validate_schema_document(path, root, errors)

    declared_instances = [
        (os.path.join(coordination_dir, "active-work.yaml"), os.path.join(coordination_dir, "active-work.schema.yaml")),
        (os.path.join(coordination_dir, "program-plan.yaml"), os.path.join(coordination_dir, "program-plan.schema.yaml")),
    ]
    for instance_path, schema_path in declared_instances:
        if not os.path.isfile(instance_path):
            errors.append(f"{os.path.relpath(instance_path, root)}: instance file is missing")
            continue
        if not os.path.isfile(schema_path):
            errors.append(f"{os.path.relpath(schema_path, root)}: schema file is missing")
            continue
        validate_instance(instance_path, schema_path, root, errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        sys.exit(1)

    print("OK: Schema validation completed")
    sys.exit(0)


if __name__ == "__main__":
    main()

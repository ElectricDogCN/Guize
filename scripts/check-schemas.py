#!/usr/bin/env python3
"""Validate workflow YAML and contract schema documents."""

import argparse
import glob
import json
import os
import sys

import jsonschema
import yaml


def parse_args():
    parser = argparse.ArgumentParser(description="Validate Guize YAML/JSON schemas and contract documents")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    return parser.parse_args()


def load_document(path):
    with open(path, "r", encoding="utf-8") as handle:
        if path.endswith(".json"):
            return json.load(handle)
        return yaml.safe_load(handle)


def main():
    args = parse_args()
    root = os.path.abspath(args.repo_root)
    errors = []

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

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        sys.exit(1)

    print("OK: Schema validation completed")
    sys.exit(0)


if __name__ == "__main__":
    main()

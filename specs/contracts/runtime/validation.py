"""Shared offline readers for the versioned runtime contract fixtures."""

import json

from jsonschema import Draft202012Validator, FormatChecker
import yaml


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate configuration field {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_mapping)


def validate_shape(path, value):
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if error := next(validator.iter_errors(value), None):
        location = ".".join(map(str, error.absolute_path)) or "root"
        raise ValueError(f"{location}: {error.message}")

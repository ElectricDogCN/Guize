"""Shared offline readers for the versioned runtime contract fixtures."""

from datetime import datetime
import json
import re

from jsonschema import Draft202012Validator, FormatChecker
import yaml

FORMATS = FormatChecker()
TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


@FORMATS.checks("date-time", raises=ValueError)
def is_timestamp(value):
    # jsonschema supplies this format only when its optional dependencies are installed.
    if not isinstance(value, str):
        return True
    if not TIMESTAMP.fullmatch(value):
        return False
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return True


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate configuration field {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_mapping)


def validate_shape(path, value, definition=None):
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    if definition is not None:
        schema = {key: schema[key] for key in ("$schema", "$defs")} | {"$ref": "#/$defs/" + definition}
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FORMATS)
    if error := next(validator.iter_errors(value), None):
        location = ".".join(map(str, error.absolute_path)) or "root"
        raise ValueError(f"{location}: {error.message}")

"""Validate versioned domain events offline."""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[3]
BASE = 'https://guize.local/contracts/events/'
ENVELOPE_ID = BASE + 'event-envelope.schema.json'
CORE = frozenset({
    'source.object.observed', 'source.object.deleted', 'asset.created', 'asset.version.created',
    'cache.complete.verified', 'replica.verified', 'rendition.published', 'artifact.published',
    'task.status.changed', 'policy.published',
})
EXECUTION_EVENTS = frozenset({
    'task.plan.accepted',
    'task.step.ready',
    'task.attempt.leased',
    'task.attempt.cancellation.requested',
    'task.attempt.cancelled',
    'task.attempt.result.accepted',
    'task.attempt.capability.bound',
    'task.resource.reserved',
    'task.resource.released',
})
FACT_TIMES = (
    'observedAt', 'deletedAt', 'createdAt', 'publishedAt', 'changedAt',
    'acceptedAt', 'readyAt', 'leasedAt', 'requestedAt', 'cancelledAt',
    'boundAt', 'reservedAt', 'releasedAt',
)
CATALOG_FIELDS = (
    'eventType', 'eventVersion', 'aggregateType', 'aggregateKey', 'revisionKey',
    'producer', 'producerModule', 'consumers', 'schema',
    'compatibility', 'idempotency', 'authorization', 'semantics',
)
IMMUTABLE_METADATA = (
    'aggregateType', 'aggregateKey', 'revisionKey', 'producer', 'producerModule',
    'semantics', 'compatibility', 'idempotency', 'authorization',
)
EVENT_TIME = re.compile(
    r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}'
    r'(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])'
)


class ContractViolation(ValueError):
    def __init__(self, code, path=''):
        self.code = code
        self.path = path
        super().__init__(code + (' at ' + path if path else ''))


def parse_event_time(value):
    if not isinstance(value, str) or EVENT_TIME.fullmatch(value) is None:
        raise ValueError('invalid event timestamp')
    return datetime.fromisoformat(value.upper().replace('Z', '+00:00'))


def event_format_checker():
    checker = FormatChecker()

    @checker.checks('date-time')
    def date_time(value):
        if not isinstance(value, str):
            return True
        try:
            parse_event_time(value)
        except ValueError:
            return False
        return True

    return checker


def read(path):
    def reject_constant(value):
        raise ContractViolation('CONTRACT_NONFINITE_JSON_NUMBER')

    try:
        return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant)
    except json.JSONDecodeError:
        raise ContractViolation('CONTRACT_INVALID_JSON') from None


def contained(folder, relative):
    if not isinstance(relative, str):
        raise ContractViolation('CATALOG_INVALID_PATH')
    path = (folder / relative).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise ContractViolation('CATALOG_INVALID_PATH')
    return path


def check_schema_dependencies(schema, supported_external):
    """The version owns its local definitions and can reference the frozen Envelope."""
    if isinstance(schema, list):
        for entry in schema:
            check_schema_dependencies(entry, supported_external)
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        if key in ('$ref', '$dynamicRef'):
            if not isinstance(value, str) or not (value.startswith('#') or value in supported_external):
                raise ContractViolation('CATALOG_UNREGISTERED_SCHEMA_REFERENCE')
        elif isinstance(value, (dict, list)):
            check_schema_dependencies(value, supported_external)


class EventContracts:
    def __init__(self, root=ROOT, *, historical=False):
        self.root = Path(root)
        self.folder = self.root / 'contracts/events'
        self.catalog = read(self.folder / 'catalog.json')
        self.entries = {}
        self.schemas = {}
        self.envelope = read(self.folder / 'event-envelope.schema.json')
        Draft202012Validator.check_schema(self.envelope)
        if self.envelope.get('$id') != ENVELOPE_ID:
            raise ContractViolation('CATALOG_ENVELOPE_ID_MISMATCH')
        check_schema_dependencies(self.envelope, ())
        resources = [(ENVELOPE_ID, Resource.from_contents(self.envelope))]
        for entry in self.catalog['events']:
            key, schema = self.read_registered_schema(entry)
            self.entries[key] = entry
            self.schemas[key] = schema
            resources.append((schema['$id'], Resource.from_contents(schema)))
        required = CORE if historical else CORE | EXECUTION_EVENTS
        if not required.issubset(name for name, version in self.entries if version == 1):
            raise ContractViolation('CATALOG_INCOMPLETE')

        registry = Registry().with_resources(resources)
        formats = event_format_checker()
        self.validators = {
            key: Draft202012Validator(schema, registry=registry, format_checker=formats)
            for key, schema in self.schemas.items()
        }

    def read_registered_schema(self, entry):
        if not isinstance(entry, dict) or not all(key in entry for key in CATALOG_FIELDS):
            raise ContractViolation('CATALOG_MISSING_METADATA')
        name, version = entry['eventType'], entry['eventVersion']
        key = (name, version)
        if not isinstance(name, str) or name not in CORE | EXECUTION_EVENTS:
            raise ContractViolation('CATALOG_INVALID_IDENTITY')
        if type(version) is not int or version < 1 or key in self.entries:
            raise ContractViolation('CATALOG_INVALID_IDENTITY')
        consumers = entry['consumers']
        if (not isinstance(consumers, list) or not consumers
                or not all(isinstance(module, str) for module in consumers)
                or len(consumers) != len(set(consumers))):
            raise ContractViolation('CATALOG_INVALID_CONSUMERS')
        path = contained(self.folder, entry['schema'])
        if name in EXECUTION_EVENTS and (
            entry['producerModule'] != 'MOD-TASK'
            or entry['producer'] != 'guize-control'
            or set(consumers) != {'MOD-AUDIT', 'MOD-OBS'}
            or path.parent != (self.folder / 'task').resolve()
        ):
            raise ContractViolation('CATALOG_INVALID_EXECUTION_OWNERSHIP')
        schema = read(path)
        Draft202012Validator.check_schema(schema)
        if schema.get('$id') != BASE + entry['schema']:
            raise ContractViolation('CATALOG_SCHEMA_ID_MISMATCH')
        check_schema_dependencies(schema, (ENVELOPE_ID,))
        try:
            envelope_ref, event_schema = schema['allOf']
            props = event_schema['properties']
            required = props['payload']['required']
        except (KeyError, TypeError, ValueError):
            raise ContractViolation('CATALOG_INVALID_SCHEMA_SHAPE') from None
        if envelope_ref != {'$ref': ENVELOPE_ID}:
            raise ContractViolation('CATALOG_ENVELOPE_REFERENCE_MISMATCH')
        for field in ('eventType', 'eventVersion', 'aggregateType', 'producer'):
            if not same_json(props.get(field, {}).get('const'), entry[field]):
                raise ContractViolation('CATALOG_SCHEMA_IDENTITY_MISMATCH', field)
        if entry['aggregateKey'] not in required or entry['revisionKey'] not in required:
            raise ContractViolation('CATALOG_MISSING_AGGREGATE_BINDING')
        return key, schema

    def validate(self, event):
        if not isinstance(event, dict):
            raise ContractViolation('EVENT_INVALID_ENVELOPE')
        name, version = event.get('eventType'), event.get('eventVersion')
        if not isinstance(name, str) or type(version) is not int:
            raise ContractViolation('EVENT_INVALID_IDENTITY')
        key = (name, version)
        if key not in self.validators:
            raise ContractViolation('EVENT_UNSUPPORTED_VERSION')
        error = next(self.validators[key].iter_errors(event), None)
        if error:
            raise ContractViolation('EVENT_SCHEMA_INVALID', '/'.join(map(str, error.absolute_path)))

        entry = self.entries[key]
        payload = event['payload']
        for field in ('confidence', 'progress'):
            if field in payload and not math.isfinite(payload[field]):
                raise ContractViolation('EVENT_NONFINITE_NUMBER', field)
        if event['aggregateId'] != payload[entry['aggregateKey']]:
            raise ContractViolation('EVENT_AGGREGATE_MISMATCH')
        if name in {'cache.complete.verified', 'replica.verified'}:
            verification = payload['verification']
            if verification['expectedHash'] != verification['actualHash']:
                raise ContractViolation('EVENT_FULL_HASH_MISMATCH')
        if name == 'task.status.changed' and payload['previousStatus'] == payload['status']:
            raise ContractViolation('EVENT_STATUS_UNCHANGED')

        occurred = parse_event_time(event['occurredAt'])
        for field in FACT_TIMES:
            if field in payload and parse_event_time(payload[field]) > occurred:
                raise ContractViolation('EVENT_FACT_AFTER_OCCURRENCE', field)
        if 'verification' in payload:
            if parse_event_time(payload['verification']['verifiedAt']) > occurred:
                raise ContractViolation('EVENT_FACT_AFTER_OCCURRENCE', 'verification/verifiedAt')
        if name in {'task.attempt.leased', 'task.resource.reserved'}:
            if parse_event_time(payload['expiresAt']) <= occurred:
                raise ContractViolation('EVENT_EXPIRES_BEFORE_OR_AT_OCCURRENCE', 'expiresAt')
        return entry


def same_json(left, right):
    """Compare JSON types as well as values, independently of object key order."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def compare_versions(previous, current):
    """Keep existing effective schemas and meaning immutable across releases."""
    if not same_json(previous.envelope, current.envelope):
        raise ContractViolation('EVENT_ENVELOPE_MUTATED')
    for key, entry in previous.entries.items():
        if key not in current.entries:
            raise ContractViolation('EVENT_VERSION_REMOVED')
        if not same_json(previous.schemas[key], current.schemas[key]):
            raise ContractViolation('EVENT_VERSION_MUTATED')
        if any(not same_json(entry[field], current.entries[key][field]) for field in IMMUTABLE_METADATA):
            raise ContractViolation('EVENT_VERSION_SEMANTICS_MUTATED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--event', type=Path)
    parser.add_argument('--previous-root', type=Path)
    args = parser.parse_args()
    try:
        contracts = EventContracts(args.root)
        if args.previous_root:
            compare_versions(EventContracts(args.previous_root, historical=True), contracts)
        if args.event:
            contracts.validate(read(args.event))
        else:
            for name, version in contracts.entries:
                sample = args.root / 'specs/contracts/events/examples' / f'{name}-v{version}.json'
                contracts.validate(read(sample))
        print(f'PASS: {len(contracts.entries)} registered event versions; no business execution')
        return 0
    except ContractViolation as error:
        print(f'FAIL: {error}')
        return 1


if __name__ == '__main__':
    sys.exit(main())

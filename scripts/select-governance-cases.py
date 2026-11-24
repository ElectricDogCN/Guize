#!/usr/bin/env python3
"""Partition the complete pytest collection into balanced file groups."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zlib


SHARD_COUNT = 3
EXPENSIVE_FILES = {
    'test_poc_contract_repair_admission.py': 0,
    'test_program_plan_history.py': 1,
    'test_program_schema_cache.py': 1,
    'test_program_planning_revision.py': 2,
    'test_work_branch_migration.py': 2,
    'test_active_metadata_scope.py': 2,
    'test_program_lifecycle_guards.py': 2,
}


def load_collection(collection: Path) -> list[str]:
    lines = collection.read_text(encoding='utf-8-sig').splitlines()
    cases = [line for line in lines if line.startswith('tests/governance/') and '::' in line]
    totals = [int(match[1]) for line in lines if (match := re.fullmatch(r'(\d+) tests? collected(?: in .+)?', line))]
    if totals != [len(cases)] or not cases or len(set(cases)) != len(cases):
        raise ValueError('pytest collection is missing, ambiguous, or incomplete')

    return cases


def assigned_shard(case: str) -> int:
    path = case.split('::', 1)[0]
    assigned = EXPENSIVE_FILES.get(Path(path).name)
    return zlib.crc32(path.encode('utf-8')) % SHARD_COUNT if assigned is None else assigned


def select_cases(collection: Path, shard: int) -> list[str]:
    selected = [case for case in load_collection(collection) if assigned_shard(case) == shard]
    if not selected:
        raise ValueError(f'pytest shard {shard} is empty')
    return selected


def junit_identity(case: str) -> tuple[str, str]:
    file, qualified = case.split('::', 1)
    name, bracket, parameters = qualified.partition('[')
    classes = name.split('::')
    module = file.removesuffix('.py').replace('/', '.')
    return '.'.join([module, *classes[:-1]]), classes[-1] + bracket + parameters


def verify_report(selected: list[str], report: Path) -> None:
    expected = Counter(junit_identity(case) for case in selected)
    observed = Counter((row.get('classname'), row.get('name')) for row in ET.parse(report).iter('testcase'))
    if expected != observed:
        missing = sum((expected - observed).values())
        unexpected = sum((observed - expected).values())
        raise ValueError(f'pytest report has {missing} missing and {unexpected} unexpected cases')


def collection_digest(cases: list[str]) -> str:
    return hashlib.sha256('\n'.join(sorted(cases)).encode('utf-8')).hexdigest()


def verify_receipts(directory: Path, commit: str, attempt: int) -> int:
    complete = []
    inventories = set()
    for shard in range(SHARD_COUNT):
        path = directory / f'governance-shard-{attempt}-{shard}' / 'result.json'
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if (receipt['commit'], receipt['attempt'], receipt['shard']) != (commit, attempt, shard):
            raise ValueError(f'wrong commit, attempt, or identity in shard {shard}')
        cases = receipt['cases']
        if not cases or any(assigned_shard(case) != shard for case in cases):
            raise ValueError(f'incomplete case allocation in shard {shard}')
        complete.extend(cases)
        inventories.add(receipt['collectionSha256'])
    if len(complete) != len(set(complete)) or inventories != {collection_digest(complete)}:
        raise ValueError('shard receipts do not cover the same complete collection exactly once')
    return len(complete)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='action', required=True)
    select = subparsers.add_parser('select')
    audit = subparsers.add_parser('audit')
    combine = subparsers.add_parser('combine')
    for subparser in (select, audit):
        subparser.add_argument('collection', type=Path)
        subparser.add_argument('shard', type=int, choices=range(SHARD_COUNT))
    audit.add_argument('report', type=Path)
    audit.add_argument('receipt', type=Path)
    audit.add_argument('commit')
    audit.add_argument('attempt', type=int)
    combine.add_argument('receipts', type=Path)
    combine.add_argument('commit')
    combine.add_argument('attempt', type=int)
    args = parser.parse_args()
    try:
        if args.action == 'combine':
            print(f'All {verify_receipts(args.receipts, args.commit, args.attempt)} cases covered exactly once')
        else:
            selected = select_cases(args.collection, args.shard)
            if args.action == 'select':
                print('\n'.join(selected))
            else:
                verify_report(selected, args.report)
                result = dict(commit=args.commit, attempt=args.attempt, shard=args.shard, cases=selected,
                              collectionSha256=collection_digest(load_collection(args.collection)))
                args.receipt.write_text(json.dumps(result, ensure_ascii=False) + '\n', encoding='utf-8')
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()

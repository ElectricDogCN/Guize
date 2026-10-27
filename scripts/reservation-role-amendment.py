#!/usr/bin/env python3
"""Prove the two prospective POC actor transactions without creating aliases."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import re
import subprocess
import tempfile

import yaml

PLAN = 'specs/coordination/program-plan.yaml'
ACTIVE = 'specs/coordination/active-work.yaml'
LEDGER = 'specs/coordination/task-completions.yaml'
OWNER = 'OPS-015'
REGISTRATION = '36d8ba69581c98ab15559e5a4a7f6281435d327f'
RESERVATION_SOURCE = '8b2cfa1aebdcd301d5f8ced698c0014e250d1074'
ORIGINAL_BASE = '746e23e582501fa08380c3f3301bdc1774902f7c'
INTENT = 'evidence/OPS-015/reservation-intent.json'
FIELDS = frozenset({'implementer', 'reviewer'})
CLAIMS = frozenset({
    'scripts/check-program-plan-transitions.py',
    'scripts/check-program-plan-history.py',
    'scripts/reservation-role-amendment.py',
    'tests/governance/test_reservation_role_amendment.py',
    'rules/reservation-role-amendment.md',
})


class AmendmentError(ValueError):
    pass


def require(value, message):
    if not value:
        raise AmendmentError(message)


def git(root, *args, missing=False):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if result.returncode:
        if missing:
            return None
        raise AmendmentError('Cannot inspect actor amendment Git history: '+str(args[:2]))
    return result.stdout


def resolve(root, ref):
    return git(root, 'rev-parse', '--verify', ref+'^{commit}').decode().strip()


def blob(root, ref, path, *, missing=False):
    return git(root, 'show', ref+':'+path, missing=missing)


def document(root, ref, path):
    value = yaml.safe_load(blob(root, ref, path))
    require(isinstance(value, dict), 'Actor amendment requires a mapping: '+path)
    return value


def rows(document, field='tasks'):
    result = {}
    require(isinstance(document.get(field), list), 'Actor amendment requires a task list')
    for row in document[field]:
        require(isinstance(row, dict) and isinstance(row.get('taskId'), str)
                and row['taskId'] not in result, 'Invalid or duplicate actor task identity')
        result[row['taskId']] = row
    return result


def actors(row):
    return {key: row.get(key) for key in sorted(FIELDS)}


def without_actors(row):
    return {key: value for key, value in row.items() if key not in FIELDS}


def parents(root, ref):
    return git(root, 'show', '-s', '--format=%P', ref).decode().split()


def changed(root, before, after):
    return set(git(root, 'diff', '--name-only', '--no-renames', before, after).decode().splitlines())


def chain(root, ref):
    return git(root, 'rev-list', '--first-parent', '--reverse', ref).decode().split()


def ancestor(root, before, after):
    return subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', before, after],
                          capture_output=True).returncode == 0


def instant(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
            'Actor approval requires an explicit UTC timestamp')
    return parsed


def commit_time(root, ref):
    return datetime.fromtimestamp(int(git(root, 'show', '-s', '--format=%ct', ref)), timezone.utc)


@lru_cache(maxsize=128)
def authority(root, admitted):
    """Only the original main reservation followed by normal main completion."""
    canonical = chain(root, admitted)
    require(REGISTRATION in canonical, 'Actor mechanism reservation is not admitted main history')
    require(parents(root, REGISTRATION) == [ORIGINAL_BASE, RESERVATION_SOURCE],
            'Actor mechanism original reservation graph differs')
    original = blob(root, REGISTRATION, INTENT)
    intent = json.loads(original)
    require(intent['taskId'] == OWNER and intent['sourceMain'] == ORIGINAL_BASE
            and intent['targetTasks'] == ['POC-003', 'POC-005']
            and set(intent['mutableActorFields']) == FIELDS
            and set(intent['implementationPaths']) == CLAIMS
            and intent['oldExecutionAliasOrQualificationTransferAllowed'] is False,
            'Original actor authority intent differs')
    registered = rows(document(root, REGISTRATION, ACTIVE))[OWNER]
    require(registered['status'] == 'reserved' and registered['riskLevel'] == 'high'
            and registered['moduleIds'] == ['MOD-GOV'] and set(registered['exclusivePaths']) == CLAIMS
            and registered['sharedPaths'] == [] and registered['implementer'] == '/root'
            and registered['reviewer'] == '/root/gz022_planning_independent_review',
            'Actor mechanism lacks its original independent registration')
    current = document(root, admitted, PLAN)
    require(current['status'] == 'active', 'Frozen Program cannot amend actors')
    completed = rows(current, 'foundationTasks').get(OWNER, {})
    require(completed.get('status') == 'completed' and OWNER not in rows(document(root, admitted, ACTIVE)),
            'Actor mechanism must normally complete and release capacity first')
    implementation = completed.get('mergeCommit')
    require(implementation in canonical and canonical.index(implementation) > canonical.index(REGISTRATION),
            'Actor implementation must be integrated after the real reservation')
    implementation_paths = changed(root, parents(root, implementation)[0], implementation)
    require(CLAIMS & implementation_paths, 'Actor mechanism has no nonempty registered implementation')
    # A real incremental rework need not rewrite every original path. Net
    # coverage still excludes paths touched and then restored to registration.
    cumulative_paths = changed(root, REGISTRATION, implementation)
    require(CLAIMS <= cumulative_paths, 'Actor mechanism has no complete registered implementation')
    reference = completed.get('completionRef', '')
    require(re.fullmatch(r'PR-[1-9][0-9]*', reference) is not None
            and OWNER in git(root, 'show', '-s', '--format=%B', implementation).decode()
            and '#'+reference[3:] in git(root, 'show', '-s', '--format=%B', implementation).decode(),
            'Actor implementation identity does not bind its real PR')
    reviewed = False
    finished = False
    for node in canonical[canonical.index(REGISTRATION):]:
        require(blob(root, node, INTENT) == original, 'Original actor intent changed in main history')
        plan = document(root, node, PLAN)
        state = rows(plan, 'foundationTasks').get(OWNER, {})
        live = rows(document(root, node, ACTIVE)).get(OWNER)
        if state.get('status') in {'review', 'integration'}:
            require(live is not None and live['implementer'] == registered['implementer']
                    and live['reviewer'] == registered['reviewer']
                    and live['agentRole'] in {'reviewer', 'integrator'}
                    and ancestor(root, implementation, node), 'Actor mechanism has no independent integrated Review')
            reviewed = True
        if state.get('status') == 'completed' and not finished:
            require(reviewed and state == completed and live is None,
                    'Actor mechanism did not normally complete after Review')
            prior = parents(root, node)[0]
            require(rows(document(root, prior, PLAN), 'foundationTasks')[OWNER]['status'] in {'review', 'integration'},
                    'Actor completion requires a real preceding Review')
            allowed = {PLAN, ACTIVE, 'specs/tasks/'+OWNER+'.md'}
            require(all(path in allowed or path.startswith('evidence/'+OWNER+'/')
                        for path in changed(root, prior, node)), 'Actor completion contains implementation')
            finished = True
    require(finished, 'Actor mechanism has no actual main completion')
    return intent


def replace_lines(raw, old, new, indent=b''):
    for key in sorted(FIELDS):
        pattern = rb'^'+indent+key.encode()+rb': '+re.escape(str(old[key]).encode())+rb'(?=\r?$)'
        raw, count = re.subn(pattern, indent+key.encode()+b': '+new[key].encode(), raw, flags=re.M)
        require(count == 1, 'Actor scalar line is missing, quoted or duplicated: '+key)
    return raw


def task_replacement(raw, old, new):
    parts = raw.split(b'---', 2)
    require(len(parts) == 3 and parts[0] == b'', 'Actor Task requires front matter')
    return b'---'+replace_lines(parts[1], old, new)+b'---'+parts[2]


def task_actors(raw):
    parts = raw.split(b'---', 2)
    require(len(parts) == 3 and parts[0] == b'', 'Actor Task requires front matter')
    result = {}
    for key in sorted(FIELDS):
        values = re.findall(rb'^'+key.encode()+rb': ([^\r\n]+)\r?$', parts[1], re.M)
        require(len(values) == 1, 'Actor Task field is missing or duplicated: '+key)
        result[key] = values[0].decode('utf-8')
    return result


def registry_replacement(raw, task, old, new):
    marker = ('- taskId: '+task).encode()
    starts = list(re.finditer(rb'^'+re.escape(marker)+rb'(?=\r?$)', raw, re.M))
    require(len(starts) == 1, 'Actor Registry target must be unique')
    start = starts[0].start()
    following = re.search(rb'^- taskId:', raw[starts[0].end():], re.M)
    end = starts[0].end()+following.start() if following else len(raw)
    return raw[:start]+replace_lines(raw[start:end], old, new, b'  ')+raw[end:]


def mode_blob(root, ref, path):
    raw = git(root, 'ls-tree', '-z', ref, '--', path)
    if not raw:
        return None
    mode, _, sha = raw.split(b'\t', 1)[0].split()
    return mode.decode(), sha.decode()


def strict_transaction(root, before, after, target, admitted):
    intent = authority(root, admitted)
    require(target in intent['targetTasks'], 'No actor amendment authority for this task')
    old = dict(zip(('implementer', 'reviewer'), intent['oldProgramRoleValues']))
    new = intent['futureActualActors'][target]
    prior, current = document(root, before, ACTIVE), document(root, after, ACTIVE)
    left, right = rows(prior).get(target), rows(current).get(target)
    require(left is not None and right is not None and actors(left) == old and actors(right) == new
            and left['status'] == right['status'] == 'reserved', 'Actor amendment must be the declared reserved pair')
    require(new['implementer'] != new['reviewer'] and not set(new.values()) & set(old.values()),
            'Actor amendment requires concrete independent identities')
    for path in (PLAN, LEDGER):
        require(blob(root, before, path) == blob(root, after, path), 'Actor amendment changed '+path)
    require(document(root, before, PLAN)['status'] == 'active', 'Frozen actor changes are forbidden')
    require(blob(root, after, ACTIVE) == registry_replacement(blob(root, before, ACTIVE), target, old, new),
            'Actor amendment changed other Registry bytes or stable fields')
    task_path = 'specs/tasks/'+target+'.md'
    require(blob(root, after, task_path) == task_replacement(blob(root, before, task_path), old, new),
            'Actor amendment changed other Task bytes')
    for path in (ACTIVE, task_path):
        require(mode_blob(root, before, path)[0] == mode_blob(root, after, path)[0] == '100644',
                'Actor amendment changed a metadata file mode')
    prefix = 'evidence/'+target+'/actor-amendment-v1/'
    approval_path = prefix+'approval.json'
    raw = blob(root, after, approval_path)
    require(mode_blob(root, after, approval_path)[0] == '100644', 'Actor approval must be regular metadata')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate actor approval field')
            result[key] = value
        return result
    record = json.loads(raw, object_pairs_hook=unique)
    require(set(record) == {'schemaVersion', 'kind', 'taskId', 'admittedMain', 'oldActors', 'newActors',
                            'reviewer', 'approvedAt', 'decision'} and record['schemaVersion'] == 1
            and type(record['schemaVersion']) is int
            and record['kind'] == 'prospective_poc_actor_amendment' and record['taskId'] == target
            and record['oldActors'] == old and record['newActors'] == new
            and record['reviewer'] == new['reviewer'] and record['decision'] == 'approved',
            'Actor approval does not bind the exact independent prospective transaction')
    baseline = record['admittedMain']
    require(baseline in chain(root, admitted) and authority(root, baseline)
            and rows(document(root, baseline, ACTIVE)).get(target) == left
            and blob(root, baseline, task_path) == blob(root, before, task_path),
            'Actor approval baseline is not the admitted unchanged reservation')
    when = instant(record['approvedAt'])
    acquired, expires = (instant(left['lease'][key]) for key in ('acquiredAt', 'expiresAt'))
    # Git timestamps have whole-second precision; the preceding-commit proof
    # below supplies causal ordering within that second.
    require(commit_time(root, baseline) <= when < commit_time(root, after)+timedelta(seconds=1)
            and acquired <= when < expires and acquired <= commit_time(root, after) < expires
            and 0 < (expires-acquired).total_seconds() <= 168*3600, 'Actor approval or historical lease is late or invalid')
    require(any(blob(root, parent, approval_path, missing=True) == raw
                and mode_blob(root, parent, approval_path)[0] == '100644' for parent in parents(root, after)),
            'Actor approval must already exist in a preceding Git commit')
    paths = changed(root, before, after)
    require({ACTIVE, task_path} <= paths, 'Actor transaction must update Task and Registry together')
    handoff = 'evidence/'+target+'/handoff.md'
    for path in paths - {ACTIVE, task_path}:
        if path == handoff:
            original = blob(root, before, path)
            updated = blob(root, after, path)
            require(updated.startswith(original) and len(updated) > len(original), 'Actor handoff must preserve its original prefix')
        else:
            require(path.startswith(prefix) and blob(root, baseline, path, missing=True) is None
                    and mode_blob(root, after, path)[0] == '100644', 'Actor amendment changed old evidence or unrelated files')
    return FIELDS


@lru_cache(maxsize=128)
def automatic_task(root, node, incoming, path):
    """Recreate only the narrow Task stage-0 result; no general import exception."""
    previous = parents(root, node)[0]
    with tempfile.TemporaryDirectory(prefix='guize-actor-import-') as temporary:
        scratch = Path(temporary)/'repo'
        git(root, 'clone', '--shared', '--no-checkout', '--quiet', '--', str(Path(root).resolve()), str(scratch))
        for key, value in [('core.autocrlf', 'false'), ('user.name', 'Actor import audit'), ('user.email', 'audit@example.invalid')]:
            git(scratch, 'config', key, value)
        git(scratch, 'sparse-checkout', 'set', '--no-cone', '/'+path)
        git(scratch, 'checkout', '--detach', '--quiet', previous)
        merge = subprocess.run(['git', '-C', str(scratch), 'merge', '--no-commit', '--no-ff', incoming], capture_output=True)
        require(merge.returncode in {0, 1}, 'Cannot reproduce actor import merge')
        staged = git(scratch, 'ls-files', '--stage', '-z', '--', path).decode().split('\0')
        entries = [entry for entry in staged if entry]
        require(len(entries) == 1, 'Actor Task merge contains a conflict')
        metadata, _ = entries[0].split('\t', 1)
        mode, sha, stage = metadata.split()
        require(stage == '0', 'Actor Task merge is not a clean stage-0 result')
        return mode, sha


def imported_transaction(root, before, after, target, admitted):
    intent = authority(root, admitted)
    require(target in intent['targetTasks'], 'Unknown imported actor target')
    graph = parents(root, after)
    require(len(graph) == 2 and graph[0] == before and ancestor(root, graph[1], admitted),
            'Actor import requires an already admitted incoming main parent')
    incoming = graph[1]
    require(document(root, before, PLAN)['status'] == document(root, after, PLAN)['status'] == 'active',
            'Frozen actor imports are forbidden')
    left = rows(document(root, before, ACTIVE))[target]
    right = rows(document(root, after, ACTIVE))[target]
    imported = rows(document(root, incoming, ACTIVE))[target]
    old = dict(zip(('implementer', 'reviewer'), intent['oldProgramRoleValues']))
    new = intent['futureActualActors'][target]
    require(actors(left) == old and actors(right) == actors(imported) == new
            and without_actors(left) == without_actors(right), 'Actor import changed local stable fields')
    require(all(mode_blob(root, ref, ACTIVE)[0] == '100644' for ref in (before, after, incoming)),
            'Actor import changed Registry metadata mode')
    common = git(root, 'merge-base', '--all', before, incoming).decode().split()
    require(common and all(actors(rows(document(root, ref, ACTIVE))[target]) == old for ref in common),
            'Actor import has conflicting or ambiguous original actor bases')
    # Revalidate the first real main change; current names alone are not authority.
    previous = None
    original = None
    canonical = chain(root, incoming)
    require(REGISTRATION in canonical, 'Actor import predates the mechanism reservation')
    for ref in canonical[canonical.index(REGISTRATION):]:
        if previous is not None:
            a = rows(document(root, previous, ACTIVE)).get(target)
            b = rows(document(root, ref, ACTIVE)).get(target)
            if a is not None and b is not None and actors(a) != actors(b):
                require(original is None, 'Actor assignment was amended more than once')
                validate_range(root, previous, ref, admitted)
                original = ref
        previous = ref
    require(original is not None, 'Actor import has no original accepted main transaction')
    approval_path = 'evidence/'+target+'/actor-amendment-v1/approval.json'
    require(blob(root, after, approval_path) == blob(root, incoming, approval_path)
            and mode_blob(root, after, approval_path)[0] == mode_blob(root, incoming, approval_path)[0] == '100644',
            'Actor import changed the accepted approval')
    path = 'specs/tasks/'+target+'.md'
    require(blob(root, after, path) == task_replacement(blob(root, before, path), old, new)
            and mode_blob(root, after, path) == automatic_task(root, after, incoming, path),
            'Actor import Task is not the exact automatic hybrid result')
    return FIELDS


def edge_fields(root, before, after, target, admitted):
    left, right = rows(document(root, before, ACTIVE)), rows(document(root, after, ACTIVE))
    if target not in left or target not in right or actors(left[target]) == actors(right[target]):
        return frozenset()
    # Reserved foreign peers can also arrive in a feature merge. Status alone
    # must not dispatch that multi-target import as a new original transaction.
    path = 'specs/tasks/'+target+'.md'
    prefix = 'evidence/'+target+'/actor-amendment-v1/'
    metadata_shape = (
        left[target].get('status') == right[target].get('status') == 'reserved'
        and blob(root, before, PLAN) == blob(root, after, PLAN)
        and blob(root, before, LEDGER) == blob(root, after, LEDGER)
        and blob(root, after, ACTIVE) == registry_replacement(blob(root, before, ACTIVE), target,
                                                            actors(left[target]), actors(right[target]))
        and blob(root, after, path) == task_replacement(blob(root, before, path),
                                                       actors(left[target]), actors(right[target]))
        and all(p in {ACTIVE, path, 'evidence/'+target+'/handoff.md'} or p.startswith(prefix)
                for p in changed(root, before, after)))
    if metadata_shape:
        return strict_transaction(root, before, after, target, admitted)
    return imported_transaction(root, before, after, target, admitted)


def validate_range(root, before, after, admitted=None):
    root, before, after = str(Path(root).resolve()), resolve(root, before), resolve(root, after)
    admitted = resolve(root, admitted or before)
    introduced = git(root, 'rev-list', '--reverse', before+'..'+after).decode().split()
    for node in introduced:
        prior = parents(root, node)
        if not prior:
            continue
        paths = changed(root, prior[0], node)
        if INTENT in paths and ancestor(root, REGISTRATION, node):
            require(blob(root, node, INTENT) == blob(root, REGISTRATION, INTENT),
                    'Original actor intent changed in introduced history')
        for target in ('POC-003', 'POC-005'):
            path = 'evidence/'+target+'/actor-amendment-v1/approval.json'
            if path in paths:
                previous = blob(root, prior[0], path, missing=True)
                require(mode_blob(root, node, path) is not None
                        and mode_blob(root, node, path)[0] == '100644', 'Actor approval must remain regular metadata')
                if previous is not None:
                    require(blob(root, node, path, missing=True) == previous
                            and mode_blob(root, prior[0], path)[0] == '100644',
                            'Committed actor approval cannot be rewritten or deleted')
        if ACTIVE not in paths and not any('specs/tasks/'+target+'.md' in paths for target in ('POC-003', 'POC-005')):
            continue
        a, b = rows(document(root, prior[0], ACTIVE)), rows(document(root, node, ACTIVE))
        for target in ('POC-003', 'POC-005'):
            if target in a and target in b:
                path = 'specs/tasks/'+target+'.md'
                require(task_actors(blob(root, prior[0], path)) == actors(a[target])
                        and task_actors(blob(root, node, path)) == actors(b[target]),
                        'Introduced Task/Registry actor mismatch for '+target)
        for target in sorted(a.keys() & b.keys()):
            if actors(a[target]) != actors(b[target]):
                edge_fields(root, prior[0], node, target, admitted)
    # A role PR cannot hide later business work behind a lawful earlier edge.
    a, b = rows(document(root, before, ACTIVE)), rows(document(root, after, ACTIVE))
    result = {}
    for target in sorted(a.keys() & b.keys()):
        if actors(a[target]) != actors(b[target]):
            result[target] = strict_transaction(root, before, after, target, admitted)
    return result


def checked_range(root, before, after, errors, *, admitted=None):
    try:
        return validate_range(root, before, after, admitted)
    except (AmendmentError, KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        errors.append('Prospective actor amendment rejected: '+str(exc))
        return {}


def checked_edge(root, before, after, target, errors, *, admitted=None):
    try:
        return edge_fields(str(Path(root).resolve()), resolve(root, before), resolve(root, after),
                           target, resolve(root, admitted or before))
    except (AmendmentError, KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        errors.append('Prospective actor amendment edge rejected: '+str(exc))
        return frozenset()

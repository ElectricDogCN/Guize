#!/usr/bin/env python3
"""One prospective POC-003 branch transaction; never an evidence/source alias.

Ordinary events use only path-limited Git history. Full authority and ancestry
proofs run only when this exact task's work branch changes.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import yaml

PLAN = 'specs/coordination/program-plan.yaml'
ACTIVE = 'specs/coordination/active-work.yaml'
LEDGER = 'specs/coordination/task-completions.yaml'
OWNER = 'OPS-019'
TARGET = 'POC-003'
TASK = 'specs/tasks/POC-003.md'
BASE = '1b5c68bab02d98f8e11286d80033585090c7af99'
REGISTRATION = '7d82fb61f434f57bb97cb9d80f4613cee3be2721'
RESERVATION_SOURCE = '3dfa21260d9fdd449a99c47b277c0d99f52c7c47'
INTENT = 'evidence/OPS-019/delivery-migration-intent.json'
INTENT_SHA256 = '6a563cd81331c9ebc6141e12f1b678b9e97a808daeb816d5b2c4794abbc9cec4'
APPROVAL = 'evidence/OPS-019/implementation-v1/migration-approval.json'
GRAPH = 'evidence/OPS-019/implementation-v1/retired-delivery-graph.json'
GRAPH_SHA256 = '9d943de7eebb76e3a269f851b1009124dbc21beb22fc0ad5fc7e46b14863b60c'
OLD = 'chore/POC-003-ats-range'
NEW = 'chore/POC-003-qualified-lfs-evidence-v1'
CREATION = '760f6c5838597d1d66c0a536ecbf440ef5a7dfec'
RETIRED = (
    '3564346d2bdfbd80f2f705ae3dd4f7ba79103cb6',
    'deda108d1cbba2ce17e0aaf66213337e2cc88ac9',
    '5a9d20b545636e379d632c8c64f7d9012053e475',
    'e72d32b170a209aa55e3fde620ff38d3b4ccee22',
)
CLAIMS = frozenset({
    '.github/workflows/governance-gate.yml',
    'scripts/check-program-plan-history.py',
    'scripts/check-program-plan-transitions.py',
    'scripts/work-branch-migration.py',
    'tests/governance/test_work_branch_migration.py',
})
FIELDS = frozenset({'branch'})
PREFIX = 'evidence/POC-003/work-branch-migration-v1/'
PROBE = 'evidence/OPS-019/implementation-v1/lfs-probe.bin'
PROBE_BYTES = bytes((index * 73 + 19) % 256 for index in range(4096))
PROBE_SHA256 = hashlib.sha256(PROBE_BYTES).hexdigest()


class MigrationError(ValueError):
    pass


def require(value, message):
    if not value:
        raise MigrationError(message)


def git(root, *args, missing=False):
    result = subprocess.run(['git', '--no-replace-objects', '-C', str(root), *args],
                            capture_output=True)
    if result.returncode:
        if missing:
            return None
        raise MigrationError('Cannot inspect complete branch migration Git history: '+str(args[:2]))
    return result.stdout


def resolve(root, ref):
    return git(root, 'rev-parse', '--verify', ref+'^{commit}').decode().strip()


def blob(root, ref, path, *, missing=False):
    return git(root, 'show', ref+':'+path, missing=missing)


def document(root, ref, path):
    value = yaml.load(blob(root, ref, path), Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader))
    require(isinstance(value, dict), 'Migration requires a mapping: '+path)
    return value


def rows(document, field='tasks'):
    result = {}
    require(isinstance(document.get(field), list), 'Migration requires a task list')
    for row in document[field]:
        require(isinstance(row, dict) and isinstance(row.get('taskId'), str)
                and row['taskId'] not in result, 'Invalid or duplicate migration task identity')
        result[row['taskId']] = row
    return result


def parents(root, ref):
    return git(root, 'show', '-s', '--format=%P', ref).decode().split()


def changed(root, before, after):
    return set(git(root, 'diff', '--name-only', '--no-renames', before, after).decode().splitlines())


def chain(root, ref):
    return git(root, 'rev-list', '--first-parent', '--reverse', ref).decode().split()


def ancestor(root, before, after):
    result = subprocess.run(['git', '--no-replace-objects', '-C', str(root),
                             'merge-base', '--is-ancestor', before, after], capture_output=True)
    require(result.returncode in (0, 1), 'Cannot establish migration ancestry')
    return result.returncode == 0


def mode_blob(root, ref, path):
    raw = git(root, 'ls-tree', '-z', ref, '--', path)
    if not raw:
        return None
    mode, kind, oid = raw.split(b'\t', 1)[0].split()
    require(kind == b'blob', 'Migration metadata must be a blob')
    return mode.decode(), oid.decode()


def instant(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
            'Migration requires explicit UTC')
    return parsed


def commit_time(root, ref):
    return datetime.fromtimestamp(int(git(root, 'show', '-s', '--format=%ct', ref)), timezone.utc)


def front(raw):
    parts = raw.split(b'---', 2)
    require(len(parts) == 3 and parts[0] == b'', 'Migration Task requires front matter')
    result = yaml.safe_load(parts[1])
    require(isinstance(result, dict), 'Migration Task front matter must be a mapping')
    return result


def scalar(raw, key, old, new, indent=b''):
    pattern = rb'^'+indent+key.encode()+rb': '+re.escape(old.encode())+rb'(?=\r?$)'
    updated, count = re.subn(pattern, lambda _: indent+key.encode()+b': '+new.encode(),
                             raw, flags=re.M)
    require(count == 1, 'Migration scalar missing, quoted or duplicated: '+key)
    return updated


def task_replacement(raw):
    parts = raw.split(b'---', 2)
    front(raw)
    return b'---'+scalar(parts[1], 'workBranch', OLD, NEW)+b'---'+parts[2]


def registry_replacement(raw):
    starts = list(re.finditer(rb'^- taskId: POC-003(?=\r?$)', raw, re.M))
    require(len(starts) == 1, 'Migration Registry target must be unique')
    start = starts[0].start()
    following = re.search(rb'^- taskId:', raw[starts[0].end():], re.M)
    end = starts[0].end()+following.start() if following else len(raw)
    return raw[:start]+scalar(raw[start:end], 'branch', OLD, NEW, b'  ')+raw[end:]


def history_module():
    spec = importlib.util.spec_from_file_location('guize_work_branch_authority_history',
                                                 Path(__file__).with_name('check-program-plan-history.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def complete_ancestry(root, after):
    require(git(root, 'rev-parse', '--is-shallow-repository').strip() == b'false',
            'Migration cannot use shallow history')
    for name in ('info/grafts', 'shallow'):
        location = git(root, 'rev-parse', '--git-path', name).decode().strip()
        location = Path(location) if Path(location).is_absolute() else Path(root)/location
        require(not location.exists(), 'Migration cannot use grafted or shallow history')
    require(not git(root, 'for-each-ref', '--format=%(refname)', 'refs/replace/').strip(),
            'Migration cannot use replacement history')
    reachable = set(git(root, 'rev-list', after).decode().split())
    require(BASE in reachable, 'Migration history does not reach the original media base')
    require(not reachable.intersection(RETIRED),
            'Migration clean lineage contains an old large-delivery ancestor')
    return reachable


def verify_retired_graph(root, ref):
    raw = blob(root, ref, GRAPH)
    require(hashlib.sha256(raw).hexdigest() == GRAPH_SHA256,
            'Original retired-delivery graph changed')
    graph = json.loads(raw)
    require(graph['base'] == BASE and graph['oldCandidate'] == RETIRED[0]
            and [row['sha'] for row in graph['nodes']] == list(RETIRED),
            'Retired-delivery graph identity differs')
    for index, row in enumerate(graph['nodes']):
        data = base64.b64decode(row['rawBase64'], validate=True)
        require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
                and hashlib.sha1(b'commit '+str(len(data)).encode()+b'\0'+data).hexdigest() == row['sha'],
                'Retired-delivery commit bytes differ')
        expected = RETIRED[index+1] if index+1 < len(RETIRED) else BASE
        require(re.findall(rb'^parent ([0-9a-f]{40})$', data.split(b'\n\n', 1)[0], re.M)
                == [expected.encode()], 'Retired-delivery commit parent differs')


def authority(root, admitted):
    canonical = chain(root, admitted)
    require(REGISTRATION in canonical and parents(root, REGISTRATION) == [BASE, RESERVATION_SOURCE],
            'Migration requires the original actual main reservation')
    original = blob(root, REGISTRATION, INTENT)
    require(hashlib.sha256(original).hexdigest() == INTENT_SHA256,
            'Original migration intent differs')
    intent = json.loads(original)
    require(set(intent['authorityClaims']) == CLAIMS and intent['authorityTaskId'] == OWNER,
            'Migration intent scope differs')
    registered = rows(document(root, REGISTRATION, ACTIVE))[OWNER]
    require(registered['status'] == 'reserved' and registered['moduleIds'] == ['MOD-GOV']
            and registered['riskLevel'] == 'high' and set(registered['exclusivePaths']) == CLAIMS
            and registered['sharedPaths'] == [] and registered['implementer'] == '/root'
            and registered['reviewer'] == '/root/independent_review',
            'Migration mechanism lacks its exact independent reservation')
    plan = document(root, admitted, PLAN)
    completed = rows(plan, 'foundationTasks').get(OWNER, {})
    require(plan['status'] == 'active' and completed.get('status') == 'completed'
            and OWNER not in rows(document(root, admitted, ACTIVE)),
            'Migration authority must normally complete and release capacity first')
    implementation = completed.get('mergeCommit', '')
    require(implementation in canonical and canonical.index(implementation) > canonical.index(REGISTRATION)
            and CLAIMS.intersection(changed(root, parents(root, implementation)[0], implementation))
            and CLAIMS <= changed(root, REGISTRATION, implementation),
            'Migration authority lacks its complete nonempty registered implementation')
    # Inspect side histories too, including an edit followed by a restoration.
    for node in git(root, 'rev-list', '--full-history', REGISTRATION+'..'+admitted, '--', INTENT).decode().split():
        require(blob(root, node, INTENT) == original, 'Migration intent was rewritten on a source edge')
    finished = None
    reviewed = False
    module = history_module()
    # The unchanged normal Foundation validator proves original reservation,
    # every source edge, independent Review, implementation PR identity and
    # metadata-only normal Completion. A completed label is not authority.
    for index, node in enumerate(canonical[canonical.index(REGISTRATION):]):
        state = rows(document(root, node, PLAN), 'foundationTasks').get(OWNER, {})
        require(blob(root, node, INTENT) == original, 'Migration intent changed in admitted history')
        if state.get('status') in {'review', 'integration'} and ancestor(root, implementation, node):
            live = rows(document(root, node, ACTIVE)).get(OWNER, {})
            require(live.get('implementer') == registered['implementer']
                    and live.get('reviewer') == registered['reviewer']
                    and live.get('agentRole') in {'reviewer', 'integrator'},
                    'Migration authority lacks an independent admitted main Review')
            reviewed = True
        if state.get('status') == 'completed' and finished is None:
            graph = parents(root, node)
            require(len(graph) == 2, 'Migration authority Completion must be an ordinary actual main merge')
            prior = graph[0]
            prior_state = rows(document(root, prior, PLAN), 'foundationTasks').get(OWNER, {})
            prior_live = rows(document(root, prior, ACTIVE)).get(OWNER, {})
            require(reviewed and prior_state.get('status') in {'review', 'integration'}
                    and prior_live.get('implementer') == registered['implementer']
                    and prior_live.get('reviewer') == registered['reviewer']
                    and prior_live.get('agentRole') in {'reviewer', 'integrator'},
                    'Migration authority Completion requires a preceding independent admitted main Review')
            errors = []
            module.validate_foundations(root, document(root, prior, PLAN), document(root, node, PLAN),
                document(root, prior, ACTIVE), document(root, node, ACTIVE),
                document(root, prior, LEDGER), document(root, node, LEDGER),
                prior, node, front(blob(root, node, 'specs/tasks/OPS-019.md'))['workBranch'],
                errors, task_hint=OWNER)
            require(not errors, 'Normal migration authority rejected: '+'; '.join(errors))
            finished = node
        if finished is not None:
            require(state == completed and OWNER not in rows(document(root, node, ACTIVE)),
                    'Completed migration authority identity or released capacity changed')
    require(finished is not None, 'Migration authority has no actual main Completion')
    verify_retired_graph(root, implementation)
    return implementation, finished


def unique_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate migration approval field')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    require(isinstance(value, dict), 'Migration approval must be an object')
    return value


def approved_transaction(root, before, after, admitted, implementation, completion):
    require(ancestor(root, completion, before),
            "Migration source must follow the actual admitted authority Completion")
    left = rows(document(root, before, ACTIVE)).get(TARGET)
    right = rows(document(root, after, ACTIVE)).get(TARGET)
    require(left is not None and right is not None and left['branch'] == OLD and right['branch'] == NEW
            and left['status'] == right['status'] == 'in_progress'
            and left['integrationStrategy'] == 'merge'
            and left['implementer'] != left['reviewer'],
            'Migration is only the original active POC-003 branch pair')
    require(blob(root, after, ACTIVE) == registry_replacement(blob(root, before, ACTIVE)),
            'Migration changed other Registry bytes, roles, lease or claims')
    require(blob(root, after, TASK) == task_replacement(blob(root, before, TASK)),
            'Migration changed other Task bytes')
    for path in (PLAN, LEDGER):
        require(blob(root, before, path) == blob(root, after, path),
                'Migration changed '+path)
    require(document(root, before, PLAN)['status'] == 'active', 'Frozen migration forbidden')
    for path in (ACTIVE, TASK):
        require(mode_blob(root, before, path)[0] == mode_blob(root, after, path)[0] == '100644',
                'Migration metadata mode changed')
    raw = blob(root, before, APPROVAL)
    record = unique_json(raw)
    expected_keys = {'schemaVersion', 'kind', 'authorityTaskId', 'taskId', 'reservation',
        'implementationCommit', 'intentSha256', 'oldBranch', 'newBranch', 'originalCreationBase',
        'oldUnmergedCandidate', 'beforeRegistrySha256', 'beforeTaskSha256', 'reviewer',
        'approvedAt', 'decision', 'condition'}
    require(set(record) == expected_keys and type(record['schemaVersion']) is int
            and record['schemaVersion'] == 1
            and record['kind'] == 'conditional_prospective_work_branch_migration'
            and record['authorityTaskId'] == OWNER and record['taskId'] == TARGET
            and record['reservation'] == REGISTRATION and record['implementationCommit'] == implementation
            and record['intentSha256'] == INTENT_SHA256 and record['oldBranch'] == OLD
            and record['newBranch'] == NEW and record['originalCreationBase'] == CREATION
            and record['oldUnmergedCandidate'] == RETIRED[0]
            and record['beforeRegistrySha256'] == hashlib.sha256(json.dumps(left, sort_keys=True,
                separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            and record['beforeTaskSha256'] == hashlib.sha256(blob(root, before, TASK)).hexdigest()
            and record['reviewer'] == left['reviewer'] == '/root/independent_review'
            and record['decision'] == 'approved'
            and record['condition'] == 'normal_authority_completion_full_ci_capacity_release_and_fresh_main',
            'Migration approval does not bind the exact independent conditional transaction')
    # Conditional approval may be committed during the normal Review/Completion,
    # but cannot be added as a completed-task correction or invented afterwards.
    canonical = chain(root, admitted)
    creators = []
    for node in git(root, 'rev-list', '--reverse', REGISTRATION+'..'+before, '--', APPROVAL).decode().split():
        prior = parents(root, node)[0]
        previous = blob(root, prior, APPROVAL, missing=True)
        current = blob(root, node, APPROVAL, missing=True)
        require(current == raw and mode_blob(root, node, APPROVAL)[0] == '100644',
                'Committed migration approval was rewritten, deleted or chmodded')
        if previous is None:
            # Ordinary merge imports represent the same approval creator.
            if not any(blob(root, side, APPROVAL, missing=True) == raw for side in parents(root, node)[1:]):
                creators.append(node)
    require(len(creators) == 1, 'Migration approval lacks one preceding creator commit')
    creator = creators[0]
    require(ancestor(root, creator, before) and creator != after
            and any(ancestor(root, creator, node) for node in canonical)
            and rows(document(root, creator, PLAN), 'foundationTasks')[OWNER]['status'] in {'review', 'integration'}
            and rows(document(root, creator, ACTIVE))[OWNER]['agentRole'] in {'reviewer', 'integrator'}
            and ancestor(root, implementation, creator),
            'Migration approval must precede migration in the normal independent Review/Completion')
    require(blob(root, admitted, APPROVAL) == raw and mode_blob(root, admitted, APPROVAL)[0] == '100644'
            and blob(root, after, APPROVAL) == raw,
            'Migration approval is not immutable admitted main metadata')
    when = instant(record['approvedAt'])
    acquired, expires = (instant(left['lease'][key]) for key in ('acquiredAt', 'expiresAt'))
    require(commit_time(root, implementation) <= when < commit_time(root, creator)+timedelta(seconds=1)
            and acquired <= when < expires and acquired <= commit_time(root, after) < expires
            and 0 < (expires-acquired).total_seconds() <= 168*3600,
            'Migration approval or historical lease is late or invalid')
    paths = changed(root, before, after)
    require({ACTIVE, TASK} <= paths, 'Migration must update Task and Registry together')
    handoff = 'evidence/POC-003/handoff.md'
    for path in paths - {ACTIVE, TASK}:
        if path == handoff:
            original, updated = blob(root, before, path), blob(root, after, path)
            require(updated.startswith(original) and len(updated) > len(original),
                    'Migration handoff must append to original bytes')
        else:
            require(path.startswith(PREFIX) and blob(root, completion, path, missing=True) is None
                    and mode_blob(root, after, path)[0] == '100644',
                    'Migration contains code, media, old evidence or unrelated files')
    return FIELDS


def branch_pair(root, before, after):
    a, b = rows(document(root, before, ACTIVE)), rows(document(root, after, ACTIVE))
    if TARGET not in a or TARGET not in b:
        return None
    fa, fb = front(blob(root, before, TASK)), front(blob(root, after, TASK))
    require(fa['workBranch'] == a[TARGET]['branch'] and fb['workBranch'] == b[TARGET]['branch'],
            'Migration Task/Registry branch mismatch')
    if a[TARGET]['branch'] == b[TARGET]['branch']:
        return None
    return a[TARGET]['branch'], b[TARGET]['branch']


def transaction_shape(root, before, after):
    require(branch_pair(root, before, after) == (OLD, NEW),
            'Migration branch change is not the declared one-way pair')
    require(blob(root, after, ACTIVE) == registry_replacement(blob(root, before, ACTIVE))
            and blob(root, after, TASK) == task_replacement(blob(root, before, TASK)),
            'Migration changed other Task or Registry bytes, roles, lease or claims')
    allowed = {ACTIVE, TASK, 'evidence/POC-003/handoff.md'}
    require(all(path in allowed or path.startswith(PREFIX) for path in changed(root, before, after)),
            'Migration contains code, media or unrelated changes')


def validate_range(root, before, after, admitted=None):
    before, after = resolve(root, before), resolve(root, after)
    admitted = resolve(root, admitted or before)
    # Path-limited history sees protected Evidence rewrites and branch
    # change-then-restore without auditing unrelated full Foundation histories.
    candidates = git(root, 'rev-list', '--full-history', '--reverse', before+'..'+after,
                     '--', ACTIVE, TASK, INTENT, GRAPH, APPROVAL).decode().split()
    edits = []
    for node in candidates:
        graph = parents(root, node)
        if not graph:
            continue
        paths = changed(root, graph[0], node)
        for path, digest in ((INTENT, INTENT_SHA256), (GRAPH, GRAPH_SHA256)):
            if path not in paths:
                continue
            current = blob(root, node, path, missing=True)
            require(current is not None and mode_blob(root, node, path)[0] == '100644'
                    and hashlib.sha256(current).hexdigest() == digest,
                    'Protected migration intent or graph was rewritten, deleted or chmodded')
        if APPROVAL in paths:
            previous = blob(root, graph[0], APPROVAL, missing=True)
            current = blob(root, node, APPROVAL, missing=True)
            require(current is not None and mode_blob(root, node, APPROVAL)[0] == '100644',
                    'Protected migration approval was deleted or chmodded')
            if previous is not None:
                require(current == previous and mode_blob(root, graph[0], APPROVAL)[0] == '100644',
                        'Protected migration approval was rewritten')
            elif not any(blob(root, side, APPROVAL, missing=True) == current for side in graph[1:]):
                state = rows(document(root, node, PLAN), 'foundationTasks').get(OWNER, {})
                live = rows(document(root, node, ACTIVE)).get(OWNER, {})
                require(state.get('status') in {'review', 'integration'}
                        and live.get('agentRole') in {'reviewer', 'integrator'}
                        and live.get('reviewer') == '/root/independent_review'
                        and live.get('implementer') == '/root',
                        'Conditional approval must originate in normal independent Review/Completion')
        if branch_pair(root, graph[0], node):
            edits.append(node)
    if not edits:
        return {}
    for node in edits:
        require(branch_pair(root, parents(root, node)[0], node) == (OLD, NEW),
                'Migration branch change is not the declared one-way pair')
    if branch_pair(root, before, after):
        transaction_shape(root, before, after)
    complete_ancestry(root, after)
    implementation, completion = authority(root, admitted)
    # Scan the complete reachable lineage after the fixed original reservation,
    # so an accepted old event cannot be consumed a second time on another side.
    events = {}
    nodes = git(root, 'rev-list', '--full-history', '--topo-order', '--reverse',
                REGISTRATION+'..'+after, '--', ACTIVE, TASK).decode().split()
    for node in nodes:
        graph = parents(root, node)
        if not graph or not branch_pair(root, graph[0], node):
            continue
        require(branch_pair(root, graph[0], node) == (OLD, NEW),
                'Migration branch change is not the declared one-way pair')
        if len(graph) == 1:
            approved_transaction(root, graph[0], node, admitted, implementation, completion)
            events[node] = node
        else:
            require(len(graph) == 2 and graph[0] not in (node, graph[1])
                    and resolve(root, graph[0]) == graph[0],
                    'Migration requires an ordinary two-parent merge')
            incoming = [event for event in events if ancestor(root, event, graph[1])]
            require(len(incoming) == 1 and ancestor(root, completion, graph[1])
                    and blob(root, graph[1], ACTIVE) == blob(root, node, ACTIVE)
                    and blob(root, graph[1], TASK) == blob(root, node, TASK)
                    and git(root, 'diff', '--name-only', graph[1], node) == b'',
                    'Migration merge must import the exact single qualified source tree')
            approved_transaction(root, graph[0], node, admitted, implementation, completion)
    require(len(events) == 1, 'Migration has more than one source transaction')
    # Net permission is granted only to the exact metadata-only transaction.
    if branch_pair(root, before, after):
        approved_transaction(root, before, after, admitted, implementation, completion)
        return {TARGET: FIELDS}
    return {}


def checked_range(root, before, after, errors, *, admitted=None):
    try:
        return validate_range(root, before, after, admitted)
    except (MigrationError, KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        errors.append('Prospective work branch migration rejected: '+str(exc))
        return {}


def checked_edge(root, before, after, target, errors, *, admitted=None):
    if target != TARGET:
        return frozenset()
    return checked_range(root, before, after, errors, admitted=admitted).get(target, frozenset())


def verify_probe(root, ref='HEAD'):
    """Check the tracked pointer AND materialized bytes, never accept the pointer as data."""
    pointer = blob(root, ref, PROBE)
    expected = ('version https://git-lfs.github.com/spec/v1\noid sha256:'+PROBE_SHA256+
                '\nsize '+str(len(PROBE_BYTES))+'\n').encode()
    require(pointer == expected and mode_blob(root, ref, PROBE)[0] == '100644',
            'LFS probe is not the exact tracked pointer')
    require(git(root, 'ls-files', '--error-unmatch', '--', PROBE).strip()
            and git(root, 'check-attr', 'filter', '--', PROBE).decode().strip().endswith(': lfs'),
            'LFS probe must be tracked with the LFS filter')
    actual = Path(root, PROBE).read_bytes()
    require(actual == PROBE_BYTES and hashlib.sha256(actual).hexdigest() == PROBE_SHA256,
            'LFS probe was not hydrated to the original bytes')
    return True

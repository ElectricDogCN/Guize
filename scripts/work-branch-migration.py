#!/usr/bin/env python3
"""One prospective POC-003 branch transaction; never an evidence/source alias.

Ordinary events use only path-limited Git history. Full authority and ancestry
proofs run only when this exact task's work branch changes.
"""
from __future__ import annotations

import base64
from functools import lru_cache
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

# A separate, original registration is required for the blocked tuple. The
# expired OPS-019 approval is retained exclusively for its original route.
RECOVERY_OWNER = 'OPS-020'
RECOVERY_REGISTRATION = '08ee4bc4dc3030cc86f420cc0956a0ab5146c379'
RECOVERY_RESERVATION_PARENT = '251fac61809ed4b209c4fc7a71dee41ba4061db6'
RECOVERY_RESERVATION_SOURCE = 'e9f72d781236f359de63032da68136ce25ada5d7'
RECOVERY_INTENT = 'evidence/OPS-020/recovery-intent.json'
RECOVERY_INTENT_SHA256 = '3442ac687f2fda7071b467082ffccdff2e677847c9323198cf64a7fbdc41b51d'
RECOVERY_APPROVAL = 'evidence/OPS-020/implementation-v1/recovery-approval.json'
RECOVERY_NEW = 'chore/POC-003-qualified-lfs-evidence-v2'
RECOVERY_PREFIX = 'evidence/POC-003/work-branch-recovery-v2/'
RECOVERY_CLAIMS = frozenset({
    'scripts/work-branch-migration.py',
    'tests/governance/test_work_branch_migration.py',
})


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


def creator_in_history(root, creator, canonical):
    # Every node in the complete first-parent chain reaches its final OID.
    # Use this same resolved chain, preserving moving-ref and empty semantics.
    return bool(canonical) and ancestor(root, creator, canonical[-1])


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


@lru_cache(maxsize=8)
def recovery_history_module(root):
    """Reuse H's existing successful immutable snapshot cache per real root.

    Every authority call still runs the complete normal Foundation proof.
    No permission, exception, failure or authority result is cached here.
    """
    return history_module()


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


def authority(root, admitted, *, source_before=None, _recovery=False):
    if _recovery:
        owner, registration = RECOVERY_OWNER, RECOVERY_REGISTRATION
        reservation_parent, reservation_source = RECOVERY_RESERVATION_PARENT, RECOVERY_RESERVATION_SOURCE
        intent_path, intent_sha256, claims = RECOVERY_INTENT, RECOVERY_INTENT_SHA256, RECOVERY_CLAIMS
    else:
        owner, registration = OWNER, REGISTRATION
        reservation_parent, reservation_source = BASE, RESERVATION_SOURCE
        intent_path, intent_sha256, claims = INTENT, INTENT_SHA256, CLAIMS
    authority_task = 'specs/tasks/'+owner+'.md'
    canonical = chain(root, admitted)
    require(registration in canonical and parents(root, registration) == [reservation_parent, reservation_source],
            'Migration requires the original actual main reservation')
    original = blob(root, registration, intent_path)
    require(hashlib.sha256(original).hexdigest() == intent_sha256,
            'Original migration intent differs')
    intent = json.loads(original)
    require(set(intent['authorityClaims']) == claims and intent['authorityTaskId'] == owner,
            'Migration intent scope differs')
    registered = rows(document(root, registration, ACTIVE))[owner]
    require(registered['status'] == 'reserved' and registered['moduleIds'] == ['MOD-GOV']
            and registered['riskLevel'] == 'high' and set(registered['exclusivePaths']) == claims
            and registered['sharedPaths'] == [] and registered['implementer'] == '/root'
            and registered['reviewer'] == '/root/independent_review',
            'Migration mechanism lacks its exact independent reservation')
    plan = document(root, admitted, PLAN)
    completed = rows(plan, 'foundationTasks').get(owner, {})
    require(plan['status'] == 'active' and completed.get('status') == 'completed'
            and owner not in rows(document(root, admitted, ACTIVE)),
            'Migration authority must normally complete and release capacity first')
    implementation = completed.get('mergeCommit', '')
    require(implementation in canonical and canonical.index(implementation) > canonical.index(registration)
            and claims.intersection(changed(root, parents(root, implementation)[0], implementation))
            and claims <= changed(root, registration, implementation),
            'Migration authority lacks its complete nonempty registered implementation')
    # Inspect side histories too, including an edit followed by a restoration.
    for node in git(root, 'rev-list', '--full-history', registration+'..'+admitted, '--', intent_path).decode().split():
        require(blob(root, node, intent_path) == original, 'Migration intent was rewritten on a source edge')
    finished = None
    reviewed = False
    module = recovery_history_module(str(Path(root).resolve())) if _recovery else history_module()
    # The unchanged normal Foundation validator proves original reservation,
    # every source edge, independent Review, implementation PR identity and
    # metadata-only normal Completion. A completed label is not authority.
    for index, node in enumerate(canonical[canonical.index(registration):]):
        state = rows(document(root, node, PLAN), 'foundationTasks').get(owner, {})
        require(blob(root, node, intent_path) == original, 'Migration intent changed in admitted history')
        if state.get('status') in {'review', 'integration'} and ancestor(root, implementation, node):
            live = rows(document(root, node, ACTIVE)).get(owner, {})
            require(live.get('implementer') == registered['implementer']
                    and live.get('reviewer') == registered['reviewer']
                    and live.get('agentRole') in {'reviewer', 'integrator'},
                    'Migration authority lacks an independent admitted main Review')
            reviewed = True
        if state.get('status') == 'completed' and finished is None:
            graph = parents(root, node)
            require(len(graph) == 2, 'Migration authority Completion must be an ordinary actual main merge')
            prior = graph[0]
            prior_state = rows(document(root, prior, PLAN), 'foundationTasks').get(owner, {})
            prior_live = rows(document(root, prior, ACTIVE)).get(owner, {})
            require(reviewed and prior_state.get('status') in {'review', 'integration'}
                    and prior_live.get('implementer') == registered['implementer']
                    and prior_live.get('reviewer') == registered['reviewer']
                    and prior_live.get('agentRole') in {'reviewer', 'integrator'},
                    'Migration authority Completion requires a preceding independent admitted main Review')
            if source_before is not None:
                require(ancestor(root, node, source_before),
                        'Migration source must follow the actual admitted authority Completion')
            errors = []
            module.validate_foundations(root, document(root, prior, PLAN), document(root, node, PLAN),
                document(root, prior, ACTIVE), document(root, node, ACTIVE),
                document(root, prior, LEDGER), document(root, node, LEDGER),
                prior, node, front(blob(root, node, authority_task))['workBranch'],
                errors, task_hint=owner)
            require(not errors, 'Normal migration authority rejected: '+'; '.join(errors))
            finished = node
        if finished is not None:
            require(state == completed and owner not in rows(document(root, node, ACTIVE)),
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
            and creator_in_history(root, creator, canonical)
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


def migration_edits(root, before, after):
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
    return edits


def _validate_legacy_range(root, before, after, admitted, edits):
    if not edits:
        return {}
    for node in edits:
        require(branch_pair(root, parents(root, node)[0], node) == (OLD, NEW),
                'Migration branch change is not the declared one-way pair')
    if branch_pair(root, before, after):
        transaction_shape(root, before, after)
    complete_ancestry(root, after)
    implementation, completion = authority(root, admitted, source_before=parents(root, edits[0])[0])
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


def recovery_registry_replacement(raw):
    starts = list(re.finditer(rb'^- taskId: POC-003(?=\r?$)', raw, re.M))
    require(len(starts) == 1, 'Recovery Registry target must be unique')
    start = starts[0].start()
    following = re.search(rb'^- taskId:', raw[starts[0].end():], re.M)
    end = starts[0].end()+following.start() if following else len(raw)
    row = scalar(raw[start:end], 'branch', OLD, RECOVERY_NEW, b'  ')
    row = scalar(row, 'status', 'blocked', 'in_progress', b'  ')
    row = scalar(row, 'agentRole', 'coordinator', 'implementer', b'  ')
    return raw[:start]+row+raw[end:]


def recovery_task_replacement(raw):
    parts = raw.split(b'---', 2)
    front(raw)
    value = scalar(parts[1], 'workBranch', OLD, RECOVERY_NEW)
    value = scalar(value, 'status', 'blocked', 'in_progress')
    value = scalar(value, 'agentRole', 'coordinator', 'implementer')
    return b'---'+value+b'---'+parts[2]


def recovery_program_replacement(raw):
    """Change two scalar spans; preserve every other byte and YAML layout."""
    text = raw.decode('utf-8')
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    def field(node, key):
        require(isinstance(node, yaml.nodes.MappingNode), 'Recovery Program requires mappings')
        found = [value for name, value in node.value if name.value == key]
        require(len(found) == 1, 'Recovery Program field missing or duplicated: '+key)
        return found[0]
    replacements = []
    for section, key, identity in [('tasks', 'taskId', TARGET), ('pocs', 'pocId', 'POC-03')]:
        sequence = field(root, section)
        require(isinstance(sequence, yaml.nodes.SequenceNode), 'Recovery Program requires lists')
        matched = [row for row in sequence.value if field(row, key).value == identity]
        require(len(matched) == 1, 'Recovery Program target missing or duplicated')
        value = field(matched[0], 'status')
        require(isinstance(value, yaml.nodes.ScalarNode) and value.value == 'blocked'
                and value.style in (None, "'", '"'), 'Recovery Program target must be blocked')
        quote = value.style or ''
        require(matched[0].start_mark.index <= value.start_mark.index < value.end_mark.index
                <= matched[0].end_mark.index
                and text[value.start_mark.index:value.end_mark.index] == quote+'blocked'+quote,
                'Recovery Program status must be an owned literal scalar')
        replacements.append((value.start_mark.index, value.end_mark.index,
                             quote+'in_progress'+quote))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start]+replacement+text[end:]
    original = yaml.safe_load(raw)
    expected = dict(original)
    expected['tasks'] = [dict(row, status='in_progress') if row['taskId'] == TARGET else row
                         for row in original['tasks']]
    expected['pocs'] = [dict(row, status='in_progress') if row['pocId'] == 'POC-03' else row
                        for row in original['pocs']]
    require(yaml.safe_load(text) == expected, 'Recovery Program changed foreign values or aliases')
    return text.encode('utf-8')


def recovery_approval_record(root, raw):
    record = unique_json(raw)
    keys = {'schemaVersion', 'kind', 'authorityTaskId', 'taskId', 'reservation',
        'implementationCommit', 'intentSha256', 'oldBranch', 'newBranch', 'originalCreationBase',
        'oldUnmergedCandidate', 'beforeRegistrySha256', 'beforeTaskSha256', 'reviewer',
        'approvedAt', 'decision', 'condition'}
    intent = unique_json(blob(root, RECOVERY_REGISTRATION, RECOVERY_INTENT))
    require(hashlib.sha256(blob(root, RECOVERY_REGISTRATION, RECOVERY_INTENT)).hexdigest()
            == RECOVERY_INTENT_SHA256, 'Original recovery intent differs')
    target = intent['migration']
    require(set(record) == keys and type(record['schemaVersion']) is int
            and record['schemaVersion'] == 1
            and record['kind'] == 'conditional_prospective_blocked_work_branch_recovery'
            and record['authorityTaskId'] == RECOVERY_OWNER and record['taskId'] == TARGET
            and record['reservation'] == RECOVERY_REGISTRATION
            and record['intentSha256'] == RECOVERY_INTENT_SHA256
            and record['oldBranch'] == OLD and record['newBranch'] == RECOVERY_NEW
            and record['originalCreationBase'] == CREATION and record['oldUnmergedCandidate'] == RETIRED[0]
            and record['beforeRegistrySha256'] == target['beforeRegistrySha256']
            and record['beforeTaskSha256'] == target['beforeTaskSha256']
            and record['reviewer'] == target['beforeRegistry']['reviewer'] == '/root/independent_review'
            and record['decision'] == 'approved'
            and record['condition'] == 'normal_authority_completion_full_ci_capacity_release_and_fresh_main'
            and isinstance(record['implementationCommit'], str)
            and re.fullmatch('[0-9a-f]{40}', record['implementationCommit'])
            and isinstance(record['approvedAt'], str),
            'Recovery approval does not bind the original independent transaction')
    instant(record['approvedAt'])
    return record


def audit_recovery_metadata(root, before, after):
    nodes = git(root, 'rev-list', '--full-history', '--reverse', before+'..'+after,
                '--', RECOVERY_INTENT, RECOVERY_APPROVAL).decode().split()
    for node in nodes:
        graph = parents(root, node)
        if not graph:
            continue
        paths = changed(root, graph[0], node)
        if RECOVERY_INTENT in paths:
            raw = blob(root, node, RECOVERY_INTENT, missing=True)
            require(raw is not None and mode_blob(root, node, RECOVERY_INTENT)[0] == '100644'
                    and hashlib.sha256(raw).hexdigest() == RECOVERY_INTENT_SHA256,
                    'Protected recovery intent was rewritten, deleted or chmodded')
        if RECOVERY_APPROVAL in paths:
            previous = blob(root, graph[0], RECOVERY_APPROVAL, missing=True)
            current = blob(root, node, RECOVERY_APPROVAL, missing=True)
            require(current is not None and mode_blob(root, node, RECOVERY_APPROVAL)[0] == '100644',
                    'Protected recovery approval was deleted or chmodded')
            recovery_approval_record(root, current)
            if previous is not None:
                require(current == previous, 'Protected recovery approval was rewritten')
            elif not any(blob(root, side, RECOVERY_APPROVAL, missing=True) == current for side in graph[1:]):
                state = rows(document(root, node, PLAN), 'foundationTasks').get(RECOVERY_OWNER, {})
                live = rows(document(root, node, ACTIVE)).get(RECOVERY_OWNER, {})
                previous_state = rows(document(root, graph[0], PLAN), 'foundationTasks').get(RECOVERY_OWNER, {})
                previous_live = rows(document(root, graph[0], ACTIVE)).get(RECOVERY_OWNER, {})
                require(state.get('status') in {'review', 'integration'}
                        and live.get('agentRole') in {'reviewer', 'integrator'}
                        and previous_state.get('status') in {'review', 'integration'}
                        and previous_live.get('agentRole') in {'reviewer', 'integrator'}
                        and live.get('reviewer') == '/root/independent_review'
                        and live.get('implementer') == '/root'
                        and previous_live.get('reviewer') == '/root/independent_review'
                        and previous_live.get('implementer') == '/root'
                        and len(graph) == 1 and paths == {RECOVERY_APPROVAL},
                        'Recovery approval needs a separate preceding normal Review approval commit')


def recovery_shape(root, before, after):
    """Necessary metadata conditions only; this never grants permission."""
    left = rows(document(root, before, ACTIVE)).get(TARGET)
    right = rows(document(root, after, ACTIVE)).get(TARGET)
    require(left and right and left['branch'] == OLD and right['branch'] == RECOVERY_NEW
            and left['status'] == 'blocked' and right['status'] == 'in_progress'
            and left['agentRole'] == 'coordinator' and right['agentRole'] == 'implementer'
            and left['baseSha'] == right['baseSha'] == CREATION
            and left['integrationStrategy'] == 'merge' and left['implementer'] != left['reviewer'],
            'Recovery is only the declared blocked POC-003 tuple')
    for path, replacement in ((ACTIVE, recovery_registry_replacement),
                              (TASK, recovery_task_replacement),
                              (PLAN, recovery_program_replacement)):
        require(blob(root, after, path) == replacement(blob(root, before, path)),
                'Recovery changed other metadata bytes: '+path)
        require(mode_blob(root, before, path)[0] == mode_blob(root, after, path)[0] == '100644',
                'Recovery metadata mode changed')
    require(blob(root, before, LEDGER) == blob(root, after, LEDGER)
            and document(root, before, PLAN)['status'] == 'active', 'Frozen or ledger-changing recovery forbidden')
    handoff, readme = 'evidence/POC-003/handoff.md', RECOVERY_PREFIX+'README.md'
    require(changed(root, before, after) == {ACTIVE, TASK, PLAN, handoff, readme},
            'Recovery must be the exact five metadata/evidence paths')
    original, updated = blob(root, before, handoff), blob(root, after, handoff)
    require(updated.startswith(original) and len(updated) > len(original)
            and mode_blob(root, before, handoff)[0] == mode_blob(root, after, handoff)[0] == '100644',
            'Recovery handoff must append to original bytes')
    require(mode_blob(root, after, readme)[0] == '100644'
            and 0 < len(blob(root, after, readme)) <= 8192,
            'Recovery README must be a new bounded metadata record')
    acquired, expires = (instant(left['lease'][key]) for key in ('acquiredAt', 'expiresAt'))
    require(acquired <= commit_time(root, after) < expires
            and 0 < (expires-acquired).total_seconds() <= 168*3600,
            'Recovery historical source/merge lease is invalid')
    return left


def recovery_transaction(root, before, after, admitted, implementation, completion):
    require(ancestor(root, completion, before), 'Recovery source must follow actual authority Completion')
    left = recovery_shape(root, before, after)
    raw = blob(root, before, RECOVERY_APPROVAL)
    record = recovery_approval_record(root, raw)
    require(record['implementationCommit'] == implementation
            and record['beforeRegistrySha256'] == hashlib.sha256(json.dumps(left, sort_keys=True,
                separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            and record['beforeTaskSha256'] == hashlib.sha256(blob(root, before, TASK)).hexdigest(),
            'Recovery approval does not match the current before tuple')
    canonical = chain(root, admitted)
    creators = []
    for node in git(root, 'rev-list', '--full-history', '--reverse', RECOVERY_REGISTRATION+'..'+before,
                    '--', RECOVERY_APPROVAL).decode().split():
        graph = parents(root, node)
        previous = blob(root, graph[0], RECOVERY_APPROVAL, missing=True)
        current = blob(root, node, RECOVERY_APPROVAL, missing=True)
        require(current == raw and mode_blob(root, node, RECOVERY_APPROVAL)[0] == '100644',
                'Committed recovery approval was rewritten, deleted or chmodded')
        if previous is None and not any(blob(root, side, RECOVERY_APPROVAL, missing=True) == raw for side in graph[1:]):
            creators.append(node)
    require(len(creators) == 1, 'Recovery approval needs one preceding creator commit')
    creator = creators[0]
    creator_parents = parents(root, creator)
    require(creator != after and ancestor(root, creator, before)
            and creator_in_history(root, creator, canonical)
            and len(creator_parents) == 1 and creator_parents[0] in canonical
            and rows(document(root, creator, PLAN), 'foundationTasks')[RECOVERY_OWNER]['status'] in {'review', 'integration'}
            and rows(document(root, creator, ACTIVE))[RECOVERY_OWNER]['agentRole'] in {'reviewer', 'integrator'}
            and ancestor(root, implementation, creator)
            and blob(root, admitted, RECOVERY_APPROVAL) == blob(root, after, RECOVERY_APPROVAL) == raw
            and mode_blob(root, admitted, RECOVERY_APPROVAL)[0] == '100644',
            'Recovery approval must precede recovery on normally admitted Review/Completion')
    when = instant(record['approvedAt'])
    acquired, expires = (instant(left['lease'][key]) for key in ('acquiredAt', 'expiresAt'))
    require(commit_time(root, implementation) <= when < commit_time(root, creator)+timedelta(seconds=1)
            and acquired <= when < expires and acquired <= commit_time(root, after) < expires
            and 0 < (expires-acquired).total_seconds() <= 168*3600,
            'Recovery approval or historical source/merge lease is invalid')
    require(blob(root, completion, RECOVERY_PREFIX+'README.md', missing=True) is None,
            'Recovery README must be new after authority Completion')
    return FIELDS


def _validate_recovery_range(root, before, after, admitted, edits):
    # A merge whose tree restores the original approval can hide side edits
    # from Git's simplified path history. Recheck the whole admitted proof,
    # including creator shape, rather than trusting only this call's range.
    audit_recovery_metadata(root, RECOVERY_REGISTRATION, after)
    if not ancestor(root, admitted, after):
        audit_recovery_metadata(root, RECOVERY_REGISTRATION, admitted)
    if branch_pair(root, before, after) == (OLD, RECOVERY_NEW):
        left = recovery_shape(root, before, after)
        record = recovery_approval_record(root, blob(root, before, RECOVERY_APPROVAL))
        require(record['beforeRegistrySha256'] == hashlib.sha256(json.dumps(left, sort_keys=True,
                    separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
                and record['beforeTaskSha256'] == hashlib.sha256(blob(root, before, TASK)).hexdigest(),
                'Recovery approval does not match the current before tuple')
    for node in edits:
        require(branch_pair(root, parents(root, node)[0], node) == (OLD, RECOVERY_NEW),
                'Recovery branch change is not the declared one-way pair')
    complete_ancestry(root, after)
    implementation, completion = authority(root, admitted,
        source_before=parents(root, edits[0])[0], _recovery=True)
    main_nodes = set()
    for reference in ('refs/heads/main', 'refs/remotes/origin/main'):
        head = git(root, 'rev-parse', '--verify', reference+'^{commit}', missing=True)
        if head:
            main_nodes.update(chain(root, head.decode().strip()))
    require(main_nodes, 'Recovery requires a main reference for integration history')
    events = {}
    nodes = git(root, 'rev-list', '--full-history', '--topo-order', '--reverse',
                RECOVERY_REGISTRATION+'..'+after, '--', ACTIVE, TASK).decode().split()
    for node in nodes:
        graph = parents(root, node)
        if not graph or not branch_pair(root, graph[0], node):
            continue
        require(branch_pair(root, graph[0], node) == (OLD, RECOVERY_NEW),
                'Recovery branch change is not the declared one-way pair')
        require(node not in main_nodes or len(graph) == 2,
                'Recovery integration on main requires an ordinary two-parent merge')
        if len(graph) == 1:
            recovery_transaction(root, graph[0], node, admitted, implementation, completion)
            events[node] = node
        else:
            require(len(graph) == 2, 'Recovery requires an ordinary two-parent merge')
            incoming = [event for event in events if ancestor(root, event, graph[1])]
            require(len(incoming) == 1 and ancestor(root, completion, graph[1])
                    and git(root, 'diff', '--name-only', graph[1], node) == b'',
                    'Recovery merge must import the exact single qualified source tree')
            recovery_transaction(root, graph[0], node, admitted, implementation, completion)
    require(len(events) == 1, 'Recovery has more than one source transaction')
    if branch_pair(root, before, after):
        recovery_transaction(root, before, after, admitted, implementation, completion)
        return {TARGET: FIELDS}
    return {}


def validate_range(root, before, after, admitted=None):
    before, after = resolve(root, before), resolve(root, after)
    admitted = resolve(root, admitted or before)
    registration = git(root, 'rev-parse', '--verify', RECOVERY_REGISTRATION+'^{commit}', missing=True)
    if registration is None or not ancestor(root, RECOVERY_REGISTRATION, after):
        # Copied records and a reachable object outside this lineage cannot
        # establish the new authority. Preserve every original legacy check;
        # in particular, its exact one-way pair cannot admit RECOVERY_NEW.
        edits = migration_edits(root, before, after)
        return _validate_legacy_range(root, before, after, admitted, edits)
    left = rows(document(root, before, ACTIVE)).get(TARGET, {})
    right = rows(document(root, after, ACTIVE)).get(TARGET, {})
    if left.get('branch') != right.get('branch') and RECOVERY_NEW in (left.get('branch'), right.get('branch')):
        # Reject a known retired ancestor before path-history traversal needs
        # any of its intentionally unimported historical large-media trees.
        complete_ancestry(root, after)
    audit_recovery_metadata(root, before, after)
    edits = migration_edits(root, before, after)
    if any(RECOVERY_NEW in branch_pair(root, parents(root, node)[0], node) for node in edits):
        return _validate_recovery_range(root, before, after, admitted, edits)
    return _validate_legacy_range(root, before, after, admitted, edits)


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

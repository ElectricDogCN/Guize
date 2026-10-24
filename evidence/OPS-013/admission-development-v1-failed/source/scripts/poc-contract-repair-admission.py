#!/usr/bin/env python3
"""Authenticate the single declared POC repair; never grant Task-ID-only scope."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml

PLAN = 'specs/coordination/program-plan.yaml'
ACTIVE = 'specs/coordination/active-work.yaml'
LEDGER = 'specs/coordination/task-completions.yaml'
AUTHORITY = 'OPS-013'
SUCCESSOR = 'OPS-014'
INTENT = 'evidence/OPS-013/contract-repair-authorization.json'
INTENT_SHA256 = '4f344a74a47a56ff1c3b0e27c368767e0cb779ebc61e721b263f102b39a83401'
AUTHORITY_CLAIMS = {
    'AGENTS.md', 'scripts/check-program-lifecycle-guards.py',
    'scripts/check-program-plan-transitions.py', 'scripts/check-program-plan-history.py',
    'scripts/poc-contract-repair-admission.py',
    'tests/governance/test_poc_contract_repair_admission.py',
}
REPAIR_PATHS = {'specs/poc/check_program.py', 'specs/poc/test_program.py'}
_HISTORY = None


class AdmissionError(ValueError):
    """Missing, malformed or noncanonical authority must retain normal denial."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdmissionError(message)


def git(root: str, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    require(result.returncode == 0, 'Cannot read committed repair authority: '+str(args[:2]))
    return result.stdout


def resolve(root: str, ref: str) -> str:
    value = git(root, 'rev-parse', '--verify', ref+'^{commit}').decode().strip()
    require(bool(re.fullmatch(r'[0-9a-f]{40}', value)), 'Invalid committed repair base')
    return value


def blob(root: str, ref: str, path: str) -> bytes:
    return git(root, 'show', ref+':'+path)


def document(root: str, ref: str, path: str) -> dict[str, Any]:
    value = yaml.safe_load(blob(root, ref, path))
    require(isinstance(value, dict), 'Repair authority document must be a mapping')
    return value


def rows(value: Any) -> dict[str, dict[str, Any]]:
    require(isinstance(value, list), 'Repair authority records must be a list')
    result = {}
    for row in value:
        require(isinstance(row, dict) and isinstance(row.get('taskId'), str), 'Invalid authority identity')
        require(row['taskId'] not in result, 'Duplicate repair authority identity')
        result[row['taskId']] = row
    return result


def chain(root: str, ref: str) -> list[str]:
    return git(root, 'rev-list', '--first-parent', '--reverse', ref).decode().split()


def parent(root: str, ref: str) -> str:
    return resolve(root, ref+'^1')


def changed(root: str, before: str, after: str) -> set[str]:
    # --no-renames explicitly retains both names; a rename cannot hide a source.
    return set(git(root, 'diff', '--name-only', '--no-renames', before, after).decode().splitlines())


def entry_at(root: str, ref: str, task_id: str) -> dict[str, Any] | None:
    return rows(document(root, ref, ACTIVE).get('tasks')).get(task_id)


def introduction(root: str, history: list[str], task_id: str) -> tuple[str, dict[str, Any]] | None:
    found = None
    was_present = False
    for node in history:
        # Early bootstrap commits may predate the Registry. Only missing files
        # are absence; unreadable/malformed later snapshots are not ignored.
        exists = subprocess.run(['git','-C',str(root),'cat-file','-e',node+':'+ACTIVE],capture_output=True)
        if exists.returncode:
            require(found is None, 'Registry disappeared after repair registration')
            continue
        entry = entry_at(root, node, task_id)
        if entry and not was_present:
            require(found is None, 'Repair identity was reintroduced')
            found = (node, entry)
        was_present = entry is not None
    return found


def history_module():
    global _HISTORY
    if _HISTORY is None:
        # Loaded lazily: history itself imports lifecycle, which uses this proof.
        spec = importlib.util.spec_from_file_location(
            'guize_poc_admission_history', Path(__file__).with_name('check-program-plan-history.py'))
        require(spec is not None and spec.loader is not None, 'Missing normal Foundation history checker')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _HISTORY = module
    return _HISTORY


def validate_entry(entry: dict[str, Any], task_id: str, paths: set[str], when: datetime) -> None:
    require(entry.get('taskId') == task_id and entry.get('programTaskId') == task_id,
            'Repair Task identity mismatch')
    require(entry.get('moduleIds') == ['MOD-GOV'] and entry.get('riskLevel') == 'high'
            and entry.get('programWave') == 'FOUNDATION' and entry.get('programPlan') == PLAN,
            'Repair requires its independent high-risk Foundation registration')
    claims = entry.get('exclusivePaths')
    require(isinstance(claims, list) and len(claims) == len(paths) and set(claims) == paths
            and entry.get('sharedPaths') == [], 'Repair claims must equal the exact declared paths')
    identities = [entry.get(k) for k in ('owner','coordinator','implementer','reviewer','integrator')]
    require(all(isinstance(x,str) and x.strip() and x.lower() not in {'none','tbd','pending','unassigned'} for x in identities)
            and entry['implementer'] != entry['reviewer'], 'Repair requires assigned independent roles')
    acquired = datetime.fromisoformat(entry['lease']['acquiredAt'].replace('Z','+00:00'))
    expires = datetime.fromisoformat(entry['lease']['expiresAt'].replace('Z','+00:00'))
    require(acquired.tzinfo is not None and expires.tzinfo is not None
            and acquired.utcoffset().total_seconds() == expires.utcoffset().total_seconds() == 0
            and acquired <= when < expires and 0 < (expires-acquired).total_seconds() <= 168*3600,
            'Repair lease is invalid at the actual observation')


def validate_capacity(root: str, base: str, entry: dict[str, Any]) -> None:
    registry = document(root,base,ACTIVE)
    current = rows(registry.get('tasks'))
    current[SUCCESSOR] = entry
    policy = registry['policy']
    require(len(current) <= policy['maxActiveTasks']
            and sum(x.get('riskLevel') in {'high','critical'} for x in current.values()) <= policy['maxHighRiskTasks'],
            'Repair exceeds the existing active/high capacity')
    errors: list[str] = []
    history_module().historical_conflicts(SUCCESSOR,entry,registry,'Bound POC repair',errors)
    require(not errors, 'Repair overlaps another actual lease: '+'; '.join(errors))


def authority(root: str, base: str) -> tuple[dict[str, Any], str]:
    """Prove immutable intent and the actual normal completed Foundation chain."""
    canonical = chain(root, base)
    original = introduction(root, canonical, AUTHORITY)
    require(original is not None, 'No original canonical authority registration')
    registration, reserved = original
    preceding = parent(root, registration)
    raw = blob(root, registration, INTENT)
    require(hashlib.sha256(raw).hexdigest() == INTENT_SHA256, 'Original authorization intent differs')
    intent = json.loads(raw)
    require(intent.get('kind') == 'one_poc_contract_repair_authorization_intent'
            and intent.get('authorityTaskId') == AUTHORITY
            and intent.get('reservationParent') == preceding,
            'Authorization intent is not parent-bound')
    require(reserved.get('status') == 'reserved' and reserved.get('agentRole') == 'coordinator'
            and reserved.get('baseSha') == preceding, 'Authority did not start metadata-only reserved')
    observed = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',registration)),timezone.utc)
    validate_entry(reserved, AUTHORITY, AUTHORITY_CLAIMS, observed)
    metadata = {PLAN,ACTIVE,'specs/tasks/'+AUTHORITY+'.md'}
    require(metadata <= changed(root,preceding,registration)
            and all(p in metadata or p.startswith('evidence/'+AUTHORITY+'/')
                    for p in changed(root,preceding,registration)), 'Authority reservation contains implementation')
    defect = intent['defect']
    for ref_key, sha_key in [('sourceObservationRef','sourceObservationSha256'),
                             ('actualExecutionReviewRef','actualExecutionReviewSha256'),
                             ('responseRef','responseSha256')]:
        require(hashlib.sha256(blob(root,registration,defect[ref_key])).hexdigest() == defect[sha_key],
                'Original defect evidence differs from declared Git bytes')
    require(len(blob(root,registration,defect['responseRef'])) == defect['responseBytes'], 'Defect response length differs')
    successor = intent['successor']
    require(successor['taskId'] == SUCCESSOR and {p['path'] for p in successor['paths']} == REPAIR_PATHS,
            'Authorization declares another repair')
    for record in successor['paths']:
        value = blob(root,preceding,record['path'])
        require(len(value) == record['bytes'] and hashlib.sha256(value).hexdigest() == record['gitBlobSha256'],
                'Original approved contract baseline differs')
    for node in canonical[canonical.index(registration):]:
        require(blob(root,node,INTENT) == raw, 'Authorization intent changed after registration')
    plan = document(root,base,PLAN)
    completed = rows(plan.get('foundationTasks')).get(AUTHORITY,{})
    require(completed.get('status') == 'completed' and entry_at(root,base,AUTHORITY) is None,
            'Authority has not normally completed and released capacity')
    implementation = completed.get('mergeCommit')
    require(implementation in canonical and canonical.index(implementation) > canonical.index(registration),
            'Authority implementation is not integrated after its reservation')
    finish = None
    reviewed = False
    for node in canonical[canonical.index(implementation)+1:]:
        state = rows(document(root,node,PLAN).get('foundationTasks')).get(AUTHORITY,{})
        live = entry_at(root,node,AUTHORITY)
        if state.get('status') in {'review','integration'} and live and live.get('agentRole') in {'reviewer','integrator'}:
            reviewed = True
        if state.get('status') == 'completed':
            require(reviewed and state == completed and live is None,
                    'Authority requires a real independent Review before Completion')
            finish = node
            break
    require(finish is not None, 'Authority Completion is not on canonical history')
    before = parent(root,finish)
    require(rows(document(root,before,PLAN).get('foundationTasks'))[AUTHORITY]['status'] in {'review','integration'},
            'Authority completed outside normal Review lifecycle')
    history = history_module()
    errors: list[str] = []
    front,_ = history.parse_front_matter(blob(root,finish,'specs/tasks/'+AUTHORITY+'.md').decode())
    history.validate_foundations(root,document(root,before,PLAN),document(root,finish,PLAN),
        document(root,before,ACTIVE),document(root,finish,ACTIVE),document(root,before,LEDGER),
        document(root,finish,LEDGER),before,finish,str(front.get('workBranch') or ''),errors,task_hint=AUTHORITY)
    require(not errors, 'Normal authority Foundation history rejected: '+'; '.join(errors))
    return intent, registration


def prove_claims(root: str, task_id: str, entry: dict[str, Any], base_ref: str,
                 *, observed_ref: str | None = None) -> set[str]:
    """Supplement ownership only; all normal transition/history/recovery gates remain."""
    require(task_id == SUCCESSOR, 'No declared repair for this identity')
    when = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',observed_ref)),timezone.utc) if observed_ref else datetime.now(timezone.utc)
    validate_entry(entry,task_id,REPAIR_PATHS,when)
    base = resolve(root,base_ref)
    original = introduction(root,chain(root,base),task_id)
    if original is None:
        require(entry.get('status') == 'reserved' and entry.get('agentRole') == 'coordinator'
                and entry.get('baseSha') == base, 'Unregistered repair cannot implement')
        admission_base = base
        reserved = entry
    else:
        registration,reserved = original
        admission_base = parent(root,registration)
        require(reserved.get('status') == 'reserved' and reserved.get('agentRole') == 'coordinator'
                and reserved.get('baseSha') == admission_base, 'Repair original reservation is not parent-bound')
        metadata = {PLAN,ACTIVE,'specs/tasks/'+task_id+'.md'}
        paths = changed(root,admission_base,registration)
        require(metadata <= paths and all(p in metadata or p.startswith('evidence/'+task_id+'/') for p in paths),
                'Repair original reservation was not metadata-only')
        # Scope/role/lease history is independently audited by the normal gates.
        require(all(entry.get(k) == reserved.get(k) for k in
                    ('owner','coordinator','implementer','reviewer','integrator','issue','dependsOn')),
                'Repair stable identity differs from its original reservation')
        history = history_module()
        front,body = history.parse_front_matter(blob(root,registration,'specs/tasks/'+task_id+'.md').decode())
        errors: list[str] = []
        history.stable_spec_matches(task_id,reserved,front,body,errors,reservation=True)
        require(not errors and front.get('schemaVersion') == 2 and front.get('status') == 'reserved'
                and front.get('agentRole') == 'coordinator' and front.get('coordinationMode') == 'registry'
                and front.get('evidencePath') == 'evidence/'+task_id
                and front.get('handoffPath') == 'evidence/'+task_id+'/handoff.md',
                'Repair original Task does not bind its exact registration: '+'; '.join(errors))
        require(bool(blob(root,registration,'evidence/'+task_id+'/handoff.md').strip()),
                'Repair original handoff is missing')
    intent,_ = authority(root,admission_base)
    require(blob(root,base,INTENT) == blob(root,admission_base,INTENT), 'Current authority intent changed')
    for record in intent['successor']['paths']:
        raw = blob(root,admission_base,record['path'])
        require(len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['gitBlobSha256'],
                'Repair original reservation base changed the approved contract')
    require(reserved.get('dependsOn') == [AUTHORITY], 'Repair must depend on its completed authority')
    original_time = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',original[0])),timezone.utc) if original else datetime.now(timezone.utc)
    validate_entry(reserved,task_id,REPAIR_PATHS,original_time)
    validate_capacity(root,admission_base,reserved)
    validate_capacity(root,base,entry)
    return set(REPAIR_PATHS)


def authenticated_claims(root: str | None, task_id: str, entry: dict[str, Any], base_ref: str,
                         *, observed_ref: str | None = None) -> set[str]:
    if not root or task_id != SUCCESSOR:
        return set()
    try:
        return prove_claims(root,task_id,entry,base_ref,observed_ref=observed_ref)
    except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError):
        return set()


def validate_repair_changes(root: str, before: str, after: str, task_id: str,
                            paths: set[str], errors: list[str]) -> None:
    """Claim admission cannot authorize changing a completed contract while active."""
    if task_id != SUCCESSOR or not paths.intersection(REPAIR_PATHS):
        return
    try:
        left, right = document(root,before,PLAN), document(root,after,PLAN)
        recovery = left.get('recovery')
        require(left.get('status') == right.get('status') == 'frozen'
                and isinstance(recovery,dict) and right.get('recovery') == recovery,
                'Contract changes require a preceding unchanged frozen recovery event')
        require(recovery.get('taskId') == SUCCESSOR
                and recovery.get('affectedTasks') == ['GZ-021'],
                'Contract recovery must bind its actual owner and completed producer GZ-021')
        source = resolve(root,recovery['sourceCommit'])
        require(source in chain(root,before) and source != resolve(root,before),
                'Contract recovery must already descend from its declared source')
        original = document(root,source,PLAN)
        require(original.get('status') == 'active'
                and rows(original.get('tasks')).get('GZ-021',{}).get('status') == 'completed',
                'Contract recovery source must retain the completed producer')
        for plan in (left,right):
            require(rows(plan.get('tasks')).get('GZ-021') == rows(original.get('tasks')).get('GZ-021'),
                    'Contract recovery cannot rewrite the completed producer')
        entry = entry_at(root,after,SUCCESSOR)
        require(entry is not None and entry.get('status') in {'in_progress','review','integration'},
                'Contract edits require a separately registered working repair')
        prove_claims(root,SUCCESSOR,entry,before,observed_ref=after)
    except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError) as exc:
        errors.append('Bound POC contract recovery rejected: '+str(exc))

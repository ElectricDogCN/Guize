#!/usr/bin/env python3
"""Authenticate the single declared POC repair; never grant Task-ID-only scope."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from contextvars import ContextVar
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, NamedTuple

import yaml

# The input remains the same immutable Git bytes and safe YAML dialect. The
# C-backed safe parser avoids reparsing each large canonical Registry in Python
# during every independently audited original-history snapshot.
SAFE_DOCUMENT_LOADER = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)

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


class RepairContract(NamedTuple):
    authority: str
    successor: str
    intent: str
    digest: str
    claims: frozenset[str]
    paths: frozenset[str]


SOURCE_COMPATIBILITY = RepairContract(
    'OPS-017', 'OPS-018', 'evidence/OPS-017/source-compatibility-admission-intent.json',
    '985942645f493d1e25f1034842aa588594d83a8a0e5587526c830251ee23fdb5',
    frozenset({'AGENTS.md', 'scripts/poc-contract-repair-admission.py',
               'scripts/check-program-lifecycle-guards.py',
               'tests/governance/test_poc_contract_repair_admission.py'}),
    frozenset({'specs/poc/program.schema.yaml', 'specs/poc/program.yaml',
               'specs/poc/check_program.py', 'specs/poc/test_program.py',
               'docs/18-testing-and-acceptance.md'}))

PERFORMANCE = RepairContract(
    'OPS-026', 'OPS-027', 'evidence/OPS-026/performance-repair-admission-intent.json',
    '1dedeb0167cf4f62bdca8de6c5f66f86764e10e6ecd7300964cdb4006543bac2',
    frozenset({'AGENTS.md', 'scripts/poc-contract-repair-admission.py',
               'scripts/check-program-lifecycle-guards.py',
               'tests/governance/test_poc_contract_repair_admission.py'}),
    frozenset({'specs/poc/check_program.py', 'specs/poc/test_program.py'}))

PERFORMANCE_SEMANTICS = (
    'equivalent bounded reuse of normalized string keys and sensitive-key classification; '
    'original str(key), value is not False, sensitive terms and boundaries, recursive traversal, '
    'value scanning and diagnostics unchanged; never cache validation, file, approval or permission results')

# A separately approved, prospective amendment. The original intent and its
# four claims retain their original meaning at every preceding snapshot.
SCOPE_AMENDMENT = 'evidence/OPS-017/scope-amendment-v1.json'
SCOPE_AMENDMENT_SHA256 = '4c08a88117b508dc4d772594d7481392f9059321a1f1a43f1928a6526ca38e5f'
SCOPE_AMENDMENT_BASE = '76be38c26dea26669819f142c572e69aac84c32b'
SCOPE_SUPPLEMENT = frozenset({'scripts/program-planning-revision.py',
                              'scripts/check-program-plan-history.py'})

# One real, independently accepted metadata integration. These are provenance
# inputs, never an observation-head override or a cached permission decision.
GOVERNANCE_SCOPE_MAIN = 'cf44f62f5141e62b5c13902809429aabe069ec51'
GOVERNANCE_SCOPE_SOURCE = '52d3ecf207ecec1b349b7ff3d4fb274e05aff3db'
GOVERNANCE_SCOPE_PARENT = '9e17626241fd1c6a6aae9d7493060b30eaa18560'
GOVERNANCE_SCOPE_TREE = '931a06e694b74beef589295bb11cdf407c9b27ed'
GOVERNANCE_MANIFEST = 'evidence/OPS-027/governance-prelude-admission-intent-v1.json'
GOVERNANCE_MANIFEST_SHA256 = 'd1fbd5e8661ae13d36809ccab0894b07467806b192aa1621763bcc9bc2ea61b1'
GOVERNANCE_PATHS = frozenset({'AGENTS.md','scripts/poc-contract-repair-admission.py',
    'tests/governance/test_poc_contract_repair_admission.py','tests/governance/test_program_schema_cache.py'})


def contract(task_id: str) -> RepairContract:
    if task_id == SUCCESSOR:
        return RepairContract(AUTHORITY, SUCCESSOR, INTENT, INTENT_SHA256,
                              frozenset(AUTHORITY_CLAIMS), frozenset(REPAIR_PATHS))
    if task_id == SOURCE_COMPATIBILITY.successor:
        return SOURCE_COMPATIBILITY
    if task_id == PERFORMANCE.successor:
        return PERFORMANCE
    raise AdmissionError('No declared repair for this identity')


def approved_paths(root: str, preceding: str, intent: dict[str, Any],
                   selected: RepairContract) -> list[dict[str, Any]]:
    if selected.successor == SUCCESSOR:
        successor = intent['successor']
        require(successor['taskId'] == selected.successor
                and {p['path'] for p in successor['paths']} == selected.paths,
                'Authorization declares another repair')
        return successor['paths']
    if selected.successor == PERFORMANCE.successor:
        require(intent.get('schemaVersion') == 1
                and intent.get('kind') == 'one_equivalent_poc_validator_performance_repair_authorization_intent'
                and intent.get('authorityTaskId') == selected.authority
                and intent.get('successorTaskId') == selected.successor
                and intent.get('reservationParent') == preceding
                and intent.get('issue') == 237,
                'Performance repair intent identity is not parent-bound')
        for field, expected in [('authorityClaims', selected.claims), ('repairPaths', selected.paths)]:
            value = intent.get(field)
            require(isinstance(value, list) and len(value) == len(expected) and set(value) == expected,
                    'Performance repair intent has different exact paths')
        for field in ('repairRequiresIndependentReservation',
                      'repairRequiresActualFreezeVerificationAndIndependentThaw',
                      'thresholdsProductionPlatformAndFullCiUnchanged'):
            require(intent.get(field) is True, 'Performance repair intent requires '+field)
        for field in ('originalAuthorityRewriteAllowed', 'historicalExecutionRebindingAllowed',
                      'compatibilityMigrationGuaranteed', 'historicalAttemptQualificationGuaranteed'):
            require(intent.get(field) is False, 'Performance repair intent forbids '+field)
        require(intent.get('requiredSemantics') == PERFORMANCE_SEMANTICS,
                'Performance repair intent has different semantics')
        bindings = intent.get('targetParentBindings')
        require(isinstance(bindings, list) and len(bindings) == len(selected.paths)
                and all(isinstance(item, dict) and set(item) == {'path', 'gitBlob', 'sha256'}
                        for item in bindings)
                and {item['path'] for item in bindings} == selected.paths,
                'Performance repair requires exact, unique original target bindings')
        records = []
        for item in bindings:
            path = item['path']
            identity = git(root, 'ls-tree', preceding, '--', path).decode().split()
            require(len(identity) == 4 and identity[0] in {'100644', '100755'}
                    and identity[1] == 'blob' and identity[3] == path
                    and identity[2] == item['gitBlob'],
                    'Performance repair original target is not its actual regular Git blob')
            raw = blob(root, preceding, path)
            digest = hashlib.sha256(raw).hexdigest()
            require(digest == item['sha256'], 'Performance repair original target digest differs')
            records.append(dict(path=path, bytes=len(raw), gitBlobSha256=digest))
        return records
    require(intent.get('schemaVersion') == 1
            and intent.get('kind') == 'one_versioned_poc_source_compatibility_repair_authorization_intent'
            and intent.get('authorityTaskId') == selected.authority
            and intent.get('successorTaskId') == selected.successor
            and intent.get('reservationParent') == preceding
            and intent.get('issue') == 168,
            'Source compatibility intent identity is not parent-bound')
    for field, expected in [('authorityClaims', selected.claims), ('repairPaths', selected.paths)]:
        value = intent.get(field)
        require(isinstance(value, list) and len(value) == len(expected) and set(value) == expected,
                'Source compatibility intent has different exact paths')
    for field in ('repairRequiresIndependentReservation', 'repairRequiresActualFreezeVerificationAndIndependentThaw',
                  'oldIndexStrictRulePreserved', 'thresholdsProductionPlatformAndFullCiUnchanged'):
        require(intent.get(field) is True, 'Source compatibility intent requires '+field)
    for field in ('originalAuthorityRewriteAllowed', 'historicalExecutionRebindingAllowed', 'compatibilityMigrationGuaranteed'):
        require(intent.get(field) is False, 'Source compatibility intent forbids '+field)
    require(intent.get('requiredSemantics') == 'versioned immutable complete dependency closure and separately approved current compatibility',
            'Source compatibility intent has different semantics')
    records = []
    for path in sorted(selected.paths):
        identity = git(root, 'ls-tree', preceding, '--', path).decode().split()
        require(len(identity) == 4 and identity[0] in {'100644', '100755'}
                and identity[1] == 'blob' and identity[3] == path,
                'Original repair baseline must be an actual regular Git blob')
        raw = blob(root, preceding, path)
        records.append(dict(path=path, bytes=len(raw), gitBlobSha256=hashlib.sha256(raw).hexdigest()))
    return records


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
    value = yaml.load(blob(root, ref, path), Loader=SAFE_DOCUMENT_LOADER)
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


def _introduction_sequential(root: str, history: list[str], task_id: str) -> tuple[str, dict[str, Any]] | None:
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


def _batched_registry_bytes(root: str, history: list[str]):
    """Fresh object IO only; None asks the original sequential reader to run."""
    # An optimization budget, not an admission limit: larger inputs retain the
    # original bounded-memory path and every original history check.
    if not history or len(history) > 4096:
        return None
    def batch(mode, expressions):
        result = subprocess.run(['git','-C',str(root),'cat-file',mode],
            input=b'\n'.join(expressions)+b'\n',capture_output=True)
        return result.stdout if result.returncode == 0 else None
    try:
        metadata = batch('--batch-check',[(node+':'+ACTIVE).encode() for node in history])
        if metadata is None:
            return None
        headers = metadata.splitlines()
        if len(headers) != len(history):
            return None
        ordered=[];unique={}
        for header in headers:
            if header.endswith(b' missing'):
                ordered.append(None)
                continue
            fields=header.split()
            if len(fields) != 3:
                return None
            oid,kind,length=fields;size=int(length)
            if size < 0:
                return None
            ordered.append((oid,kind))
            if kind == b'blob':
                if oid in unique and unique[oid] != size:
                    return None
                unique[oid]=size
        if sum(unique.values()) > 4*1024*1024:
            return None
        raw=batch('--batch',list(unique)) if unique else b''
        if raw is None:
            return None
        cursor=0;blobs={}
        for oid,size in unique.items():
            end=raw.find(b'\n',cursor)
            if end < 0:
                return None
            fields=raw[cursor:end].split()
            if len(fields) != 3 or fields[:2] != [oid,b'blob'] or int(fields[2]) != size:
                return None
            cursor=end+1;value=raw[cursor:cursor+size];cursor+=size
            if len(value) != size or raw[cursor:cursor+1] != b'\n':
                return None
            blobs[oid]=value;cursor+=1
        return (ordered,blobs) if cursor == len(raw) else None
    except (OSError,ValueError,TypeError,OverflowError):
        return None


def introduction(root: str, history: list[str], task_id: str) -> tuple[str, dict[str, Any]] | None:
    snapshots = _batched_registry_bytes(root,history)
    if snapshots is None:
        return _introduction_sequential(root,history,task_id)
    ordered,blobs=snapshots
    decoded={};found=None;was_present=False
    for node,record in zip(history,ordered):
        if record is None:
            require(found is None,'Registry disappeared after repair registration')
            continue
        oid,kind=record
        if kind != b'blob':
            # Keep git-show's existing representation/error and historical
            # error ordering for trees or any other non-file object.
            return _introduction_sequential(root,history,task_id)
        if oid not in decoded:
            value=yaml.load(blobs[oid],Loader=SAFE_DOCUMENT_LOADER)
            require(isinstance(value,dict),'Repair authority document must be a mapping')
            decoded[oid]=rows(value.get('tasks'))
        entry=decoded[oid].get(task_id)
        if entry and not was_present:
            require(found is None,'Repair identity was reintroduced')
            found=(node,entry)
        was_present=entry is not None
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


def scope_record(root: str, ref: str) -> bytes | None:
    identity = git(root,'ls-tree',ref,'--',SCOPE_AMENDMENT).decode().split()
    if not identity:
        return None
    require(len(identity) == 4 and identity[0] in {'100644','100755'}
            and identity[1] == 'blob' and identity[3] == SCOPE_AMENDMENT,
            'Scope amendment must be a regular committed file')
    raw = blob(root,ref,SCOPE_AMENDMENT)
    require(hashlib.sha256(raw).hexdigest() == SCOPE_AMENDMENT_SHA256,
            'Scope amendment differs from the approved immutable record')
    return raw


def scope_canonical_ref(root: str) -> str | None:
    for ref in ('origin/main','main'):
        probe = subprocess.run(['git','-C',str(root),'rev-parse','--verify',ref+'^{commit}'],capture_output=True)
        if probe.returncode == 0:
            return probe.stdout.decode().strip()
    return None


def scope_integration(root: str, admitted_base: str) -> str | None:
    """Only an actual main first-parent event already admitted may grant writes.

    A PR's virtual merge or an otherwise identical side merge is insufficient.
    The fetched main ref is checked independently of the observation endpoint.
    External source/main qualification and the bounded bootstrap exception are
    additional requirements; this helper certifies Git scope provenance only.
    """
    if scope_record(root,admitted_base) is None:
        return None
    canonical = scope_canonical_ref(root)
    if canonical is None:
        return None
    admitted = resolve(root,admitted_base)
    canonical_nodes = chain(root,canonical)
    if admitted not in canonical_nodes or SCOPE_AMENDMENT_BASE not in canonical_nodes:
        return None
    nodes = chain(root,admitted)
    if SCOPE_AMENDMENT_BASE not in nodes:
        return None
    event = None
    for node in nodes[nodes.index(SCOPE_AMENDMENT_BASE)+1:]:
        raw = scope_record(root,node)
        if event is None and raw is not None:
            parents = git(root,'show','-s','--format=%P',node).decode().split()
            require(len(parents) == 2 and parents[0] == SCOPE_AMENDMENT_BASE,
                    'Scope amendment requires its exact ordinary first-parent main merge')
            introduced = git(root,'rev-list','--reverse',SCOPE_AMENDMENT_BASE+'..'+parents[1],
                             '--',SCOPE_AMENDMENT).decode().split()
            require(len(introduced) == 1 and parent(root,introduced[0]) == SCOPE_AMENDMENT_BASE,
                    'Scope amendment source must start at its approved actual main')
            scope_record(root,introduced[0])
            event = node
        elif event is not None:
            require(raw is not None,'Scope amendment disappeared after main integration')
    return event


def declared_authority_paths(root: str, node: str, selected: RepairContract) -> set[str]:
    original = set(selected.claims)
    if selected.successor != SOURCE_COMPATIBILITY.successor or scope_record(root,node) is None:
        return original
    return original | set(SCOPE_SUPPLEMENT)


def audit_scope_amendment(root: str, before: str, after: str) -> None:
    """Validate declaration separately from write authority, including restores."""
    before,after = resolve(root,before),resolve(root,after)
    left,right = scope_record(root,before),scope_record(root,after)
    touched = git(root,'rev-list','--full-history',before+'..'+after,'--',SCOPE_AMENDMENT).decode().split()
    entry = entry_at(root,after,SOURCE_COMPATIBILITY.authority)
    if left is None and right is None and not touched:
        if entry is not None:
            require(set(entry.get('exclusivePaths') or []) == set(SOURCE_COMPATIBILITY.claims),
                    'Repair claims must equal the exact declared paths')
        return
    require(right is not None,'Scope amendment cannot be removed or supplied only in an intermediate node')
    require(subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',SCOPE_AMENDMENT_BASE,after],capture_output=True).returncode == 0,
            'Scope amendment is not descended from its approved integration base')
    # Historical H callers supply each edge's actual parent, which can be an
    # old peer. Only fetched canonical main supplies the shared admission.
    canonical = scope_canonical_ref(root)
    grant = scope_integration(root,canonical) if canonical is not None else None
    nodes = git(root,'rev-list','--reverse',before+'..'+after).decode().split()
    for node in nodes:
        # A peer may predate this policy's fixed base. Preserve that immutable
        # pre-existing prefix; unrelated local side work is not its ancestor
        # and remains audited, including edit/restore before a later import.
        if subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',node,SCOPE_AMENDMENT_BASE],capture_output=True).returncode == 0:
            continue
        previous = parent(root,node)
        paths = changed(root,previous,node)
        history = history_module()
        incoming = history.approved_synchronization_parents(root,node,canonical) if canonical is not None else []
        imports = history.clean_synchronization_paths(root,node,
                    paths & ({SCOPE_AMENDMENT} | set(SCOPE_SUPPLEMENT)),incoming) if incoming else set()
        old_record,new_record = scope_record(root,previous),scope_record(root,node)
        if old_record is not None:
            require(new_record is not None,'Scope amendment disappeared in introduced history')
        elif new_record is not None:
            require(previous == SCOPE_AMENDMENT_BASE or SCOPE_AMENDMENT in imports,
                    'Scope amendment cannot be introduced late or on another baseline')
        if (paths & set(SCOPE_SUPPLEMENT)) - imports:
            require(grant is not None and subprocess.run(
                ['git','-C',str(root),'merge-base','--is-ancestor',grant,previous],capture_output=True).returncode == 0,
                'Supplemental writes require the previously integrated amendment main')
        own = entry_at(root,node,SOURCE_COMPATIBILITY.authority)
        if own is not None and new_record is not None:
            observed = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',node)),timezone.utc)
            validate_entry(own,SOURCE_COMPATIBILITY.authority,
                           set(SOURCE_COMPATIBILITY.claims) | set(SCOPE_SUPPLEMENT),observed,historical=True)


def audit_source_authority_intent(root: str, base: str, observation: str,
                                 *, selected: RepairContract | None = None) -> None:
    """Protect the registered original even while its authority is implementing."""
    selected = SOURCE_COMPATIBILITY if selected is None else selected
    exists = lambda ref: subprocess.run(
        ['git','-C',str(root),'cat-file','-e',ref+':'+selected.intent],capture_output=True).returncode == 0
    admitted = exists(base)
    if admitted:
        # This check grants no scope and does not require Completion. Inspect
        # original canonical intent changes too, including an earlier restore.
        nodes = git(root,'rev-list','--first-parent','--reverse',base,'--',selected.intent).decode().split()
        for node in nodes:
            require(hashlib.sha256(blob(root,node,selected.intent)).hexdigest() == selected.digest,
                    'Authorization intent changed after registration')
    # Follow every side branch and retain merges, including TREESAME imports.
    # The displayed parents are rewritten by Git: only select commit identities
    # here and keep auditing each commit against its real first parent below.
    candidates = git(root,'rev-list','--full-history','--parents','--reverse',
                     base+'..'+observation,'--',selected.intent).decode().splitlines()
    for record in candidates:
        node = record.split()[0]
        previous = parent(root,node)
        if selected.intent not in changed(root,previous,node):
            continue
        incoming = history_module().approved_synchronization_parents(root,node,base)
        imports = history_module().clean_synchronization_paths(root,node,{selected.intent},incoming) if incoming else set()
        if selected.intent in imports:
            continue
        # Only the first real, parent-bound reservation may create the original.
        first = entry_at(root,node,selected.authority) if not admitted and not exists(previous) else None
        require(first is not None and first.get('status') == 'reserved'
                and first.get('agentRole') == 'coordinator' and first.get('baseSha') == previous
                and hashlib.sha256(blob(root,node,selected.intent)).hexdigest() == selected.digest,
                'Authorization intent changed after registration')
    if selected.successor == SOURCE_COMPATIBILITY.successor:
        audit_scope_amendment(root,base,observation)


def validate_source_authority_intent(root: str, before: str, after: str, errors: list[str],
                                     *, selected: RepairContract | None = None) -> None:
    try:
        if selected is None:
            audit_source_authority_intent(root,resolve(root,before),resolve(root,after))
        else:
            audit_source_authority_intent(root,resolve(root,before),resolve(root,after),selected=selected)
    except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError) as exc:
        errors.append('Bound POC authority intent audit rejected: '+str(exc))


def source_protected_ref(root: str, base: str, observation: str,
                         *, selected: RepairContract | None = None) -> str:
    """Use admitted main history for a peer's proven, automatic main import."""
    if selected is None:
        selected = SOURCE_COMPATIBILITY
        audit_source_authority_intent(root,base,observation)
    else:
        audit_source_authority_intent(root,base,observation,selected=selected)
    admitted = introduction(root,chain(root,base),selected.successor)
    observed = introduction(root,chain(root,observation),selected.successor)
    if admitted is None or (observed is not None and admitted[0] == observed[0]):
        return observation
    require(subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',base,observation],
                           capture_output=True).returncode == 0,
            'Peer synchronization does not import its admitted main base')
    history = history_module()
    task_paths = {task:'specs/tasks/'+task+'.md' for task in (selected.authority,selected.successor)}
    fixed = set(selected.claims) | set(selected.paths) | {selected.intent,*task_paths.values()}
    if selected.successor == PERFORMANCE.successor:
        fixed |= set(GOVERNANCE_PATHS) | {GOVERNANCE_MANIFEST}
    for node in git(root,'rev-list','--reverse',base+'..'+observation).decode().split():
        previous = parent(root,node)
        paths = changed(root,previous,node)
        own = {path for path in paths if path in fixed or any(
            path.startswith('evidence/'+task+'/') for task in task_paths)}
        incoming = history.approved_synchronization_parents(root,node,base)
        candidates = (own | {PLAN,ACTIVE}) & paths
        imports = history.clean_synchronization_paths(root,node,candidates,incoming) if incoming and candidates else set()
        require(not (own-imports), 'Peer synchronization contains unadmitted local authority or repair changes')
        for task,path in task_paths.items():
            require(not history.foundation_local_metadata_changed(root,previous,node,task,paths,{path},imports,incoming),
                    'Peer synchronization changed protected authority or repair metadata')
    return base


def validate_entry(entry: dict[str, Any], task_id: str, paths: set[str], when: datetime,
                   *, historical: bool = False) -> None:
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
            and (acquired < when+timedelta(seconds=1) if historical else acquired <= when)
            and when < expires and 0 < (expires-acquired).total_seconds() <= 168*3600,
            'Repair lease is invalid at the actual observation')


def _audit_performance_target_history(root: str, preceding: str, admitted: str) -> None:
    """Keep both original targets intact on every imported pre-admission edge."""
    paths = sorted(PERFORMANCE.paths)
    expected = git(root,'ls-tree',preceding,'--',*paths)
    records = git(root,'rev-list','--full-history','--parents','--reverse',
                  preceding+'..'+admitted,'--',*paths).decode().splitlines()
    for record in records:
        node = record.split()[0]
        # Git's path-filtered display may rewrite parents; use the real edge.
        for ref in (parent(root,node), node):
            require(git(root,'ls-tree',ref,'--',*paths) == expected,
                    'Performance repair target changed in original admission history')


def validate_capacity(root: str, base: str, entry: dict[str, Any], *, successor: str = SUCCESSOR) -> None:
    registry = document(root,base,ACTIVE)
    current = rows(registry.get('tasks'))
    current[successor] = entry
    policy = registry['policy']
    require(len(current) <= policy['maxActiveTasks']
            and sum(x.get('riskLevel') in {'high','critical'} for x in current.values()) <= policy['maxHighRiskTasks'],
            'Repair exceeds the existing active/high capacity')
    errors: list[str] = []
    history_module().historical_conflicts(successor,entry,registry,'Bound POC repair',errors)
    require(not errors, 'Repair overlaps another actual lease: '+'; '.join(errors))


def audit_performance_governance_phase(root: str, base: str, observation: str) -> set[str]:
    """Authenticate historical Gov facts, without granting either P claim.

    Full authority and ordinary lifecycle/scope gates remain separate. Nothing
    here accepts CI or Review flags from Evidence. Source/main qualification is
    an additional external integration requirement, as in the original grant.
    """
    base,observation=resolve(root,base),resolve(root,observation)
    record=lambda ref:git(root,'ls-tree',ref,'--',GOVERNANCE_MANIFEST)
    touched=git(root,'rev-list','--full-history',base+'..'+observation,'--',GOVERNANCE_MANIFEST)
    if not record(base) and not record(observation) and not touched:
        # Claims cannot hide this phase by omitting/deleting its manifest,
        # including an intermediate expansion later restored at a merge tip.
        candidates={base,observation}
        candidates.update(git(root,'rev-list','--full-history','--reverse',base+'..'+observation,'--',ACTIVE).decode().split())
        entries=[entry_at(root,node,PERFORMANCE.successor) for node in candidates]
        if all(entry is None or (set(entry.get('exclusivePaths') or [])==set(PERFORMANCE.paths)
                                and entry.get('sharedPaths')==[]) for entry in entries):
            return set()  # Genuine original exact-two history keeps its meaning.
    require(_immutable_git_view(root) is not None,'Gov phase requires an ordinary immutable Git view')
    canonical=scope_canonical_ref(root)
    require(canonical is not None and GOVERNANCE_SCOPE_MAIN in chain(root,canonical),
            'Gov phase requires its actual canonical scope main')
    parents=lambda ref:git(root,'show','-s','--format=%P',ref).decode().split()
    ancestor=lambda a,b:subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',a,b],capture_output=True).returncode==0
    require(parents(GOVERNANCE_SCOPE_MAIN)==[GOVERNANCE_SCOPE_PARENT,GOVERNANCE_SCOPE_SOURCE]
            and parent(root,GOVERNANCE_SCOPE_SOURCE)==GOVERNANCE_SCOPE_PARENT
            and git(root,'rev-parse',GOVERNANCE_SCOPE_MAIN+'^{tree}').decode().strip()==GOVERNANCE_SCOPE_TREE
            and git(root,'rev-parse',GOVERNANCE_SCOPE_SOURCE+'^{tree}').decode().strip()==GOVERNANCE_SCOPE_TREE,
            'Gov phase scope integration differs from its fixed real graph')
    require(observation==GOVERNANCE_SCOPE_SOURCE or ancestor(GOVERNANCE_SCOPE_MAIN,observation),
            'Gov phase cannot originate on a late or unadmitted side branch')
    raw=blob(root,GOVERNANCE_SCOPE_SOURCE,GOVERNANCE_MANIFEST)
    require(hashlib.sha256(raw).hexdigest()==GOVERNANCE_MANIFEST_SHA256,
            'Gov phase manifest differs from its fixed original')
    intent=json.loads(raw)
    frozen=set(SOURCE_COMPATIBILITY.paths)
    require(set(intent['governancePaths'])==set(GOVERNANCE_PATHS)
            and set(x['path'] for x in intent['protectedFrozenParentBindings'])==frozen,
            'Gov phase fixed path bindings differ')
    for pin in intent['protectedFrozenParentBindings']:
        value=blob(root,GOVERNANCE_SCOPE_PARENT,pin['path'])
        require(len(value)==pin['bytes'] and hashlib.sha256(value).hexdigest()==pin['sha256'],
                'Gov phase original frozen bytes differ')
    objects=lambda ref,paths:git(root,'ls-tree',ref,'--',*sorted(paths))
    frozen_objects=objects(GOVERNANCE_SCOPE_PARENT,frozen)
    manifest_object=record(GOVERNANCE_SCOPE_SOURCE)
    original_intent=objects(GOVERNANCE_SCOPE_PARENT,{PERFORMANCE.intent})
    task='OPS-027';task_path='specs/tasks/'+task+'.md';prefix='evidence/'+task+'/'
    metadata={PLAN,ACTIVE,task_path}
    allowed=lambda paths:all(p in metadata or p.startswith(prefix) for p in paths)
    fixed=entry_at(root,GOVERNANCE_SCOPE_MAIN,task)
    require(fixed is not None and fixed['status']=='reserved' and fixed['agentRole']=='coordinator'
            and fixed['baseSha']==GOVERNANCE_SCOPE_PARENT,
            'Gov phase did not start from its exact reserved scope')
    require(allowed(changed(root,GOVERNANCE_SCOPE_PARENT,GOVERNANCE_SCOPE_SOURCE))
            and blob(root,GOVERNANCE_SCOPE_SOURCE,PLAN)==blob(root,GOVERNANCE_SCOPE_PARENT,PLAN)
            and objects(GOVERNANCE_SCOPE_SOURCE,GOVERNANCE_PATHS|frozen)==objects(GOVERNANCE_SCOPE_PARENT,GOVERNANCE_PATHS|frozen),
            'Gov scope registration contains implementation')
    policy=document(root,GOVERNANCE_SCOPE_MAIN,ACTIVE)['policy']
    mutable={'status','agentRole','branch','baseSha','lease','exclusivePaths'}
    stable=lambda entry:{k:v for k,v in entry.items() if k not in mutable}
    history=history_module()
    canonical_nodes=set(chain(root,canonical))
    gov_nodes=set();gov_work=set();restoration=None

    def entry_facts(node,own,claims):
        moment=datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',node)),timezone.utc)
        validate_entry(own,task,set(claims),moment,historical=True)
        require(document(root,node,ACTIVE)['policy']==policy,'Gov phase changed capacity policy')
        validate_capacity(root,node,own,successor=task)
        front,body=history.parse_front_matter(blob(root,node,task_path).decode())
        errors=[];history.stable_spec_matches(task,own,front,body,errors,reservation=own['status']=='reserved')
        require(not errors and front.get('status')==own['status'] and front.get('agentRole')==own['agentRole']
                and front.get('workBranch')==own['branch'] and front.get('baseSha')==own['baseSha'],
                'Gov phase Task differs from its registered state: '+'; '.join(errors))

    def clean_merge(node,ps):
        if len(ps)!=2:
            return False
        result=subprocess.run(['git','-C',str(root),'merge-tree','--write-tree',*ps],capture_output=True)
        return result.returncode==0 and result.stdout.decode().splitlines()[0]==git(root,'rev-parse',node+'^{tree}').decode().strip()

    def integrated_code(before):
        for node in chain(root,before):
            if node not in canonical_nodes or not ancestor(GOVERNANCE_SCOPE_MAIN,node) or node==GOVERNANCE_SCOPE_MAIN:
                continue
            entry=entry_at(root,node,task);ps=parents(node)
            if (entry and set(entry.get('exclusivePaths') or [])==set(GOVERNANCE_PATHS)
                    and entry.get('status')=='in_progress' and entry.get('agentRole')=='implementer'
                    and len(ps)==2 and clean_merge(node,ps)
                    and GOVERNANCE_PATHS<=changed(root,GOVERNANCE_SCOPE_MAIN,node)
                    and GOVERNANCE_PATHS.intersection(changed(root,ps[0],node))):
                return True
        return False

    nodes=git(root,'rev-list','--topo-order','--reverse',GOVERNANCE_SCOPE_PARENT+'..'+observation).decode().split()
    for node in nodes:
        ps=parents(node);previous=ps[0];paths=changed(root,previous,node)
        own=entry_at(root,node,task);old=entry_at(root,previous,task)
        plan=document(root,node,PLAN)
        own_changed=(own!=old or blob(root,node,task_path)!=blob(root,previous,task_path)
            or rows(plan.get('foundationTasks')).get(task)!=rows(document(root,previous,PLAN).get('foundationTasks')).get(task)
            or any(p.startswith(prefix) for p in paths)) if own is not None and old is not None else own!=old
        if not record(node):
            # An older peer may have no 027 yet. Its ordinary history and clean
            # import are still audited by source_protected_ref/normal gates.
            require(not record(previous) and not own_changed and not paths.intersection(GOVERNANCE_PATHS|frozen),
                    'Gov manifest missing in introduced local history')
            continue
        require(record(node)==manifest_object,'Gov manifest was changed or restored in history')
        require(objects(node,{PERFORMANCE.intent})==original_intent,
                'Gov phase changed the original authority intent')
        if own is None:
            require(restoration is not None and ancestor(restoration,node),
                    'Gov identity disappeared before restoration')
            continue  # Normal Completion/released-identity checks still apply.
        claims=set(own.get('exclusivePaths') or [])
        require(stable(own)==stable(fixed),'Gov phase stable identity changed')
        if claims==set(GOVERNANCE_PATHS):
            require(node==GOVERNANCE_SCOPE_SOURCE or ancestor(GOVERNANCE_SCOPE_MAIN,node),
                    'Gov activation metadata requires its already integrated actual scope main')
            require(restoration is None or not ancestor(restoration,node),'Gov phase cannot reenter after restoration')
            require(plan.get('status')=='active','Gov prerequisite requires an active Program')
            entry_facts(node,own,GOVERNANCE_PATHS)
            require((own['status'],own['agentRole']) in {('reserved','coordinator'),('in_progress','implementer')},
                    'Gov technical review cannot change the task lifecycle')
            require(objects(node,frozen)==frozen_objects,'Gov phase changed or restored a frozen target')
            gov_nodes.add(node)
            if own_changed or paths.intersection(GOVERNANCE_PATHS):
                gov_work.add(node)
            if paths.intersection(GOVERNANCE_PATHS):
                preceding_work=bool(old and set(old.get('exclusivePaths') or [])==set(GOVERNANCE_PATHS)
                    and old.get('status')=='in_progress' and old.get('agentRole')=='implementer'
                    and ancestor(GOVERNANCE_SCOPE_MAIN,previous))
                incoming_work=bool(len(ps)==2 and entry_at(root,ps[1],task)
                    and ps[1] in gov_nodes and entry_at(root,ps[1],task).get('status')=='in_progress')
                require(preceding_work or (incoming_work and clean_merge(node,ps)),
                        'Gov implementation requires a preceding working registration')
                require(all(p in GOVERNANCE_PATHS or p in metadata or p.startswith(prefix) for p in paths),
                        'Gov implementation includes undeclared paths')
            if len(ps)>1 and (own_changed or paths.intersection(GOVERNANCE_PATHS)):
                require(node==GOVERNANCE_SCOPE_MAIN or clean_merge(node,ps),'Gov merge has an unproved resolution')
        elif claims==set(PERFORMANCE.paths):
            entry_facts(node,own,PERFORMANCE.paths)
            gov_changes=paths.intersection(GOVERNANCE_PATHS)
            if gov_changes:
                incoming=history.approved_synchronization_parents(root,node,canonical)
                imports=history.clean_synchronization_paths(root,node,gov_changes,incoming) if incoming else set()
                require(not own_changed and gov_changes<=imports,
                        'Restored P scope cannot continue Gov writes or hide a side-branch edit')
            if old is not None and set(old.get('exclusivePaths') or [])==set(GOVERNANCE_PATHS):
                imported=bool(restoration and len(ps)==2 and ancestor(restoration,ps[1]) and clean_merge(node,ps))
                if not imported:
                    require(restoration is None and len(ps)==1 and allowed(paths),
                            'P scope restoration must be one metadata-only edge')
                    require((own.get('status'),own.get('agentRole'))==('in_progress','implementer')
                            and (old.get('status'),old.get('agentRole'))==('in_progress','implementer')
                            and plan.get('status')=='active' and integrated_code(previous),
                            'P scope restoration requires previously integrated nonempty Gov code')
                    restoration=node
                require(objects(node,frozen)==frozen_objects,'P scope restoration changed a frozen target')
            else:
                require(restoration is not None and ancestor(restoration,node),
                        'P scope lacks the authenticated Gov restoration')
        else:
            raise AdmissionError('Gov phase claims must be exactly four Gov or restored two P paths')
    if restoration is not None:
        require(all(ancestor(node,parent(root,restoration)) for node in gov_work),
                'Gov work was introduced outside the closed continuous phase')
    return gov_nodes


_AUDIT_SESSION = ContextVar('bound_repair_audit_session', default=None)


@contextmanager
def audit_session():
    """Keep successful immutable-history work private to one caller's audit.

    There is no process-wide or disk cache, and a nested audit starts fresh.
    Current entry, lease, capacity and working-file checks remain live.
    """
    token = _AUDIT_SESSION.set({})
    try:
        yield
    finally:
        _AUDIT_SESSION.reset(token)


def _immutable_git_view(root: str):
    """Bypass reuse for replacement/graft/custom object or config views."""
    custom = ('GIT_DIR','GIT_COMMON_DIR','GIT_WORK_TREE','GIT_REPLACE_REF_BASE',
              'GIT_GRAFT_FILE','GIT_SHALLOW_FILE','GIT_OBJECT_DIRECTORY',
              'GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_CONFIG','GIT_CONFIG_COUNT',
              'GIT_CONFIG_PARAMETERS','GIT_CONFIG_SYSTEM','GIT_CONFIG_GLOBAL','GIT_NAMESPACE')
    if any(name in os.environ for name in custom):
        return None
    try:
        git_dir = Path(git(root,'rev-parse','--absolute-git-dir').decode().strip())
        common = Path(git(root,'rev-parse','--git-common-dir').decode().strip())
        common = (Path(root)/common).resolve() if not common.is_absolute() else common.resolve()
        if any((directory/name).exists() for directory in (git_dir,common)
               for name in ('info/grafts','shallow','objects/info/alternates')):
            return None
        if git(root,'for-each-ref','--format=%(refname)','refs/replace/'):
            return None
        # Hash configuration in memory only; it may contain private transport
        # settings and must never be emitted as evidence or cache contents.
        config = hashlib.sha256(git(root,'config','--null','--list','--show-origin')).digest()
        # Normal Foundation proofs depend on actual HEAD ancestry, and may
        # resolve repository refs while auditing the immutable edge.
        head = git(root,'rev-parse','--verify','HEAD').decode().strip()
        refs = hashlib.sha256(git(root,'for-each-ref','--format=%(refname) %(objectname)')).digest()
        return str(git_dir.resolve()),str(common),config,head,refs
    except (AdmissionError,OSError,ValueError):
        return None


def _normal_foundation_edge(root: str, before: str, after: str, branch: str,
                            errors: list[str], *, selected) -> None:
    """Reuse only successful exact immutable edges in this private audit."""
    session = _AUDIT_SESSION.get()
    eligible = (session is not None and selected.successor == SOURCE_COMPATIBILITY.successor
                and re.fullmatch(r'[0-9a-f]{40}',before)
                and re.fullmatch(r'[0-9a-f]{40}',after))
    view = _immutable_git_view(root) if eligible else None
    key = ('normal-foundation-edge',str(Path(root).resolve()),before,after,
           selected.authority,branch,view)
    if view is not None and key in session:
        # These are the only mutable filesystem prerequisites of the normal
        # validator. Successful immutable history cannot replace their checks.
        for task in session[key]:
            if not (Path(root,'evidence',task).is_dir()
                    and Path(root,'evidence',task,'handoff.md').is_file()):
                errors.append('Foundation '+task+' Evidence/Handoff does not exist')
        return
    before_plan,after_plan = document(root,before,PLAN),document(root,after,PLAN)
    observed: list[str] = []
    history_module().validate_foundations(root,before_plan,after_plan,
        document(root,before,ACTIVE),document(root,after,ACTIVE),document(root,before,LEDGER),
        document(root,after,LEDGER),before,after,branch,observed,task_hint=selected.authority)
    errors.extend(observed)
    if view is not None and not observed and _immutable_git_view(root) == view:
        previous = rows(before_plan.get('foundationTasks'))
        session[key] = tuple(task for task,state in rows(after_plan.get('foundationTasks')).items()
                             if state.get('status') == 'completed'
                             and previous.get(task,{}).get('status') != 'completed')


def _authority_working_evidence(root: str, selected) -> None:
    # validate_foundations also checks these current filesystem prerequisites.
    # Immutable commit IDs alone cannot stand in for their present existence.
    task = selected.authority
    require(Path(root,'evidence',task).is_dir()
            and Path(root,'evidence',task,'handoff.md').is_file(),
            'Source compatibility authority history rejected: Foundation '+task+' Evidence/Handoff does not exist')


def authority(root: str, base: str, *, protected_through: str | None = None,
              successor: str = SUCCESSOR) -> tuple[dict[str, Any], str]:
    session = _AUDIT_SESSION.get()
    eligible = (session is not None and successor == SOURCE_COMPATIBILITY.successor
                and re.fullmatch(r'[0-9a-f]{40}',base)
                and (protected_through is None or re.fullmatch(r'[0-9a-f]{40}',protected_through)))
    view = _immutable_git_view(root) if eligible else None
    if view is None:
        return _authority(root,base,protected_through=protected_through,successor=successor)
    key = (str(Path(root).resolve()),base,protected_through,successor,view)
    if key in session:
        _authority_working_evidence(root,contract(successor))
        return copy.deepcopy(session[key])
    result = _authority(root,base,protected_through=protected_through,successor=successor)
    # Failed proofs are never stored. A changed Git view cannot populate this
    # session; the next call runs the complete ordinary proof again.
    if _immutable_git_view(root) == view:
        session[key] = copy.deepcopy(result)
    return result


def _authority(root: str, base: str, *, protected_through: str | None = None,
              successor: str = SUCCESSOR) -> tuple[dict[str, Any], str]:
    """Prove immutable intent and the actual normal completed Foundation chain."""
    selected = contract(successor)
    AUTHORITY, SUCCESSOR, INTENT, INTENT_SHA256, AUTHORITY_CLAIMS, REPAIR_PATHS = selected
    canonical = chain(root, base)
    original = introduction(root, canonical, AUTHORITY)
    require(original is not None, 'No original canonical authority registration')
    registration, reserved = original
    preceding = parent(root, registration)
    raw = blob(root, registration, INTENT)
    require(hashlib.sha256(raw).hexdigest() == INTENT_SHA256, 'Original authorization intent differs')
    intent = json.loads(raw)
    require((SUCCESSOR in {SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor}
             or intent.get('kind') == 'one_poc_contract_repair_authorization_intent')
            and intent.get('authorityTaskId') == AUTHORITY
            and intent.get('reservationParent') == preceding,
            'Authorization intent is not parent-bound')
    require(reserved.get('status') == 'reserved' and reserved.get('agentRole') == 'coordinator'
            and reserved.get('baseSha') == preceding, 'Authority did not start metadata-only reserved')
    observed = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',registration)),timezone.utc)
    validate_entry(reserved, AUTHORITY, AUTHORITY_CLAIMS, observed,historical=True)
    metadata = {PLAN,ACTIVE,'specs/tasks/'+AUTHORITY+'.md'}
    require(metadata <= changed(root,preceding,registration)
            and all(p in metadata or p.startswith('evidence/'+AUTHORITY+'/')
                    for p in changed(root,preceding,registration)), 'Authority reservation contains implementation')
    defect = intent['defect'] if SUCCESSOR not in {SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor} else None
    defect_fields = [('sourceObservationRef','sourceObservationSha256'),
                     ('actualExecutionReviewRef','actualExecutionReviewSha256'),
                     ('responseRef','responseSha256')] if defect is not None else []
    for ref_key, sha_key in defect_fields:
        require(hashlib.sha256(blob(root,registration,defect[ref_key])).hexdigest() == defect[sha_key],
                'Original defect evidence differs from declared Git bytes')
    if defect is not None:
        require(len(blob(root,registration,defect['responseRef'])) == defect['responseBytes'], 'Defect response length differs')
    records = approved_paths(root, preceding, intent, selected)
    for record in records:
        value = blob(root,preceding,record['path'])
        require(len(value) == record['bytes'] and hashlib.sha256(value).hexdigest() == record['gitBlobSha256'],
                'Original approved contract baseline differs')
    # Completion and contract admission still belong to the original base.
    # Only the immutable blobs' audit extends across later successor history.
    protected = chain(root,protected_through) if protected_through is not None else canonical
    require(canonical[-1] in protected and registration in protected,
            'Protected authority audit must extend the original first-parent admission chain')
    for node in protected[protected.index(registration):]:
        require(blob(root,node,INTENT) == raw, 'Authorization intent changed after registration')
        for ref_key,sha_key in defect_fields:
            require(hashlib.sha256(blob(root,node,defect[ref_key])).hexdigest() == defect[sha_key],
                    'Declared original defect evidence changed after registration')
    if SUCCESSOR == SOURCE_COMPATIBILITY.successor:
        for endpoint in dict.fromkeys([base,protected_through] if protected_through is not None else [base]):
            contains_base = subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',SCOPE_AMENDMENT_BASE,endpoint],capture_output=True).returncode == 0
            if contains_base:
                # Do not decide whether history exists from the tip's bytes:
                # deleting the record or restoring four claims cannot erase it.
                audit_scope_amendment(root,SCOPE_AMENDMENT_BASE,endpoint)
            elif scope_record(root,endpoint) is not None:
                raise AdmissionError('Scope amendment is not descended from its approved integration base')
    plan = document(root,base,PLAN)
    completed = rows(plan.get('foundationTasks')).get(AUTHORITY,{})
    require(completed.get('status') == 'completed' and entry_at(root,base,AUTHORITY) is None,
            'Authority has not normally completed and released capacity')
    implementation = completed.get('mergeCommit')
    require(implementation in canonical and canonical.index(implementation) > canonical.index(registration),
            'Authority implementation is not integrated after its reservation')
    finish = None
    reviewed = False
    # An integrator may introduce reviewed source in this very snapshot.
    # The normal Foundation history audit below still authenticates its state.
    for node in canonical[canonical.index(implementation):]:
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
    _normal_foundation_edge(root,before,finish,str(front.get('workBranch') or ''),errors,selected=selected)
    require(not errors, 'Normal authority Foundation history rejected: '+'; '.join(errors))
    if SUCCESSOR in {SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor}:
        implementation_paths = declared_authority_paths(root,implementation,selected)
        require(AUTHORITY_CLAIMS <= changed(root, preceding, implementation)
                and bool(implementation_paths.intersection(changed(root, parent(root, implementation), implementation))),
                'Source compatibility authority has no complete registered implementation')
        # The new authority is audited at every original canonical snapshot;
        # changing and restoring an intent, role or claim cannot erase history.
        previous = preceding
        for node in canonical[canonical.index(registration):canonical.index(finish)+1]:
            current = entry_at(root, node, AUTHORITY)
            if node != finish:
                require(current is not None, 'Source compatibility authority disappeared before Completion')
                moment = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',node)),timezone.utc)
                validate_entry(current, AUTHORITY, declared_authority_paths(root,node,selected), moment, historical=True)
                require(all(current.get(key) == reserved.get(key) for key in
                            ('owner','coordinator','implementer','reviewer','integrator','issue','dependsOn')),
                        'Source compatibility authority stable identity changed')
                task_front, task_body = history.parse_front_matter(blob(root,node,'specs/tasks/'+AUTHORITY+'.md').decode())
                task_errors: list[str] = []
                history.stable_spec_matches(AUTHORITY,current,task_front,task_body,task_errors,
                                           reservation=current.get('status') == 'reserved')
                require(not task_errors, 'Source compatibility authority Task differs: '+'; '.join(task_errors))
            for record in records:
                require(blob(root,node,record['path']) == blob(root,preceding,record['path']),
                        'Source compatibility authority changed a frozen repair target before admission')
            # Full ordinary Foundation history owns transitions and identity;
            # only actual metadata changes need its otherwise expensive audit.
            # The exact parent(finish)->finish audit already ran above. Earlier
            # prefixes remain mandatory: their foreign edit/restore checks may
            # cover history outside a later implementation's integrated range.
            if node != finish and any(blob(root,previous,path) != blob(root,node,path) for path in
                   (PLAN,ACTIVE,'specs/tasks/'+AUTHORITY+'.md')):
                normal_errors: list[str] = []
                task_front,_ = history.parse_front_matter(blob(root,node,'specs/tasks/'+AUTHORITY+'.md').decode())
                _normal_foundation_edge(root,previous,node,str(task_front.get('workBranch') or ''),normal_errors,selected=selected)
                require(not normal_errors, 'Source compatibility authority history rejected: '+'; '.join(normal_errors))
            previous = node
        # The original admission base may be later than Completion. A target
        # edit/restore in that interval cannot acquire fresh repair authority.
        for node in canonical[canonical.index(finish)+1:]:
            for record in records:
                require(blob(root,node,record['path']) == blob(root,preceding,record['path']),
                        'Source compatibility authority changed an approved contract frozen repair target before admission')
    if SUCCESSOR == PERFORMANCE.successor:
        # The original admitted base stays fixed. Lawful successor writes
        # after its separate freeze are outside this historical interval.
        _audit_performance_target_history(root,preceding,base)
    return intent, registration


def prove_claims(root: str, task_id: str, entry: dict[str, Any], base_ref: str,
                 *, observed_ref: str | None = None) -> set[str]:
    """Supplement ownership only; all normal transition/history/recovery gates remain."""
    selected = contract(task_id)
    AUTHORITY, SUCCESSOR, INTENT, _, _, REPAIR_PATHS = selected
    require(task_id == SUCCESSOR, 'No declared repair for this identity')
    when = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',observed_ref)),timezone.utc) if observed_ref else datetime.now(timezone.utc)
    validate_entry(entry,task_id,REPAIR_PATHS,when,historical=observed_ref is not None)
    base = resolve(root,base_ref)
    if task_id == PERFORMANCE.successor and observed_ref is None:
        # The live lifecycle caller supplies no observation argument. Bind it
        # to its real committed checkout, rather than treating its old target
        # base as the current phase. Uncommitted prospective P entries deny.
        head=resolve(root,'HEAD')
        if (git(root,'ls-tree',base,'--',GOVERNANCE_MANIFEST)
                or git(root,'ls-tree',head,'--',GOVERNANCE_MANIFEST)):
            require(entry_at(root,head,task_id)==entry,
                    'Current P entry must equal its actual committed checkout')
            require(subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',base,head],capture_output=True).returncode==0,
                    'Current P checkout does not descend from its admitted base')
            observed_ref=head
    protected = observed_ref if task_id in {SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor} and observed_ref is not None else base
    if task_id == SOURCE_COMPATIBILITY.successor and observed_ref is not None:
        protected = source_protected_ref(root,base,resolve(root,observed_ref))
    elif task_id == PERFORMANCE.successor and observed_ref is not None:
        protected = source_protected_ref(root,base,resolve(root,observed_ref),selected=selected)
    gov_nodes = audit_performance_governance_phase(root,base,protected) if task_id == PERFORMANCE.successor else set()
    if gov_nodes:
        # Historical P declarations retain their meaning only at their real
        # historical observations, never as permission observed in Gov scope.
        endpoints=[entry_at(root,ref,task_id) for ref in dict.fromkeys((base,protected))]
        observed_entry=entry_at(root,protected,task_id)
        require(observed_entry is not None and set(observed_entry.get('exclusivePaths') or [])==set(REPAIR_PATHS)
                and any(actual==entry and set(actual.get('exclusivePaths') or [])==set(REPAIR_PATHS)
                    for actual in endpoints if actual is not None),
                'Current P permission requires its committed metadata restoration')
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
        require(entry_at(root,base,task_id) is not None, 'Released repair identity cannot regain scope')
        metadata = {PLAN,ACTIVE,'specs/tasks/'+task_id+'.md'}
        paths = changed(root,admission_base,registration)
        require(metadata <= paths and all(p in metadata or p.startswith('evidence/'+task_id+'/') for p in paths),
                'Repair original reservation was not metadata-only')
        # Scope/role/lease history is independently audited by the normal gates.
        require(all(entry.get(k) == reserved.get(k) for k in
                    ('owner','coordinator','implementer','reviewer','integrator','issue','dependsOn')),
                'Repair stable identity differs from its original reservation')
        for node in chain(root,base)[chain(root,base).index(registration):]:
            historical = entry_at(root,node,task_id)
            require(historical is not None, 'Repair lease disappeared before its working state')
            moment = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',node)),timezone.utc)
            historical_paths = set(GOVERNANCE_PATHS) if node in gov_nodes else REPAIR_PATHS
            validate_entry(historical,task_id,historical_paths,moment,historical=True)
            require(all(historical.get(k) == reserved.get(k) for k in
                        ('owner','coordinator','implementer','reviewer','integrator','issue','dependsOn')),
                    'Repair stable identity changed in its history')
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
    intent, authority_registration = authority(root,admission_base,protected_through=protected,successor=task_id)
    require(blob(root,base,INTENT) == blob(root,admission_base,INTENT), 'Current authority intent changed')
    for record in approved_paths(root,parent(root,authority_registration),intent,selected):
        raw = blob(root,admission_base,record['path'])
        require(len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['gitBlobSha256'],
                'Repair original reservation base changed the approved contract')
    require(reserved.get('dependsOn') == [AUTHORITY], 'Repair must depend on its completed authority')
    original_time = datetime.fromtimestamp(int(git(root,'show','-s','--format=%ct',original[0])),timezone.utc) if original else when
    validate_entry(reserved,task_id,REPAIR_PATHS,original_time,
                   historical=original is not None or observed_ref is not None)
    validate_capacity(root,admission_base,reserved,successor=task_id)
    validate_capacity(root,base,entry,successor=task_id)
    return set(REPAIR_PATHS)


def authenticated_claims(root: str | None, task_id: str, entry: dict[str, Any], base_ref: str,
                         *, observed_ref: str | None = None) -> set[str]:
    if not root or task_id not in {SUCCESSOR, SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor}:
        return set()
    try:
        return prove_claims(root,task_id,entry,base_ref,observed_ref=observed_ref)
    except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError):
        return set()


def validate_repair_changes(root: str, before: str, after: str, task_id: str,
                            paths: set[str], errors: list[str]) -> None:
    """Claim admission cannot authorize changing a completed contract while active."""
    if task_id == SOURCE_COMPATIBILITY.authority:
        try:
            audit_scope_amendment(root,before,after)
        except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError) as exc:
            errors.append('Prospective authority scope amendment rejected: '+str(exc))
        return
    if task_id == PERFORMANCE.authority:
        validate_source_authority_intent(root,before,after,errors,selected=PERFORMANCE)
        return
    if task_id not in {SUCCESSOR, SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor}:
        return
    selected = contract(task_id)
    if task_id in {SOURCE_COMPATIBILITY.successor, PERFORMANCE.successor}:
        # Authority Evidence is also protected on metadata-only changes, on a
        # net-empty edit/restore range and when Completion removes the entry.
        # The original successor admission base must never move to this tip.
        try:
            observation = resolve(root, after)
            admitted = resolve(root,before)
            original = introduction(root, chain(root, admitted), task_id)
            if original is None:
                original = introduction(root, chain(root, observation), task_id)
            require(original is not None, 'Source compatibility repair has no original canonical reservation')
            protected = (source_protected_ref(root,admitted,observation)
                         if task_id == SOURCE_COMPATIBILITY.successor else
                         source_protected_ref(root,admitted,observation,selected=selected))
            if task_id == PERFORMANCE.successor:
                audit_performance_governance_phase(root,admitted,protected)
            authority(root, parent(root, original[0]), protected_through=protected, successor=task_id)
        except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError) as exc:
            errors.append('Bound POC contract authority audit rejected: '+str(exc))
            return
    if not paths.intersection(selected.paths):
        return
    try:
        left, right = document(root,before,PLAN), document(root,after,PLAN)
        recovery = left.get('recovery')
        require(left.get('status') == right.get('status') == 'frozen'
                and isinstance(recovery,dict) and right.get('recovery') == recovery,
                'Contract changes require a preceding unchanged frozen recovery event')
        require(recovery.get('taskId') == task_id
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
        entry = entry_at(root,after,task_id)
        require(entry is not None and entry.get('status') in {'in_progress','review','integration'},
                'Contract edits require a separately registered working repair')
        prove_claims(root,task_id,entry,before,observed_ref=after)
    except (AdmissionError,KeyError,TypeError,ValueError,OSError,yaml.YAMLError) as exc:
        errors.append('Bound POC contract recovery rejected: '+str(exc))

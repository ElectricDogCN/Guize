"""Assemble actual POC005 execution records; never grant qualification or replay work."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import yaml


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('UTC identity requires an explicit timezone')
    return parsed.astimezone(timezone.utc)


def scoped(root: Path, ref: str, prefix: str) -> Path:
    if not isinstance(ref, str) or '\\' in ref or Path(ref).is_absolute() or '..' in Path(ref).parts:
        raise ValueError('Normalized selected-slot reference required')
    path = (root / ref).resolve(strict=True)
    if not path.is_relative_to((root / prefix).resolve()) or not path.is_file():
        raise ValueError('Existing selected-slot file required')
    if (root / ref).is_symlink():
        raise ValueError('Symbolic evidence reference rejected')
    return path


def load(root: Path, ref: str, prefix: str):
    return json.loads(scoped(root, ref, prefix).read_bytes())


def descriptor(root: Path, ref: str, kind: str, prefix: str) -> dict:
    path = scoped(root, ref, prefix)
    return dict(ref=ref, artifactType=kind, byteCount=path.stat().st_size, sha256=digest(path))


def select_raw_artifacts(root: Path, records: list, input_refs: list[str], structured_refs: list[str], prefix: str):
    """Project a journal without changing it; physical input/record aliases stay out."""
    inputs = [scoped(root, ref, prefix) for ref in input_refs]
    structured = [scoped(root, ref, prefix) for ref in structured_refs]
    seen, selected, excluded = set(), [], []
    for row in records:
        if not isinstance(row, dict) or row.get('ref') in seen:
            raise ValueError('Unique structured journal rows required')
        seen.add(row.get('ref'))
        path = scoped(root, row['ref'], prefix)
        if set(row) - {'ref', 'artifactType', 'byteCount', 'sha256', 'nodeId'}:
            raise ValueError('Unexpected raw descriptor fields')
        if row.get('byteCount') != path.stat().st_size or row.get('sha256') != digest(path):
            raise ValueError('Journal bytes changed: ' + row['ref'])
        if any(path.samefile(peer) for peer in inputs):
            excluded.append(dict(ref=row['ref'], reason='physical_input_alias'))
        elif any(path.samefile(peer) for peer in structured):
            excluded.append(dict(ref=row['ref'], reason='structured_record_alias'))
        else:
            selected.append(dict(row))
    return selected, excluded


def validate_actual_wait(execution: dict, facts: dict) -> None:
    if execution['exitCode'] != 0 or not execution['actualWaitCompleted'] or execution['overallDeadlineExceeded']:
        raise ValueError('Successful real parent wait required')
    if facts['realWaitReturnCode'] != 0 or not facts['exitObservedAfterWait'] or facts['outcome'] != 'accepted':
        raise ValueError('Successful actual scanner wait required')


def validate_approved_control_chain(root: Path, slot: str, prefix: str, approval: dict, cfg: dict,
                                    before: dict, ready: dict, facts: dict, execution: dict) -> None:
    bindings = approval['bindingFiles']
    def bound(name):
        ref = slot + '/' + name
        rows = [row for row in bindings.values() if isinstance(row,dict) and row.get('ref') == ref]
        path = scoped(root,ref,prefix)
        if len(rows) != 1 or rows[0].get('bytes') != path.stat().st_size or rows[0].get('sha256') != digest(path):
            raise ValueError('Final independent byte binding mismatch: ' + name)
        return rows[0]
    for name in ['runtime.json','resource.json','openlist-resource.json','profile-configuration.json',
                 'sample-approval.json','before-environment.json','controller-launch.json','native-manifest.json']:
        bound(name)
    for ref_field, sha_field, name in [('runtimeConfigRef','runtimeConfigSha256','runtime.json'),
                                     ('configurationRef','configurationSha256','resource.json'),
                                     ('manifestRef','manifestSha256','native-manifest.json'),
                                     ('sampleApprovalRef','sampleApprovalSha256','sample-approval.json'),
                                     ('beforeEnvironmentRef','beforeEnvironmentSha256','before-environment.json')]:
        row = bound(name)
        if approval[ref_field] != row['ref'] or approval[sha_field] != row['sha256']:
            raise ValueError('Final independent control reference mismatch: ' + name)
    resource_rows = {row['ref']: row for row in approval['resourceRefs']}
    if len(approval['resourceRefs']) != 2 or set(resource_rows) != {slot+'/resource.json',slot+'/openlist-resource.json'}:
        raise ValueError('Exactly two independently bound resources required')
    for name in ['resource.json','openlist-resource.json']:
        if resource_rows[slot+'/'+name] != bound(name):
            raise ValueError('Independent resource binding mismatch')
    manifest = load(root,slot+'/native-manifest.json',prefix)
    launch = load(root,slot+'/controller-launch.json',prefix)
    scanner = approval['reservation']
    scanner_pid = scanner['nativeProcessId']
    if ready['identity'] != scanner or before['scannerIdentity'] != scanner or facts['reservation']['identity'] != scanner:
        raise ValueError('Approved scanner identity chain mismatch')
    if facts['reservation']['reservedAt'] != approval['reservationAt'] or facts['processId'] != scanner_pid:
        raise ValueError('Approved scanner reservation/PID mismatch')
    if ready['processStart']['processId'] != scanner_pid or facts['processExit']['processId'] != scanner_pid:
        raise ValueError('Actual scanner entry/exit PID mismatch')
    if not (manifest['argv'] == approval['scannerArgv'] == ready['argv'] == facts['argv']):
        raise ValueError('Approved scanner argv chain mismatch')
    if launch['identity'] != execution['identity'] or launch['argv'] != execution['argv'] or launch['supervisorPid'] != execution['supervisorPid']:
        raise ValueError('Approved controller execution chain mismatch')
    if facts['observerProcessId'] != launch['identity']['nativeProcessId']:
        raise ValueError('Actual scanner observer/controller PID mismatch')
    source = cfg['context']['subjectVersion']
    if launch['source'] != source or execution['source'] != source or approval['source'] != source:
        raise ValueError('Approved source/controller mismatch')
    if ready['context'] != cfg['context'] or facts['context'] != cfg['context']:
        raise ValueError('Actual execution context mismatch')
    if facts['scanId'] != cfg['scanId'] or facts['changeSetId'] != cfg['changeSetId']:
        raise ValueError('Actual scan/change-set identity mismatch')
    if before['upstreamIdentity'] != cfg['sourceRun']['upstreamIdentity'] or approval['sourceIdentity'] != cfg['sourceRun']['identity']:
        raise ValueError('Approved actual source identity mismatch')


def assemble(root: Path, attempt: str, method_ref: str) -> tuple[dict, dict]:
    root = root.resolve(strict=True)
    prefix = 'evidence/POC-005/profiles/local-v1/v1'
    if attempt != 'attempt-010':
        raise ValueError('This prospective method is restricted to attempt010')
    slot = prefix + '/' + attempt
    read = lambda name: load(root, slot + '/' + name, prefix)
    profile_ref = slot + '/profile-configuration.json'
    profile = read('profile-configuration.json')
    cfg, before, ready = read('runtime.json'), read('before-environment.json'), read('ready.json')
    execution, approval, facts = read('controller-execution.json'), read('independent-approval.json'), read('phase-facts.json')
    metadata_ref, openlist_ref, sample_ref = slot + '/resource.json', slot + '/openlist-resource.json', slot + '/sample-approval.json'
    metadata, openlist, sample_approval = read('resource.json'), read('openlist-resource.json'), read('sample-approval.json')
    task = yaml.safe_load((root / 'specs/tasks/POC-005.md').read_text(encoding='utf-8').split('---', 2)[1])
    reviewer, implementer = task['reviewer'], task['implementer']
    if reviewer != 'independent-review-agent' or implementer != 'task-owner-agent':
        raise ValueError('Unexpected concrete Task identities')
    validate_approved_control_chain(root,slot,prefix,approval,cfg,before,ready,facts,execution)
    validate_actual_wait(execution, facts)
    outcomes = [json.loads(line) for line in scoped(root, slot + '/controller.stdout', prefix).read_bytes().splitlines() if line]
    outcome = outcomes[-1]
    if outcome['kind'] != 'original13_observations_completed' or outcome['original13MetricCount'] != 13 or outcome['unitFixtureOnly']:
        raise ValueError('Actual full original13 observation outcome required')
    if outcome['actualScannerProcessId'] != ready['identity']['nativeProcessId'] or facts['processStart'] != ready['processStart']:
        raise ValueError('Same actually executed scanner identity required')
    started, finished = utc(ready['processStart']['observedAt']), utc(execution['finishedAt'])
    if not utc(approval['windowStart']) <= started <= utc(facts['processExit']['observedAt']) <= finished <= utc(approval['windowEnd']):
        raise ValueError('Actual complete work must fit approved finite window')
    if utc(approval['approvedAt']) > started or approval['decision'] != 'approved' or approval['reviewer'] != reviewer:
        raise ValueError('Actual independent pre-execution decision required')
    method_path = scoped(root, method_ref, prefix)
    if method_path.read_bytes() != Path(__file__).read_bytes():
        raise ValueError('Actual assembler bytes must equal the prospectively approved method')
    binding = approval.get('assemblyMethod')
    if binding != dict(ref=method_ref, byteCount=method_path.stat().st_size, sha256=digest(method_path)):
        raise ValueError('Final independent approval must bind the exact pre-execution assembler')
    if profile['decision'] != 'approved' or profile['approvedBy'] != reviewer or utc(profile['approvedAt']) > started:
        raise ValueError('Full profile must be independently approved before execution')
    expected_source = dict(commit=cfg['context']['subjectVersion'], tree=profile['testedSource']['tree'])
    actual_tree = subprocess.check_output(['git', '-c', 'core.longpaths=true', '-C', str(root), 'show', '-s', '--format=%T', expected_source['commit']], text=True).strip()
    if profile['testedSource'] != expected_source or actual_tree != expected_source['tree'] or before['sourceCommit'] != expected_source['commit'] or approval['tree'] != expected_source['tree']:
        raise ValueError('Exact tested commit/tree/environment binding required')
    if before['runtimeConfigSha256'] != digest(scoped(root, slot + '/runtime.json', prefix)):
        raise ValueError('Pre-execution environment must bind actual runtime bytes')
    for resource, resource_id in [(metadata, 'RES-METADATA-SCALE'), (openlist, 'RES-OPENLIST-LOCAL')]:
        if resource['resourceId'] != resource_id or resource['approvedBy'] != reviewer or resource['status'] != 'approved':
            raise ValueError('Correct independent resource approval required')
        if not utc(resource['approvedAt']) <= started or not utc(resource['validFrom']) <= started <= finished <= utc(resource['validUntil']):
            raise ValueError('Resource validity must cover actual full execution')
    boundary = metadata['configuration']['syntheticHierarchySandbox']
    sandbox = before['syntheticHierarchySandbox']
    if sandbox != dict(schemaVersion=1, configurationRef=metadata_ref, boundary=boundary):
        raise ValueError('Actual pre-execution sandbox capture must equal approved boundary')
    if before['synthetic_hierarchy_manifest'] != profile['capturedSettings']['synthetic_hierarchy_manifest']:
        raise ValueError('Actual structured hierarchy must equal pre-execution profile')
    sample = cfg['context']['inputSamples'][0]
    if sample_approval['approver'] != reviewer or sample_approval['decision'] != 'approved' or utc(sample_approval['approvedAt']) > started:
        raise ValueError('Correct independent sample approval required')
    if (sample_approval.get('pocId'),sample_approval.get('taskId'),sample_approval.get('sampleId'),sample_approval.get('immutableId'),sample_approval.get('checksum')) != ('POC-05','POC-005',sample['id'],sample['immutableId'],sample['checksum']):
        raise ValueError('Approved exact sample tuple mismatch')
    baseline_ref = cfg['baseline']['ref']
    baseline = scoped(root, baseline_ref, prefix)
    if digest(baseline) != sample['checksum'] or metadata['configuration']['metadataScanPolicy']['baseline']['ref'] != baseline_ref:
        raise ValueError('Exact approved immutable baseline required')
    journal = [json.loads(line) for line in scoped(root, outcome['artifactIndex'], prefix).read_bytes().splitlines()]
    structured_refs = [profile_ref, metadata_ref, openlist_ref, sample_ref]
    selected, excluded = select_raw_artifacts(root, journal, [baseline_ref], structured_refs, prefix)
    additions = [(slot + '/controller.stdout', 'command_output'), (slot + '/controller-execution.json', 'command_output'),
                 (outcome['reports']['measurements'], 'measurement_output'), (outcome['reports']['faultMatrix'], 'scope_observation')]
    selected_refs = {row['ref'] for row in selected}
    for ref, kind in additions:
        if ref not in selected_refs:
            selected.append(descriptor(root, ref, kind, prefix))
            selected_refs.add(ref)
    values = load(root, outcome['reports']['measurements'], prefix)
    plan = yaml.safe_load((root / 'specs/poc/plans/POC-005.yaml').read_text(encoding='utf-8'))
    measurements = plan['localValidation']['protocol']['measurements']
    if set(values) != {row['id'] for row in measurements}:
        raise ValueError('Exact original13 actual measurements required')
    environment = {key: before[key] for key in plan['localValidation']['captureBeforeExecution']}
    environment.update(acceptanceProfile=cfg['context']['acceptanceProfile'], acceptanceProfileConfigurationRef=profile_ref,
        testedSource=expected_source, executionWindow=dict(startedAt=started.isoformat().replace('+00:00', 'Z'), finishedAt=finished.isoformat().replace('+00:00', 'Z')),
        syntheticHierarchySandbox=sandbox, rawExecutionArtifacts=selected,
        inputSampleArtifacts=[dict(sampleId=sample['id'], immutableId=sample['immutableId'], inputArtifactRef=baseline_ref, byteCount=baseline.stat().st_size, sha256=digest(baseline))],
        metadataScanRef=outcome['reports']['scan'], metadataResourceRef=outcome['reports']['resources'], metadataProfilingRef=outcome['reports']['profiling'])
    record = dict(schemaVersion=1, pocId='POC-05', taskId='POC-005', evidencePath='evidence/POC-005', executor=implementer,
        resources=[dict(id='RES-METADATA-SCALE', configurationRef=metadata_ref, bookingRef=None), dict(id='RES-OPENLIST-LOCAL', configurationRef=openlist_ref, bookingRef=None)],
        environmentCaptured=environment, commands=[dict(command=subprocess.list2cmdline(execution['argv']), expectedExitCodes=[0], exitCode=execution['exitCode'], outputRef=slot + '/controller.stdout')],
        rawOutputRefs=[row['ref'] for row in selected], samples=[{**sample, 'approved': True, 'approvalRef': sample_ref}],
        measurements=[dict(id=row['id'], actual=values[row['id']]) for row in measurements], provenance={}, complianceReviews=[],
        notes='Actual Windows1m source/scanner observations only. Source and scanner throughput differ; adapter quota is not provider quota. This assembled record alone grants no result, scale1m, Task, V1 or production acceptance.')
    definitions = yaml.safe_load((root / 'specs/poc/program.schema.yaml').read_text(encoding='utf-8'))['$defs']
    schemas = [(record, yaml.safe_load((root / 'specs/poc/execution-record.schema.yaml').read_text(encoding='utf-8'))),
               (profile, definitions['profileConfiguration']), (sandbox, definitions['localHierarchySandboxCapture']),
               *[(row, definitions['rawExecutionArtifact']) for row in selected],
               *[(row, definitions['inputSampleArtifact']) for row in environment['inputSampleArtifacts']]]
    for value, schema in schemas:
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(value)
    selection = dict(kind='actual_original_journal_projection', source=expected_source, originalJournalRef=outcome['artifactIndex'],
        originalJournalSha256=digest(scoped(root, outcome['artifactIndex'], prefix)), originalJournalUnmodified=True,
        excluded=excluded, selectedRawCount=len(selected), selectedInputRef=baseline_ref, method=binding,
        fullQualificationValidated=False, qualificationAccepted=False, taskCompleted=False)
    return record, selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--attempt', choices=['attempt-010'], required=True)
    parser.add_argument('--method-ref', required=True)
    args = parser.parse_args()
    record, selection = assemble(args.root, args.attempt, args.method_ref)
    slot = args.root / 'evidence/POC-005/profiles/local-v1/v1' / args.attempt
    outputs = [(slot / 'execution-candidate.json', canonical(record)), (slot / 'raw-selection.json', canonical(selection))]
    if any(path.exists() for path, _ in outputs):
        raise FileExistsError('Refuse to replace any prior execution/report record')
    for path, raw in outputs:
        with path.open('xb') as stream:
            stream.write(raw)
    print(json.dumps(dict(executionRef=outputs[0][0].relative_to(args.root).as_posix(), schemaAccepted=True, selectedRawCount=len(record['rawOutputRefs']), fullQualificationValidated=False, qualificationAccepted=False)))


if __name__ == '__main__':
    main()

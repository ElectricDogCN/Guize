"""Reserve concrete inputs/PID, await independent approval, then execute original13."""
from __future__ import annotations

import argparse
import base64
import copy
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from canonical_metadata import CanonicalPair
from controlled_source_run import (Artifacts, SourceSession, WindowsSourceSession, original13_reports,
                                   retain_approved_metadata_inputs, source_build)
from loopback_gateway import ControlledGateway
from metadata_scan import ScanError, file_sha256
from native_scan_control import NativeRun, manifest_for
from native_scan_protocol import ClockFailure, decode, emit, process_identity, read_json, scoped, utc, write_json
from openlist_listing import OpenListListing
from openlist_source import OpenListSource, _NoRedirect


def reserve_config(draft):
    if not sys.platform.startswith('linux'):
        raise ScanError('LINUX_SOURCE_EXPERIMENT_REQUIRED')
    return _reserve_config(draft, windows=False)


def reserve_windows_config(draft):
    if os.name != 'nt':
        raise ScanError('WINDOWS_SOURCE_EXPERIMENT_REQUIRED')
    return _reserve_config(draft, windows=True)


def _reserve_config(draft, *, windows):
    cfg, resource, refs = (copy.deepcopy(draft[key]) for key in ('runtimeConfig', 'resourceConfiguration', 'refs'))
    root, source = cfg['artifactRoot'], cfg['sourceRun']
    source['unitFixtureOnly'] = draft.get('unitFixtureOnly')
    if (source['identity']['adapterBuild'] != source_build()
            or cfg['context']['configurationRef'] != refs['resourceConfiguration']
            or not isinstance(draft.get('unitFixtureOnly'), bool)):
        raise ScanError('EXACT_CONTROLLER_BUILD_AND_CONFIGURATION_REQUIRED')
    if not draft['unitFixtureOnly']:
        repository = Path(__file__).resolve().parents[2]
        head = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(repository), 'status', '--porcelain', '--',
            'poc/POC-05-metadata-scale', 'specs/tasks/POC-005.md'], text=True)
        if dirty or cfg['context']['subjectVersion'] != head or cfg['context']['scannerBuild'] != head:
            raise ScanError('COMMITTED_REVIEWABLE_EXPERIMENT_CODE_REQUIRED')
    if process_identity(source['upstreamIdentity']['nativeProcessId']) != source['upstreamIdentity']:
        raise ScanError('EXACT_OWNED_OPENLIST_PROCESS_REQUIRED')
    OpenListListing(source['origin'], source['scope'])  # Validate fixed route; no request.
    if type(source['gatewayPort']) is not int or not 1 <= source['gatewayPort'] <= 65535:
        raise ScanError('FIXED_GATEWAY_PORT_REQUIRED')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', source['gatewayPort']))
    paths = [scoped(root, ref) for ref in refs.values()]
    if len(paths) != len(set(paths)) or any(path.exists() for path in paths):
        raise ScanError('NEW_RESERVATION_OUTPUTS_REQUIRED')
    if windows:
        from windows_scan_control import WindowsNativeRun, windows_manifest_for
        cfg['counterFormat'] = 'windows_process_memory_counters'
        manifest = windows_manifest_for(refs['runtimeConfiguration'], cfg, draft['reservationDeadline'], identity_ref=refs['processIdentity'])
        run_type = WindowsNativeRun
    else:
        manifest = manifest_for(refs['runtimeConfiguration'], cfg, draft['reservationDeadline'])
        run_type = NativeRun
    manifest_sha = write_json(scoped(root, refs['manifest']), manifest)
    run = run_type(refs['manifest'], manifest_sha, trace_ref=scoped(root, refs['stdout']), stderr_ref=scoped(root, refs['stderr']))
    try:
        identity = run.reservation['identity']
        from native_scan_protocol import argv_sha
        if windows:
            memory_args = [sys.executable, '-B', str(Path(__file__).with_name('windows_native.py').resolve()),
                '--expected', refs['processIdentity'], '--expected-sha256', run.identity_sha]
        else:
            memory_args = [sys.executable, '-B', str(Path(__file__).with_name('native_memory.py').resolve()),
                '--start-ticks', str(identity['startTicks']), '--boot-id', identity['bootId'], '--exe', identity['executable'],
                '--exe-sha256', identity['executableSha256'], '--cmdline-sha256', argv_sha(manifest['argv'])]
        cfg['memoryCollectorCommandArgs'] = memory_args
        policies = resource['configuration']
        policies['metadataScanPolicy'].update(manifestId=cfg['context']['manifestId'], scannerBuild=cfg['context']['scannerBuild'],
            scanId=cfg['scanId'], changeSetId=cfg['changeSetId'], nativeProcessId=run.process.pid,
            scannerCommandArgs=manifest['argv'][:6], timingCollectorBuild=cfg['timingCollectorBuild'],
            timingCollectorCommandArgs=cfg['timingCollectorCommandArgs'])
        policies['metadataResourcePolicy'].update(manifestId=cfg['context']['manifestId'], scannerBuild=cfg['context']['scannerBuild'],
            scanId=cfg['scanId'], processId=cfg['processId'], collectorBuild=cfg['counterCollectorBuild'],
            nativeProcessId=run.process.pid, counterFormat=cfg.get('counterFormat', 'linux_proc_status'), collectorCommandArgs=memory_args,
            sourceIdentity=source['identity'], quotaDocumentRef=source['quotaRef'], quotaDocumentSha256=source['quotaSha256'])
        policy = policies['metadataProfilingPolicy']
        policy.update(manifestId=cfg['context']['manifestId'], scannerBuild=cfg['context']['scannerBuild'],
            sourceIdentity=source['identity'], endpointURL='http://127.0.0.1:'+str(source['gatewayPort'])+'/api/fs/list')
        resource_sha = write_json(scoped(root, refs['resourceConfiguration']), resource)
        cfg_sha = write_json(scoped(root, refs['runtimeConfiguration']), cfg)
        request = dict(kind='independent_source_experiment_approval_request', unitFixtureOnly=draft['unitFixtureOnly'],
            executor=cfg['executor'], manifestRef=refs['manifest'], manifestSha256=manifest_sha,
            runtimeConfigRef=refs['runtimeConfiguration'], runtimeConfigSha256=cfg_sha,
            configurationRef=refs['resourceConfiguration'], configurationSha256=resource_sha,
            reservation=identity, reservationAt=run.reservation['reservedAt'], reservationDeadline=draft['reservationDeadline'],
            scannerArgv=manifest['argv'], sourceIdentity=source['identity'], approvalRef=draft['approvalRef'],
            requiredDecision='independent actual reviewer, immutable bytes/PID and a future executionWindow; no approval generated here')
        write_json(scoped(root, refs['approvalRequest']), request)
        return run, cfg, request
    except BaseException:
        run.close()
        raise


def reader_credentials(source):
    path = Path(source['credentialRef'])
    if os.name == 'nt':
        from windows_source_files import read_private
        credentials = decode(read_private(path))
    else:
        state = path.stat()
        if path.is_symlink() or state.st_uid != os.getuid() or state.st_mode & 0o077:
            raise ScanError('PRIVATE_OWNED_READER_CREDENTIAL_FILE_REQUIRED')
        credentials, _ = read_json(path, limit=16384)
    if set(credentials) != {'username', 'password'} or credentials['username'] != source['readerUsername']:
        raise ScanError('EXACT_SCOPED_READER_REQUIRED')
    endpoint = OpenListListing(source['origin'], source['scope']).endpoint.removesuffix('/api/fs/list')+'/api/auth/login'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    from metadata_scan import canonical
    # Authentication bytes and responses deliberately have no artifact/logging path.
    with opener.open(urllib.request.Request(endpoint, data=canonical(credentials).encode(),
                                            headers={'Content-Type': 'application/json'}, method='POST'), timeout=5) as response:
        raw = response.read(16385)
    if len(raw) > 16384:
        raise ScanError('SOURCE_AUTH_RESPONSE_LIMIT')
    login = decode(raw)
    if login.get('code') != 200 or not isinstance(login.get('data'), dict):
        raise ScanError('SOURCE_AUTH_FAILED')
    token = login['data']['token']
    basic = 'Basic '+base64.b64encode((credentials['username']+':'+credentials['password']).encode()).decode()
    return token, basic, credentials['password']


def execute(run, cfg, approval):
    source, root = cfg['sourceRun'], cfg['artifactRoot']
    if (source['identity']['adapterBuild'] != source_build()
            or process_identity(source['upstreamIdentity']['nativeProcessId']) != source['upstreamIdentity']):
        raise ScanError('SOURCE_OR_OBSERVER_CHANGED_AFTER_APPROVAL')
    window = approval['windowStart'], approval['windowEnd']
    if not utc(window[0]) <= datetime.now(timezone.utc) <= utc(window[1]):
        raise ScanError('ACTUAL_APPROVED_SOURCE_WINDOW_REQUIRED')
    token, basic, password = reader_credentials(source)
    artifacts = Artifacts(root, source['artifactPrefix'], maximum_bytes=source['artifactBytes'], maximum_files=source['artifactFiles'])
    gateway = ControlledGateway(source['origin'], source['scope'], upstream_token=token, upstream_basic=basic,
        window=window, request_limit=source['requestLimit'], period_seconds=source['periodSeconds'],
        port=source['gatewayPort'], timeout=source['timeout'])
    session = None
    try:
        artifacts.set_sensitive_values((token, basic, basic[6:], password, gateway.token, gateway.expired_token, gateway.basic, gateway.password))
        gateway.start_server()
        run.memory()
        pair = CanonicalPair(scoped(root, cfg['baseline']['ref']), scoped(root, cfg['profiled']['ref']),
            baseline_sha256=cfg['baseline']['sha256'][7:], profiled_sha256=cfg['profiled']['sha256'][7:],
            source_id=cfg['sourceId'], snapshot_version=cfg['snapshotVersion'], page_size=cfg['pageSize'])
        session_type = WindowsSourceSession if os.name == 'nt' else SourceSession
        session = session_type(pair, OpenListListing(gateway.endpoint, source['scope'], token=gateway.token, timeout=source['timeout']),
            OpenListSource(gateway.endpoint+'/dav/'+source['scope']+'/', username=gateway.username,
                           password=gateway.password, timeout=source['timeout']), artifacts,
            identity=source['identity'], window=window, local_root=source['localRoot'], per_page=source['perPage'])
        session.repeated_listings(source['listingRuns'])
        session.exercise_faults(gateway, maximum_backoff=source['maximumBackoffSeconds'])
        run.enumerate()
        probe = source['probe']
        for case in ('unchanged_first', 'unchanged_second', 'bounded', 'unsatisfiable'):
            session.probe(case, probe['objectId'], probe['baselineVersion'], probe['path'], size=probe['baselineBytes'])
        run.begin_changes()
        for intent in source['intents']:
            observed = session.mutation(intent, run.clock)
            run.observe_change(observed['ref'], observed['sha256'])
        session.probe('changed', probe['objectId'], probe['updatedVersion'], probe['path'], size=probe['updatedBytes'])
        run.end_changes()
        run.incremental()
        run.post_catalogue()
        run.memory(final=True)
        facts = run.finish()
        reports = original13_reports(run, facts, session, quota_ref=source['quotaRef'], quota_sha=source['quotaSha256'],
                                     extension_categories=source['extensionCategories'])
        report_refs = {key: artifacts.json(value, 'measurement_output' if key in ('scan', 'resources', 'profiling') else 'command_output')['ref']
                       for key, value in reports.items() if key != 'qualificationAccepted'}
        # Adopt actual completed scanner files and native counter/capture bytes.
        retained = [*cfg['outputs'].values(), *cfg['phaseCaptures'].values(), cfg['phaseFacts'], cfg['readyReceipt'], cfg['postReceipt']]
        for refs in cfg['memory'].values():
            retained.extend(refs[key] for key in ('counter', 'stdout', 'capture'))
        for ref in retained:
            kind = 'measurement_output' if any(ref == refs['capture'] for refs in cfg['memory'].values()) else 'command_output'
            artifacts.keep(ref, kind)
        approved_configuration, _ = read_json(scoped(root, cfg['context']['configurationRef']), run.approval['configurationSha256'])
        retain_approved_metadata_inputs(artifacts, approved_configuration['configuration'])
        for ref in (source['quotaRef'], *[intent['payloadRef'] for intent in source['intents'] if 'payloadRef' in intent]):
            if not any(row['ref'] == ref for row in artifacts.records):
                artifacts.keep(ref, 'produced_media' if ref != source['quotaRef'] else 'command_output')
        snapshot = list(artifacts.records)
        with artifacts.stream() as (append, index_ref):
            for row in snapshot:
                append(row)
        return dict(kind='original13_observations_completed', reports=report_refs, artifactIndex=index_ref,
                    actualScannerProcessId=run.process.pid, original13MetricCount=len(reports['measurements']),
                    unitFixtureOnly=source['unitFixtureOnly'], qualificationAccepted=False, taskCompleted=False)
    except BaseException as failure:
        artifacts.json(dict(kind='failed_source_experiment', error=str(failure) if isinstance(failure, ScanError) else type(failure).__name__,
                            observedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), qualificationAccepted=False,
                            runtimeFailure=getattr(failure, 'runtime_failure', None),
                            clockObservation=failure.observation if isinstance(failure, ClockFailure) else None,
                            rollback='retain all raw bytes and dirty fixture; no automatic source restoration'), 'scope_observation')
        raise
    finally:
        if session:
            session.close()
        gateway.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--draft', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    draft, _ = read_json(args.draft, args.sha256)
    reserve = reserve_windows_config if os.name == 'nt' else reserve_config
    run, cfg, request = reserve(draft)
    try:
        emit(dict(kind='awaiting_independent_approval', approvalRequestRef=draft['refs']['approvalRequest'],
                  actualProcessId=run.process.pid, unitFixtureOnly=draft['unitFixtureOnly']))
        approval_path = scoped(cfg['artifactRoot'], draft['approvalRef'])
        while not approval_path.exists():
            if datetime.now(timezone.utc) >= utc(request['reservationDeadline']) or run.process.poll() is not None:
                raise ScanError('INDEPENDENT_APPROVAL_RESERVATION_EXPIRED')
            time.sleep(.1)
        approval, approval_sha = read_json(approval_path)
        while datetime.now(timezone.utc) < utc(approval['windowStart']):
            if run.process.poll() is not None:
                raise ScanError('RESERVATION_ENDED_BEFORE_WINDOW')
            time.sleep(.1)
        run.release(str(approval_path), approval_sha)
        emit(execute(run, cfg, approval))
    finally:
        run.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as failure:
        emit(dict(kind='source_experiment_failed', error=str(failure) if isinstance(failure, ScanError) else type(failure).__name__))
        raise SystemExit(1)

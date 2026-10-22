"""Real source observations and original13 reports; no experiment approval or fake input."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from canonical_metadata import validate_profile
from controlled_fixture_map import ControlledFixtureMap
from metadata_scan import MAX_LINE_BYTES, ScanError, canonical, file_sha256
from native_scan_protocol import decode, descriptor, read_json, scoped, utc
from openlist_listing import MAX_OBJECTS, OpenListListing
from openlist_source import OpenListSource, SourceError, _segments

SOURCE_FILES = ('controlled_source_run.py', 'loopback_gateway.py', 'controlled_fixture_map.py',
                'openlist_listing.py', 'openlist_source.py', 'run_source_experiment.py')


def source_build():
    return 'sha256:'+hashlib.sha256(canonical({name: file_sha256(Path(__file__).with_name(name))
                                             for name in SOURCE_FILES}).encode()).hexdigest()


class Artifacts:
    """A bounded journal of physical files. Omitted bodies never become empty substitutes."""
    def __init__(self, root, prefix, *, maximum_bytes=128*1024*1024, maximum_files=20000):
        if (type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 1024**3
                or type(maximum_files) is not int or not 1 <= maximum_files <= 20000):
            raise ScanError('FINITE_ARTIFACT_BUDGET_REQUIRED')
        self.root, self.prefix = root, str(prefix)
        scoped(root, prefix).mkdir()
        self.maximum_bytes, self.maximum_files = maximum_bytes, maximum_files
        self.total, self.serial, self.records, self.identities = 0, 0, [], set()
        self.sensitive_values = ()

    def set_sensitive_values(self, values):
        values = tuple(value.encode() if isinstance(value, str) else value for value in values)
        if len(values) > 32 or any(not isinstance(value, bytes) or not 1 <= len(value) <= 8192 for value in values):
            raise ScanError('BOUNDED_PRIVATE_CREDENTIAL_VALUES_REQUIRED')
        self.sensitive_values = values

    def new(self, suffix):
        self.serial += 1
        if self.serial > self.maximum_files:
            raise ScanError('ARTIFACT_COUNT_BUDGET')
        return (Path(self.prefix)/(str(self.serial).zfill(6)+suffix)).as_posix()

    def reserve(self, count):
        if self.total+count > self.maximum_bytes:
            raise ScanError('ARTIFACT_BYTE_BUDGET')
        self.total += count

    def keep(self, ref, kind, *, accounted=False):
        path = scoped(self.root, ref)
        state = path.stat()
        identity = state.st_dev, state.st_ino
        if not stat.S_ISREG(state.st_mode) or identity in self.identities:
            raise ScanError('DISTINCT_PHYSICAL_ARTIFACT_REQUIRED')
        if len(self.records) >= self.maximum_files:
            raise ScanError('ARTIFACT_COUNT_BUDGET')
        if not accounted:
            self.reserve(state.st_size)
        row = dict(ref=ref, artifactType=kind, byteCount=state.st_size, sha256='sha256:'+file_sha256(path))
        self.records.append(row)
        self.identities.add(identity)
        return row

    def bytes(self, raw, suffix='.bin', kind='command_output'):
        if not isinstance(raw, bytes) or len(raw) > 4*1024*1024+1:
            raise ScanError('BOUNDED_RAW_ARTIFACT_REQUIRED')
        if any(value in raw for value in self.sensitive_values):
            raise ScanError('SENSITIVE_SOURCE_ARTIFACT_REJECTED')
        ref = self.new(suffix)
        self.reserve(len(raw))
        with scoped(self.root, ref).open('xb') as output:
            output.write(raw)
        return self.keep(ref, kind, accounted=True)

    def json(self, value, kind='command_output'):
        raw = (canonical(value)+'\n').encode()
        if len(raw) > 262144:
            raise ScanError('BOUNDED_JSON_ARTIFACT_REQUIRED')
        return self.bytes(raw, '.json', kind)

    @contextmanager
    def stream(self):
        ref, count = self.new('.jsonl'), 0
        with scoped(self.root, ref).open('xb') as output:
            def append(row):
                nonlocal count
                raw = (canonical(row)+'\n').encode()
                if len(raw) > MAX_LINE_BYTES:
                    raise ScanError('ARTIFACT_RECORD_LIMIT')
                self.reserve(len(raw))
                output.write(raw)
                count += 1
            yield append, ref
        self.keep(ref, 'command_output', accounted=True)

    def observation(self, observation):
        if any(value in observation.get('body', b'') for value in self.sensitive_values):
            observation.update(bodyRetained=False, bodyOmittedReason='SENSITIVE_SOURCE_CREDENTIAL')
        metadata = {key: value for key, value in observation.items() if key not in ('body', 'requestBody')}
        for key in ('body', 'requestBody'):
            raw = observation.get(key)
            if key == 'body' and observation.get('bodyRetained') is False:
                metadata['bodyRef'] = None
            elif raw is not None:
                row = self.bytes(raw)
                metadata[key+'Ref'] = row['ref']
        return self.json(metadata)


class SourceSession:
    def __init__(self, pair, listing, dav, artifacts, *, identity, window, local_root, per_page=200):
        if (not isinstance(listing, OpenListListing) or not isinstance(dav, OpenListSource)
                or identity.get('adapterBuild') != source_build() or type(per_page) is not int or not 1 <= per_page <= 1000):
            raise ScanError('EXACT_OBSERVER_BUILD_AND_CLIENTS_REQUIRED')
        self.pair, self.listing, self.dav, self.artifacts = pair, listing, dav, artifacts
        self.identity, self.window = dict(identity), tuple(map(utc, window))
        if len(self.window) != 2 or not 0 < (self.window[1]-self.window[0]).total_seconds() <= 86400:
            raise ScanError('FINITE_SOURCE_WINDOW_REQUIRED')
        self.local_root, self.per_page = Path(local_root), per_page
        if self.local_root.resolve() != self.local_root.absolute() or not self.local_root.is_dir():
            raise ScanError('EXPLICIT_NATIVE_FIXTURE_ROOT_REQUIRED')
        self.check()
        self.mapper = ControlledFixtureMap(scoped(artifacts.root, artifacts.new('.mapping.sqlite')), pair, listing,
                                           source_identity=identity)
        self.mapper.db.execute('CREATE TABLE mutation_versions(objectId TEXT PRIMARY KEY,version TEXT NOT NULL)')
        self.mapper.db.commit()
        self.sequence, self.provider_pages, self.probes, self.fault_cases = 0, None, [], None

    def close(self):
        self.mapper.close()

    def check(self):
        if not self.window[0] <= datetime.now(timezone.utc) <= self.window[1]:
            raise ScanError('SOURCE_OUTSIDE_APPROVED_WINDOW')

    def repeated_listings(self, runs=2):
        if type(runs) is not int or not 2 <= runs <= 10:
            raise ScanError('FINITE_REPEATED_LISTINGS_REQUIRED')
        pages = 0
        with self.artifacts.stream() as (append, ref):
            for number in range(runs):
                self.check()
                run_id = 'actual-listing-'+str(number+1)
                self.mapper.begin_run(run_id)
                def on_page(page):
                    nonlocal pages
                    self.check()
                    bound = self.mapper.bind_page(run_id, page)
                    count = 0
                    with self.artifacts.stream() as (objects, object_ref):
                        for profile in bound['profiles']:
                            objects(profile)
                            count += 1
                    append({**bound['header'], 'objects': {**descriptor(scoped(self.artifacts.root, object_ref), count), 'ref': object_ref}})
                    pages += 1
                def on_observation(observation):
                    self.artifacts.observation(observation)
                    self.check()
                self.listing.walk(scoped(self.artifacts.root, self.artifacts.new('.listing.sqlite')),
                                  on_observation=on_observation, on_page=on_page, per_page=self.per_page)
        self.provider_pages = {**descriptor(scoped(self.artifacts.root, ref), pages), 'ref': ref}
        return self.provider_pages

    def find(self, locator):
        """Complete parent enumeration, with disk-backed uniqueness before absence is trusted."""
        parts = _segments(locator)
        if not parts:
            raise ScanError('LEAF_LOCATOR_REQUIRED')
        parent, name = '/'.join(parts[:-1]), parts[-1]
        db = sqlite3.connect(scoped(self.artifacts.root, self.artifacts.new('.parent.sqlite')))
        found, count, expected, page = None, 0, None, 1
        try:
            db.executescript('PRAGMA journal_mode=OFF; PRAGMA temp_store=FILE; PRAGMA cache_size=-2048;'
                             'PRAGMA max_page_count=32768; CREATE TABLE names(name TEXT PRIMARY KEY);')
            with self.artifacts.stream() as (append, ref):
                while True:
                    self.check()
                    try:
                        observation = self.listing.observe(parent, page=page, per_page=self.per_page)
                    except SourceError as failure:
                        if failure.observation is not None:
                            self.artifacts.observation(failure.observation)
                        raise
                    raw = self.artifacts.observation(observation)
                    self.check()
                    total, entries = self.listing.parse_page(observation)
                    if expected is not None and expected != total:
                        raise ScanError('CHANGE_PARENT_POPULATION_DRIFT')
                    expected = total
                    append(dict(observationRef=raw['ref'], observationSha256=raw['sha256'], page=page, total=total))
                    for entry in entries:
                        db.execute('INSERT INTO names VALUES(?)', (entry['locator'].rsplit('/', 1)[-1],))
                        if entry['locator'].rsplit('/', 1)[-1] == name:
                            found = entry
                        count += 1
                    if count >= total:
                        if count != total:
                            raise ScanError('INCOMPLETE_CHANGE_PARENT_POPULATION')
                        break
                    page += 1
                    if page > MAX_OBJECTS:
                        raise ScanError('CHANGE_PARENT_PAGE_LIMIT')
            journal = {**descriptor(scoped(self.artifacts.root, ref), page), 'ref': ref}
            return found, self.artifacts.json(dict(kind='complete_parent_observation', locator=locator,
                observedAt=datetime.now(timezone.utc).isoformat(), complete=True, childCount=count,
                found=found, observations=journal))
        finally:
            db.close()

    def mutation(self, intent, clock):
        """Intent names desired fixture versions; observation attributes come from the source."""
        if not sys.platform.startswith('linux'):
            raise ScanError('NATIVE_CONTROLLED_MUTATION_REQUIRES_LINUX')
        self.check()
        operation, object_id, locator = (intent[key] for key in ('operation', 'objectId', 'path'))
        if operation not in ('create', 'update', 'delete'):
            raise ScanError('CONTROLLED_LEAF_MUTATION_REQUIRED')
        parts = _segments(locator)
        if not parts:
            raise ScanError('CONTROLLED_LEAF_MUTATION_REQUIRED')
        target = self.local_root.joinpath(*parts)
        if target.resolve() != target.absolute() or not target.resolve().is_relative_to(self.local_root.resolve()):
            raise ScanError('CONTROLLED_MUTATION_OUTSIDE_ROOT')
        old = self.mapper.db.execute('SELECT * FROM approved WHERE objectId=?', (object_id,)).fetchone()
        changed = self.mapper.db.execute('SELECT version FROM mutation_versions WHERE objectId=?', (object_id,)).fetchone()
        before = changed[0] if changed else old['versionId'] if old else 'absent'
        if (before != intent['beforeVersion'] or before == 'absent' and operation != 'create'
                or before != 'absent' and operation == 'create' or old and old['path'] != locator):
            raise ScanError('CONTROLLED_FIXTURE_VERSION_OR_LOCATOR_MISMATCH')
        remote_before, before_evidence = self.find(locator)
        if (remote_before is None) != (before == 'absent'):
            raise ScanError('ACTUAL_SOURCE_BEFORE_DISPOSITION_MISMATCH')
        receipt = dict(kind='controlled_local_mutation', operation=operation, objectId=object_id, locator=locator,
                       startedAt=datetime.now(timezone.utc).isoformat(), filesystemMutated=False, outcome='pending')
        try:
            if before != 'absent':
                with os.fdopen(os.open(target, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
                    state, raw_before = os.fstat(source.fileno()), source.read(65537)
                    if (not stat.S_ISREG(state.st_mode) or len(raw_before) > 65536
                            or intent['beforeSha256'] != 'sha256:'+hashlib.sha256(raw_before).hexdigest()
                            or remote_before['kind'] != 'file' or remote_before['fileSizeBytes'] != len(raw_before)
                            or utc(remote_before['modifiedAt']).timestamp() != state.st_mtime_ns/1e9):
                        raise ScanError('APPROVED_ACTUAL_BEFORE_PAYLOAD_REQUIRED')
                    receipt['beforeActualSha256'] = 'sha256:'+hashlib.sha256(raw_before).hexdigest()
                    receipt['beforeInode'] = state.st_ino
            if operation == 'delete':
                if intent['afterVersion'] != 'absent' or target.lstat().st_ino != state.st_ino:
                    raise ScanError('CONTROLLED_DELETE_IDENTITY_MISMATCH')
                target.unlink()
                receipt['filesystemMutated'] = True
            else:
                if intent['afterVersion'] == 'absent' or intent['afterVersion'] == before:
                    raise ScanError('CONTROLLED_NEW_VERSION_REQUIRED')
                payload_ref = scoped(self.artifacts.root, intent['payloadRef'])
                with payload_ref.open('rb') as source:
                    payload = source.read(65537)
                if len(payload) > 65536 or intent['payloadSha256'] != 'sha256:'+hashlib.sha256(payload).hexdigest():
                    raise ScanError('APPROVED_CONTROLLED_PAYLOAD_REQUIRED')
                flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if operation == 'create' else 0)
                fd = os.open(target, flags, 0o600)
                if operation == 'create':
                    receipt['filesystemMutated'] = True
                with os.fdopen(fd, 'wb') as output:
                    if operation == 'update' and os.fstat(output.fileno()).st_ino != state.st_ino:
                        raise ScanError('CONTROLLED_UPDATE_IDENTITY_MISMATCH')
                    output.truncate(0)
                    receipt['filesystemMutated'] = True
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
                stamp = utc(intent['modifiedAt']).timestamp()
                os.utime(target, (stamp, stamp), follow_symlinks=False)
                receipt['afterActualSha256'] = 'sha256:'+file_sha256(target)
                if receipt['afterActualSha256'] != intent['payloadSha256']:
                    raise ScanError('ACTUAL_CONTROLLED_WRITE_MISMATCH')
            remote_after, after_evidence = self.find(locator)
            profile = None
            if operation == 'delete':
                if remote_after is not None or target.exists():
                    raise ScanError('CONTROLLED_DELETE_NOT_OBSERVED')
            else:
                actual = target.stat()
                if (remote_after is None or remote_after['kind'] != 'file' or remote_after['fileSizeBytes'] != actual.st_size
                        or utc(remote_after['modifiedAt']).timestamp() != actual.st_mtime_ns/1e9):
                    raise ScanError('CONTROLLED_WRITE_NOT_OBSERVED')
                profile = dict(objectId=object_id, versionId=intent['afterVersion'], kind=remote_after['kind'],
                               depth=len(parts), fileSizeBytes=remote_after['fileSizeBytes'],
                               name=remote_after['locator'].rsplit('/', 1)[-1], path=remote_after['locator'],
                               modifiedAt=remote_after['modifiedAt'])
                validate_profile(profile)
            receipt['outcome'] = 'observed'
        except BaseException as failure:
            receipt.update(outcome='failed', error=str(failure) if isinstance(failure, ScanError) else type(failure).__name__)
            raise
        finally:
            receipt['finishedAt'] = datetime.now(timezone.utc).isoformat()
            mutation_evidence = self.artifacts.json(receipt)
        self.check()
        self.sequence += 1
        event = dict(eventId=intent['eventId'], sequence=self.sequence, objectId=object_id, operation=operation,
                     beforeVersion=before, afterVersion=intent['afterVersion'])
        observation = dict(kind='controlled_source_change_observation', sourceId=self.identity['sourceId'],
                           event=event, profile=profile, observedAt=clock.mapped_utc(time.monotonic_ns()),
                           evidenceRefs=[{key: row[key] for key in ('ref', 'sha256')}
                                         for row in (before_evidence, after_evidence, mutation_evidence)])
        with self.mapper.db:
            self.mapper.db.execute('INSERT INTO mutation_versions VALUES(?,?) ON CONFLICT(objectId) DO UPDATE SET version=excluded.version',
                                   (object_id, intent['afterVersion']))
        return self.artifacts.json(observation)

    def probe(self, case, object_id, version, locator, *, size):
        if case not in ('unchanged_first', 'unchanged_second', 'bounded', 'unsatisfiable', 'changed') or any(row['case'] == case for row in self.probes):
            raise ScanError('EXACT_UNIQUE_SOURCE_PROBE_REQUIRED')
        self.check()
        range_value = 'bytes=0-1' if case == 'bounded' else 'bytes='+str(size)+'-' if case == 'unsatisfiable' else ''
        try:
            observation = self.dav.observe('GET', locator, headers={'Range': range_value} if range_value else {}, maximum_bytes=65536)
        except SourceError as failure:
            if failure.observation is not None:
                self.artifacts.observation(failure.observation)
            raise
        self.check()
        self.artifacts.observation(observation)
        body = self.artifacts.bytes(observation['body'], kind='produced_media')
        row = dict(case=case, requestId='actual-probe-'+str(len(self.probes)+1), objectId=object_id,
                   objectVersion=version, observedAt=observation['endedAt'], requestRange=range_value,
                   statusCode=observation['status'], contentRange=observation['headers'].get('content-range', ''),
                   etag=observation['headers'].get('etag', ''), versionValidator='', responseRef=body['ref'],
                   responseSha256=body['sha256'], responseByteCount=body['byteCount'])
        self.probes.append(row)
        return row

    def exercise_faults(self, gateway, *, maximum_backoff=1):
        if (self.listing.endpoint != gateway.endpoint+'/api/fs/list'
                or type(maximum_backoff) not in (int, float) or not 0 <= maximum_backoff <= 5):
            raise ScanError('EXACT_CONTROLLED_GATEWAY_AND_RETRY_BUDGET_REQUIRED')
        cases = []
        for fault in ('http_429', 'http_5xx', 'network_disconnect', 'auth_expired'):
            self.check()
            with gateway.lock:
                first_index = len(gateway.events)
            if fault != 'auth_expired':
                gateway.inject(fault)
            client = (OpenListListing(gateway.endpoint, self.listing.scope, token=gateway.expired_token,
                                      timeout=self.listing.timeout) if fault == 'auth_expired' else self.listing)
            attempts = []
            for number in range(1 if fault == 'auth_expired' else 2):
                self.check()
                observation, failure_code, captured = None, None, None
                try:
                    observation = client.observe(per_page=self.per_page)
                    captured = self.artifacts.observation(observation)
                    client.parse_page(observation)
                except SourceError as failure:
                    failure_code = failure.code
                    observation = failure.observation
                    if captured is None and observation is not None:
                        captured = self.artifacts.observation(observation)
                if captured is None or observation is None:
                    raise ScanError('ACTUAL_FAULT_REQUEST_EVIDENCE_REQUIRED')
                status = observation['status']
                success = failure_code is None and status == 200 and observation.get('applicationCode') == 200
                expected = (status == 429 if fault == 'http_429' else status is not None and 500 <= status < 600
                            if fault == 'http_5xx' else status is None and failure_code == 'SOURCE_TRANSPORT_FAILURE'
                            if fault == 'network_disconnect' else status in (401, 403))
                if not (expected if number == 0 else success):
                    raise ScanError('INJECTED_FAULT_OR_BOUNDED_RETRY_NOT_OBSERVED')
                delay = 0.0
                if fault != 'auth_expired' and number == 0:
                    try:
                        delay = float(observation['headers'].get('retry-after', '0.01'))
                    except ValueError:
                        raise ScanError('FINITE_RETRY_AFTER_REQUIRED') from None
                    if not 0 <= delay <= maximum_backoff:
                        raise ScanError('RETRY_AFTER_EXCEEDS_APPROVED_BUDGET')
                attempts.append(dict(number=number+1, statusCode=status, applicationCode=observation.get('applicationCode'),
                                     error=failure_code, observationRef=captured['ref'], observationSha256=captured['sha256'],
                                     startedAt=observation['startedAt'], finishedAt=observation['endedAt'], retryDelaySeconds=delay))
                if delay:
                    time.sleep(delay)
            deadline = time.monotonic()+1
            while True:
                with gateway.lock:
                    server_events = list(gateway.events[first_index:])
                if len(server_events) >= len(attempts):
                    break
                if time.monotonic() >= deadline:
                    raise ScanError('ACTUAL_GATEWAY_DECISION_EVIDENCE_REQUIRED')
                time.sleep(.001)
            if server_events[0]['injectedFault'] != fault or server_events[0]['upstreamContacted']:
                raise ScanError('EXPLICIT_ADAPTER_FAULT_PROVENANCE_REQUIRED')
            raw = self.artifacts.json(dict(schemaVersion=1, kind='controlled_source_fault_observation',
                sourceIdentity=self.identity, fault=fault, attempts=attempts, actualGatewayEvents=server_events,
                providerFaultClaim=False, gatewayAuthorizationOnly=fault == 'auth_expired'), 'scope_observation')
            cases.append(dict(caseId='adapter-'+fault, fault=fault, rawOutputRef=raw['ref'],
                              parameters=dict(adapterOnly=True, maximumAttempts=len(attempts), maximumBackoffSeconds=maximum_backoff,
                                              scope=gateway.scope, outcome='explicit_failure' if fault == 'auth_expired' else 'bounded_retry_success'),
                              observation='exercised'))
        self.gateway_quota = gateway.request_limit, gateway.period_seconds
        self.fault_cases = cases
        return cases


def records(path):
    with Path(path).open('rb') as source:
        while True:
            raw = source.readline(MAX_LINE_BYTES+1)
            if not raw:
                return
            if len(raw) > MAX_LINE_BYTES or not raw.endswith(b'\n'):
                raise ScanError('BOUNDED_COMPLETE_RECORD_REQUIRED')
            yield decode(raw)


def original13_reports(run, facts, session, *, quota_ref, quota_sha, extension_categories):
    """Derive actual observations; a frozen qualification checker still decides acceptance."""
    if (facts.get('outcome') != 'accepted' or session.provider_pages is None or len(session.probes) != 5
            or session.fault_cases is None):
        raise ScanError('COMPLETE_REAL_OBSERVATIONS_REQUIRED')
    cfg, context = run.cfg, run.cfg['context']
    quota, _ = read_json(scoped(cfg['artifactRoot'], quota_ref), quota_sha)
    if (quota['sourceIdentity'] != session.identity or (quota['requestLimit'], quota['periodSeconds']) != session.gateway_quota
            or session.identity['sourceId'] != cfg['sourceId'] or session.pair.shas != [cfg[key]['sha256'][7:] for key in ('baseline', 'profiled')]):
        raise ScanError('EXACT_SOURCE_QUOTA_DOCUMENT_REQUIRED')
    phases = {}
    for name in ('enumeration', 'changeStream', 'incremental'):
        phase = facts['phases'][name]
        keys = ('objects',) if name == 'enumeration' else ('events',) if name == 'changeStream' else ('appliedEvents', 'traversedObjects')
        phases[name] = dict(startedAt=phase['start']['observedAt'], finishedAt=phase['end']['observedAt'],
                            executionRef=cfg['phaseCaptures'][name], **{key: phase['outputs'][key] for key in keys})
    phases['enumeration']['scanId'] = cfg['scanId']
    for name in ('changeStream', 'incremental'):
        phases[name]['changeSetId'] = cfg['changeSetId']
    phases['incremental']['postScanObjects'] = {**facts['postCatalogue']['objects'], 'observedAt': facts['postCatalogue']['observedAt']}
    scan = dict(schemaVersion=1, kind='metadata_scan_observation', **context, **phases)
    resources = dict(schemaVersion=1, kind='metadata_resource_observation', **context, scanId=cfg['scanId'],
                     processId=cfg['processId'], collectorBuild=cfg['counterCollectorBuild'],
                     method='os_process_peak_resident_counter', sourceIdentity=session.identity,
                     quotaDocumentRef=quota_ref, quotaDocumentSha256=quota_sha, memorySamples=facts['memorySamples'],
                     nativeProcessId=run.process.pid, counterFormat='linux_proc_status', collectorCommandArgs=cfg['memoryCollectorCommandArgs'])
    filename_ref = cfg['outputs']['filenameObjects']
    counts, byte_count, maximum_depth, total = {'file': 0, 'directory': 0}, 0, 0, 0
    distributions = {key: {} for key in ('nameLength', 'characterSet', 'extension', 'pathDepth')}
    for row in records(scoped(cfg['artifactRoot'], filename_ref)):
        validate_profile(row)
        counts[row['kind']] += 1
        total += 1
        maximum_depth = max(maximum_depth, row['depth'])
        name = row['name']
        suffix = name.rsplit('.', 1)[1].lower() if '.' in name and not name.startswith('.') else ''
        values = dict(nameLength=str(len(name)), characterSet='ascii' if name.isascii() else 'non_ascii', pathDepth=str(row['depth']))
        if row['kind'] == 'file':
            byte_count += row['fileSizeBytes']
            values['extension'] = suffix if suffix in extension_categories else 'other' if suffix else 'none'
        for key, value in values.items():
            distributions[key][value] = distributions[key].get(value, 0)+1
    probes = {row['case']: row for row in session.probes}
    if set(probes) != {'unchanged_first', 'unchanged_second', 'bounded', 'unsatisfiable', 'changed'}:
        raise ScanError('EXACT_COMPLETE_PROBE_SET_REQUIRED')
    statuses = probes['bounded']['statusCode'], probes['unsatisfiable']['statusCode']
    if statuses == (206, 416):
        disposition = 'supported'
    elif statuses == (200, 200):
        disposition = 'ignored'
    elif all(status in (400, 405, 501) for status in statuses):
        disposition = 'unsupported'
    else:
        raise ScanError('UNCLASSIFIED_ACTUAL_RANGE_BEHAVIOR')
    validator = 'etag' if any(row['etag'] for row in probes.values()) else 'none'
    first, second, changed = (probes[key]['etag'] for key in ('unchanged_first', 'unchanged_second', 'changed'))
    profiling = dict(schemaVersion=1, kind='metadata_profiling_observations', **context, sourceIdentity=session.identity,
                     filenameObjects={**descriptor(scoped(cfg['artifactRoot'], filename_ref), total), 'ref': filename_ref},
                     filenameDistributions=distributions, providerPages=session.provider_pages, rangeDisposition=disposition,
                     validatorKind=validator, validatorStableOnUnchanged=bool(first) and first == second,
                     validatorChangedOnUpdate=bool(first) and bool(changed) and first != changed, probes=session.probes)
    def seconds(name):
        phase = facts['phases'][name]
        elapsed = (phase['end']['monotonicNs']-phase['start']['monotonicNs'])/1e9
        if elapsed <= 0:
            raise ScanError('POSITIVE_REAL_PHASE_INTERVAL_REQUIRED')
        return elapsed
    metrics = dict(file_count=counts['file'], directory_count=counts['directory'], directory_depth_max=maximum_depth,
                   average_file_size=byte_count/counts['file'], source_api_quota=quota['requestLimit']*60/quota['periodSeconds'],
                   source_change_frequency=phases['changeStream']['events']['count']*3600/seconds('changeStream'),
                   enumeration_rate=phases['enumeration']['objects']['count']/seconds('enumeration'),
                   incremental_scan_cost=seconds('incremental'), memory_peak=facts['memorySamples'][-1]['peakResidentBytes']/(1024*1024),
                   filename_characteristics_profiled=True, provider_characteristics_profiled=True,
                   range_support_profiled=True, etag_behavior_profiled=True)
    return dict(scan=scan, resources=resources, profiling=profiling, measurements=metrics,
                faultMatrix=dict(schemaVersion=1, scope='LOCAL_FULL_V1', cases=session.fault_cases), qualificationAccepted=False)

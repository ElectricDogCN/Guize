"""Actual loopback/fixture tests, not a real OpenList or approved scale experiment."""
import base64
import hashlib
import gzip
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import jsonschema
import yaml

from canonical_metadata import CanonicalPair, generate_canonical
from controlled_source_run import (Artifacts, SourceSession, original13_reports, records,
                                   retain_approved_metadata_inputs, source_build)
from loopback_gateway import ControlledGateway
from metadata_scan import ScanError, canonical, file_sha256
from native_scan_protocol import Clock, read_json
from native_memory import native_identity
from openlist_listing import OpenListListing
from openlist_source import OpenListSource, SourceError
import test_native_scan as native_fixtures
from run_source_experiment import reserve_config


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.source = self.root/'source'
        self.source.mkdir()
        self.baseline, self.profiled = self.root/'base.jsonl', self.root/'profile.jsonl'
        generate_canonical(self.baseline, self.profiled, file_count=4, directory_count=2, maximum_depth=2, seed=1)
        self.rows = list(records(self.profiled))
        for row in self.rows:
            path = self.source/row['path']
            if row['kind'] == 'directory':
                path.mkdir()
            else:
                path.write_bytes(b'x'*row['fileSizeBytes'])
        self.align_times(self.source, self.rows)
        self.requests, self.duplicate_pages, self.hide_name = [], False, None
        self.upstream_token = 'private-unit-upstream-token'
        self.upstream_basic = 'Basic '+base64.b64encode(b'unit-reader:private-unit-password').decode()
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def send(self, status, raw, headers=()):
                self.send_response(status)
                for key, value in headers:
                    self.send_header(key, value)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(raw)
            def do_POST(self):
                owner.requests.append(dict(method='POST', path=self.path))
                if self.headers.get('Authorization') != owner.upstream_token:
                    self.send(401, b'{"code":401}')
                    return
                doc = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                relative = doc['path'].removeprefix('/fixture').lstrip('/')
                folder = owner.source/relative
                entries = []
                for path in sorted(folder.iterdir()):
                    if path.name == owner.hide_name:
                        continue
                    state = path.stat()
                    entries.append(dict(name=path.name, is_dir=path.is_dir(), size=state.st_size,
                        modified=datetime.fromtimestamp(state.st_mtime, timezone.utc).isoformat().replace('+00:00', 'Z'), sign='', thumb=''))
                offset = 0 if owner.duplicate_pages else (doc['page']-1)*doc['per_page']
                length = min(doc['per_page'], max(0, len(entries)-(doc['page']-1)*doc['per_page']))
                raw = canonical(dict(code=200, data=dict(total=len(entries), content=entries[offset:offset+length]))).encode()
                self.send(200, raw, [('Content-Type', 'application/json')])
            def do_HEAD(self):
                self.do_GET()
            def do_GET(self):
                owner.requests.append(dict(method=self.command, path=self.path))
                if self.headers.get('Authorization') != owner.upstream_basic:
                    self.send(401, b'')
                    return
                path = owner.source/urllib.parse.unquote(self.path.removeprefix('/dav/fixture/'))
                raw = path.read_bytes()
                etag = '"'+hashlib.sha256(raw).hexdigest()+'"'
                value = self.headers.get('Range')
                if value == 'bytes='+str(len(raw))+'-':
                    self.send(416, b'unit-original-negative-body\n', [('Content-Range', 'bytes */'+str(len(raw)))])
                elif value == 'bytes=0-1':
                    self.send(206, raw[:2], [('Content-Range', 'bytes 0-1/'+str(len(raw))), ('ETag', etag)])
                else:
                    self.send(200, raw, [('ETag', etag)])
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 10)
        self.addCleanup(self.server.shutdown)

    @staticmethod
    def align_times(root, rows):
        for row in sorted(rows, key=lambda row: row['depth'], reverse=True):
            stamp = datetime.fromisoformat(row['modifiedAt'].replace('Z', '+00:00')).timestamp()
            os.utime(root/row['path'], (stamp, stamp))

    def gateway(self, **kwargs):
        now = datetime.now(timezone.utc)
        window = kwargs.pop('window', ((now-timedelta(seconds=1)).isoformat(), (now+timedelta(seconds=60)).isoformat()))
        gateway = ControlledGateway('http://127.0.0.1:'+str(self.server.server_port), 'fixture',
            upstream_token=self.upstream_token, upstream_basic=self.upstream_basic,
            window=window, request_limit=kwargs.pop('request_limit', 10000), period_seconds=kwargs.pop('period_seconds', 60), **kwargs).start_server()
        self.addCleanup(gateway.close)
        listing = OpenListListing(gateway.endpoint, 'fixture', token=gateway.token)
        dav = OpenListSource(gateway.endpoint+'/dav/fixture/', username=gateway.username, password=gateway.password)
        return gateway, listing, dav, window

    def session(self):
        gateway, listing, dav, window = self.gateway()
        artifacts = Artifacts(self.root, self.root/'retained')
        pair = CanonicalPair(self.baseline, self.profiled, baseline_sha256=file_sha256(self.baseline),
            profiled_sha256=file_sha256(self.profiled), source_id='unit-source', snapshot_version='v1', page_size=2)
        identity = dict(adapterId='controlled-unit-gateway', adapterBuild=source_build(), sourceId='unit-source', sourceVersion='unit-http-not-openlist')
        session = SourceSession(pair, listing, dav, artifacts, identity=identity, window=window, local_root=self.source, per_page=2)
        self.addCleanup(session.close)
        return gateway, session

    def request(self, gateway, path, method='GET', token=None, body=None):
        headers = {'Authorization': token or gateway.basic}
        req = urllib.request.Request(gateway.endpoint+path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as response:
            return response.status, response.read()

    def test_gateway_denies_admin_mutators_scope_escape_and_expired_auth_before_forwarding(self):
        gateway, listing, _, _ = self.gateway()
        total, _ = listing.parse_page(listing.observe(per_page=2))
        self.assertGreater(total, 0)
        count = len(self.requests)
        for path, method in (('/api/admin/storage/list', 'GET'), ('/dav/other/file', 'GET'),
                             ('/dav/fixture/file', 'PUT'), ('/dav/fixture/%2e%2e/other', 'GET'),
                             ('/dav/fixture/file?secret=denied', 'GET')):
            self.assertEqual(self.request(gateway, path, method)[0], 403)
        allowed = dict(path='/fixture', page=1, per_page=200, refresh=False)
        for document in ({**allowed, 'path':'/other'}, {**allowed, 'refresh':True},
                         {**allowed, 'password':''}, {**allowed, 'password':'unit-not-a-real-secret'},
                         {**allowed, 'unexpected':True}):
            self.assertEqual(self.request(gateway, '/api/fs/list', 'POST', gateway.token, canonical(document).encode())[0], 403)
        expired = OpenListListing(gateway.endpoint, 'fixture', token=gateway.expired_token).observe()
        self.assertEqual(expired['status'], 401)
        self.assertEqual(len(self.requests), count)

    def test_actual_forwarded_range_and_negative_bytes_and_missing_validator_are_unchanged(self):
        _, _, dav, _ = self.gateway()
        row = next(row for row in self.rows if row['kind'] == 'file' and row['fileSizeBytes'] == 4096)
        full = dav.observe('GET', row['path'], maximum_bytes=65536)
        bounded = dav.observe('GET', row['path'], headers={'Range': 'bytes=0-1'}, maximum_bytes=65536)
        rejected = dav.observe('GET', row['path'], headers={'Range': 'bytes=4096-'}, maximum_bytes=65536)
        self.assertEqual(full['body'], b'x'*4096)
        self.assertEqual(bounded['status'], 206)
        self.assertEqual(bounded['body'], full['body'][:2])
        self.assertEqual(rejected['status'], 416)
        self.assertEqual(rejected['body'], b'unit-original-negative-body\n')
        self.assertNotIn('etag', rejected['headers'])

    def test_actual_quota_reset_and_injected_status_disconnect_are_distinct_from_upstream(self):
        gateway, listing, _, _ = self.gateway(request_limit=1, period_seconds=1)
        listing.observe()
        self.assertEqual(listing.observe()['status'], 429)
        self.assertEqual(len(self.requests), 1)
        time.sleep(1.01)
        self.assertEqual(listing.observe()['status'], 200)
        # A separate gateway has a generous real quota so explicit fault injection is isolated.
        other, client, _, _ = self.gateway()
        for fault, status in (('http_429', 429), ('http_5xx', 503)):
            before = len(self.requests)
            other.inject(fault)
            self.assertEqual(client.observe()['status'], status)
            self.assertEqual(len(self.requests), before)
            self.assertEqual(client.observe()['status'], 200)
        other.inject('network_disconnect')
        with self.assertRaises(SourceError):
            client.observe()
        self.assertEqual(client.observe()['status'], 200)

    def test_complete_repeated_observations_have_frozen_pages_and_no_credentials_in_artifacts(self):
        gateway, session = self.session()
        result = session.repeated_listings(2)
        pages = list(records(result['ref']))
        self.assertEqual(len(pages), result['count'])
        schema = yaml.safe_load((Path(__file__).resolve().parents[2]/'specs/poc/program.schema.yaml').read_text(encoding='utf8'))['$defs']
        validator = jsonschema.Draft202012Validator(schema['metadataProviderPageRecord'], format_checker=jsonschema.FormatChecker())
        for page in pages:
            validator.validate(page)
        for run_id in ('actual-listing-1', 'actual-listing-2'):
            self.assertEqual(session.mapper.state(run_id)['objects'], len(self.rows))
            self.assertTrue(session.mapper.state(run_id)['completed'])
        secret_values = (gateway.token, gateway.expired_token, gateway.password, gateway.basic, self.upstream_token, self.upstream_basic)
        for row in session.artifacts.records:
            raw = Path(row['ref']).read_bytes()
            self.assertEqual('sha256:'+hashlib.sha256(raw).hexdigest(), row['sha256'])
            for value in secret_values:
                self.assertNotIn(value.encode(), raw)

    def test_incomplete_duplicate_parent_pages_never_prove_absence(self):
        _, session = self.session()
        self.duplicate_pages = True
        with self.assertRaises(sqlite3.IntegrityError):
            session.find('missing.bin')

    def test_fault_matrix_binds_real_adapter_decisions_and_bounded_retries(self):
        gateway, session = self.session()
        cases = session.exercise_faults(gateway)
        self.assertEqual({row['fault'] for row in cases}, {'http_429', 'http_5xx', 'network_disconnect', 'auth_expired'})
        for case in cases:
            raw = read_json(case['rawOutputRef'])[0]
            self.assertFalse(raw['providerFaultClaim'])
            self.assertFalse(raw['actualGatewayEvents'][0]['upstreamContacted'])
            if case['fault'] == 'auth_expired':
                self.assertEqual(len(raw['attempts']), 1)
                self.assertEqual(raw['attempts'][0]['statusCode'], 401)
                self.assertTrue(raw['gatewayAuthorizationOnly'])
            else:
                self.assertEqual(len(raw['attempts']), 2)
                self.assertEqual(raw['attempts'][-1]['statusCode'], 200)
                self.assertTrue(raw['actualGatewayEvents'][-1]['upstreamContacted'])

    def test_artifact_budget_alias_and_omitted_body_are_not_successful_substitutes(self):
        journal = Artifacts(self.root, self.root/'small', maximum_bytes=1000)
        first = journal.bytes(b'actual')
        alias = self.root/'alias'
        os.link(first['ref'], alias)
        with self.assertRaisesRegex(ScanError, 'DISTINCT_PHYSICAL'):
            journal.keep(str(alias), 'command_output')
        row = journal.observation(dict(body=b'', bodyRetained=False, bodyBytes=2000,
            bodySha256='f'*64, bodyOmittedReason='UNINSPECTABLE_LISTING_BODY', status=200))
        value = read_json(row['ref'])[0]
        self.assertIsNone(value['bodyRef'])
        self.assertEqual(value['bodyBytes'], 2000)
        journal.set_sensitive_values(('known-private-credential',))
        raw = b'upstream echoed known-private-credential'
        observation = dict(body=raw, bodyRetained=True, bodyBytes=len(raw), bodySha256=hashlib.sha256(raw).hexdigest(), status=200)
        row = journal.observation(observation)
        value = read_json(row['ref'])[0]
        self.assertFalse(observation['bodyRetained'])
        self.assertIsNone(value['bodyRef'])
        self.assertEqual(value['bodyBytes'], len(raw))
        self.assertEqual(value['bodySha256'], hashlib.sha256(raw).hexdigest())
        self.assertNotIn(b'known-private-credential', Path(row['ref']).read_bytes())
        with self.assertRaisesRegex(ScanError, 'BYTE_BUDGET'):
            journal.bytes(b'x'*1000)

    def test_actual_binary_get_body_keeps_binary_artifact_and_exact_http_observation(self):
        _,_,dav,_=self.gateway()
        row=next(row for row in self.rows if row['kind']=='file' and row['fileSizeBytes']==4096)
        raw=bytes(range(256))*16
        (self.source/row['path']).write_bytes(raw)
        observation=dav.observe('GET',row['path'],maximum_bytes=65536)
        self.assertEqual(observation['status'],200)
        self.assertEqual(observation['body'],raw)
        with self.assertRaises(UnicodeDecodeError): raw.decode('utf8')
        journal=Artifacts(self.root,self.root/'binary-response-journal')
        retained=journal.observation(observation)
        metadata=read_json(retained['ref'])[0]
        body=next(item for item in journal.records if item['ref']==metadata['bodyRef'])
        self.assertEqual(body['artifactType'],'produced_media')
        self.assertEqual(Path(body['ref']).read_bytes(),raw)
        self.assertEqual(body['byteCount'],4096)
        self.assertEqual(body['sha256'],'sha256:'+hashlib.sha256(raw).hexdigest())
        self.assertEqual(retained['artifactType'],'command_output')
        expected={key:value for key,value in observation.items() if key not in ('body','requestBody')}
        self.assertEqual(metadata,{**expected,'bodyRef':body['ref']})

    def test_unapproved_payload_and_failed_confirmation_preserve_actual_fixture_state(self):
        _, session = self.session()
        clock = Clock()
        row = next(row for row in self.rows if row['kind'] == 'file' and row['fileSizeBytes'] == 4096)
        intent = dict(eventId='bad', operation='update', objectId=row['objectId'], path=row['path'],
                      beforeVersion='v1', afterVersion='v2', beforeSha256='sha256:'+'0'*64)
        if not sys.platform.startswith('linux'):
            with self.assertRaisesRegex(ScanError, 'NATIVE_CONTROLLED_MUTATION_REQUIRES_LINUX'):
                session.mutation(intent, clock)
            return
        with self.assertRaisesRegex(ScanError, 'BEFORE_PAYLOAD'):
            session.mutation(intent, clock)
        self.assertEqual((self.source/row['path']).read_bytes(), b'x'*4096)
        payload = session.artifacts.bytes(b'created', kind='produced_media')
        self.hide_name = 'created.bin'
        intent = dict(eventId='create', operation='create', objectId='created', path='created.bin',
            beforeVersion='absent', afterVersion='v1', payloadRef=payload['ref'], payloadSha256=payload['sha256'], modifiedAt='2026-01-01T00:00:02Z')
        with self.assertRaisesRegex(ScanError, 'WRITE_NOT_OBSERVED'):
            session.mutation(intent, clock)
        self.assertEqual((self.source/'created.bin').read_bytes(), b'created')
        receipts = [read_json(row['ref'])[0] for row in session.artifacts.records if row['ref'].endswith('.json')]
        self.assertTrue(any(row.get('outcome') == 'failed' and row.get('filesystemMutated') for row in receipts))
        self.assertEqual(session.sequence, 0)

    def test_actual_native_chain_assembles_all_original13_from_observed_source_without_qualifying_it(self):
        if not sys.platform.startswith('linux'):
            _, session = self.session()
            with self.assertRaisesRegex(ScanError, 'NATIVE_CONTROLLED_MUTATION_REQUIRES_LINUX'):
                session.mutation({}, Clock())
            return
        native = native_fixtures.NativeLifecycleTests('test_actual_linux_lifetime_counters_replay_post_catalogue_and_frozen_captures')
        native.setUp()
        self.addCleanup(native.doCleanups)
        def compressed_exports(cfg):
            for key in ('objects', 'filenameObjects', 'enumeratedVersions'):
                cfg['outputs'][key] += '.gz'
        run = native.prepare(alter_config=compressed_exports)
        self.source = native.source
        self.align_times(self.source, native.rows)
        native.release()
        gateway, listing, dav, window = self.gateway()
        artifacts = Artifacts(native.root, native.root/'source-observations')
        pair = CanonicalPair(native.cfg['baseline']['ref'], native.cfg['profiled']['ref'],
            baseline_sha256=native.cfg['baseline']['sha256'][7:], profiled_sha256=native.cfg['profiled']['sha256'][7:],
            source_id=native.cfg['sourceId'], snapshot_version='v1', page_size=2)
        identity = dict(adapterId='controlled-unit-gateway', adapterBuild=source_build(), sourceId=native.cfg['sourceId'], sourceVersion='unit-http-not-openlist')
        session = SourceSession(pair, listing, dav, artifacts, identity=identity, window=window, local_root=self.source, per_page=2)
        self.addCleanup(session.close)
        run.memory()
        session.repeated_listings()
        session.exercise_faults(gateway)
        try:
            run.enumerate()
        except ScanError as failure:
            print('Actual native component failure: '+canonical(getattr(failure, 'runtime_failure', {})))
            raise
        probe = next(row for row in native.rows if row['kind'] == 'file' and row['fileSizeBytes'] == 4096)
        for case in ('unchanged_first', 'unchanged_second', 'bounded', 'unsatisfiable'):
            session.probe(case, probe['objectId'], 'v1', probe['path'], size=4096)
        run.begin_changes()
        delete = next(row for row in native.rows if row['kind'] == 'file' and row['fileSizeBytes'] == 0)
        for number, operation, row, content in ((1, 'create', dict(objectId='created', path='created.bin'), b'created'),
                                               (2, 'update', probe, b'changed'), (3, 'delete', delete, None)):
            intent = dict(eventId='actual-event-'+str(number), operation=operation, objectId=row['objectId'], path=row['path'],
                          beforeVersion='absent' if operation == 'create' else 'v1', afterVersion='absent' if operation == 'delete' else 'v2' if operation == 'update' else 'v1')
            if operation != 'create':
                intent['beforeSha256'] = 'sha256:'+file_sha256(self.source/row['path'])
            if content is not None:
                payload = artifacts.bytes(content, kind='produced_media')
                intent.update(payloadRef=payload['ref'], payloadSha256=payload['sha256'], modifiedAt='2026-01-01T00:00:02Z')
            observed = session.mutation(intent, run.clock)
            run.observe_change(observed['ref'], observed['sha256'])
        session.probe('changed', probe['objectId'], 'v2', probe['path'], size=7)
        run.end_changes()
        run.incremental()
        run.post_catalogue()
        run.memory(final=True)
        facts = run.finish()
        quota = artifacts.json(dict(schemaVersion=1, kind='documented_source_quota', sourceIdentity=identity,
            requestLimit=gateway.request_limit, periodSeconds=gateway.period_seconds,
            resetSemantics='monotonic adapter fixed buckets', backoffStrategy='bounded retry', maximumBackoffSeconds=1,
            documentationRevision='unit-gateway-v1'))
        reports = original13_reports(run, facts, session, quota_ref=quota['ref'], quota_sha=quota['sha256'], extension_categories=['mp4', 'mkv', 'webm', 'mov'])
        schema = yaml.safe_load((Path(__file__).resolve().parents[2]/'specs/poc/program.schema.yaml').read_text(encoding='utf8'))['$defs']
        for key, definition in (('scan', 'metadataScanObservation'), ('resources', 'metadataResourceObservation'), ('profiling', 'metadataProfilingObservation')):
            jsonschema.Draft202012Validator(schema[definition], format_checker=jsonschema.FormatChecker()).validate(reports[key])
        self.assertEqual(len(reports['measurements']), 13)
        self.assertEqual(reports['measurements']['file_count'], 5)
        self.assertEqual(reports['measurements']['directory_count'], 2)
        self.assertEqual(reports['measurements']['memory_peak'], facts['memorySamples'][-1]['peakResidentBytes']/(1024*1024))
        self.assertFalse(reports['qualificationAccepted'])
        negative = next(row for row in reports['profiling']['probes'] if row['case'] == 'unsatisfiable')
        self.assertEqual(Path(negative['responseRef']).read_bytes(), b'unit-original-negative-body\n')
        self.assertEqual(negative['etag'], '')

    def test_concrete_reservation_binds_actual_pid_config_and_independent_request_before_any_source_access(self):
        if not sys.platform.startswith('linux'):
            with self.assertRaisesRegex(ScanError, 'LINUX_SOURCE_EXPERIMENT_REQUIRED'):
                reserve_config({})
            return
        native = native_fixtures.NativeLifecycleTests('test_actual_linux_lifetime_counters_replay_post_catalogue_and_frozen_captures')
        native.setUp()
        self.addCleanup(native.doCleanups)
        old = native.prepare()
        old.close()
        root = native.root/'concrete'
        root.mkdir()
        cfg = json.loads(json.dumps(native.cfg).replace(str(native.root), str(root)))
        for name in ('baseline.jsonl', 'profiled.jsonl'):
            shutil.copyfile(native.root/name, root/name)
        refs = {key: str(root/name) for key, name in dict(resourceConfiguration='unit-resource.json',
            runtimeConfiguration='config.json', manifest='manifest.json', stdout='scanner.stdout',
            stderr='scanner.stderr', approvalRequest='request.json').items()}
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1', 0))
            port = candidate.getsockname()[1]
        identity = dict(adapterId='controlled-unit-gateway', adapterBuild=source_build(), sourceId=cfg['sourceId'], sourceVersion='unit-http-not-openlist')
        cfg['sourceRun'] = dict(identity=identity, upstreamIdentity=native_identity(os.getpid()),
            origin='http://127.0.0.1:'+str(self.server.server_port), scope='fixture', gatewayPort=port,
            quotaRef=str(root/'quota.json'), quotaSha256='sha256:'+'1'*64)
        draft = dict(runtimeConfig=cfg, resourceConfiguration=dict(configuration=dict(metadataScanPolicy={},
            metadataResourcePolicy={}, metadataProfilingPolicy={})), refs=refs, unitFixtureOnly=True,
            approvalRef=str(root/'not-created-approval.json'), reservationDeadline=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat())
        run, actual, request = reserve_config(draft)
        self.addCleanup(run.close)
        self.assertEqual(request['reservation']['nativeProcessId'], run.process.pid)
        self.assertIsNone(run.process.poll())
        self.assertEqual(request['runtimeConfigSha256'], 'sha256:'+file_sha256(refs['runtimeConfiguration']))
        self.assertEqual(request['configurationSha256'], 'sha256:'+file_sha256(refs['resourceConfiguration']))
        configuration = read_json(refs['resourceConfiguration'])[0]['configuration']
        self.assertEqual(configuration['metadataScanPolicy']['nativeProcessId'], run.process.pid)
        self.assertEqual(configuration['metadataResourcePolicy']['collectorCommandArgs'], actual['memoryCollectorCommandArgs'])
        self.assertEqual(configuration['metadataProfilingPolicy']['endpointURL'], 'http://127.0.0.1:'+str(port)+'/api/fs/list')
        self.assertEqual(self.requests, [])
        self.assertFalse(Path(draft['approvalRef']).exists())
        self.assertTrue(all(not Path(ref).exists() for ref in actual['outputs'].values()))

    def test_qualification_inputs_retain_expected_changes_and_baseline_probe_with_exact_bytes(self):
        artifacts = Artifacts(self.root, str(self.root/'input-retention'))
        def sample(name, raw):
            path = self.root/name
            path.write_bytes(raw)
            return dict(ref=str(path), sha256='sha256:'+file_sha256(path))
        baseline = dict(ref=str(self.baseline), sha256='sha256:'+file_sha256(self.baseline))
        profiled = dict(ref=str(self.profiled), sha256='sha256:'+file_sha256(self.profiled))
        changes = sample('expected-changes.jsonl', b'{"eventId":"actual-approved-input"}\n')
        before = sample('baseline-probe.bin', bytes(range(256))*16)
        after = sample('updated-probe.bin', bytes(reversed(range(256)))*16)
        quota = sample('input-quota.json', b'{"requestLimit":6000}\n')
        configuration = dict(metadataScanPolicy=dict(baseline=baseline, expectedChanges=changes),
            metadataProfilingPolicy=dict(filenameInput=profiled, baselinePayload=before, updatedPayload=after),
            metadataResourcePolicy=dict(quotaDocumentRef=quota['ref'], quotaDocumentSha256=quota['sha256']))
        retain_approved_metadata_inputs(artifacts, configuration)
        self.assertEqual(len(artifacts.records), 6)
        retained = {row['ref']: row for row in artifacts.records}
        for descriptor in (baseline, profiled, changes, before, after, quota):
            self.assertEqual(retained[descriptor['ref']]['sha256'], descriptor['sha256'])
            self.assertEqual(retained[descriptor['ref']]['byteCount'], Path(descriptor['ref']).stat().st_size)
        self.assertEqual(retained[changes['ref']]['artifactType'], 'command_output')
        self.assertEqual(retained[before['ref']]['artifactType'], 'produced_media')
        retain_approved_metadata_inputs(artifacts, configuration)
        self.assertEqual(len(artifacts.records), 6)
        Path(before['ref']).write_bytes(b'changed after approval')
        with self.assertRaisesRegex(ScanError, 'APPROVED_METADATA_INPUT_CHANGED'):
            retain_approved_metadata_inputs(artifacts, configuration)
        self.assertEqual(len(artifacts.records), 6)


class CompressedArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_physical_budget_includes_gzip_header_and_footer(self):
        rows = [{'name': 'x'*3000}, {'name': 'x'*3000}]
        decoded = b''.join((canonical(row)+'\n').encode() for row in rows)
        budget = len(gzip.compress(decoded, compresslevel=6, mtime=0))
        self.assertGreater(len(decoded), budget)
        artifacts = Artifacts(self.root, self.root/'exact', maximum_bytes=budget)
        with artifacts.stream(metadata=True) as (append, ref):
            for row in rows:
                append(row)
        path = self.root/ref
        self.assertTrue(ref.endswith('.jsonl.gz'))
        self.assertEqual(artifacts.total, path.stat().st_size)
        self.assertEqual(artifacts.total, budget)
        self.assertEqual(artifacts.records[0]['sha256'], 'sha256:'+file_sha256(path))
        self.assertEqual(artifacts.records[0]['byteCount'], budget)
        self.assertEqual(list(records(path)), rows)

    def test_compressed_quota_failure_retains_partial_file_without_success_record(self):
        row = {'name': 'x'*3000}
        decoded = (canonical(row)+'\n').encode()
        complete_size = len(gzip.compress(decoded, compresslevel=6, mtime=0))
        for label, budget in (('header', 1), ('footer', complete_size-1)):
            with self.subTest(label=label):
                artifacts = Artifacts(self.root, self.root/label, maximum_bytes=budget)
                with self.assertRaisesRegex(ScanError, 'ARTIFACT_BYTE_BUDGET'):
                    with artifacts.stream(metadata=True) as (append, _):
                        append(row)
                paths = list((self.root/label).iterdir())
                self.assertEqual(len(paths), 1)
                self.assertEqual(artifacts.records, [])
                self.assertEqual(artifacts.total, paths[0].stat().st_size)
                self.assertLessEqual(artifacts.total, budget)
                with self.assertRaises(ScanError):
                    list(records(paths[0]))

    def test_compressed_reader_rejects_damaged_members_and_decoded_limits(self):
        decoded = b'{"actual":true}\n'
        good = gzip.compress(decoded, mtime=0)
        crc_bad = bytearray(good)
        crc_bad[-8] ^= 1
        for label, data in [('crc', bytes(crc_bad)), ('truncated', good[:-1]),
                            ('second-member', good+good), ('trailing', good+b'garbage'),
                            ('line', gzip.compress(b'x'*65537+b'\n', mtime=0))]:
            with self.subTest(label=label):
                path = self.root/(label+'.jsonl.gz')
                path.write_bytes(data)
                with self.assertRaises(ScanError):
                    list(records(path))
        path = self.root/'good.jsonl.gz'
        path.write_bytes(good)
        with patch('canonical_metadata.MAX_DECODED_BYTES', len(decoded)-1):
            with self.assertRaisesRegex(ScanError, 'DECODED_BYTE_LIMIT'):
                list(records(path))
        with patch('canonical_metadata.MAX_RECORDS', 0):
            with self.assertRaisesRegex(ScanError, 'RECORD_LIMIT'):
                list(records(path))
        self.assertEqual(list(records(path)), [{'actual': True}])

    def test_sensitive_decoded_metadata_is_rejected_before_compression(self):
        artifacts = Artifacts(self.root, self.root/'sensitive')
        artifacts.set_sensitive_values(('private-test-token',))
        with self.assertRaisesRegex(ScanError, 'SENSITIVE_SOURCE_ARTIFACT_REJECTED'):
            with artifacts.stream(metadata=True) as (append, _):
                append({'echo': 'private-test-token'})
        self.assertEqual(artifacts.records, [])
        path = next((self.root/'sensitive').iterdir())
        self.assertNotIn(b'private-test-token', gzip.decompress(path.read_bytes()))


if __name__ == '__main__':
    unittest.main()

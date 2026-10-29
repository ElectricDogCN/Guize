"""Real Windows unit HTTP/handle chain; no actual OpenList/scale qualification."""
import copy
import json
import os
import shutil
import socket
import unittest
from unittest import mock
from datetime import datetime,timedelta,timezone
from pathlib import Path

import jsonschema
import yaml
import test_controlled_source_run as fixtures
import test_windows_scan as windows_fixtures
import windows_source_files as windows_files
from canonical_metadata import CanonicalPair
from controlled_source_run import Artifacts,WindowsSourceSession,original13_reports,source_build
from metadata_scan import ScanError,file_sha256
from native_scan_protocol import Clock,read_json
from run_source_experiment import reserve_windows_config
from windows_native import identity


class WindowsSourceTests(unittest.TestCase):
    setUp=fixtures.SourceTests.setUp
    gateway=fixtures.SourceTests.gateway
    align_times=staticmethod(fixtures.SourceTests.align_times)

    def supported(self):
        if os.name=='nt': return True
        with self.assertRaisesRegex(ScanError,'WINDOWS_SOURCE_EXPERIMENT_REQUIRED'):
            reserve_windows_config({})
        with self.assertRaisesRegex(ScanError,'NATIVE_CONTROLLED_MUTATION_REQUIRES_WINDOWS'):
            WindowsSourceSession.mutation(None,{},None)
        return False

    def session(self,native=None):
        gateway,listing,dav,window=self.gateway()
        root=native.root if native else self.root
        baseline=native.cfg['baseline']['ref'] if native else self.baseline
        profiled=native.cfg['profiled']['ref'] if native else self.profiled
        source_id=native.cfg['sourceId'] if native else 'unit-source'
        pair=CanonicalPair(baseline,profiled,baseline_sha256=file_sha256(baseline),profiled_sha256=file_sha256(profiled),
            source_id=source_id,snapshot_version='v1',page_size=2)
        artifacts=Artifacts(root,root/'windows-source-observations')
        source_identity=dict(adapterId='controlled-unit-gateway',adapterBuild=source_build(),sourceId=source_id,
            sourceVersion='unit-http-not-openlist')
        session=WindowsSourceSession(pair,listing,dav,artifacts,identity=source_identity,window=window,local_root=self.source,per_page=2)
        self.addCleanup(session.close)
        return gateway,session

    def test_rejected_payload_and_failed_confirmation_preserve_actual_dirty_state_without_event(self):
        if not self.supported(): return
        _,session=self.session()
        row=next(row for row in self.rows if row['kind']=='file' and row['fileSizeBytes']==4096)
        with self.assertRaisesRegex(ScanError,'BEFORE_PAYLOAD'):
            session.mutation(dict(eventId='bad',operation='update',objectId=row['objectId'],path=row['path'],
                beforeVersion='v1',afterVersion='v2',beforeSha256='sha256:'+'0'*64),Clock())
        self.assertEqual((self.source/row['path']).read_bytes(),b'x'*4096)
        payload=session.artifacts.bytes(b'created',kind='produced_media')
        self.hide_name='created.bin'
        with self.assertRaisesRegex(ScanError,'WRITE_NOT_OBSERVED'):
            session.mutation(dict(eventId='create',operation='create',objectId='created',path='created.bin',
                beforeVersion='absent',afterVersion='v1',payloadRef=payload['ref'],payloadSha256=payload['sha256'],
                modifiedAt='2026-01-01T00:00:02Z'),Clock())
        self.assertEqual((self.source/'created.bin').read_bytes(),b'created')
        receipts=[read_json(row['ref'])[0] for row in session.artifacts.records if row['ref'].endswith('.json')]
        self.assertTrue(any(row.get('outcome')=='failed' and row.get('filesystemMutated') for row in receipts))
        self.assertFalse(any(row.get('kind')=='controlled_source_change_observation' for row in receipts))
        self.assertEqual(session.sequence,0)
        self.assertEqual(session.mapper.db.execute('SELECT count(*) FROM mutation_versions').fetchone()[0],0)

    def test_actual_native_source_chain_assembles_original13_with_windows_counters_and_real_changes(self):
        if not self.supported(): return
        native=windows_fixtures.WindowsLifecycleTests('test_actual_windows_lifetime_counters_replay_post_catalogue_and_frozen_captures')
        native.setUp();self.addCleanup(native.doCleanups)
        def compressed_exports(cfg):
            for key in ('objects','filenameObjects','enumeratedVersions'):
                cfg['outputs'][key]+='.gz'
        run=native.prepare(alter_config=compressed_exports);self.source=native.source
        self.align_times(self.source,native.rows)
        native.release()
        gateway,session=self.session(native)
        artifacts=session.artifacts
        run.memory();session.repeated_listings();session.exercise_faults(gateway);run.enumerate()
        probe=next(row for row in native.rows if row['kind']=='file' and row['fileSizeBytes']==4096)
        for case in ('unchanged_first','unchanged_second','bounded','unsatisfiable'):
            session.probe(case,probe['objectId'],'v1',probe['path'],size=4096)
        run.begin_changes()
        delete=next(row for row in native.rows if row['kind']=='file' and row['fileSizeBytes']==0)
        for number,operation,row,content in ((1,'create',dict(objectId='created',path='created.bin'),b'created'),
                (2,'update',probe,b'changed'),(3,'delete',delete,None)):
            intent=dict(eventId='actual-event-'+str(number),operation=operation,objectId=row['objectId'],path=row['path'],
                beforeVersion='absent' if operation=='create' else 'v1',
                afterVersion='absent' if operation=='delete' else 'v2' if operation=='update' else 'v1')
            if operation!='create': intent['beforeSha256']='sha256:'+file_sha256(self.source/row['path'])
            if content is not None:
                payload=artifacts.bytes(content,kind='produced_media')
                intent.update(payloadRef=payload['ref'],payloadSha256=payload['sha256'],modifiedAt='2026-01-01T00:00:02Z')
            observed=session.mutation(intent,run.clock)
            run.observe_change(observed['ref'],observed['sha256'])
        session.probe('changed',probe['objectId'],'v2',probe['path'],size=7)
        run.end_changes();run.incremental();run.post_catalogue();run.memory(final=True)
        facts=run.finish()
        quota=artifacts.json(dict(schemaVersion=1,kind='documented_source_quota',sourceIdentity=session.identity,
            requestLimit=gateway.request_limit,periodSeconds=gateway.period_seconds,
            resetSemantics='monotonic adapter fixed buckets',backoffStrategy='bounded retry',maximumBackoffSeconds=1,
            documentationRevision='unit-gateway-v1'))
        reports=original13_reports(run,facts,session,quota_ref=quota['ref'],quota_sha=quota['sha256'],
            extension_categories=['mp4','mkv','webm','mov'])
        schema=yaml.safe_load((Path(__file__).resolve().parents[2]/'specs/poc/program.schema.yaml').read_text(encoding='utf8'))['$defs']
        for key,definition in (('scan','metadataScanObservation'),('resources','metadataResourceObservation'),('profiling','metadataProfilingObservation')):
            jsonschema.Draft202012Validator(schema[definition],format_checker=jsonschema.FormatChecker()).validate(reports[key])
        self.assertEqual(len(reports['measurements']),13)
        self.assertEqual(reports['measurements']['file_count'],5)
        self.assertEqual(reports['measurements']['directory_count'],2)
        self.assertEqual(reports['resources']['counterFormat'],'windows_process_memory_counters')
        self.assertEqual(reports['measurements']['memory_peak'],facts['memorySamples'][-1]['peakResidentBytes']/(1024*1024))
        self.assertEqual(session.sequence,3)
        self.assertEqual(run.process.returncode,0)
        self.assertFalse(reports['qualificationAccepted'])
        negative=next(row for row in reports['profiling']['probes'] if row['case']=='unsatisfiable')
        self.assertEqual(Path(negative['responseRef']).read_bytes(),b'unit-original-negative-body\n')
        self.assertEqual(negative['etag'],'')

    def test_actual_create_followed_by_failed_identity_keeps_dirty_receipt_without_event(self):
        if not self.supported(): return
        _,session=self.session()
        payload=session.artifacts.bytes(b'approved',kind='produced_media')
        original=windows_files.check_handle
        def reject_created_leaf(handle,path,*,directory):
            if not directory:
                raise windows_files.WindowsFileError('NATIVE_FILE_IDENTITY_REQUIRED')
            return original(handle,path,directory=directory)
        with mock.patch.object(windows_files,'check_handle',side_effect=reject_created_leaf):
            with self.assertRaisesRegex(ScanError,'NATIVE_FILE_IDENTITY_REQUIRED'):
                session.mutation(dict(eventId='create',operation='create',objectId='created',path='created.bin',
                    beforeVersion='absent',afterVersion='v1',payloadRef=payload['ref'],payloadSha256=payload['sha256'],
                    modifiedAt='2026-01-01T00:00:02Z'),Clock())
        self.assertEqual((self.source/'created.bin').read_bytes(),b'')
        receipts=[read_json(row['ref'])[0] for row in session.artifacts.records if row['ref'].endswith('.json')]
        failed=[row for row in receipts if row.get('kind')=='controlled_local_mutation']
        self.assertEqual(len(failed),1)
        self.assertTrue(failed[0]['filesystemMutated'])
        self.assertEqual(failed[0]['outcome'],'failed')
        self.assertEqual(failed[0]['error'],'NATIVE_FILE_IDENTITY_REQUIRED')
        self.assertFalse(any(row.get('kind')=='controlled_source_change_observation' for row in receipts))
        self.assertEqual(session.sequence,0)
        self.assertEqual(session.mapper.db.execute('SELECT count(*) FROM mutation_versions').fetchone()[0],0)

    def test_concrete_reservation_binds_actual_suspended_image_and_policy_before_source_access(self):
        if not self.supported(): return
        native=windows_fixtures.WindowsLifecycleTests('test_actual_windows_lifetime_counters_replay_post_catalogue_and_frozen_captures')
        native.setUp();self.addCleanup(native.doCleanups)
        native.prepare().close()
        root=native.root/'concrete';root.mkdir()
        def relocate(value):
            if isinstance(value,dict): return {key:relocate(item) for key,item in value.items()}
            if isinstance(value,list): return [relocate(item) for item in value]
            return value.replace(str(native.root),str(root)) if isinstance(value,str) else value
        cfg=relocate(copy.deepcopy(native.cfg))
        for name in ('baseline.jsonl','profiled.jsonl'): shutil.copyfile(native.root/name,root/name)
        refs={key:str(root/name) for key,name in dict(resourceConfiguration='resource.json',runtimeConfiguration='config.json',
            manifest='manifest.json',stdout='scanner.stdout',stderr='scanner.stderr',approvalRequest='request.json',processIdentity='identity.json').items()}
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1',0));port=candidate.getsockname()[1]
        source_identity=dict(adapterId='controlled-unit-gateway',adapterBuild=source_build(),sourceId=cfg['sourceId'],
            sourceVersion='unit-http-not-openlist')
        cfg['sourceRun']=dict(identity=source_identity,upstreamIdentity=identity(os.getpid()),
            origin='http://127.0.0.1:'+str(self.server.server_port),scope='fixture',gatewayPort=port,
            quotaRef=str(root/'quota.json'),quotaSha256='sha256:'+'1'*64)
        draft=dict(runtimeConfig=cfg,resourceConfiguration=dict(configuration=dict(metadataScanPolicy={},metadataResourcePolicy={},
            metadataProfilingPolicy={})),refs=refs,unitFixtureOnly=True,approvalRef=str(root/'not-created-approval.json'),
            reservationDeadline=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat())
        run,actual,request=reserve_windows_config(draft);self.addCleanup(run.close)
        self.assertEqual(request['reservation'],identity(run.process.pid))
        self.assertEqual(read_json(refs['processIdentity'])[0],request['reservation'])
        self.assertEqual(request['runtimeConfigSha256'],'sha256:'+file_sha256(refs['runtimeConfiguration']))
        self.assertEqual(request['configurationSha256'],'sha256:'+file_sha256(refs['resourceConfiguration']))
        configuration=read_json(refs['resourceConfiguration'])[0]['configuration']
        self.assertEqual(configuration['metadataScanPolicy']['nativeProcessId'],run.process.pid)
        self.assertEqual(configuration['metadataResourcePolicy']['collectorCommandArgs'],actual['memoryCollectorCommandArgs'])
        self.assertEqual(configuration['metadataResourcePolicy']['counterFormat'],'windows_process_memory_counters')
        self.assertEqual(configuration['metadataProfilingPolicy']['endpointURL'],'http://127.0.0.1:'+str(port)+'/api/fs/list')
        self.assertFalse(run.process.resumed)
        self.assertIsNone(run.process.poll())
        self.assertEqual(self.requests,[])
        self.assertFalse(Path(draft['approvalRef']).exists())
        self.assertTrue(all(not Path(ref).exists() for ref in actual['outputs'].values()))


if __name__=='__main__': unittest.main()

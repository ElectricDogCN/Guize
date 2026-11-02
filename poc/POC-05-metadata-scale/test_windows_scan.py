"""Actual Windows counterparts of the unchanged native phase and failure contracts."""
import copy
import json
import os
import subprocess
import sys
import time
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

import jsonschema
import yaml
import test_native_scan as fixtures
from canonical_metadata import generate_canonical
from metadata_scan import ScanError,file_sha256
from native_scan_protocol import read_json,utc,write_json
from windows_native import identity
from windows_scan_control import WindowsNativeRun,windows_manifest_for


class WindowsLifecycleTests(unittest.TestCase):
    setUp=fixtures.NativeLifecycleTests.setUp
    release=fixtures.NativeLifecycleTests.release
    observation=fixtures.NativeLifecycleTests.observation
    until_incremental=fixtures.NativeLifecycleTests.until_incremental

    def supported(self):
        if os.name=='nt':
            return True
        with self.assertRaisesRegex(ScanError,'WINDOWS_NATIVE_RUNTIME_REQUIRED'):
            WindowsNativeRun('not-read','not-read',trace_ref='not-created',stderr_ref='not-created')
        return False

    def prepare(self,alter_config=None,alter_manifest=None):
        def ref(name):
            return str(self.root/name)
        baseline,profiled=self.root/'baseline.jsonl',self.root/'profiled.jsonl'
        generate_canonical(baseline,profiled,file_count=5,directory_count=2,maximum_depth=2,seed=4)
        self.rows=[json.loads(row) for row in profiled.read_bytes().splitlines()]
        self.source=self.root/'unit-source';self.source.mkdir()
        for row in self.rows:
            path=self.source/row['path']
            if row['kind']=='directory':
                path.mkdir(parents=True,exist_ok=True)
            else:
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'x'*row['fileSizeBytes'])
        resource=ref('resource.json')
        resource_sha=write_json(resource,dict(unitFixtureOnly=True,productionClaim=False))
        build='unit-windows-native-v1'
        cfg=dict(executor='unit-executor',artifactRoot=str(self.root),
            context=dict(configurationRef=resource,acceptanceProfile=dict(unitFixtureOnly=True),subjectVersion=build,
                scannerBuild=build,manifestId='unit-inputs',inputSamples=[dict(id='unit',immutableId='unit-v1',checksum='sha256:'+file_sha256(baseline))]),
            scanId='unit-scan',changeSetId='unit-changes',sourceId='unit-controlled-source',snapshotVersion='unit-v1',pageSize=2,
            baseline=dict(ref=str(baseline),sha256='sha256:'+file_sha256(baseline)),
            profiled=dict(ref=str(profiled),sha256='sha256:'+file_sha256(profiled)),database=ref('index.sqlite'),
            outputs={key:ref(key+'.jsonl') for key in ('objects','filenameObjects','enumeratedVersions','events','appliedEvents','traversedObjects','postScanObjects')},
            readyReceipt=ref('ready.json'),postReceipt=ref('post.json'),postStderr=ref('post.stderr'),phaseFacts=ref('phase-facts.json'),
            phaseCaptures={key:ref(key+'.json') for key in ('enumeration','changeStream','incremental')},
            phaseStderr={key:ref(key+'.stderr') for key in ('enumeration','changeStream','incremental')},
            counterCollectorBuild='sha256:'+file_sha256(self.here/'windows_native.py'),
            memory={tag:{key:ref(tag+'-'+key) for key in ('counter','stdout','stderr','capture')} for tag in ('before','after')},
            processId='unit-windows-scanner',counterFormat='windows_process_memory_counters',
            timingCollectorBuild='sha256:'+file_sha256(self.here/'native_scan_control.py'))
        cfg['timingCollectorCommandArgs']=[sys.executable,'-B',str(self.here/'native_scan_control.py'),'phase','--facts',cfg['phaseFacts']]
        if alter_config:
            alter_config(cfg)
        config_ref,manifest_ref=ref('config.json'),ref('manifest.json')
        manifest=windows_manifest_for(config_ref,cfg,(datetime.now(timezone.utc)+timedelta(seconds=90)).isoformat(),identity_ref=ref('identity.json'))
        if alter_manifest:
            alter_manifest(manifest)
        manifest_sha=write_json(manifest_ref,manifest)
        run=WindowsNativeRun(manifest_ref,manifest_sha,trace_ref=ref('scanner.stdout'),stderr_ref=ref('scanner.stderr'))
        self.addCleanup(run.close)
        cfg['memoryCollectorCommandArgs']=[sys.executable,'-B',str(self.here/'windows_native.py'),
            '--expected',manifest['processIdentityRef'],'--expected-sha256',run.identity_sha]
        config_sha=write_json(config_ref,cfg)
        at=datetime.now(timezone.utc);begin=at+timedelta(milliseconds=50)
        self.approval=dict(decision='approved',reviewer='unit-independent-reviewer',manifestSha256=manifest_sha,
            runtimeConfigRef=config_ref,runtimeConfigSha256=config_sha,configurationRef=resource,configurationSha256=resource_sha,
            reservation=run.reservation['identity'],reservationAt=run.reservation['reservedAt'],approvedAt=at.isoformat(),
            windowStart=begin.isoformat(),windowEnd=(begin+timedelta(seconds=60)).isoformat())
        self.cfg,self.run=cfg,run
        return run

    # Identical failure assertions and actual process waits, exercised on the new
    # backend. Linux-specific exec/proc claims are covered by its original class.
    test_reservation_rejects_self_approval_wrong_pid_and_past_window=fixtures.NativeLifecycleTests.test_reservation_rejects_self_approval_wrong_pid_and_past_window
    test_scanner_requires_first_independent_counter_and_new_outputs=fixtures.NativeLifecycleTests.test_scanner_requires_first_independent_counter_and_new_outputs
    test_expected_change_row_without_source_evidence_is_rejected=fixtures.NativeLifecycleTests.test_expected_change_row_without_source_evidence_is_rejected
    test_actual_change_with_missing_evidence_is_rejected=fixtures.NativeLifecycleTests.test_actual_change_with_missing_evidence_is_rejected
    test_final_counter_requires_post_catalogue_after_incremental=fixtures.NativeLifecycleTests.test_final_counter_requires_post_catalogue_after_incremental
    test_existing_output_fails_before_scanner_ready=fixtures.NativeLifecycleTests.test_existing_output_fails_before_scanner_ready
    test_changed_runtime_source_closure_rejects_reservation=fixtures.NativeLifecycleTests.test_changed_runtime_source_closure_rejects_reservation
    test_changed_input_after_release_fails_actual_enumeration=fixtures.NativeLifecycleTests.test_changed_input_after_release_fails_actual_enumeration
    test_timing_capture_refuses_nonzero_exit_or_rewritten_native_tick=fixtures.NativeLifecycleTests.test_timing_capture_refuses_nonzero_exit_or_rewritten_native_tick
    test_real_exit_observation_after_window_preserves_failure_without_success_captures=fixtures.NativeLifecycleTests.test_real_exit_observation_after_window_preserves_failure_without_success_captures

    def test_tampered_approval_config_terminates_exact_suspended_image_before_any_work(self):
        if not self.supported():
            return
        run=self.prepare()
        with Path(run.manifest['configRef']).open('ab') as out:
            out.write(b' ')
        with self.assertRaises(ScanError):
            self.release()
        self.assertFalse(run.process.resumed)
        self.assertNotEqual(run.process.wait(timeout=5),0)
        self.assertEqual(Path(self.root/'scanner.stdout').read_bytes(),b'')
        self.assertFalse(Path(self.cfg['database']).exists())

    def test_actual_windows_lifetime_counters_replay_post_catalogue_and_frozen_captures(self):
        if not self.supported():
            return
        run=self.prepare();pid=run.process.pid
        before=identity(pid)
        self.assertEqual(before,run.reservation['identity'])
        self.assertFalse(Path(self.cfg['database']).exists())
        self.release()
        self.assertEqual(identity(pid),before)
        self.assertEqual(run.handoff['kind'],'suspended_image_resumed')
        self.assertEqual(run.handoff['previousSuspendCount'],1)
        self.assertEqual(run.ready['processStart']['processId'],pid)
        self.assertEqual(run.ready['calibration']['clock'],'windows_qpc_ns')
        before_resume=run.handoff['resumeCallBefore']
        after_resume=run.handoff['resumeCallAfter']
        self.assertLessEqual(before_resume['afterNs'],after_resume['beforeNs'])
        self.assertGreaterEqual(run.ready['processStart']['monotonicNs'],before_resume['beforeNs'])
        changes=self.until_incremental()
        post=run.post_catalogue();run.memory(final=True);facts=run.finish()
        self.assertEqual(run.process.returncode,0)
        self.assertTrue(facts['exitObservedAfterWait'])
        self.assertNotEqual(facts['observerProcessId'],pid)
        self.assertNotEqual(post['collectorProcessId'],pid)
        schema=yaml.safe_load((self.here.parents[1]/'specs/poc/program.schema.yaml').read_text(encoding='utf8'))
        for name in ('enumeration','changeStream','incremental'):
            capture,_=read_json(self.cfg['phaseCaptures'][name])
            jsonschema.Draft202012Validator(schema['$defs']['metadataPhaseExecution'],format_checker=jsonschema.FormatChecker()).validate(capture)
            self.assertEqual(capture['argv'],run.manifest['argv'])
            self.assertEqual(capture['collectorCommandArgs'],self.cfg['timingCollectorCommandArgs']+['--phase',name])
            self.assertEqual([x['type'] for x in capture['events']],['process_start','phase_start','phase_exit','process_exit'])
            for event in capture['events']:
                self.assertEqual(event['processId'],pid)
                self.assertEqual(event['observedAt'],run.clock.mapped_utc(event['monotonicNs']))
            self.assertEqual(capture['events'][0]['monotonicNs'],facts['processStart']['monotonicNs'])
            self.assertEqual(capture['events'][-1]['monotonicNs'],facts['processExit']['monotonicNs'])
            elapsed=(utc(capture['events'][2]['observedAt'])-utc(capture['events'][1]['observedAt'])).total_seconds()
            ticks=(capture['events'][2]['monotonicNs']-capture['events'][1]['monotonicNs'])/1e9
            self.assertLessEqual(abs(elapsed-ticks),1e-6)
        for tag in ('before','after'):
            capture,_=read_json(self.cfg['memory'][tag]['capture'])
            jsonschema.Draft202012Validator(schema['$defs']['metadataMemoryCounterCapture'],format_checker=jsonschema.FormatChecker()).validate(capture)
            counter=json.loads(Path(capture['counterRef']).read_bytes())
            jsonschema.Draft202012Validator(schema['$defs']['metadataWindowsMemoryCounter']).validate(counter)
            sample=facts['memorySamples'][0 if tag=='before' else 1]
            self.assertEqual(counter['ProcessId'],pid)
            self.assertEqual(sample['peakResidentBytes'],counter['PeakWorkingSetSize'])
            self.assertNotEqual(capture['collectorProcessId'],pid)
        self.assertLessEqual(utc(facts['memorySamples'][0]['observedAt']),utc(facts['phases']['enumeration']['start']['observedAt']))
        self.assertLessEqual(utc(post['observedAt']),utc(facts['memorySamples'][1]['observedAt']))
        self.assertGreaterEqual(facts['memorySamples'][1]['peakResidentBytes'],facts['memorySamples'][0]['peakResidentBytes'])
        expected={row['objectId']:row['versionId'] for row in self.rows}
        for _,_,event,profile in changes:
            if profile:
                expected[event['objectId']]=event['afterVersion']
            else:
                expected.pop(event['objectId'])
        rows=lambda key:[json.loads(x) for x in Path(self.cfg['outputs'][key]).read_bytes().splitlines()]
        self.assertEqual({row['objectId']:row['versionId'] for row in rows('postScanObjects')},expected)
        self.assertEqual([row['eventId'] for row in rows('appliedEvents')],[row[2]['eventId'] for row in changes])
        self.assertEqual({row['objectId'] for row in rows('traversedObjects')},{row[2]['objectId'] for row in changes})
        self.assertEqual([row['observedAt'] for row in rows('events')],[read_json(row[0])[0]['observedAt'] for row in changes])
        physical=[(Path(ref).stat().st_dev,Path(ref).stat().st_ino) for ref in self.cfg['outputs'].values()]
        self.assertEqual(len(physical),len(set(physical)))


if __name__=='__main__':
    unittest.main()

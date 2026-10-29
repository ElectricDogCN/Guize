"""Synthetic closed-record/file regressions only; no native or media experiment."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from durable_peak_probe import parse_durable_peaks
from media_capacity import closed_request_peaks, complete_serial_native_epochs, conservative_total


def request_records():
    start='2026-10-29T07:00:00Z';end='2026-10-29T07:00:10Z'
    windows=[dict(listenerPort=port,closed=True,active=0,admitted=3,finished=3,peak=2,
                  startedAt=start,closedAt=end) for port in (18231,18233)]
    controller=dict(kind='CLOSED_CONTROLLER_REQUEST_WINDOW_NOT_AGGREGATE_MEMORY',closed=True,
        startedAt=start,closedAt=end,httpRequestWindows=windows,
        requestConcurrency=dict(kind='SYNCHRONOUS_REQUEST_INTERVAL_HIGH_WATER_NOT_MEMORY_SAMPLING',
                               activeOrigin=0,activeGateway=0,peakOrigin=2,peakGateway=2))
    collection=dict(requestConcurrency=dict(kind='SYNCHRONOUS_REQUEST_INTERVAL_HIGH_WATER_NOT_MEMORY_SAMPLING',
        admissionClosed=True,active=0,peak=2,closedAt=end),
        rows=[dict(startedAt=start,finishedAt=end) for _ in range(3)])
    return controller,collection


def native_records(root):
    """Write explicit synthetic counterparts of the actual producer's raw shapes."""
    pins={'/test/traffic_server':'a'*64}
    components={'/test/traffic_server':dict(sha256='a'*64,bytes=4,device=1,inode=2)}
    for number,peak in enumerate((7,11,77,13)):
        folder=root/'process-epochs'/('epoch-'+str(number))
        (folder/'launch').mkdir(parents=True);(folder/'finished').mkdir()
        pid=100+number;birth=dict(pid=pid,startTicks=1000+number);go=number*100+1
        rows=[]
        for seq,size in enumerate((0,peak)):
            rows.append(dict(kind='INSTRUMENTED_ATS_DURABLE_PEAK',schemaVersion=1,pid=pid,
                startTicks=birth['startTicks'],sequence=seq,abiVersion=1,generation=0,
                accountingWindow='process-lifetime',beforeMonotonicNs=go+10+seq,
                peakBytes=size,currentBytes=size,currentByKind=[size,0,0,0],
                acquisitions=[seq,0,0,0],releases=[0,0,0,0],violations=0,uncoveredExternalEvents=0))
        raw=b''.join((json.dumps(row)+'\n').encode() for row in rows)
        (folder/'finished/durable-peaks.raw').write_bytes(raw)
        parsed=parse_durable_peaks(raw,birth,finished=True,exit_code=0)
        parsed.update(waitCompleted=True,exitCode=0)
        command=['/test/traffic_server','--run-root=/test/work']
        command+=['-C','verify_config'] if number==0 else ['-C','clear_cache'] if number==2 else ['-n','2']
        launch=dict(state='completed',fixedSingleExecRequested=True,targetExecAttestedByNativeJournal=True,
            completeTrackedProcessEpoch=True,waitCompleted=True,exitCode=0,execErrorPipeClosedWithoutMessage=True,
            componentsBeforeExec=components,componentsAfterExit=components,
            singleExecHandoff=dict(grantAttempted=True,continueSent=True,listenerClosed=True),
            launchIdentity=birth,pid=pid,goMonotonicNs=go,journalSha256=hashlib.sha256(raw).hexdigest(),targetCommand=command)
        closure=dict(accepted=True,error=None,actualWaitCompleted=True,exitCode=0,pid=pid,
                     epochRef='process-epochs/epoch-'+str(number),trackedEpoch=parsed)
        (folder/'launch/launch.json').write_text(json.dumps(launch),encoding='utf-8')
        (folder/'closure.json').write_text(json.dumps(closure),encoding='utf-8')
    owner=dict(actualOwnerWaitCompleted=True,ownerExitCode=0,
        targetClosureSummary=dict(epochCount=4,closedEpochCount=4,acceptedCount=4,allAccepted=True,closureRoot='process-epochs'))
    return owner,pins


class MediaCapacityTests(unittest.TestCase):
    def test_closed_idle_counters_retain_completed_transient_peaks(self):
        controller,collection=request_records()
        self.assertEqual(closed_request_peaks(controller,collection),dict(origin=2,gateway=2,collector=2))
        for place in ('controller','HTTP','Collector'):
            with self.subTest(place=place):
                c=copy.deepcopy(controller);client=copy.deepcopy(collection)
                if place=='controller':c['closed']=False
                elif place=='HTTP':c['httpRequestWindows'][0]['finished']-=1
                else:client['requestConcurrency']['admissionClosed']=False
                with self.assertRaises(ValueError):closed_request_peaks(c,client)

    def test_request_peak_and_interval_must_fit_actual_closed_windows(self):
        controller,collection=request_records()
        for changed in ('peak','late','active','boolean'):
            with self.subTest(changed=changed):
                c=copy.deepcopy(controller);client=copy.deepcopy(collection)
                if changed=='peak':c['requestConcurrency']['peakOrigin']=3
                elif changed=='late':client['rows'][0]['finishedAt']='2026-10-29T07:00:11Z'
                elif changed=='active':client['requestConcurrency']['active']=1
                else:c['requestConcurrency']['peakOrigin']=True
                with self.assertRaises(ValueError):closed_request_peaks(c,client)

    def test_all_native_epochs_include_a_middle_helper_peak(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);owner,pins=native_records(root)
            row=complete_serial_native_epochs(root,owner,pins,expected_count=4)
            self.assertEqual(row['maximumTrackedCapacityBytes'],77)
            self.assertEqual([e['token'] for e in row['epochs']],['0','1','2','3'])

    def test_missing_native_epoch_and_empty_owner_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);owner,pins=native_records(root)
            with self.assertRaises(ValueError):complete_serial_native_epochs(root,owner,pins,expected_count=0)
            source=root/'process-epochs/epoch-2';target=root/'missing-helper'
            self.assertTrue(source.resolve().is_relative_to(root.resolve()))
            self.assertTrue(target.resolve().is_relative_to(root.resolve()))
            source.rename(target)
            with self.assertRaisesRegex(ValueError,'missing or extra'):complete_serial_native_epochs(root,owner,pins,expected_count=4)

    def test_actual_wait_and_native_component_replacement_are_rejected(self):
        for changed in ('owner','wait','component'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);owner,pins=native_records(root)
                if changed=='owner':owner['actualOwnerWaitCompleted']=False
                elif changed=='wait':
                    path=root/'process-epochs/epoch-1/closure.json';row=json.loads(path.read_text());row['actualWaitCompleted']=False;path.write_text(json.dumps(row))
                else:
                    path=root/'process-epochs/epoch-2/launch/launch.json';row=json.loads(path.read_text());row['componentsAfterExit']['/test/traffic_server']['inode']=3;path.write_text(json.dumps(row))
                with self.assertRaises(ValueError):complete_serial_native_epochs(root,owner,pins,expected_count=4)

    def test_raw_peak_tampering_and_truncation_are_not_aggregate_success(self):
        for changed in ('tamper','truncate'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);owner,pins=native_records(root)
                path=root/'process-epochs/epoch-2/finished/durable-peaks.raw';raw=path.read_bytes()
                path.write_bytes(raw[:-1] if changed=='truncate' else raw.replace(b'77',b'78'))
                with self.assertRaises(ValueError):complete_serial_native_epochs(root,owner,pins,expected_count=4)

    def test_all_owner_terms_add_and_separate_revocation_reader_is_charged(self):
        peers=dict(origin=2,gateway=2,collector=2)
        row=conservative_total(peers,5246976)
        self.assertEqual(row['terms'],dict(native=5246976,origin=147458,gateway=819220,
            collector=1064984,synchronousPhase=1048577,hash=28672))
        extra=conservative_total(peers,5246976,external_revocation_readers=1)
        self.assertEqual(extra['maximumBufferedBytes']-row['maximumBufferedBytes'],532492+4096)
        self.assertFalse(row['independentAggregateAccepted'])
        self.assertFalse(row['formalPocAccepted'])
        with self.assertRaises(ValueError):conservative_total(peers,5246976,external_revocation_readers=2)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MediaCapacityTests))
    if result.testsRun!=7 or result.skipped:raise SystemExit('Expected seven synthetic closed-record tests without skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)

"""Offline control/provenance regressions only; no real ATS/POC acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from cache_probe import select_export_keys
from collect import Collector
from lab import context

SLICE=1048576

class NativeSelectionTests(unittest.TestCase):
    def cfg(self):
        return dict(aclVersion='unit-acl',sliceBytes=SLICE,inputs={'base':dict(sizeBytes=4*SLICE)})
    def key(self,index,start,user='alice'):
        return dict(keyId=index,lookupUrl='http://127.0.0.1:18231/ctx/'+context('unit-acl',user)+'/base/object.bin-bytes='+str(start)+'-'+str(start+SLICE-1))
    def test_target_read_uses_only_the_observed_same_context_key(self):
        rows=[self.key(1,0),self.key(2,SLICE),self.key(3,0,'bob')]
        self.assertEqual([r['keyId'] for r in select_export_keys(rows,self.cfg(),'base','alice',(0,SLICE-1))],[1])
        self.assertEqual([r['keyId'] for r in select_export_keys(rows,self.cfg(),'base','bob',(0,SLICE-1))],[3])
        self.assertEqual([r['keyId'] for r in select_export_keys(rows,self.cfg(),'base','alice')],[1,2])
    def test_missing_native_key_is_not_constructed_from_requested_range(self):
        self.assertEqual(select_export_keys([self.key(1,0)],self.cfg(),'base','alice',(SLICE,2*SLICE-1)),[])
    def test_arbitrary_or_multiple_slice_read_selection_is_rejected(self):
        for selected in [(1,SLICE),(0,2*SLICE-1),[0,SLICE-1],(True,SLICE-1)]:
            with self.subTest(selected=selected),self.assertRaisesRegex(ValueError,'one exact'):
                select_export_keys([self.key(1,0)],self.cfg(),'base','alice',selected)

class ReadabilityObservationTests(unittest.TestCase):
    def setup(self,root):
        c=object.__new__(Collector);c.run=root/'run';c.out=root/'out';(c.out/'observations').mkdir(parents=True)
        c.cfg=dict(aclVersion='unit-acl',sliceBytes=SLICE,liveBufferObserver={'synthetic':True},
            inputs={'base':dict(sizeBytes=4*SLICE,sha256='a'*64,etag='"unit"')})
        c.lock=threading.Lock();c.readability_observations=[];c.save=lambda:None
        row=dict(requestId='1'*32,startedAt='2026-11-02T00:00:00Z',finishedAt='2026-11-02T00:00:01Z',
            sourceVersion='base',sourceSha256='a'*64,userId='alice',aclVersion='unit-acl',requestRange='bytes=0-7',
            ifRange='',bodyBytes=8,statusCode=206,transportCompleted=True,sourceIntervalComparison={'actualBytesEqual':True},
            originPollingSettled=True,originObservation={'gatewayTransactions':[dict(cacheContextPath='/ctx/'+context('unit-acl','alice')+'/base/object.bin',finishedAt='2026-11-02T00:00:01Z')]})
        snap=dict(atsPid=42,sourceVersion='base',originRequestCount=1,originObjectReadBytes=SLICE,activeOriginRequests=0,activeGatewayRequests=0)
        c.control=lambda action,**kw:dict(snap,stage=kw['stage'])
        return c,row,snap
    def report(self):
        key=dict(keyId=1,start=0,end=SLICE-1,lookupUrl='unit-observed-native-key')
        return dict(atsPid=42,sourceVersion='base',selectedKeys=[key],exports=[dict(keyId=1,lookupUrl=key['lookupUrl'],status='exported',exactInputSliceEqual=True,reportedObjectBytes=SLICE,exportedBytes=SLICE,actualBytes=SLICE)],
            nativeRequests=[{'requestId':'unit-native'}],nativeExportFinished=True,originJournalUnchangedDuringExport=True,completeLogicalObjectVerified=False)
    def test_export_metadata_is_separate_and_preserves_http_timing_and_record(self):
        with tempfile.TemporaryDirectory() as d:
            c,row,_=self.setup(Path(d));original=copy.deepcopy(row)
            with patch('cache_probe.export_stage',return_value=self.report()) as export:
                result=c.capture_readability(row)
            self.assertTrue(result['readableSliceVerified']);self.assertFalse(result['logicalWholeObjectVerified'])
            self.assertEqual(export.call_args.kwargs,dict(user='alice',requested_slice=(0,SLICE-1)))
            self.assertEqual(row,original)
            saved=json.loads((c.out/'observations'/('cache-readability-'+row['requestId']+'.json')).read_text())
            self.assertEqual(saved['originalRequestFinishedAt'],row['finishedAt'])
            self.assertEqual(c.readability_observations[0]['requestId'],row['requestId'])
    def test_missing_short_or_failed_native_read_is_never_promoted(self):
        for kind in ('no-key','no-doc','short'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                c,row,_=self.setup(Path(d));r=self.report()
                if kind=='no-key':r.update(selectedKeys=[],exports=[],nativeRequests=[])
                elif kind=='no-doc':r['exports'][0].update(status='open_read_failed',exactInputSliceEqual=False)
                else:r['exports'][0]['actualBytes']=SLICE-1
                with patch('cache_probe.export_stage',return_value=r):result=c.capture_readability(row)
                self.assertFalse(result['readableSliceVerified']);self.assertFalse(result['formalPocAccepted'])
    def test_origin_activity_or_epoch_change_invalidates_readability_binding(self):
        for key,value in [('originRequestCount',2),('atsPid',43)]:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as d:
                c,row,snap=self.setup(Path(d));calls=[]
                def control(action,**kw):
                    value_row=dict(snap,stage=kw['stage']);calls.append(kw['stage'])
                    if len(calls)==2:value_row[key]=value
                    return value_row
                c.control=control
                with patch('cache_probe.export_stage',return_value=self.report()):result=c.capture_readability(row)
                self.assertFalse(result['readableSliceVerified'])
    def test_incomplete_or_wrong_identity_response_does_not_trigger_native_read(self):
        for change in [dict(statusCode=503),dict(bodyBytes=4),dict(transportCompleted=False),dict(aclVersion='other'),dict(sourceSha256='b'*64)]:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
                c,row,_=self.setup(Path(d));row.update(change);original=copy.deepcopy(row)
                with patch('cache_probe.export_stage') as export:result=c.capture_readability(row)
                export.assert_not_called();self.assertEqual(row,original);self.assertFalse(result['readableSliceVerified'])
    def test_native_failure_is_retained_and_propagated(self):
        with tempfile.TemporaryDirectory() as d:
            c,row,_=self.setup(Path(d))
            with patch('cache_probe.export_stage',side_effect=TimeoutError('synthetic native deadline')):
                with self.assertRaisesRegex(TimeoutError,'synthetic'):c.capture_readability(row)
            saved=json.loads((c.out/'observations'/('cache-readability-'+row['requestId']+'.json')).read_text())
            self.assertEqual(saved['errorType'],'TimeoutError');self.assertFalse(saved['readableSliceVerified'])
            self.assertTrue(saved['nativeExportInvoked']);self.assertIsNone(saved['nativeReadAttempted'])
            self.assertEqual(saved['exportOutputDirectory'],'cache-readability-'+row['requestId'])
    def test_invalid_request_identity_cannot_escape_sidecar_directory(self):
        with tempfile.TemporaryDirectory() as d:
            c,row,_=self.setup(Path(d));row['requestId']='../escape'
            with patch('cache_probe.export_stage') as export,self.assertRaisesRegex(ValueError,'identity'):
                c.capture_readability(row)
            export.assert_not_called();self.assertEqual(list((c.out/'observations').iterdir()),[])
    def test_hook_occurs_only_after_target_response_and_never_adds_media_requests(self):
        c=object.__new__(Collector);c.lock=threading.Lock();c.request_active=c.request_peak=0;c.request_admission_closed=False;c.cfg={'liveBufferObserver':{}}
        events=[];row={}
        def response(*a):events.append('response-finished');return row
        c._request=response;c.capture_readability=lambda r:events.append('native-proof')
        for name in ('miss','other_user','latency_cold','latency_slow','hit','latency_multi','slice'):
            events.clear();self.assertIs(c.request(name),row)
            self.assertEqual(events,['response-finished','native-proof'] if name in ('miss','other_user','latency_cold','latency_slow') else ['response-finished'])
            self.assertEqual(c.request_active,0)

if __name__=='__main__':unittest.main(verbosity=2)

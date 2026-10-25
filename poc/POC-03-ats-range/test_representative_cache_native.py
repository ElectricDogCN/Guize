"""Real large-file export/assembly regression with a simulated native producer.

This runs no ATS, HTTP, source scan or formal POC experiment.
"""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cache_probe
from test_representative_cache import SLICE,catalogue,configuration

class LargeNativeExportTests(unittest.TestCase):
    def budget_rejection(self,events,prior_rows,message):
        with tempfile.TemporaryDirectory(prefix='guize-export-quota-') as tmp:
            root=Path(tmp);run=root/'run';native=run/'cache-observer/cache-export-12345'
            native.mkdir(parents=True,mode=0o700)
            for row in events:
                if row['event']=='request_accepted':
                    (native/('request-'+row['requestId'])).mkdir(mode=0o700)
            rows=catalogue(129*SLICE)
            def journal(path):
                if path.name=='lookups.jsonl':return b'fixture-catalogue\n',rows
                if path.name=='events.jsonl':return b'fixture-events\n',events
                if path.name=='results.jsonl':return b'fixture-prior-results\n',prior_rows
                raise AssertionError(path)
            snapshot=dict(atsPid=12345,stage='offline-quota',activeOriginRequests=0,activeGatewayRequests=0)
            with patch.object(cache_probe,'journal',side_effect=journal),patch.object(cache_probe,'rename_noreplace') as publish,patch.object(cache_probe.time,'sleep'):
                with self.assertRaisesRegex(ValueError,message):
                    cache_probe.export_stage(run,root/'out',configuration(129*SLICE),snapshot,'base',user='alice')
                publish.assert_not_called()
            self.assertTrue((root/'out/stage.failed.json').is_file())

    def test_exhausted_native_job_budget_refuses_before_publication(self):
        events=[]
        for index in range(8):
            events.extend([dict(event='request_accepted',requestId='old'+str(index)),dict(event='request_finished')])
        self.budget_rejection(events,[],'request/control budget')

    def test_exhausted_native_control_budget_refuses_before_publication(self):
        self.budget_rejection([dict(event='request_rejected') for _ in range(16)],[],'request/control budget')

    def test_insufficient_native_byte_budget_refuses_before_publication(self):
        events=[dict(event='request_accepted',requestId='old'),dict(event='request_finished')]
        self.budget_rejection(events,[dict(exportedBytes=64<<20) for _ in range(7)],'export byte budget')

    def test_129_real_slice_files_are_verified_and_assembled_without_trimming(self):
        if os.name!='posix' or os.geteuid()==0:
            self.fail('This filesystem regression requires ordinary-user native Linux')
        with tempfile.TemporaryDirectory(prefix='guize-representative-export-') as tmp:
            root=Path(tmp);run=root/'run';native=run/'cache-observer/cache-export-12345'
            native.mkdir(parents=True,mode=0o700)
            source=root/'source.bin';size=129*SLICE-17
            block=bytes(range(256))*(SLICE//256);sha=hashlib.sha256()
            with source.open('xb') as stream:
                remaining=size
                while remaining:
                    part=block[:min(remaining,SLICE)];stream.write(part);sha.update(part);remaining-=len(part)
            cfg=configuration(size);cfg['inputs']['base'].update(path=str(source),sha256=sha.hexdigest())
            rows=catalogue(size);produced={};events=[];batch_sizes=[]
            original_rename=cache_probe.rename_noreplace
            def simulated_producer(preparing,ready):
                requested=preparing.read_text().splitlines()
                ids=list(map(int,requested[1:]))
                if not 1<=len(ids)<=128 or len(ids)!=len(set(ids)):
                    raise ValueError('native RequestKeys128 boundary')
                if len(produced)>=8:raise ValueError('native RequestLimit8 boundary')
                original_rename(preparing,ready)
                request_id=ready.read_text().splitlines()[0]
                job=native/('request-'+request_id);job.mkdir(mode=0o700)
                ready.rename(job/'request.txt')
                batch_sizes.append(len(ids));results=[]
                with source.open('rb') as stream:
                    for key_id in ids:
                        key=rows[key_id-1];stream.seek((key_id-1)*SLICE)
                        content=stream.read(min(SLICE,size-stream.tell()))
                        name='key-'+str(key['keyId'])+'.body';(job/name).write_bytes(content)
                        results.append(dict(key,requestId=request_id,file=name,status='exported',
                                             reportedObjectBytes=len(content),exportedBytes=len(content)))
                produced[request_id]=results
                if sum(r['exportedBytes'] for job_rows in produced.values() for r in job_rows)>512<<20:
                    raise ValueError('native TotalLimit512MiB boundary')
                events.extend([dict(event='request_accepted',requestId=request_id,keys=len(ids)),dict(event='request_finished')])
                (job/'results.jsonl').write_bytes(b'fixture-producer-results\n')
            def journal(path):
                if path.name=='lookups.jsonl':return b'fixture-catalogue\n',rows
                if path.name=='events.jsonl':
                    return b'fixture-events\n',list(events)
                if path.name=='results.jsonl':return path.read_bytes(),produced[path.parent.name[len('request-'):]]
                raise AssertionError(path)
            invalid=native/'invalid129'
            invalid.write_text('invalid129\n'+''.join(str(row['keyId'])+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'RequestKeys128'):
                simulated_producer(invalid,native/'request.ready')
            snapshot=dict(atsPid=12345,stage='offline-large-export',activeOriginRequests=0,activeGatewayRequests=0)
            with patch.object(cache_probe,'journal',side_effect=journal),patch.object(cache_probe,'rename_noreplace',side_effect=simulated_producer),patch.object(cache_probe.time,'sleep'):
                report=cache_probe.export_stage(run,root/'out',cfg,snapshot,'base',user='alice')
            self.assertTrue(report['completeLogicalObjectVerified'])
            self.assertEqual(len(report['exports']),129)
            self.assertEqual(batch_sizes,[128,1])
            self.assertEqual([len(r['keyIds']) for r in report['nativeRequests']],[128,1])
            self.assertEqual(sum(r['actualBytes'] for r in report['exports']),size)
            assembled=root/'out'/report['derivedLogicalObject']['file']
            self.assertEqual(assembled.stat().st_size,size)
            actual=hashlib.sha256()
            with assembled.open('rb') as stream:
                while part:=stream.read(SLICE):actual.update(part)
            self.assertEqual(actual.hexdigest(),sha.hexdigest())
            self.assertFalse(report['derivedLogicalObject']['nativeSingleEntryClaimed'])

if __name__=='__main__':unittest.main(verbosity=2)

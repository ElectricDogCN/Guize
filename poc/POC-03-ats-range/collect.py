#!/usr/bin/env python3
"""Collect raw lab observations only. Does not approve samples or emit canonical PASS records."""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,http.client,json,os,threading,time,urllib.error,urllib.request,uuid
from pathlib import Path
from lab import CASES,PINNED,context,digest,interval,unique_json,utc,write_json

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('redirect refused')
class Collector:
    def __init__(self,run,out):
        self.run=Path(run).resolve();self.cfg=unique_json((self.run/'settings.private.json').read_text())
        self.out=Path(out).absolute()
        if self.out.exists() or self.out.is_symlink():raise ValueError('new output directory required')
        self.out.mkdir(mode=0o700);(self.out/'bodies').mkdir(mode=0o700);(self.out/'observations').mkdir(mode=0o700)
        self.entry=f"http://127.0.0.1:{self.cfg['entryPort']}";self.rows=[];self.controls=[];self.lock=threading.Lock()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        self.started=utc();self.monotonic=time.monotonic();self.total_bytes=0
        self.stages=[]
        self.receipt=dict(kind='RAW_POC003_LAB_COLLECTION_NOT_CANONICAL_EVIDENCE',startedAt=self.started,
          status='COLLECTING',approvalsIssuedByCollector=False,formalPocAccepted=False,canonicalRecordsGenerated=False,
          inputIdentities=self.cfg['inputs'],rows=self.rows,controls=self.controls,cacheStages=self.stages,
          cacheObjectExportImplemented=True)
    def save(self):
        # This is the collector's own current receipt, not an immutable formal record.
        data=json.dumps(self.receipt,ensure_ascii=False,indent=2)+'\n'
        with self.lock:(self.out/'collection.json').write_text(data)
    def control(self,action,**values):
        request=urllib.request.Request(self.entry+'/control',data=json.dumps(dict(action=action,**values)).encode(),
            headers={'X-Lab-Control':self.cfg['controlKey'],'Content-Type':'application/json'},method='POST')
        with self.opener.open(request,timeout=45) as response:
            raw=response.read(4194305)
            if len(raw)>4194304:raise ValueError('control observation byte bound')
        result=unique_json(raw.decode())
        with self.lock:self.controls.append(result);number=len(self.controls)
        name=f"{number:04d}-{action}.json";write_json(self.out/'observations'/name,result);return result
    def clear(self):
        # Only the controller's actual owned ATS child and runroot may be cleared.
        return self.control('clear-cache')
    def stage(self, name):
        # Run outside latency request intervals; explicit read-only native API only.
        from cache_probe import export_stage
        snapshot=self.control('snapshot',stage=name)
        output=self.out/('cache-stage-'+name)
        result=export_stage(self.run,output,self.cfg,snapshot,snapshot['sourceVersion'])
        after=self.control('snapshot',stage=name+'-after-export')
        result['controllerSnapshotBefore']=snapshot;result['controllerSnapshotAfter']=after
        result['originCountersUnchanged']=(snapshot['originRequestCount']==after['originRequestCount']
            and snapshot['originObjectReadBytes']==after['originObjectReadBytes']
            and after['activeOriginRequests']==0 and after['activeGatewayRequests']==0)
        if not result['originCountersUnchanged']:result['completeLogicalObjectVerified']=False
        write_json(output/'stage.json',result);self.stages.append(result);self.save();return result
    def request(self,case,user='lab-user-a',range_header='bytes=0-7',if_range='',version='base',barrier=None):
        if case not in CASES|{'prime','slice','bypass','revocation'}:raise ValueError('case')
        if time.monotonic()-self.monotonic>800:raise TimeoutError('collection deadline')
        rid=uuid.uuid4().hex;body=self.out/'bodies'/(case+'-'+rid+'.bin');row=dict(requestId=rid,case=case,userId=user,
          url=self.entry+'/media/object.bin',sourceVersion=version,sourceSha256=self.cfg['inputs'][version]['sha256'],
          aclVersion=self.cfg['aclVersion'],authorizationContext=context(self.cfg['aclVersion'],user),
          requestRange=range_header,ifRange=if_range,bodyRef=str(body.relative_to(self.out)),
          configuredOriginFault=None,collectorRetryCount=0,statusCode=None,responseHeaders=[],
          firstResponseByteAt=None,firstResponseByteLatencyMs=None,
          responseHeadersAt=None,firstBodyByteAt=None,firstBodyByteLatencyMs=None,
          firstBodyChunkAt=None,finishedAt=None,bodyBytes=0,clientChunkPeak=0,
          transportCompleted=False,originObservation=None)
        headers={'Authorization':'Bearer '+self.cfg['users'][user],'X-Lab-Request-ID':rid,'X-Lab-Case':case,
          'Accept-Encoding':'identity','Connection':'close'}
        if range_header:headers['Range']=range_header
        if if_range:headers['If-Range']=if_range
        if barrier:barrier.wait(timeout=10)
        row['startedAt']=utc();started=time.monotonic();response=None;block=None;hasher=hashlib.sha256()
        try:
            from http_timing import timing_handler
            request_opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),timing_handler(row,started))
            try:response=request_opener.open(urllib.request.Request(row['url'],headers=headers),timeout=35)
            except urllib.error.HTTPError as error:response=error
            row.update(statusCode=response.code,responseHeadersAt=utc(),responseHeaderLatencyMs=(time.monotonic()-started)*1000,
                       responseHeaders=list(response.headers.items()))
            with body.open('xb') as out:
                while True:
                    try:
                        incomplete=False
                        # Read exactly one body byte for the media first-byte clock;
                        # a completed64KiB read is not a first-byte observation.
                        try:block=response.read(1 if row['firstBodyByteAt'] is None else 65536)
                        except http.client.IncompleteRead as error:block=error.partial;incomplete=True
                        if not block:
                            row['transportCompleted']=not incomplete;break
                        if row['firstBodyByteAt'] is None:
                            row['firstBodyByteAt']=utc();row['firstBodyByteLatencyMs']=(time.monotonic()-started)*1000
                        if row['firstBodyChunkAt'] is None:row['firstBodyChunkAt']=utc()
                        row['bodyBytes']+=len(block);row['clientChunkPeak']=max(row['clientChunkPeak'],len(block));hasher.update(block);out.write(block)
                        if row['bodyBytes']>self.cfg['inputs'][version]['sizeBytes']+65536:raise ValueError('per-response byte bound')
                        if incomplete:row['transportError']='IncompleteRead';break
                    finally:block=None
            claimed=response.headers.get('Content-Length')
            if claimed is not None and (not claimed.isdigit() or int(claimed)!=row['bodyBytes']):row['transportCompleted']=False
        except (OSError,http.client.HTTPException,ValueError) as error:
            row['transportError']=type(error).__name__+': '+str(error)
            if not body.exists():body.write_bytes(b'')
        finally:
            block=None
            if response is not None:response.close()
            response=None
            row['finishedAt']=utc();row['elapsedMs']=(time.monotonic()-started)*1000;row['bodySha256']=hasher.hexdigest()
        # Preserve all settling observations; do not claim absence of later I/O.
        seen=[];stable=0;previous=None;deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            witness=self.control('witness',requestId=rid);seen.append(witness)
            fingerprint=(witness['originRequestCount'],witness['objectReadCount'],witness['objectReadBytes'])
            stable=stable+1 if fingerprint==previous and witness['activeOriginRequests']==0 else 0;previous=fingerprint
            if stable>=3:break
            time.sleep(.05)
        row['originObservation']=seen[-1] if seen else None;row['originPollingSettled']=stable>=3
        row['originPollingScope']='Only these timestamped snapshots; no assertion about unobserved later I/O.'
        source=self.cfg['inputs'][version]
        status,first,last=interval(range_header,source['sizeBytes'],if_range,source['etag'])
        if row['statusCode'] in (200,206) and row['transportCompleted']:
            expected=hashlib.sha256();remaining=last-first+1
            with Path(source['path']).open('rb') as stream:
                stream.seek(first)
                while remaining:
                    try:
                        chunk=stream.read(min(65536,remaining))
                        if not chunk:raise OSError('comparison input shortened')
                        expected.update(chunk);remaining-=len(chunk)
                    finally:chunk=None
            row['sourceIntervalComparison']=dict(expectedStatus=status,start=first,end=last,
              expectedBytes=last-first+1,expectedSha256=expected.hexdigest(),
              actualBytesEqual=row['bodyBytes']==last-first+1 and row['bodySha256']==expected.hexdigest())
        with self.lock:
            self.rows.append(row);self.total_bytes+=row['bodyBytes']
            if self.total_bytes>self.cfg.get('maximumCollectionBytes',1073741824):raise ValueError('collection byte budget')
        write_json(self.out/'observations'/('request-'+rid+'.json'),row);return row
    def matrix(self):
        for source in self.cfg['inputs'].values():
            if digest(source['path'])!=source['sha256']:raise ValueError('input pair changed')
        cfg=self.cfg;size=cfg['inputs']['base']['sizeBytes'];etag=cfg['inputs']['base']['etag']
        self.clear();self.control('version',version='base');self.control('fault',mode='none');self.stage('before')
        self.request('miss');self.clear();self.request('fill');self.request('hit')
        for case,header,condition in (
          ('range_start','bytes=0-7',''),('range_middle','bytes=8-15',''),
          ('range_end',f'bytes={size-8}-{size-1}',''),('suffix','bytes=-8',''),
          ('unsatisfiable',f'bytes={size}-{size+7}',''),('if_match','bytes=0-7',etag),
          ('if_stale','bytes=0-7','"stale-version"')):
            self.request(case,range_header=header,if_range=condition)
        self.request('other_user',user='lab-user-b')
        self.request('denied_user',user='lab-denied-user')
        self.request('stream',range_header='')
        self.stage('filled')
        # Actual returned fragments, not fabricated snapshots of ATS cache objects.
        for start in range(0,size,cfg['sliceBytes']):
            self.request('slice',range_header=f"bytes={start}-{min(size-1,start+cfg['sliceBytes']-1)}")
        self.clear();self.control('fault',mode='truncate')
        self.request('interrupted');self.stage('interrupted')
        self.control('fault',mode='unavailable');self.request('partial_read')
        self.control('fault',mode='none');self.request('recovered')
        self.request('prime',range_header='');self.stage('recovered')
        for _ in range(cfg['latencySampleCount']):self.request('latency_hot')
        for _ in range(cfg['latencySampleCount']):
            self.clear();self.request('latency_cold')
        for _ in range(cfg['latencySampleCount']):
            self.clear();self.control('fault',mode='slow');self.request('latency_slow');self.control('fault',mode='none')
        for user in ('lab-user-a','lab-user-b'):self.request('prime',user=user)
        for _ in range(cfg['latencySampleCount']//2):
            barrier=threading.Barrier(2)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(self.request,'latency_multi',user,'bytes=0-7','','base',barrier) for user in ('lab-user-a','lab-user-b')]
                for future in futures:future.result()
        self.control('version',version='changed');self.request('updated',version='changed')
        self.request('prime',range_header='',version='changed');self.stage('updated')
        self.clear();self.stage('cleanup')
        observed={row['case'] for row in self.rows}
        self.receipt.update(status='RAW_COLLECTION_COMPLETED_UNASSESSED',finishedAt=utc(),collectedCases=sorted(observed&CASES),
          missingCases=sorted(CASES-observed),totalResponseBodyBytes=self.total_bytes,
          limitations=['Native cache payload exports/derived logical object sidecars are raw observations, not formal lifecycle acceptance; open-read failure alone does not prove discard.',
                       'Header completion/first-body-chunk times are recorded separately; no invented socket first-byte timestamp.',
                       'Chunk high-water marks cover client/gateway only; ATS memory samples need actual interpretation.',
                       'Actual fault status/partial bytes/cache markers may differ from required outcomes; no PASS normalization.',
                       'Formal configuration/subject/sample approvals and canonical evidence assembly are not implemented.'])
        self.save()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True);parser.add_argument('--output-dir',required=True)
    parser.add_argument('--execute-raw-matrix',action='store_true',required=True)
    args=parser.parse_args();collector=Collector(args.run_dir,args.output_dir);collector.save()
    try:collector.matrix()
    except BaseException as error:
        collector.receipt.update(status='COLLECTION_STOPPED_RAW_PRESERVED',finishedAt=utc(),errorType=type(error).__name__,error=str(error));collector.save();raise
    print(json.dumps({k:collector.receipt[k] for k in ('status','collectedCases','missingCases','totalResponseBodyBytes')}))
if __name__=='__main__':main()

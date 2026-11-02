"""Reparse one completed H raw matrix; no target execution or POC qualification."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
T=Path(__file__).resolve().parent;P=Path('/home/sur/.cache/guize-takeover/poc003-common-main2e8655e-inputs-v1');D=Path('/home/sur/.cache/guize-takeover/poc003-common-main2e8655e-original-matrix-v1/data');W=D/'work';C=D/'original-matrix'
repo=Path('/home/sur/.cache/guize-takeover/poc003-pool-batch-pr182-main-seven-2e8655e')
sys.path.insert(0,str(repo/'poc/POC-03-ats-range'))
from media_capacity import complete_serial_native_epochs,closed_request_peaks,conservative_total
from lab import interval
read=lambda p:json.loads(Path(p).read_bytes())
sha=lambda b:hashlib.sha256(b).hexdigest()
cfg=read(W/'settings.private.json');collection=read(C/'collection.json');owner=read(W/'execution-owner-wait.json');closed=read(W/'media-request-window-closed.json')
manifest=read(P/'package-manifest.json');entries={e['path']:e for e in manifest['entries']}
assert manifest['source']=='2e8655e5b6d59261a4d1597d999dd7530875c1c7' and sha((P/'package-manifest.json').read_bytes())=='0ad22695ca2dba9b3c635ddbed73e8a75f8d6b54d104d53ecb0e369abe81e2f1'
for name,h in cfg['instrumentedRuntime']['components'].items():assert entries['runtime/pkgroot/'+name]['sha256']==h
required={str(Path(cfg['pkgroot'])/name):h for name,h in cfg['instrumentedRuntime']['components'].items()}
for name,row in cfg['plugins'].items():
 relative=Path(row['path']).relative_to('/poc').as_posix()
 assert entries[relative]['sha256']==row['sha256'];required[row['path']]=row['sha256']
required.update({str(Path('/runlab/work')/name):h for name,h in cfg['epochConfiguration'].items()})
for name in ('epoch_owner.py','instrumentation/single_exec_gate.py','instrumentation/single_exec_filter.py'):
 assert entries['source/poc/POC-03-ats-range/'+name]['sha256']==cfg['implementationSources'][name]
 required['/poc/source/poc/POC-03-ats-range/'+name]=cfg['implementationSources'][name]
required[cfg['executionInterpreter']['path']]=cfg['executionInterpreter']['sha256']
assert len(required)==18
native=complete_serial_native_epochs(W,owner,required,expected_count=26)
peaks=closed_request_peaks(closed,collection);total=conservative_total(peaks,native['maximumTrackedCapacityBytes'])
assert len(collection['rows'])==101 and len(collection['cacheStages'])==6 and len(collection['collectedCases'])==21 and not collection['missingCases']
body_proofs=[]
for r in collection['rows']:
 file=C/r['bodyRef'];body=file.read_bytes();assert len(body)==r['bodyBytes'] and sha(body)==r['bodySha256']
 source=cfg['inputs'][r['sourceVersion']];reference=P/Path(source['path']).relative_to('/poc')
 status,first,last=interval(r['requestRange'],source['sizeBytes'],r['ifRange'],source['etag'])
 if r['statusCode'] in (200,206):
  with reference.open('rb') as f:f.seek(first);expected=f.read(len(body))
  assert body==expected
  if r['transportCompleted']:assert len(body)==last-first+1
 else:assert len(body)==0
 body_proofs.append(dict(requestId=r['requestId'],case=r['case'],bytes=len(body),sha256=sha(body),actualSourceIntervalEqual=r['statusCode'] in (200,206),rawTransportCompleted=r['transportCompleted']))
sidecars=[]
for index in collection['nativeReadabilityObservations']:
 sc=read(C/index['observationRef']);assert sc['requestId']==index['requestId']
 sidecars.append(dict(requestId=sc['requestId'],userId=sc['userId'],sourceVersion=sc['sourceVersion'],readableSliceVerified=sc['readableSliceVerified'],nativeReadAttempted=sc['nativeReadAttempted'],nativePid=sc.get('nativeExport',{}).get('atsPid'),observedAt=sc['finishedAt'],rawRef=index['observationRef']))
assert len(sidecars)==10 and len({x['requestId'] for x in sidecars})==10
result=dict(kind='ACTUAL_H_COMPLETE_RAW_CAPACITY_AND_RETURNED_BYTE_REPLAY_NOT_FORMAL_POC',source=manifest['source'],observedAt=datetime.now(timezone.utc).isoformat(),closedRequestPeaks=peaks,native=native,conservativeTotal=total,completeConservativeBytes=total['maximumBufferedBytes'],originalAcceptanceThresholdBytes=8388608,eightMiBBoundProven=total['maximumBufferedBytes']<=8388608,exactSimultaneouslyLivePayloadLowerBoundClaimed=False,actualMediaRows=101,actualCases=21,actualStages=6,actualClears=sum(x.get('action')=='cache-cleared-by-owned-ATS-command' for x in collection['controls']),bodyProofs=body_proofs,nativeReadabilityObservations=sidecars,allTenSidecarsReportedReadable=all(x['readableSliceVerified'] for x in sidecars),nativeComponentPins=required,actualExecutionAuthenticationIndependentReviewPending=True,formalOriginal15Accepted=False,formalPocAccepted=False)
peak_epoch=max(native['epochs'],key=lambda x:x['peakBytes'])
peak_rows=[json.loads(line) for line in (W/'process-epochs'/('epoch-'+peak_epoch['token'])/'finished/durable-peaks.raw').read_bytes().splitlines()]
result['nativePeakFirstRecord']=next(row for row in peak_rows if row['peakBytes']==native['maximumTrackedCapacityBytes'])
O=T/'poc003-common-main2e8655e-original-matrix-raw-analysis-v2';O.mkdir()
(O/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(peaks=peaks,nativeBytes=native['maximumTrackedCapacityBytes'],completeBytes=total['maximumBufferedBytes'],terms=total['terms'],threshold=8388608,eightMiBBoundProven=result['eightMiBBoundProven'],sidecars=len(sidecars),allTenReportedReadable=result['allTenSidecarsReportedReadable'],actualReturnedBytes=sum(r['bytes'] for r in body_proofs),formalPocAccepted=False)))

"""Finite approved live-accounting diagnostic, never a qualified POC result."""
import json,sys,time
from pathlib import Path
r=Path('/home/sur/.cache/guize-takeover/ops012-history-parser')
sys.path.insert(0,str(r/'poc/POC-03-ats-range'))
from collect import Collector
from lab import utc
p=json.loads(Path(sys.argv[1]).read_bytes())
c=Collector(p['runDir'],p['rawOutputDir']);c.save()
observations=[]
try:
 before=c.control('snapshot',stage='live-diagnostic-before')
 assert before['nativeCacheReady']['httpCacheReady'] is True
 assert before['activeGatewayRequests']==before['activeOriginRequests']==0
 baseline=c.control('live-buffer-snapshot',afterMonotonicNs=0);observations.append(baseline)
 boundaries=[]
 for case,values in [('stream',dict(range_header='')),('if_stale',dict(if_range='"stale-live-diagnostic-version"'))]:
  started=time.monotonic_ns();response=c.request(case,**values);completed=time.monotonic_ns()
  assert response['statusCode']==200 and response['transportCompleted'] and response['sourceIntervalComparison']['actualBytesEqual']
  assert response['bodyBytes']==67108864
  assert baseline['first']['snapshotAfterMonotonicNs']<=started<=completed
  observation=c.control('live-buffer-snapshot',afterMonotonicNs=completed);observations.append(observation)
  assert observation['last']['snapshotBeforeMonotonicNs']>=completed
  boundaries.append(dict(case=case,requestId=response['requestId'],requestStartedMonotonicNs=started,
                         requestCompletedMonotonicNs=completed,postSnapshotBeforeMonotonicNs=observation['last']['snapshotBeforeMonotonicNs']))
 peaks=[row['maximumObservedLiveCapacityBytes'] for row in observations]
 c.receipt.update(status='FINITE_INSTRUMENTED_LIVE_DIAGNOSTIC_COMPLETED_UNQUALIFIED',finishedAt=utc(),
   actualResponses=2,actualExplicitObservations=3,livePeakCapacityBytes=peaks,requestBoundaries=boundaries,
   observedPeakBelowInputBytes=max(peaks)<67108864,fullMediaBufferBoundProven=False,baselineSubtracted=False,
   original15Accepted=False,qualifiedProfileAccepted=False,integrationAccepted=False)
except BaseException as error:
 c.receipt.update(status='LIVE_DIAGNOSTIC_STOPPED_RAW_PRESERVED',finishedAt=utc(),errorType=type(error).__name__,error=str(error))
 raise
finally:c.save()
print(json.dumps({key:c.receipt[key] for key in ['status','actualResponses','livePeakCapacityBytes','observedPeakBelowInputBytes','fullMediaBufferBoundProven']}))

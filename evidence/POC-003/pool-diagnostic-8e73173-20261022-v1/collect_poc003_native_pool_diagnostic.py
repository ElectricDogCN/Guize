"""Finite approved diagnostic workload; never emits a complete buffer-bound PASS."""
import json,sys
from pathlib import Path
r=Path('/home/sur/.cache/guize-takeover/ops012-history-parser')
sys.path.insert(0,str(r/'poc/POC-03-ats-range'))
from collect import Collector
from lab import utc
p=json.loads(Path(sys.argv[1]).read_bytes())
c=Collector(p['runDir'],p['rawOutputDir']);c.save()
try:
 before=c.control('snapshot',stage='diagnostic-before')
 assert before['nativeCacheReady']['httpCacheReady'] is True
 baseline=c.control('allocator-dump')
 stream=c.request('stream',range_header='')
 assert stream['statusCode']==200 and stream['transportCompleted'] and stream['sourceIntervalComparison']['actualBytesEqual']
 after_stream=c.control('allocator-dump')
 stale=c.request('if_stale',if_range='"stale-diagnostic-version"')
 assert stale['statusCode']==200 and stale['transportCompleted'] and stale['sourceIntervalComparison']['actualBytesEqual']
 after_stale=c.control('allocator-dump')
 c.receipt.update(status='FINITE_NATIVE_POOL_DIAGNOSTIC_COMPLETED_UNQUALIFIED',finishedAt=utc(),
   actualNativeDumps=3,fullMediaBufferBoundProven=False,baselineSubtracted=False,
   allocatedPoolBytes=[row['allocatedPoolBytes'] for row in (baseline,after_stream,after_stale)],
   original15Accepted=False,qualifiedProfileAccepted=False,integrationAccepted=False)
except BaseException as error:
 c.receipt.update(status='DIAGNOSTIC_STOPPED_RAW_PRESERVED',finishedAt=utc(),errorType=type(error).__name__,error=str(error))
 raise
finally:c.save()
print(json.dumps({key:c.receipt[key] for key in ['status','actualNativeDumps','allocatedPoolBytes','fullMediaBufferBoundProven']}))

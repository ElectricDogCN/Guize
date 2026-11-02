"""Prepare one task-owned aggregation-capacity source candidate; no target execution."""
from pathlib import Path
import hashlib,json,difflib,subprocess,os
from datetime import datetime,timezone
T=Path(__file__).resolve().parent
A=T/'poc003-pool-batch-performance-v1'
I=A/'poc/POC-03-ats-range/instrumentation'
S=Path('/home/sur/.cache/guize-takeover/poc003-pool-batch-ats-build-common7e-v1/source/trafficserver-9.2.3')
O=Path('/home/sur/.cache/guize-takeover/poc003-aggregation-capacity-source-v1')
assert os.geteuid()==1000 and not O.exists()
sha=lambda b:hashlib.sha256(b).hexdigest()
oldpatch=(I/'ats-live-buffer-accounting.patch').read_bytes();oldmanifest=(I/'patch-manifest.json').read_bytes();m=json.loads(oldmanifest)
assert sha(oldpatch)=='590f7a4bc9a044cbc6321ae1b1e20462aee681c0b122d6518dc2c1c9fcb072bf'
assert sha(oldmanifest)=='35a018339cc0bf54a2fc91cf518a787e1ecf1f4a63d9ce91d155b328ba43ef40'
O.mkdir(mode=0o700);(O/'original.patch').write_bytes(oldpatch);(O/'original-manifest.json').write_bytes(oldmanifest)
for row in m['files']:
 b=(S/row['path']).read_bytes();assert sha(b)==row['afterSha256']
 p=O/'pristine'/row['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
p=subprocess.run(['git','apply','--reverse',str(O/'original.patch')],cwd=O/'pristine',capture_output=True)
(O/'reverse.stdout.raw').write_bytes(p.stdout);(O/'reverse.stderr.raw').write_bytes(p.stderr);assert p.returncode==0
for row in m['files']:assert sha((O/'pristine'/row['path']).read_bytes())==row['beforeSha256']
name='iocore/cache/P_CacheVol.h';before=(O/'pristine'/name).read_bytes();after=(S/name).read_bytes()
old=b'''#define AGG_SIZE (4 * 1024 * 1024)     // 4MB
#define AGG_HIGH_WATER (AGG_SIZE / 2)  // 2MB
#define EVACUATION_SIZE (2 * AGG_SIZE) // 8MB'''
new=b'''// Private POC build: bound actual write aggregation; use a fresh cache.
#define AGG_SIZE (1 * 1024 * 1024)     // 1 MiB
#define AGG_HIGH_WATER (AGG_SIZE / 2)  // 512 KiB
#define EVACUATION_SIZE (2 * AGG_SIZE) // 2 MiB'''
assert after.count(old)==1;after=after.replace(old,new)
section=''.join(difflib.unified_diff(before.decode().splitlines(keepends=True),after.decode().splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name)).encode()
start=oldpatch.index(b'--- a/'+name.encode()+b'\n');end=oldpatch.index(b'--- a/',start+7)
patch=oldpatch[:start]+section+oldpatch[end:]
(O/'candidate.patch').write_bytes(patch)
p=subprocess.run(['git','apply','--check',str(O/'candidate.patch')],cwd=O/'pristine',capture_output=True)
(O/'check.stdout.raw').write_bytes(p.stdout);(O/'check.stderr.raw').write_bytes(p.stderr);assert p.returncode==0
p=subprocess.run(['git','apply',str(O/'candidate.patch')],cwd=O/'pristine',capture_output=True)
(O/'apply.stdout.raw').write_bytes(p.stdout);(O/'apply.stderr.raw').write_bytes(p.stderr);assert p.returncode==0
for row in m['files']:
 h=sha((O/'pristine'/row['path']).read_bytes())
 if row['path']==name:assert h==sha(after);row['afterSha256']=h
 else:assert h==row['afterSha256']
m['patchSha256']=sha(patch)
m['aggregationCapacityPolicy']={'bytesPerVolume':1048576,'previousBytesPerVolume':4194304,'highWaterBytes':524288,'evacuationAndRecoveryBytes':2097152,'scope':'Private task-owned POC build only; every later run uses a fresh empty cache. Never open an existing stock/previous-build cache.','originalLabTargetFragmentSizeBytes':8192,'sliceBytes':1048576,'defaultTargetFragmentExpressionUnchanged':'1048576 - sizeof(Doc)','maxFragmentExpressionUnchanged':'AGG_SIZE - sizeof(Doc)','accounting':'Actual allocation and unchanged full retained plus logical accounting. No excluded baseline, changed domain or threshold.','status':'Source candidate only. Exact build, source/actual-main full CI, new run approval and original full matrix plus separate warm-cache revocation remain required.','maximumBufferedBytesAcceptanceThreshold':8388608}
raw=(json.dumps(m,indent=2)+'\n').encode();(I/'ats-live-buffer-accounting.patch').write_bytes(patch);(I/'patch-manifest.json').write_bytes(raw)
record={'kind':'TASK_OWNED_AGGREGATION_CAPACITY_SOURCE_CANDIDATE_ONLY','sourceBase':'2e8655e5b6d59261a4d1597d999dd7530875c1c7','observedAt':datetime.now(timezone.utc).isoformat(),'originalPatchSha256':sha(oldpatch),'originalManifestSha256':sha(oldmanifest),'patchSha256':sha(patch),'manifestSha256':sha(raw),'newPcacheVolAfterSha256':sha(after),'unchangedOtherPatchedSourceFiles':len(m['files'])-1,'patchCheckExitCode':0,'atsStarted':False,'experimentExecuted':False,'performancePassClaimed':False}
(O/'results.json').write_text(json.dumps(record,indent=2)+'\n');public=T/'poc003-aggregation-capacity-source-v1';public.mkdir();(public/'results.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))

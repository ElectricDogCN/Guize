"""Retain the independently accepted actual warm scenario; no new service or request."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil
from poc003_full_execution_assembler_v8 import reject_actual_secrets
T=Path(__file__).resolve().parent;W=T/'poc003-pool-batch-performance-v1';P='evidence/POC-003/profiles/local-v1/v1/attempt-005/warm-cache-revocation-v1';D=W/P
R=Path('/home/sur/.cache/guize-takeover/poc003-common-main1b5c68b-fresh-warm-cache-revocation-v1/data')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=T/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-result-independent-review.json';assert sha(review)=='bde03aed7660962149320f3a7273896c705de2a22b2977879c20c70e1a367fef'
v=json.loads(review.read_bytes());assert v['warmCacheRevocationAccepted'] and not v['mustFix']
run=T/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-v1/results.json';assert sha(run)=='c13c2798c37de33c9a9fe7c6bc781f4dae62a6138af1c56025bb314a7bc61e82'
r=json.loads(run.read_bytes());assert r['warmCacheRevocationCompleted'] and r['engineExitCode']==r['attachedCliExitCode']==0 and r['finalContainerState']['Pid']==0 and not r['externalCleanup']
cfg=json.loads((R/'work/settings.private.json').read_bytes());needles=[cfg['secret'].encode(),cfg['controlKey'].encode(),*[x.encode() for x in cfg['users'].values()]]
assert os.getuid()==1000 and not D.exists();D.mkdir(parents=True);manifest=[];total=0

def copy(p,ref):
 global total
 p=Path(p);assert p.is_file() and not p.is_symlink();reject_actual_secrets(p,needles)
 q=D/ref;q.parent.mkdir(parents=True,exist_ok=True);assert not q.exists();total+=p.stat().st_size;assert total<=268435456
 with p.open('rb') as src,q.open('xb') as out:shutil.copyfileobj(src,out,65536)
 assert sha(q)==sha(p);manifest.append(dict(ref=P+'/'+ref,byteCount=q.stat().st_size,sha256=sha(q)))
for p in sorted((R/'warm-cache-revocation').rglob('*')):
 if p.is_file():copy(p,'raw/'+p.relative_to(R).as_posix())
for n in ('before-environment.json','warm-cache-revocation-client.json','revocation-cli.stdout.raw','revocation-cli.stderr.raw','work/execution-owner-wait.json','work/python-runtime-binding.prepare.json','work/python-runtime-binding.controller.json'):
 copy(R/n,'raw/'+n)
for folder in ('work/process-epochs','work/cache-observer'):
 for p in sorted((R/folder).rglob('*')):
  if p.is_file():copy(p,'raw/'+p.relative_to(R).as_posix())
copy(run,'actual-run-result.json');copy(review,'independent-result-review.json')
permits=T/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-approval-v1'
for p in sorted(permits.iterdir()):
 if p.is_file():copy(p,'before-controls/'+p.name)
for name in ('poc003_common_main1b5c68b_fresh_warm_cache_revocation_entry_v2.py','run_poc003_common_main1b5c68b_fresh_warm_cache_revocation_v2.py','launch_poc003_approved_common_main1b5c68b_fresh_warm_cache_revocation_v2.py','poc003_common_main7e405b6_revocation_failure_records_v1.py','poc003-common-main1b5c68b-fresh-warm-cache-revocation-proposal-v1.json','poc003-common-main1b5c68b-fresh-warm-cache-revocation-method-independent-review-v1.json'):
 copy(T/name,'tools/'+name)
copy(Path(__file__),'tools/archive-method.py')
record=dict(kind='ACTUAL_ACCEPTED_WARM_SCENARIO_EXACT_RETENTION',source='1b5c68bab02d98f8e11286d80033585090c7af99',scope='Independent same unexpired grant warm-cache revocation only; not a matrix/8MiB/profile/POC acceptance',reviewSha256=sha(review),runSha256=sha(run),files=manifest,totalBytes=total,actualScenarioPassed=True,actualScenarioCount=1,skippedAssertions=0,originalsUnchanged=True,privateSettingsPublished=False,newMediaExecuted=False,formalPocAccepted=False,retainedAt=datetime.now(timezone.utc).isoformat())
(D/'retention-manifest.json').write_text(json.dumps(record,indent=2)+'\n');(T/'poc003-attempt005-accepted-warm-retention-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(files=len(manifest),totalBytes=total,warmAccepted=True,newMediaExecuted=False,formalPocAccepted=False)))

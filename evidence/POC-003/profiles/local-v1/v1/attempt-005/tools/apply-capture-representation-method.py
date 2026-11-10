"""Apply only an independently approved post-run canonical captured-fact view."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess
T=Path(__file__).resolve().parent;W=T/'poc003-pool-batch-performance-v1';P='evidence/POC-003/profiles/local-v1/v1/attempt-005';D=W/P;Q=T/'poc003-attempt005-capture-representation-proposal-v2';O=T/'poc003-attempt005-capture-representation-application-v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--review-sha256',required=True);a=p.parse_args()
rp=T/'poc003-attempt005-capture-representation-reconciliation-independent-review.json';assert sha(rp)==a.review_sha256;r=json.loads(rp.read_bytes())
assert r['capturedFactRepresentationReconciliationApproved'] is True and r['reviewer']=='/root/independent_review' and not r['mustFix']
assert r['scope']=='CAPTURED_ZERO_DEVICE_DOCKER_ENUM_AND_NATIVE_MEDIA_TYPES_ONLY' and r['newMediaExecutionApproved'] is False
assert r['methodSha256']==sha(__file__) and r['proposalSha256']==sha(Q/'proposal.json')
q=json.loads((Q/'proposal.json').read_bytes())
assert subprocess.check_output(['git','-c','core.longpaths=true','-C',str(W),'rev-parse','HEAD'],text=True).strip()==q['sourceEvidenceCommit']=='e72d32b170a209aa55e3fde620ff38d3b4ccee22'
assert not subprocess.check_output(['git','-c','core.longpaths=true','-C',str(W),'status','--porcelain=v1','--untracked-files=all'],text=True)
assert sha(D/'execution.json')==r['originalExecutionSha256']==q['originalExecution']['sha256']
assert sha(D/'resource-configuration.json')==r['originalResourceSha256']==q['originalResource']['sha256']
assert sha(Q/'execution.canonical.json')==r['targetExecutionSha256']==q['targetExecution']['sha256']
assert sha(Q/'resource-configuration.canonical.json')==r['targetResourceSha256']==q['targetResource']['sha256']
assert sha(T/'poc003-common-main1b5c68b-full-original-matrix-v1/results.json')==r['actualRunResultSha256']=='354a982d62ea9b6c709b9e6bac1a71b17fd91e6b981083cc2c40392ce5d797ee'
before=json.loads((D/'execution.json').read_bytes());after=json.loads((Q/'execution.canonical.json').read_bytes())
assert before['measurements']==after['measurements'] and before['rawOutputRefs']==after['rawOutputRefs']
assert before['environmentCaptured']['executionWindow']==after['environmentCaptured']['executionWindow'] and before['environmentCaptured']['testedSource']==after['environmentCaptured']['testedSource']
left=before['environmentCaptured']['rawExecutionArtifacts'];right=after['environmentCaptured']['rawExecutionArtifacts'];assert len(left)==len(right)==709
changed=0
for b,c in zip(left,right):
 assert {k:b[k] for k in ('ref','sha256','byteCount')}=={k:c[k] for k in ('ref','sha256','byteCount')}
 if b['artifactType']!=c['artifactType']:
  assert b['artifactType']=='command_output' and c['artifactType']=='produced_media' and '/raw/observed/work/cache-observer/cache-export-' in b['ref'] and b['ref'].endswith('.body');changed+=1
assert sha(D/'raw/observed/before-environment.json')==q['originalBeforeEnvironment']['sha256']==r['originalBeforeEnvironmentSha256']
assert after['environmentCaptured']['gpu']['evidenceSha256']==after['environmentCaptured']['driver']['evidenceSha256']=='sha256:'+q['originalBeforeEnvironment']['sha256']
assert changed==202 and not O.exists() and not (D/'before-originals').exists()
O.mkdir();(D/'before-originals').mkdir()
for n in ('execution.json','resource-configuration.json'):
 with (D/'before-originals'/n).open('xb') as f:f.write((D/n).read_bytes())
(D/'tools/capture-representation-reconciliation-review.json').write_bytes(rp.read_bytes())
(D/'tools/capture-representation-proposal.json').write_bytes((Q/'proposal.json').read_bytes())
(D/'tools/capture-representation-delta.json').write_bytes((Q/'media-classification-delta.json').read_bytes())
(D/'tools/apply-capture-representation-method.py').write_bytes(Path(__file__).read_bytes())
# Forward edit canonical views only; raw input/output files and before authority remain exact.
(D/'execution.json').write_bytes((Q/'execution.canonical.json').read_bytes())
(D/'resource-configuration.json').write_bytes((Q/'resource-configuration.canonical.json').read_bytes())
record=dict(kind='ACTUAL_POST_RUN_CANONICAL_CAPTURE_VIEW_APPLICATION',sourceEvidenceCommit=q['sourceEvidenceCommit'],methodReviewSha256=a.review_sha256,changedNativeMediaDescriptors=202,allRawReferencesAndHashesAndBytesUnchanged=True,allOriginal15AndWindowUnchanged=True,originalFilesRetained=True,originalRunAndBeforeAuthorityUnchanged=True,appliedAt=datetime.now(timezone.utc).isoformat(),newMediaExecuted=False,formalPocAccepted=False)
(O/'results.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))

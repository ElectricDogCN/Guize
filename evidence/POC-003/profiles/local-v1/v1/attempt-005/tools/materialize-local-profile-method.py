"""Materialize actual independently reviewed local result; no Task completion or CI bypass."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,subprocess,yaml,jsonschema
T=Path(__file__).resolve().parent;W=T/'poc003-pool-batch-performance-v1';P='evidence/POC-003/profiles/local-v1/v1/attempt-005';D=W/P
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--review-sha256',required=True);a=p.parse_args()
rp=T/'poc003-attempt005-original15-local-profile-materialization-independent-review.json';assert sha(rp)==a.review_sha256;r=json.loads(rp.read_bytes())
assert r['localProfileMaterializationApproved'] is True and r['actualOriginal15Accepted'] is True and r['completeOriginalEightMiBBoundAccepted'] is True and r['reviewer']=='/root/independent_review' and not r['mustFix']
assert r['scope']=='ACTUAL_CURRENT_SOURCE_ORIGINAL15_LOCAL_PROFILE_RESULT_MATERIALIZATION_ONLY' and r['newMediaExecutionApproved'] is False
assert r['methodSha256']==sha(__file__) and r['proposalSha256']==sha(T/'poc003-attempt005-local-profile-result-proposal-v1.json')
q=json.loads((T/'poc003-attempt005-local-profile-result-proposal-v1.json').read_bytes());assert r['testedSource']==q['testedSource'] and r['executionSha256']==q['executionSha256']==sha(D/'execution.json')
validation=T/'poc003-attempt005-native-clean-validation-v2/results.json';assert sha(validation)==r['frozenValidationSha256'];v=json.loads(validation.read_bytes());assert v['fullQualifiedExecutionValidated'] and v['evidenceCommit']==q['evidenceCommit'] and v['testedSource']==q['testedSource']['commit'] and all(c['actualWaitCompleted'] and c['exitCode']==0 for c in v['commands'])
assert sha(T/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-result-independent-review.json')==r['warmReviewSha256']=='bde03aed7660962149320f3a7273896c705de2a22b2977879c20c70e1a367fef'
assert subprocess.check_output(['git','-c','core.longpaths=true','-C',str(W),'rev-parse','HEAD'],text=True).strip()==q['evidenceCommit']
result=r['formalResult'];expected=dict(q['resultTemplate'],reviewer=r['reviewer'],approvedAt=result['approvedAt'],approval='approved',rationale=result['rationale']);assert result==expected
assert re.fullmatch(r'20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ',result['approvedAt']) and datetime.fromisoformat(result['approvedAt'].replace('Z','+00:00'))<=datetime.now(timezone.utc)
assert datetime.fromisoformat(result['approvedAt'].replace('Z','+00:00'))>datetime.fromisoformat('2026-11-02T22:29:12.664439+00:00')
index=q['indexTemplate'];indexpath=W/q['indexRef'];assert not (D/'result.json').exists() and not indexpath.exists()
defs=yaml.safe_load((W/'specs/poc/program.schema.yaml').read_bytes())['$defs'];jsonschema.Draft202012Validator(yaml.safe_load((W/'specs/poc/result-record.schema.yaml').read_bytes())).validate(result);jsonschema.Draft202012Validator(defs['profileEvidenceIndex']).validate(index)
(D/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
indexpath.write_text(yaml.safe_dump(index,sort_keys=False,allow_unicode=True),encoding='utf-8',newline='\n')
for source,name in [(rp,'local-profile-materialization-independent-review.json'),(Path(__file__),'materialize-local-profile-method.py'),(T/'poc003-attempt005-local-profile-result-proposal-v1.json','local-profile-result-proposal.json'),(validation,'native-frozen-qualified-execution-results.json'),(T/'poc003-attempt005-native-clean-validation-v2/frozen-execution.stdout.raw','native-frozen-qualified-execution.stdout.raw')]:
 with (D/'tools'/name).open('xb') as out:out.write(source.read_bytes())
record=dict(kind='ACTUAL_INDEPENDENTLY_APPROVED_LOCAL_PROFILE_MATERIALIZATION',testedSource=q['testedSource'],executionSha256=q['executionSha256'],reviewSha256=a.review_sha256,resultRef=P+'/result.json',resultSha256=sha(D/'result.json'),profileIndexRef=q['indexRef'],profileIndexSha256=sha(indexpath),normalReviewAndOfficialCiStillRequired=True,taskCompleted=False,fullV1Accepted=False,producedAt=datetime.now(timezone.utc).isoformat())
(T/'poc003-attempt005-local-profile-materialization-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))

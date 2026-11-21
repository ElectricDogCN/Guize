"""Fresh actor/program/window checks before the exact approved one-shot native controller."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,subprocess,yaml

parser=argparse.ArgumentParser();parser.add_argument('--approval-sha256',required=True);args=parser.parse_args()
t=Path(__file__).resolve().parent
canonical=t.parent/'Guize'
SOURCE='1b5c68bab02d98f8e11286d80033585090c7af99'
TREE='f94ed8da8d83391f2474365af848bf267a0dc8d1'
approval=t/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-approval-v1/independent-approval.json'
approval_sha=args.approval_sha256
assert hashlib.sha256(approval.read_bytes()).hexdigest()==approval_sha
a=json.loads(approval.read_bytes())
canonical_main=a['canonicalMain']
qualification_base='7e405b61d872761817a0614b3b2fdc46edde9f14'
assert a['qualificationBase']==qualification_base and len(canonical_main)==40
now=datetime.now(timezone.utc)
assert a['warmCacheRevocationExecutionApproved'] and not a['mustFix']
assert datetime.fromisoformat(a['validFrom'].replace('Z','+00:00'))<=now
assert (datetime.fromisoformat(a['validUntil'].replace('Z','+00:00'))-now).total_seconds()>=900
assert a['approvedBy']=='/root/independent_review' and a['maximumActualAttempts']==1
assert a['scope']=='OWNED_PID1_COMMON_MAIN1B5C68B_FRESH_WARM_CACHE_REVOCATION_ONLY'
assert a['configurationReviewSha256']==hashlib.sha256((t/'poc003-common-main1b5c68b-full-original-matrix-config-v1-independent-review.json').read_bytes()).hexdigest()
snapshot=json.loads((t/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-start-fresh-official.json').read_bytes())
captured=datetime.fromisoformat(snapshot['capturedAt'].replace('Z','+00:00'))
assert 0<=(now-captured).total_seconds()<120
remote_main=json.loads(snapshot['main']['structuredContent']['content'])['object']['sha']
pr3=json.loads(snapshot['pr134']['structuredContent']['content']);pr5=json.loads(snapshot['pr136']['structuredContent']['content']);pr183=json.loads(snapshot['pr183']['structuredContent']['content'])
issue3=json.loads(snapshot['issue131']['structuredContent']['content']);issue5=json.loads(snapshot['issue132']['structuredContent']['content'])
assert remote_main==canonical_main==a['source']==SOURCE and a['tree']==TREE
assert pr3['state']=='closed' and pr3['merged'] and pr3['head']['sha']=='c4ee800d5438fca49339239a35e700db7cc6e809' and pr3['merge_commit_sha']=='0d8c6f43a8c3d7794c32b350c5cbb58c0c17d583'
assert pr5['state']=='closed' and pr5['merged'] and pr5['head']['sha']=='246bc11cbf711c8e750bbbb1d465c315060d8d88' and pr5['merge_commit_sha']==qualification_base
assert pr183['state']=='closed' and pr183['merged'] and pr183['head']['sha']=='34223eb00edde06c1a0fda03b6e88f70bca6f279' and pr183['merge_commit_sha']==SOURCE
assert issue3['number']==131 and issue3['state']=='open' and issue5['number']==132 and issue5['state']=='open'
resource=json.loads((t/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-fresh-start-resources-v1/results.json').read_bytes())
assert 0<=(now-datetime.fromisoformat(resource['observedAt'])).total_seconds()<120
assert resource['uid']==1000 and resource['proposedNameAbsent'] and not resource['containerCreated']
assert resource['proposedContainerName']=='guize-poc003-common-main1b5c68b-fresh-warm-cache-revocation-v1'
assert resource['disk']['free']>=4*1024**3
assert resource['sourceSnapshot']==dict(head=SOURCE,tree=TREE,branch='main',status='')
for row in a['ordinaryRecords']:
    p=Path(row['path'])
    raw=p.read_bytes()
    assert len(raw)==row['byteCount'] and hashlib.sha256(raw).hexdigest()==row['sha256']
assert a['ordinarySchemasValidated'] is True
for key in ['configurationManifestSha256','packageManifestSha256']:
    assert len(a[key])==64 and all(c in '0123456789abcdef' for c in a[key])
git=lambda r,*args:subprocess.check_output(['git','-c','core.longpaths=true','-C',str(r),*args]).decode().strip()
assert git(canonical,'rev-parse','HEAD')==canonical_main==SOURCE and git(canonical,'rev-parse','HEAD^{tree}')==TREE
assert git(canonical,'branch','--show-current')=='main' and not git(canonical,'status','--porcelain=v1','--untracked-files=all')
assert git(canonical,'ls-remote','--heads','origin','refs/heads/main').split()==[SOURCE,'refs/heads/main']
assert yaml.safe_load((canonical/'specs/coordination/program-plan.yaml').read_bytes())['status']=='active'
registry=yaml.safe_load((canonical/'specs/coordination/active-work.yaml').read_bytes());own=next(x for x in registry['tasks'] if x['taskId']=='POC-003')
assert own['branch']=='chore/POC-003-ats-range' and own['status']=='in_progress' and own['agentRole']=='implementer' and own['baseSha']=='760f6c5838597d1d66c0a536ecbf440ef5a7dfec'
assert own['implementer']=='/root' and own['reviewer']=='/root/independent_review' and own['lease']=={'acquiredAt':'2026-10-29T11:01:07Z','expiresAt':'2026-11-05T11:01:07Z'}
assert datetime.fromisoformat(own['lease']['acquiredAt'].replace('Z','+00:00'))<=now<datetime.fromisoformat(own['lease']['expiresAt'].replace('Z','+00:00'))
assert resource['ownPoc003']==own
roles=[dict(repository=str(canonical),own=own),dict(repository=resource['sourceRepository'],own=resource['ownPoc003'],nativeSnapshot=resource['sourceSnapshot'])]
qualified_path=t/'poc003-aggregation-pr183-final-actual-main-independent-review.json'
assert hashlib.sha256(qualified_path.read_bytes()).hexdigest()==a['qualificationReviewSha256']=='91e03433b09c0bf2bea535061b67419ef27946bee7371dc64ad9905422e28915'
qualified=json.loads(qualified_path.read_bytes())
assert qualified['actualMain']==SOURCE and qualified['tree']==TREE and qualified['source']=='34223eb00edde06c1a0fda03b6e88f70bca6f279' and qualified['base']=='2e8655e5b6d59261a4d1597d999dd7530875c1c7'
assert qualified['actualImplementationMainAccepted'] and qualified['fullMainCiAccepted'] and qualified['ownMainSevenAccepted'] and not qualified['mustFix']
# Keep the two staged implementation gates in their own original contexts.
for record,head,base,publication in [
 ('poc003-main98-staged-code-c4ee800-native-source15/results.json','c4ee800d5438fca49339239a35e700db7cc6e809','98cf7e5340c9a512461eb7d18659019de4c9c2a1','poc003-main98-staged-code-c4ee800-publication-v1/results.json'),
 ('poc003-pool-batch-code-d049ade-native-source15/results.json','d049adee8f5b68a5acc49d7f7a44050bc3430ba8',qualification_base,'poc003-pool-batch-code-d049ade-publication-v1/results.json'),
 ('poc005-post-poc003-staged-code-246bc11-native-source15/results.json','246bc11cbf711c8e750bbbb1d465c315060d8d88','0d8c6f43a8c3d7794c32b350c5cbb58c0c17d583','poc005-post-poc003-staged-code-246bc11-publication-v1/results.json')]:
 local15=json.loads((t/record).read_bytes());assert local15['source']==head and local15['base']==base and local15['source15Passed'] and local15['requiredProfileNegativeCaptured'] and local15['before']==local15['after']
 assert len(local15['commands'])==15 and all(x['actualWaitCompleted'] and x['exitCode']==0 for x in local15['commands'])
 pub=json.loads((t/publication).read_bytes());assert pub['source']==head and pub['actualWaitCompleted'] and pub['exitCode']==0
assert a['canonicalMainAcceptanceReview']=='poc003-aggregation-pr183-final-actual-main-independent-review.json' and a['canonicalMainAcceptanceReviewSha256']==a['qualificationReviewSha256']
protected=['AGENTS.md','scripts/poc-contract-repair-admission.py','scripts/check-program-lifecycle-guards.py','tests/governance/test_poc_contract_repair_admission.py','evidence/OPS-017/source-compatibility-admission-intent.json','specs/poc/program.schema.yaml','specs/poc/program.yaml','specs/poc/check_program.py','specs/poc/test_program.py','docs/18-testing-and-acceptance.md']
for name in protected:
 assert (canonical/name).read_bytes()==subprocess.check_output(['git','-C',str(canonical),'show',qualification_base+':'+name])
method=t/'run_poc003_common_main1b5c68b_fresh_warm_cache_revocation_v2.py'
assert hashlib.sha256(method.read_bytes()).hexdigest()==a['methodSha256']=='69307706e38f2c5f96a84d369a6d761a64a0c6e239f39ef8fc948873f6bb8d1b'
entry=t/'poc003_common_main1b5c68b_fresh_warm_cache_revocation_entry_v2.py'
assert hashlib.sha256(entry.read_bytes()).hexdigest()==a['entrySha256']=='469b68c95225fbf93aa1275c610ed8f2b163243e1ece330f9803c6cf5f54f241'
out=t/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-launch-v1'
out.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
native_root=Path(r'\\wsl.localhost\Ubuntu\home\sur\.cache\guize-takeover')
CONFIG=native_root/'poc003-common-main1b5c68b-full-original-matrix-config-v1'
PRIVATE=native_root/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-v1'
assert sha(CONFIG/'configuration-manifest.json')==a['configurationManifestSha256']
cm=json.loads((CONFIG/'configuration-manifest.json').read_bytes())
assert {p.name for p in CONFIG.iterdir()}=={v['path'] for v in cm['files']}|{'configuration-manifest.json'}
for row in cm['files']:
    path=CONFIG/row['path']
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
original_config=out/'original-configuration'
original_config.mkdir()
for path in CONFIG.iterdir():
    assert path.is_file() and not path.is_symlink()
    (original_config/path.name).write_bytes(path.read_bytes())
(out/'launcher.actual.py').write_bytes(Path(__file__).read_bytes())
(out/'method.actual.py').write_bytes(method.read_bytes())
(out/'entry.actual.py').write_bytes(entry.read_bytes())
(out/'independent-approval.actual.json').write_bytes(approval.read_bytes())
(out/'fresh-official.actual.json').write_bytes((t/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-start-fresh-official.json').read_bytes())
(out/'fresh-resource.actual.json').write_bytes((t/'poc003-common-main1b5c68b-fresh-warm-cache-revocation-fresh-start-resources-v1/results.json').read_bytes())
for row in a['ordinaryRecords']:
    path=Path(row['path'])
    (out/path.name).write_bytes(path.read_bytes())
linux=lambda p:'/mnt/c'+p.resolve().as_posix()[2:]
argv=['wsl.exe','-d','Ubuntu','-u','sur','--','env','LD_LIBRARY_PATH=/home/sur/.cache/guize-takeover/python31117-official-runtime-v1/runtime/lib','PYTHONDONTWRITEBYTECODE=1','/home/sur/.cache/guize-takeover/python31117-official-runtime-v1/venv/bin/python','-B',linux(method),'--approval',linux(approval),'--approval-sha256',approval_sha]
result=dict(approvalSha256=approval_sha,source=a['source'],roles=roles,canonicalMain=canonical_main,stagedImplementations15AndPublicationActuallyFinished=True,qualifiedSourceBase=qualification_base,canonicalEqualsFullyTestedCommonMain=True,testedSourceIsActualCanonicalMain=True,noOtherDeliberateLocalPocPerformanceOrBuildScheduled=True,argv=argv,startedAt=now.isoformat(),actualWaitCompleted=False,runtimeAccepted=False,warmCacheRevocationApproved=True)
save=lambda:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
with (out/'native.stdout.raw').open('xb') as stdout,(out/'native.stderr.raw').open('xb') as stderr:
    child=subprocess.Popen(argv,stdout=stdout,stderr=stderr)
    result['pid']=child.pid
    save()
    code=child.wait()
result.update(actualWaitCompleted=True,exitCode=code,finishedAt=datetime.now(timezone.utc).isoformat())
save()
comparisons=[]
try:
    for row in cm['files']:
        name=row['path']
        copied_name='bootstrap.original.py' if name=='entry.py' else name
        paths=[original_config/name,CONFIG/name,PRIVATE/'configuration'/copied_name]
        comparisons.append(dict(path=name,expectedSha256=row['sha256'],observed=[dict(path=str(p),exists=p.exists(),sha256=sha(p) if p.is_file() else None) for p in paths]))
    actual_entry=PRIVATE/'configuration'/'entry.py'
    result.update(actualEntryComparison=dict(path=str(actual_entry),expectedSha256=a['entrySha256'],actualSha256=sha(actual_entry) if actual_entry.is_file() else None),actualEntryUnchanged=actual_entry.is_file() and sha(actual_entry)==sha(entry)==a['entrySha256'])
    result.update(configurationComparisons=comparisons,
        originalConfigurationManifestUnchanged=sha(CONFIG/'configuration-manifest.json')==sha(original_config/'configuration-manifest.json')==a['configurationManifestSha256'],
        originalAndCopiedConfigurationUnchanged=all(v['sha256']==row['expectedSha256'] for row in comparisons for v in row['observed']))
    passed=result['originalAndCopiedConfigurationUnchanged'] and result['originalConfigurationManifestUnchanged'] and result['actualEntryUnchanged']
except (OSError,ValueError) as error:
    result.update(configurationComparisons=comparisons,configurationValidationError=type(error).__name__+': '+str(error),originalAndCopiedConfigurationUnchanged=False)
    passed=False
result.update(wrapperValidationPassed=passed,wrapperExitCode=code if code else (0 if passed else 1))
save()
print(json.dumps(dict(pid=child.pid,actualWaitCompleted=True,exitCode=code,wrapperExitCode=result['wrapperExitCode'],wrapperValidationPassed=passed,runtimeAccepted=False,warmCacheRevocationApproved=True)),flush=True)
raise SystemExit(result['wrapperExitCode'])

"""Prepare a new8aa successor strictly inside the frozen qualified profile prefix.

The failed bff author, all its refs and all original artifacts remain intact.
This is a separate unpublished evidence delivery, not reset/rebase/cherry-pick.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,subprocess,zipfile
import yaml

t=Path(__file__).resolve().parent
old=t/'poc005-feature-actor-import-v1'
parent='8aa353c42c98aa62d147d0d3295b836f021537d6'
failed_head='bff619272ec770969804f0f853cf87a3ddc85c68'
branch='chore/POC-005-metadata-scale'
prefix='evidence/POC-005/profiles/local-v1/v1'
r=t/'poc005-011-v3'
out=t/'poc005-attempt011-profile-prefix-preparation-v3'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
pin=lambda raw:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def git(repo,*a):return subprocess.check_output(['git','-c','core.longpaths=true','-c','core.autocrlf=false','-C',str(repo),*a])
old_state=lambda:dict(head=git(old,'rev-parse','HEAD').decode().strip(),tree=git(old,'rev-parse','HEAD^{tree}').decode().strip(),
    status=git(old,'status','--porcelain').decode(),refs=git(old,'for-each-ref','--format=%(refname) %(objectname)').decode())
before_old=old_state();assert before_old['head']==failed_head and not before_old['status']
negative_path=t/'poc005-attempt011-formal-profile-v1-negative-independent-review.json'
assert pin(negative_path.read_bytes())['sha256']=='c217d1e3578a61c88e4b1d860cba489aa974b341219ad1a11a6ca5be7d74757c'
context=read(t/'poc005-attempt011-tracked-validation-context.json')
bundle=t/context['bundle']
assert pin(bundle.read_bytes())==dict(bytes=context['bundleBytes'],sha256=context['bundleSha256'])
assert not r.exists() and not out.exists();out.mkdir()
clone_argv=['git','-c','core.longpaths=true','clone','--quiet','--branch',branch,'--config','core.autocrlf=false',str(bundle),str(r)]
with (out/'clone.stdout.raw').open('xb') as stdout,(out/'clone.stderr.raw').open('xb') as stderr:
    child=subprocess.Popen(clone_argv,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW);clone_code=child.wait()
clone_pid=child.pid
assert clone_code==0 and git(r,'rev-parse','HEAD').decode().strip()==parent and not git(r,'status','--porcelain')
assert not (r/'.git/objects/info/alternates').exists()
git(r,'remote','set-url','origin','https://github.com/ElectricDogCN/Guize.git')
terminal=r/prefix/'attempt-011/terminal-materials-v2';terminal.mkdir()
history=terminal/'failed-bff-context.zip';entries=[]
delta=git(old,'diff','--name-only',parent,failed_head).decode().splitlines();assert len(delta)==19
with zipfile.ZipFile(history,'x',compression=zipfile.ZIP_DEFLATED) as z:
    def save(name,raw,origin):z.writestr(name,raw);entries.append(dict(ref=name,**pin(raw),origin=origin))
    for name in delta:save('bff-delta/'+name,git(old,'show',failed_head+':'+name),'Exact committed bff blob')
    previous=t/'poc005-attempt011-formal-profile-linux-v1'
    for p in sorted(previous.iterdir()):
        if p.is_file():save('formal-profile-v1/'+p.name,p.read_bytes(),str(p))
    save('independent-negative.json',negative_path.read_bytes(),str(negative_path))
    for name in ('poc005-attempt011-profile-prefix-preparation-v2-negative.json','prepare_poc005_attempt011_profile_prefix_context_v2_once.py'):
        save('profile-prefix-preparation-v2/'+name,(t/name).read_bytes(),str(t/name))
with zipfile.ZipFile(history) as z:
    assert z.testzip() is None and len(z.namelist())==len(entries)
    for row in entries:assert pin(z.read(row['ref']))=={k:row[k] for k in ('bytes','sha256')}
old_report=git(old,'show',failed_head+':evidence/POC-005/local-v1-scale-exit-report-attempt011-v2.md')
assert pin(old_report)['sha256']=='d4cba29a9c48cb0ef316e88ce4486334d99a77423cac6538bf8c93a0a6bb1942'
target=b'(profiles/local-v1/v1/attempt-011/'
assert old_report.count(target)==2
new_report=old_report.replace(target,b'(../')
(terminal/'report-v3.md').write_bytes(new_report)
qualified='evidence/POC-005/qualified-local-1m-attempt011-v1/'
names=git(old,'ls-tree','-r','--name-only',failed_head,'--',qualified).decode().splitlines()
assert len(names)==5
for name in names:
    dest=terminal/'qualified-local-1m-attempt011-v1'/Path(name).name
    dest.parent.mkdir(exist_ok=True);dest.write_bytes(git(old,'show',failed_head+':'+name))
decision_path=t/'poc005-attempt011-local-v1-exit-independent-review.json'
decision=read(decision_path)
assert pin(decision_path.read_bytes())['sha256']=='184edc445493767cd26c1582788c6576a5eae9363689abdfd2a778fa04d0e6ad'
assert not decision['mustFix']
result=decision['approvedResultRecordFields']
for name,value in ((prefix+'/attempt-011/result.json',result),
    (prefix+'/index.yaml',dict(schemaVersion=2,pocId='POC-05',pocTaskId='POC-005',ownerTask='POC-005',
     acceptanceProfile=dict(id='local-v1',version=1,bindingRevision=1,scope='LOCAL_FULL_V1'),
     resultRef=prefix+'/attempt-011/result.json'))):
    with (r/name).open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
(terminal/'approved-exit-review.original.json').write_bytes(decision_path.read_bytes())
(terminal/'preparation-method-v3.py').write_bytes(Path(__file__).read_bytes())
manifest=dict(kind='PROFILE_PREFIX_ONLY_SUCCESSOR_WITH_PRESERVED_NEGATIVE_BFF_HISTORY',parent=parent,
    originalFailedHead=failed_head,originalFailedAuthorPreserved=True,failedFormalActualExitCode=1,
    originalReportPin=pin(old_report),currentReport='report-v3.md',currentReportPin=pin(new_report),
    reportChange='Only the two Markdown targets beginning profiles/local-v1/v1/attempt-011/ become ../; business text unchanged.',
    failedHistoryArchive=history.name,failedHistoryArchivePin=pin(history.read_bytes()),failedHistoryEntries=entries,
    qualifiedFilesRelocation='Byte-exact historical qualification/fanout records copied under this profile-local directory; their old root refs remain historical attribution.',
    taskAndRootConventionalEvidenceChanged=False,formalProfileValidated=False,reportRelocationIndependentlyAccepted=False)
with (terminal/'index.json').open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
paths=sorted(filter(None,git(r,'ls-files','--others','--exclude-standard','-z').decode().split('\0')))
assert paths and all(p.startswith(prefix+'/') for p in paths)
assert not git(r,'diff','--name-only') and not git(r,'diff','--cached','--name-only')
protected=['specs/tasks/POC-005.md','evidence/POC-005/summary.md','evidence/POC-005/handoff.md','evidence/POC-005/commands.txt']
for name in protected:assert (r/name).read_bytes()==git(old,'show',parent+':'+name),name
git(r,'add','--',*paths)
for name in paths:assert git(r,'show',':'+name)==(r/name).read_bytes(),name
argv=['git','-c','core.longpaths=true','-c','core.autocrlf=false','-C',str(r),'commit','-m',
    'chore(POC-005): deliver current011 result within qualified profile domain','-m',
    'Refs #132. Preserve failed bff context and exact approved experiment facts. Only profile-local evidence changes; Task/root conventional evidence stay at8aa. Formal checks pending.']
with (out/'commit.stdout.raw').open('xb') as stdout,(out/'commit.stderr.raw').open('xb') as stderr:
    child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW);code=child.wait()
assert code==0 and not git(r,'status','--porcelain')
head=git(r,'rev-parse','HEAD').decode().strip();tree=git(r,'rev-parse','HEAD^{tree}').decode().strip()
assert git(r,'rev-parse','HEAD^').decode().strip()==parent
assert set(git(r,'diff','--name-only',parent,head).decode().splitlines())==set(paths)
assert old_state()==before_old
preflight=out/'source-preflight.raw'
checker_path=r/'specs/poc/check_program.py'
assert hashlib.sha256(checker_path.read_bytes()).hexdigest()=='ee53ccf38e80095fd77ded709aa5dba7808d011a6346e864cd1a9f6482be8cc8'
spec=importlib.util.spec_from_file_location('profile_prefix_frozen_source_preflight',checker_path)
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
execution_ref=prefix+'/attempt-011/execution-candidate.json'
execution=read(r/execution_ref)
configuration=read(r/execution['environmentCaptured']['acceptanceProfileConfigurationRef'])
assert configuration['testedSource']==execution['environmentCaptured']['testedSource']
plan=yaml.safe_load((r/'specs/poc/plans/POC-005.yaml').read_text(encoding='utf-8'))
defs=yaml.safe_load((r/'specs/poc/program.schema.yaml').read_text(encoding='utf-8'))['$defs']
errors=[];checker.validate_qualified_source(r,plan,execution,configuration,defs,prefix,errors,{execution_ref})
with preflight.open('x',encoding='utf-8',newline='\n') as f:
    f.write('Source Commit: '+head+'\nCommand: complete unchanged validate_qualified_source, exact recorded configuration/defs\n')
    for error in errors:f.write(str(error)+'\n')
    f.write('Exit Code: '+str(1 if errors else 0)+'\n')
new_bundle=t/('poc005-attempt011-profile-prefix-'+head[:7]+'.bundle');assert not new_bundle.exists()
git(r,'bundle','create',str(new_bundle),branch)
record=dict(kind='ACTUAL_PROFILE_PREFIX_ONLY_CANDIDATE_NOT_COMPLETE_FORMAL_RESULT',parent=parent,head=head,tree=tree,
    branch=branch,repo=str(r),paths=paths,clonePid=clone_pid,cloneExitCode=clone_code,cloneActualWaitCompleted=True,
    commitPid=child.pid,commitExitCode=code,commitActualWaitCompleted=True,rawBytesEqualStagedBlobs=True,
    protectedUnchangedPins={p:pin((r/p).read_bytes()) for p in protected},oldAuthorBefore=before_old,oldAuthorAfter=old_state(),
    currentReport=(terminal/'report-v3.md').relative_to(r).as_posix(),currentReportPin=pin(new_report),
    sourcePreflightExitCode=1 if errors else 0,sourcePreflightErrors=errors,sourcePreflightPin=pin(preflight.read_bytes()),
    bundle=str(new_bundle),bundlePin=pin(new_bundle.read_bytes()),formalProfileValidated=False,
    reportRelocationIndependentlyAccepted=False,published=False,taskCompleted=False)
with (out/'results.json').open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert not errors and not git(r,'status','--porcelain')
print(json.dumps({k:record[k] for k in ('head','tree','repo','currentReportPin','sourcePreflightExitCode','formalProfileValidated')}),flush=True)

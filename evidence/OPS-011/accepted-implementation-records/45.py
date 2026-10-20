"""Six commands for the actual PR111 implementation merge; no full-suite repeat."""
import argparse, hashlib, importlib.util, json, os, re, shlex, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import yaml

T = "16c5ccbde7e4af8972afc45dc53203d45546cf65"
BASE = "39afaf007d800bab43d7703ac082df2bbc7e8e87"
SOURCE = "1c077f7eefe76c1452f9362229730ee2ccf19404"
PARENT = "b42e5c8900ae3f39ec9f63762111185594455fb2"
IMPLEMENTATION = "chore/OPS-011-agent-edge-104-scope"
PYTHON = "/home/sur/.cache/guize-takeover/governance-venv/bin/python"
PRIMARY = Path(__file__).resolve().parents[1] / "Guize"
NATIVE_LAYOUTS = {
    "legacy-main": (Path("/home/sur/.cache/guize-takeover/eight-follow-up-265001d"), "/home/sur/.cache/guize-takeover/eleven-follow-up-62a246d"),
    "implementation-verifier": (Path("/home/sur/.cache/guize-takeover/ops011-scope-verification-4d38068"), "/home/sur/.cache/guize-takeover/eight-follow-up-265001d"),
}
FIRST_USE = "evidence/OPS-011/agent-edge-104-first-use.json"
FIRST_USE_SHA = "2815479d0d322abc8afdf94e73518f0b9a0fa23fbcc0a5bd39c9e9daaa6017d9"
LEDGER = "specs/coordination/task-completions.yaml"
IDENTITY = """import importlib.util,sys
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
task,reference,merge=sys.argv[1:]
i=load('actual_integrity','scripts/check-program-plan-integrity.py'); h=load('actual_history','scripts/check-program-plan-history.py')
errors=i.commit_identity_errors('.',merge,task,reference,'Actual implementation')
h.validate_commit('.',merge,task,reference,'Actual implementation',errors)
assert not errors,errors
print('PASS: actual implementation Task/PR/merge identity accepted by both existing entries')
"""
def require(value, message):
    if not value: raise RuntimeError(message)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
    with path.open("w",encoding="utf-8",newline="\n") as f: json.dump(value,f,ensure_ascii=False,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("repo","main","tree","base","source","official-merge","official-merge-sha256","output"): p.add_argument("--"+name,required=True)
    p.add_argument("--native-layout", choices=tuple(NATIVE_LAYOUTS), required=True)
    a=p.parse_args(); out=Path(a.output).resolve(); M=a.main; NATIVE, native_origin=NATIVE_LAYOUTS[a.native_layout]
    require(re.fullmatch(r"[0-9a-f]{40}",M) is not None and M not in {BASE,SOURCE,PARENT},"Actual merge SHA must be supplied after PR111 really merges")
    require(sys.platform.startswith("linux") and sys.executable==PYTHON and Path(a.repo).resolve()==NATIVE,"Use the explicitly selected existing native layout/venv")
    require((a.main,a.tree,a.base,a.source)==(M,T,BASE,SOURCE),"Only the published PR111 implementation source/tree/base identities are supported")
    require(Path(a.output).is_absolute() and not out.exists() and all(out!=repo and repo not in out.parents for repo in (PRIMARY,*[row[0] for row in NATIVE_LAYOUTS.values()])) ,"Output must be new, absolute and outside primary/native repos")
    official_raw=Path(a.official_merge).read_bytes(); require(re.fullmatch(r"[0-9a-f]{64}",a.official_merge_sha256) is not None and sha(official_raw)==a.official_merge_sha256,"Actual official merge pin differs"); official=json.loads(official_raw)
    require(official['actualMain']==M and official['tree']==T and official['base']==BASE and official['source']==SOURCE and [x['sha'] for x in official['commit']['parents']]==[BASE,SOURCE],"Official ordered merge identity differs")
    pr=official['pr']; require(pr['number']==111 and pr['merged'] is True and pr['state']=='closed' and pr['merge_commit_sha']==M and pr['head']['sha']==SOURCE and pr['base']['ref']=='main',"PR111 is not actually merged from the published source into main")
    def git(repo,*args):
        prefix=["/mnt/c/Program Files/Git/cmd/git.exe","-C",str(repo).replace('/mnt/c/','C:/')] if repo==PRIMARY else ["git","-C",str(repo)]
        return subprocess.check_output([*prefix,"-c","core.fsmonitor=false","-c","core.untrackedCache=false",*args],env={**os.environ,"GIT_OPTIONAL_LOCKS":"0"})
    def text(repo,*args): return git(repo,*args).decode('utf-8').strip()
    require(text(NATIVE,'show','-s','--format=%P',SOURCE).split()==[PARENT] and text(NATIVE,'rev-parse',SOURCE+'^{tree}')==T,"Published implementation source parent/tree differs")
    original=git(NATIVE,'show',BASE+':evidence/OPS-011/reservation-inputs.json'); require(sha(original)=='1f9f8589d296cd72e012ce580b318aa1837344bba42535a604a7b9d045a33677','Original fifteen-claim input changed')
    claims=json.loads(original)['reservationInputs']['exclusivePaths']+['scripts/check-program-plan-history.py']
    paths=text(NATIVE,'diff','--name-only',BASE,SOURCE).splitlines()
    require(len(paths)==len(set(paths))==175 and all(path.startswith('evidence/OPS-011/') or path in set(claims)|{'specs/coordination/active-work.yaml','specs/tasks/OPS-011.md'} for path in paths),'Published implementation delta must contain exactly 175 claimed/OwnMetadata paths')
    physical_paths=sorted(set(paths)|{FIRST_USE,LEDGER,'specs/tasks/OPS-011.md','specs/coordination/active-work.yaml','specs/coordination/program-plan.yaml'})
    def snapshot():
        result={}
        for name,repo in (('primary',PRIMARY),('native',NATIVE)):
            expected_origin='https://github.com/ElectricDogCN/Guize.git' if name=='primary' else native_origin
            remote=text(repo,'remote','get-url','origin'); push=text(repo,'remote','get-url','--push','origin')
            require(remote==push==expected_origin,'Existing origin topology differs from the explicitly selected layout: '+name)
            live=text(repo,'ls-remote','--heads','origin','refs/heads/main')
            row=dict(path=str(repo),source=text(repo,'rev-parse','HEAD'),tree=text(repo,'rev-parse','HEAD^{tree}'),parents=text(repo,'show','-s','--format=%P','HEAD').split(),branch=text(repo,'branch','--show-current'),main=text(repo,'rev-parse','refs/heads/main'),trackingMain=text(repo,'rev-parse','refs/remotes/origin/main'),origin=remote,pushOrigin=push,liveOriginMain=live,files={},status=text(repo,'status','--porcelain=v1','--untracked-files=all'))
            for path in physical_paths:
                raw=(repo/path).read_bytes(); blob=git(repo,'show',SOURCE+':'+path)
                require(git(repo,'show',M+':'+path)==blob and raw.replace(b'\r\n',b'\n')==blob,'Physical/main/source blob mismatch: '+name+'/'+path)
                row['files'][path]=dict(sha256=sha(raw),canonicalLfSha256=sha(blob),byteCount=len(raw))
            require((row['source'],row['tree'],row['parents'],row['branch'],row['main'],row['status'])==(M,T,[BASE,SOURCE],'main',M,''),'Actual clean main identity differs: '+name); result[name]=row
        return result
    before=snapshot()
    front=yaml.safe_load((NATIVE/'specs/tasks/OPS-011.md').read_text().split('---',2)[1]); active=yaml.safe_load((NATIVE/'specs/coordination/active-work.yaml').read_bytes()); plan=yaml.safe_load((NATIVE/'specs/coordination/program-plan.yaml').read_bytes())
    own=[x for x in active['tasks'] if x['taskId']=='OPS-011']; foundation=[x for x in plan['foundationTasks'] if x['taskId']=='OPS-011']; require(len(own)==len(foundation)==1,'Own implementation metadata missing'); entry=own[0]
    require(front['schemaVersion']==2 and front['id']=='OPS-011' and front['issue']==entry['issue']==108 and front['status']==entry['status']==foundation[0]['status']=='in_progress' and front['agentRole']==entry['agentRole']=='implementer' and front['baseSha']==entry['baseSha']==BASE and front['workBranch']==entry['branch']==IMPLEMENTATION and front['wave']==entry['programWave']=='FOUNDATION','Implementation Task/Registry identity differs')
    require(foundation[0]['completionRef']=='ISSUE-108' and foundation[0]['mergeCommit'] is None,'Implementation Foundation falsely records code completion')
    require(len(entry['exclusivePaths'])==len(set(entry['exclusivePaths']))==16 and set(entry['exclusivePaths'])==set(claims) and entry['sharedPaths']==[],'Exact sixteen claims differ')
    prior_active=yaml.safe_load(git(NATIVE,'show',BASE+':specs/coordination/active-work.yaml')); prior=[row for row in prior_active['tasks'] if row['taskId']=='OPS-011']
    stable=lambda row:{key:value for key,value in row.items() if key not in {'baseSha','status','agentRole'}}
    require(len(prior)==1 and stable(entry)==stable(prior[0]),'Implementation changes stable reservation identity, assigned roles or original lease')
    date=lambda value: datetime.fromisoformat(str(value).replace('Z','+00:00')); acquired,expires=map(date,(entry['lease']['acquiredAt'],entry['lease']['expiresAt']))
    require(acquired.utcoffset()==expires.utcoffset()==timedelta(0) and acquired<=datetime.now(timezone.utc)<expires and timedelta(0)<expires-acquired<=timedelta(hours=168) and date(front['leaseExpiresAt'])==expires,'Actual implementation lease is invalid')
    for path in (FIRST_USE,LEDGER): require(git(NATIVE,'show',M+':'+path)==git(NATIVE,'show',SOURCE+':'+path)==git(NATIVE,'show',BASE+':'+path),'Protected original declaration/Ledger differs: '+path)
    first_raw=git(NATIVE,'show',M+':'+FIRST_USE); require(sha(first_raw)==FIRST_USE_SHA,'First-use declaration differs'); first=json.loads(first_raw)
    boundary,planned,baseline=first['targets']
    require(plan['scopeBoundary']==boundary['after'] and [row for row in plan['tasks'] if row['taskId']=='GZ-022']==[planned['after']] and [row for row in plan['planningBaselines'] if row['id']=='BASELINE-GZ-022']==[baseline['after']],'Original exact three-target planning transaction differs')
    require(set(row['taskId'] for row in plan['tasks'])==set(first['originalV1TaskIds'])|{'GZ-022'} and plan['scopeBoundary']['agentEdge104']['state']=='planning' and planned['after']['status']=='planned' and planned['after']['issue'] is None and baseline['after']['requiredBy']==['POC-003','POC-005'],'Planning-only GZ022 boundary differs')
    require(not any(row['taskId']=='GZ-022' for row in active['tasks']) and not (NATIVE/'specs/tasks/GZ-022.md').exists(),'GZ022 cannot obtain a Task/lease during OPS011 implementation acceptance')
    common=['--base-ref',BASE,'--head-ref',M,'--task','OPS-011','--branch-name','main']
    checks={'identity':['python','-c',IDENTITY,'OPS-011','PR-111',M],'integrity':['python','scripts/check-program-plan-integrity.py','--base-ref',BASE]}
    for label,name in (('history','check-program-plan-history.py'),('transitions','check-program-plan-transitions.py'),('raw-lifecycle','check-program-lifecycle-guards.py'),('coordination','run-agent-coordination-gate.py')): checks[label]=['python','scripts/'+name,*common]
    require(snapshot()==before,'Actual main changed during preflight')
    out.mkdir(parents=True,exist_ok=False); save(out/'execution-entry.json',dict(kind='OPS011_IMPLEMENTATION_ACTUAL_MAIN_SIX_ENTRY',actualMain=M,tree=T,orderedParents=[BASE,SOURCE],base=BASE,source=SOURCE,sourceParent=PARENT,prNumber=111,nativeLayout=a.native_layout,pid=os.getpid(),argv=[sys.executable,*sys.argv],startedAt=utc(),scriptSha256=sha(Path(__file__).read_bytes()),officialMergeSha256=sha(official_raw),lease=entry['lease'],status='in_progress',agentRole='implementer',taskImplementationBranch=IMPLEMENTATION,firstUseSha256=FIRST_USE_SHA,before=before,checks=checks,sourceExecutionNotTransferred=True))
    os.environ.update(PATH=str(Path(PYTHON).parent)+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',GITHUB_REPOSITORY='ElectricDogCN/Guize',GITHUB_HEAD_REF='main'); status={}; executions=[]
    for label,argv in checks.items():
        rawpath=out/(label+'.txt'); row=dict(label=label,argv=argv,cwd=str(NATIVE),startedAt=utc(),rawLog=rawpath.name)
        with rawpath.open('x',encoding='utf-8',buffering=1) as log:
            log.write('Source Commit: '+M+'\nCommand: '+shlex.join(argv)+'\n'); log.flush(); os.fsync(log.fileno())
            child=subprocess.Popen(argv,cwd=NATIVE,stdout=log,stderr=subprocess.STDOUT,text=True); row['pid']=child.pid; executions.append(row); save(out/'command-executions.json',executions)
            code=child.wait(); row.update(exitCode=code,waitCompleted=True,completedAt=utc()); log.write('\nExit Code: '+str(code)+'\n'); log.flush(); os.fsync(log.fileno())
        raw=rawpath.read_bytes(); row.update(rawSha256=sha(raw),rawByteCount=len(raw)); status[label]=code; save(out/'command-executions.json',executions); save(out/'status.json',status); print(label+': exit '+str(code),flush=True)
        if code: save(out/'failed-gate-worktrees.json',dict(actualMain=M,tree=T,failedGate=label,exitCode=code,before=before,after=snapshot(),requiredMainSixPassed=False)); return code
    after=snapshot(); require(before==after and len(status)==6 and set(status.values())=={0},'Main files changed or six commands incomplete')
    save(out/'verification-worktrees.json',dict(kind='OPS011_IMPLEMENTATION_ACTUAL_MAIN_SIX_IDENTITY_LIFECYCLE',actualMain=M,tree=T,orderedParents=[BASE,SOURCE],base=BASE,source=SOURCE,sourceParent=PARENT,prNumber=111,nativeLayout=a.native_layout,before=before,after=after,allCleanBeforeAndAfter=True,checks=status,commandExecutions=executions,requiredMainSixPassed=True,localFullSuiteRepeated=False,sourceExecutionNotTransferred=True,currentMainCiAccepted=False,actualMainAccepted=False,formalSourceAccepted=False,runtimeAccepted=False,fullV1Complete=False)); print('Actual implementation main six passed; actual main CI and independent acceptance remain pending.',flush=True)
    return 0
if __name__=='__main__': raise SystemExit(main())

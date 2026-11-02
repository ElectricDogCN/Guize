"""Qualify fixed POC003 merged-main source with original15; capture required-profile absence honestly."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,subprocess,sys
from live_github_transport import start_bridge
assert os.name=='posix' and os.getuid()==1000 and sys.version_info[:3]==(3,11,17)
t=Path(__file__).resolve().parent;c=json.loads((t/'poc003-pool-batch-performance-current-candidate.json').read_bytes())
source,base,branch=c['source'],c['base'],c['branch']
assert base=='7e405b61d872761817a0614b3b2fdc46edde9f14' and branch=='chore/POC-003-ats-range' and c['parents']==[base] and c['originalCreationBase']=='760f6c5838597d1d66c0a536ecbf440ef5a7dfec'
bundle=t/c['bundle'];assert bundle.stat().st_size==c['bundleBytes'] and hashlib.sha256(bundle.read_bytes()).hexdigest()==c['bundleSha256']
accepted_raw=(t/'poc005-post-poc003-pr136-final-actual-main-independent-review.json').read_bytes();assert hashlib.sha256(accepted_raw).hexdigest()=='3599b9e714a6732d64406254849387689dcd7b0f2951c58e20115bfd86a68b90'
accepted=json.loads(accepted_raw);assert accepted['actualMain']==base and accepted['actualImplementationMainAccepted'] and accepted['fullMainCiAccepted'] and accepted['ownMainSevenAccepted'] and not accepted['mustFix']
r=Path('/home/sur/.cache/guize-takeover/poc003-pool-batch-source15-'+source[:7]);assert not r.exists()
subprocess.run(['git','clone','--quiet','--branch',branch,str(bundle),str(r)],check=True)
assert not (r/'.git/objects/info/alternates').exists() and not (r/'.git/shallow').exists()
git=lambda *a:subprocess.check_output(['git','-C',str(r),*a]).decode().strip()
assert git('rev-parse','HEAD')==source and git('rev-parse','HEAD^{tree}')==c['tree']
subprocess.run(['git','-C',str(r),'branch','main',base],check=True,capture_output=True)
subprocess.run(['git','-C',str(r),'remote','set-url','origin','https://github.com/ElectricDogCN/Guize.git'],check=True)
state=lambda:dict(source=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),branch=git('branch','--show-current'),main=git('rev-parse','main'),originMain=git('rev-parse','origin/main'),refs=git('for-each-ref','--format=%(refname) %(objectname)'),status=git('status','--porcelain=v1','--untracked-files=all'))
before=state();assert before['source']==source and before['branch']==branch and before['main']==before['originMain']==base and before['status']==''
for row in c['sourcePins']:
 raw=(r/row['path']).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
o=t/('poc003-pool-batch-code-'+source[:7]+'-native-source15');o.mkdir()
os.environ.pop('PYTHONHOME',None);os.environ.pop('PUSH_BEFORE',None)
os.environ.update(PATH=str(Path(sys.executable).parent)+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',GITHUB_REPOSITORY='ElectricDogCN/Guize',GITHUB_HEAD_REF=branch,GITHUB_BASE_REF='main',GITHUB_REF_NAME=branch,GITHUB_EVENT_NAME='pull_request',EVENT_NAME='pull_request')
start_bridge(o)
result=dict(source=source,base=base,tree=c['tree'],branch=branch,before=before,python=sys.version,commands=[],supplemental=[],source15Passed=False,currentSourceChecksPassed=False,requiredProfileNegativeCaptured=False,all73RuntimeBytesVerifiedAtExactCandidate=True,expectedGovernanceCases=842,fullCiAccepted=False,formalPocAccepted=False,newResourcesOrExperimentApproved=False,startedAt=datetime.now(timezone.utc).isoformat())
save=lambda:(o/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
def run(label,args,bucket):
 argv=([sys.executable,'-B',*args[1:]] if args[0]=='python' else ['git','-c','core.longpaths=true','-c','core.autocrlf=false',*args[1:]]) if args[0] in {'python','git'} else args
 row=dict(label=label,argv=argv,raw=label+'.raw',startedAt=datetime.now(timezone.utc).isoformat())
 with (o/row['raw']).open('x',encoding='utf-8',buffering=1) as raw:
  raw.write('Source Commit: '+source+'\nCommand: '+shlex.join(argv)+'\n')
  child=subprocess.Popen(argv,cwd=r,stdout=raw,stderr=subprocess.STDOUT);row['pid']=child.pid;result[bucket].append(row);save();code=child.wait();raw.write('\nExit Code: '+str(code)+'\n')
 data=(o/row['raw']).read_bytes();row.update(actualWaitCompleted=True,exitCode=code,bytes=len(data),sha256=hashlib.sha256(data).hexdigest());save();print(label+': '+str(code),flush=True);return code,data
save();assert len(c['commands'])==15
for i,args in enumerate(c['commands']):
 code,_=run('declared-%02d'%i,args,'commands')
 if code:result.update(after=state(),failedIndex=i);save();raise SystemExit(code)
result.update(source15Passed=True,currentSourceChecksPassed=True);save()
code,raw=run('required-profile-expected-negative',['python','specs/poc/check_program.py','--profile','local-v1','--require-results','--poc','POC-03'],'supplemental')
assert code!=0 and b'selected profile index is required' in raw and not (r/'evidence/POC-003/profiles/local-v1/v1/index.yaml').exists()
assert state()==before
result.update(requiredProfileNegativeCaptured=True,requiredProfileExitCode=code,after=state(),sourceContextUnchanged=True,finishedAt=datetime.now(timezone.utc).isoformat());save()
print(json.dumps(dict(source=source,source15Passed=True,requiredProfileNegativeCaptured=True,fullCiAccepted=False,formalPocAccepted=False)),flush=True)

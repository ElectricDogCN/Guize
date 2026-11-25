"""Capture fresh real host/backing plus waiting native state; never create approval."""
import base64,hashlib,json,subprocess,sys
from pathlib import Path
from poc005_full_execution_assembler_023_v1 import build_environment_summaries

T=Path(__file__).resolve().parent;OUT=T/'poc005-attempt023-before-release-capture-v1'
assert not OUT.exists();OUT.mkdir()
prefix=['wsl.exe','--distribution','Guize-Poc005-Neutral-81348fd-v1','--user','guize','--exec','/usr/bin/env',
    'HOME=/work/home','TMPDIR=/work/tmp','PYTHONDONTWRITEBYTECODE=1','PYTHONUTF8=1','GIT_LFS_SKIP_SMUDGE=1','/usr/local/bin/python3.11','-B']
commands=[]
def run(label,argv,data=None):
    p=subprocess.Popen(argv,stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:stdout,stderr=p.communicate(input=data,timeout=90)
    except subprocess.TimeoutExpired:p.kill();p.communicate();raise
    (OUT/(label+'.stdout')).write_bytes(stdout);(OUT/(label+'.stderr')).write_bytes(stderr)
    commands.append(dict(label=label,argv=argv,pid=p.pid,actualWaitCompleted=True,exitCode=p.returncode,stdoutSha256=hashlib.sha256(stdout).hexdigest(),stderrSha256=hashlib.sha256(stderr).hexdigest()))
    (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8');assert p.returncode==0,label+' failed; all outputs retained'
    return stdout
hostdir=T/'poc005-attempt023-actual-before-release-host-v1'
run('fresh-host',[sys.executable,str(T/'capture_poc005_attempt022_host_facts_v1_once.py'),'--output-dir',str(hostdir)])
payload={target:dict(base64=base64.b64encode((hostdir/source).read_bytes()).decode(),sha256=hashlib.sha256((hostdir/source).read_bytes()).hexdigest()) for target,source in
    [('host-observation-before.json','host-observation.json'),('backing-observation-before.json','backing-observation.json')]}
transfer="import base64,hashlib,json,sys;from pathlib import Path;d=Path('/work/Guize-attempt023/evidence/POC-005/profiles/local-v1/v1/attempt-023');assert not (d/'independent-approval.json').exists();v=json.load(sys.stdin);\nfor name,row in v.items():\n assert '/' not in name and '\\\\' not in name;raw=base64.b64decode(row['base64']);assert hashlib.sha256(raw).hexdigest()==row['sha256'];p=d/name;f=p.open('xb');f.write(raw);f.close()"
run('host-facts-materialization',[*prefix,'-c',transfer],json.dumps(payload).encode())
run('actual-preflight',[*prefix,'/work/Guize-attempt023/evidence/POC-005/profiles/local-v1/v1/attempt-023/tools/capture_poc005_attempt023_full_preflight_v1.py','--root','/work/Guize-attempt023'])
files=['approval-request.json','runtime.json','resource.json','openlist-resource.json','profile-configuration.json','sample-approval.json',
    'before-environment.json','controller-launch.json','native-manifest.json','template-materialization.json','template-bound-draft.json',
    'template-independent-decision.json','fixed-inputs-materialized.json','host-observation-before.json','backing-observation-before.json',
    'selected-linux-mounts-before.raw']
reader="import base64,hashlib,json;from pathlib import Path;d=Path('/work/Guize-attempt023/evidence/POC-005/profiles/local-v1/v1/attempt-023');names="+repr(files)+";print(json.dumps({n:{'base64':base64.b64encode((d/n).read_bytes()).decode(),'sha256':hashlib.sha256((d/n).read_bytes()).hexdigest(),'bytes':(d/n).stat().st_size} for n in names}))"
records=json.loads(run('control-record-readback',[*prefix,'-c',reader]))
(OUT/'controls').mkdir()
for name,row in records.items():
    raw=base64.b64decode(row['base64']);assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
    (OUT/'controls'/name).write_bytes(raw)
before_name='before-environment.json'
before_bytes=(OUT/'controls'/before_name).read_bytes()
before_digest=records[before_name]['sha256']
before_ref='evidence/POC-005/profiles/local-v1/v1/attempt-023/'+before_name
projection=build_environment_summaries(json.loads(before_bytes),before_ref,before_digest)
projection_bytes=(json.dumps(projection,sort_keys=True,indent=2)+'\n').encode()
with (OUT/'controls'/'environment-summary.json').open('xb') as stream:
    stream.write(projection_bytes)
method=OUT/'controls'/'template-materialization.json'
assembler=json.loads(method.read_bytes())['assemblyMethod']
assembler_path=T/'poc005_full_execution_assembler_023_v1.py'
assert assembler['byteCount']==assembler_path.stat().st_size
assert assembler['sha256']=='sha256:'+hashlib.sha256(assembler_path.read_bytes()).hexdigest()
result=dict(kind='ACTUAL_PRE_RELEASE_CONTROL_CAPTURE',records={k:{p:v for p,v in row.items() if p!='base64'} for k,row in records.items()},
    environmentSummary=dict(bytes=len(projection_bytes),sha256=hashlib.sha256(projection_bytes).hexdigest(),
                            rawRef=before_ref,rawSha256=before_digest,assemblyMethod=assembler),
    scannerReservationCreatedEarlier=True,sourceRequestsSent=False,actualReleaseApproved=False,qualificationAccepted=False)
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(actualPreflightCaptured=True,controls=len(records),sourceRequestsSent=False,actualReleaseApproved=False)))

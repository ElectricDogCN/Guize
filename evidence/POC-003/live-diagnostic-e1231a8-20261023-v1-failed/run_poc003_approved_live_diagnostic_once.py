"""One new finite sandbox, only after a concrete independent before-run receipt."""
import hashlib,json,os,signal,socket,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
t=Path(__file__).resolve().parent;r=Path('/home/sur/.cache/guize-takeover/ops012-history-parser')
proposal=t/'poc003-live-diagnostic-proposal-v1.json'
approval=t/'poc003-live-diagnostic-independent-approval-v1.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc)
def instant(text):return datetime.fromisoformat(text.replace('Z','+00:00'))
def git(*args):return subprocess.check_output(['git','-C',str(r),*args],text=True).strip()
p=json.loads(proposal.read_bytes());a=json.loads(approval.read_bytes())
assert os.name=='posix' and os.geteuid()==1000
assert a['decision']=='approved' and a['approver']=='independent-review-agent' and a['mustFix']==[]
assert a['proposalSha256']==sha(proposal) and a['configSha256']==sha(Path(p['configPath']))
assert a['testedSource']==p['testedSource'] and a['executionScope']==p['executionScope']
assert git('rev-parse','HEAD')==p['testedSource']['commit'] and git('rev-parse','HEAD^{tree}')==p['testedSource']['tree'] and not git('status','--porcelain')
assert sha(Path(__file__))==p['runnerSha256'] and sha(Path(p['collectorPath']))==p['collectorSha256']
deadline=instant(a['validUntil'])
assert instant(a['approvedAt'])<=now() and instant(a['validFrom'])<=now()<deadline and (deadline-now()).total_seconds()>250
for row in p['samples']:assert Path(row['path']).stat().st_size==row['sizeBytes'] and sha(Path(row['path']))==row['sha256']
run=Path(p['runDir']);raw=Path(p['rawOutputDir']);audit=t/'poc003-live-diagnostic-v1-execution'
assert not any(path.exists() for path in (run,raw,audit));audit.mkdir()
def ports():
 rows=[]
 for port in (18231,18232,18233):
  with socket.socket() as sock:sock.settimeout(.2);rows.append(dict(port=port,listening=sock.connect_ex(('127.0.0.1',port))==0))
 return rows
record=dict(source=p['testedSource'],proposalSha256=sha(proposal),approvalSha256=sha(approval),startedAt=now().isoformat(),commands=[],portsBefore=ports(),fullMediaBufferBoundProven=False,original15Accepted=False)
assert not any(row['listening'] for row in record['portsBefore'])
def save():(audit/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
def budget(ceiling,reserve=40):
 remaining=stop_at-time.monotonic()-reserve
 if remaining<=0:raise TimeoutError('overall diagnostic deadline cleanup reserve reached')
 return min(ceiling,remaining)
def execute(argv,label,timeout):
 timeout=budget(timeout)
 with (audit/(label+'.stdout.raw')).open('xb') as out,(audit/(label+'.stderr.raw')).open('xb') as err:
  process=subprocess.Popen(argv,cwd=r,stdout=out,stderr=err,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  try:process.wait(timeout=timeout)
  except subprocess.TimeoutExpired:process.kill();process.wait(timeout=budget(5,35));record[label+'TimedOut']=True
 record['commands'].append(dict(argv=argv,exitCode=process.returncode,waitCompleted=True));save();return process.returncode
controller=None;streams=[];started=time.monotonic();stop_at=started+240;save()
try:
 assert execute([sys.executable,'-B','poc/POC-03-ats-range/lab.py','prepare','--config',p['configPath'],'--run-dir',str(run)],'prepare',30)==0
 streams=[(audit/'controller.stdout.raw').open('xb'),(audit/'controller.stderr.raw').open('xb')]
 controller=subprocess.Popen([sys.executable,'-B','poc/POC-03-ats-range/lab.py','serve','--run-dir',str(run)],cwd=r,stdout=streams[0],stderr=streams[1],start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 record['controllerPid']=controller.pid;save();ready=time.monotonic()+budget(20)
 while not (run/'listeners-started.json').exists() and time.monotonic()<ready:
  if controller.poll() is not None:raise RuntimeError('controller failed before native cache readiness')
  time.sleep(.1)
 assert (run/'listeners-started.json').exists(),'readiness deadline'
 record['initialListeners']=json.loads((run/'listeners-started.json').read_bytes());save()
 record['experimentExitCode']=execute([sys.executable,'-B',p['collectorPath'],str(proposal)],'experiment',90)
finally:
 if controller is not None:
  if controller.poll() is None:controller.send_signal(signal.SIGINT)
  try:controller.wait(timeout=min(20,max(.001,stop_at-time.monotonic()-10)))
  except subprocess.TimeoutExpired:
   record['forcedOwnedStop']=True;os.killpg(controller.pid,signal.SIGTERM)
   try:controller.wait(timeout=min(5,max(.001,stop_at-time.monotonic()-5)))
   except subprocess.TimeoutExpired:os.killpg(controller.pid,signal.SIGKILL);controller.wait(timeout=min(5,max(.001,stop_at-time.monotonic())))
  record['controllerExitCode']=controller.returncode
 for stream in streams:stream.close()
 rows=[json.loads(line) for line in (run/'controller.jsonl').read_text().splitlines()] if (run/'controller.jsonl').exists() else []
 children={row['pid'] for row in rows if row.get('action')=='ats-start'}
 record.update(ownedAtsPids=sorted(children),ownedAtsGone=all(not Path('/proc',str(pid)).exists() for pid in children),
  portsAfter=ports(),finishedAt=now().isoformat(),elapsedSeconds=time.monotonic()-started,insideApprovalWindow=now()<deadline)
 record['portsReleased']=not any(row['listening'] for row in record['portsAfter'])
 record['rawBytes']=sum(path.stat().st_size for path in raw.rglob('*') if path.is_file()) if raw.exists() else 0
 save();print(json.dumps({key:record.get(key) for key in ['experimentExitCode','controllerExitCode','elapsedSeconds','ownedAtsGone','portsReleased','insideApprovalWindow','rawBytes']}),flush=True)
assert record['insideApprovalWindow'] and record['elapsedSeconds']<=240 and record['rawBytes']<=536870912
assert record['ownedAtsGone'] and record['portsReleased']
raise SystemExit(0 if record.get('experimentExitCode')==0 and record.get('controllerExitCode')==0 else 1)

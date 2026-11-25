"""Read-only clock observer with Windows deadline and only-own native cleanup."""
import hashlib,json,os,queue,secrets,subprocess,threading,time
from datetime import datetime,timezone
from pathlib import Path
T=Path(__file__).resolve().parent
OUT=T/'poc005-attempt023-clock-stability-v1'
assert os.name=='nt' and not OUT.exists()
OUT.mkdir();nonce='guize-clock-'+secrets.token_hex(16)
code="""import json,os,sys,time
from pathlib import Path
p=Path('/proc/self')
s=(p/'stat').read_text();start=s[s.rfind(')')+2:].split()[19]
print(json.dumps(dict(kind='owned_identity',pid=os.getpid(),startTicks=start,bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),nonce=sys.argv[-1])),flush=True)
for i in range(3601):
 a=time.monotonic_ns();w=time.time_ns();b=time.monotonic_ns();r=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
 print(json.dumps(dict(sequence=i,monotonicBeforeNs=a,utcNs=w,monotonicAfterNs=b,monotonicRawNs=r)),flush=True)
 time.sleep(.05)
"""
base=['wsl.exe','--distribution','Guize-Poc005-Neutral-81348fd-v1','--user','guize','--exec','/usr/local/bin/python3.11','-B','-c']
events=queue.Queue();identity=None;count=0;jumps=[];previous=None;failure=None;cleanup=None
began=datetime.now(timezone.utc);tick=time.perf_counter()
error=(OUT/'guest.stderr').open('xb')
p=subprocess.Popen(base+[code,nonce],stdout=subprocess.PIPE,stderr=error,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
def read():
 try:
  for line in p.stdout:events.put((line,time.time_ns(),time.perf_counter_ns()))
 except Exception as e:events.put(('reader-error',repr(e),None))
 finally:events.put(None)
reader=threading.Thread(target=read,daemon=True);reader.start()
try:
 with (OUT/'samples.jsonl').open('xb') as raw:
  while True:
   assert time.perf_counter()-tick<230,'Windows QPC deadline'
   try:item=events.get(timeout=.1)
   except queue.Empty:continue
   if item is None:break
   line,win_utc,win_perf=item
   assert line!='reader-error',str(win_utc)
   (OUT/'guest.raw').open('ab').write(line)
   v=json.loads(line)
   if v.get('kind')=='owned_identity':
    assert identity is None and v['nonce']==nonce;identity=v
    (OUT/'identity.json').write_text(json.dumps(v,indent=2)+'\n');continue
   assert identity and v['sequence']==count
   row=dict(guest=v,windowsUtcAtReceiveNs=win_utc,windowsPerfAtReceiveNs=win_perf)
   raw.write((json.dumps(row,separators=(',',':'))+'\n').encode());raw.flush();count+=1
   if previous:
    g=previous['guest'];delta=v['utcNs']-g['utcNs'];md=((v['monotonicBeforeNs']+v['monotonicAfterNs'])-(g['monotonicBeforeNs']+g['monotonicAfterNs']))//2
    if delta<0 or abs(delta-md)>10000000:jumps.append(dict(sequence=v['sequence'],guestUtcDeltaNs=delta,guestMonotonicDeltaNs=md,guestUtcOffsetStepNs=delta-md))
   previous=row
 p.wait(timeout=10);reader.join(timeout=2)
 assert p.returncode==0 and count==3601
except BaseException as e:
 failure=repr(e)
 # Match only this unpredictable final argv token; no other guest process qualifies.
 cleanup_code="""import json,os,signal,time
from pathlib import Path
nonce=NONCE
matches=[]
for d in Path('/proc').iterdir():
 if d.name.isdigit():
  try:
   args=(d/'cmdline').read_bytes().rstrip(b'\\0').split(b'\\0')
   if args and args[-1]==nonce.encode():matches.append(int(d.name))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert len(matches)<=1
for pid in matches:os.kill(pid,signal.SIGTERM)
deadline=time.clock_gettime(time.CLOCK_MONOTONIC_RAW)+10
while matches and time.clock_gettime(time.CLOCK_MONOTONIC_RAW)<deadline:
 try:
  s=Path('/proc/%s/stat'%matches[0]).read_text();state=s[s.rfind(')')+2:].split()[0]
  if state=='Z':break
 except FileNotFoundError:break
 time.sleep(.05)
else:
 assert not matches,'only-own native sampler did not terminate'
print(json.dumps(dict(nonce=nonce,matched=matches,onlyOwnSamplerTerminatedOrAlreadyExited=True)))
""".replace('NONCE',repr(nonce))
 c=subprocess.run(base+[cleanup_code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
 (OUT/'cleanup.stdout').write_bytes(c.stdout);(OUT/'cleanup.stderr').write_bytes(c.stderr)
 cleanup=dict(exitCode=c.returncode,actualWaitCompleted=True)
 assert c.returncode==0,'Native cleanup unconfirmed; observation invalid'
 p.wait(timeout=15);reader.join(timeout=2)
finally:
 error.close()
 result=dict(kind='ACTUAL_CLOCK_DIAGNOSTIC_ONLY',startedAt=began.isoformat(),finishedAt=datetime.now(timezone.utc).isoformat(),frontendPid=p.pid,frontendExitCode=p.returncode,actualWaitCompleted=p.returncode is not None,identity=identity,samples=count,discontinuities=jumps,failure=failure,cleanup=cleanup,sourceApiContacted=False,scannerExperimentExecuted=False,qualificationAccepted=False)
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
assert failure is None,failure
print(json.dumps(dict(observationCompleted=True,samples=count,discontinuities=len(jumps))),flush=True)

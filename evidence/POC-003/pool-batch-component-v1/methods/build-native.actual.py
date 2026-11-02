"""Prepare exact upstream+Ubuntu patches in a new ordinary-user build directory."""
import hashlib,json,os,subprocess,tarfile
from pathlib import Path
t=Path(__file__).resolve().parent
archives=t.parent/'local-lab/ats-buffer-domain-ubuntu-source-9.2.3'
out=Path('/home/sur/.cache/guize-takeover/poc003-pool-batch-ats-build-common7e-v1')
assert os.geteuid()==1000 and not out.exists();out.mkdir(mode=0o700)
orig=archives/'trafficserver_9.2.3+ds.orig.tar.xz'
assert hashlib.sha256(orig.read_bytes()).hexdigest()=='0e323e1c4c01d1506cfd49d4c6935dbebd125b187d9ba72fe909bd6b10d81110'
with tarfile.open(orig) as tar:
 members=tar.getmembers();assert len(members)<20000 and sum(m.size for m in members)<256*1048576
 tar.extractall(out/'source',filter='data')
src=out/'source/trafficserver-9.2.3';assert (src/'configure').is_file()
reference_raw=Path('/home/sur/.cache/guize-takeover/poc003-durable-ats-build-20261026-v3/source-preparation.json').read_bytes()
assert hashlib.sha256(reference_raw).hexdigest()=='4fdd78a4247ce7d898690351aca4bce5c1f6832a4c38f59ebc31da0663deffd6'
reference=json.loads(reference_raw)
assert reference['sourceArchiveSha256']==hashlib.sha256(orig.read_bytes()).hexdigest()
patchroot=archives/'debian-source-text/debian/patches';series=(patchroot/'series').read_text().splitlines()
rows=[]
for name in series:
 if not name.strip() or name.startswith('#'):continue
 patch=patchroot/name.strip();data=patch.read_bytes()
 result=subprocess.run(['patch','--batch','-p1','-i',str(patch)],cwd=src,capture_output=True)
 (out/(name+'.stdout.raw')).write_bytes(result.stdout);(out/(name+'.stderr.raw')).write_bytes(result.stderr)
 rows.append(dict(file=name,sha256=hashlib.sha256(data).hexdigest(),exitCode=result.returncode))
 assert result.returncode==0,name
assert rows==reference['patches'],'Exact original upstream Ubuntu patch series required'
result=subprocess.run([str(src/'configure'),'--help'],cwd=src,capture_output=True,timeout=15)
(out/'configure-help.raw').write_bytes(result.stdout+result.stderr);assert result.returncode==0
record=dict(kind='EXACT_SOURCE_PREPARED_ONLY_NOT_RUNTIME',uid=os.geteuid(),sourceArchiveSha256=hashlib.sha256(orig.read_bytes()).hexdigest(),sourceRoot=str(src),patches=rows,atsStarted=False,instrumentationApplied=False,experimentExecuted=False)
(out/'source-preparation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))

"""Compile the exact task-owned diagnostic ATS source as an ordinary user only."""
import hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
t=Path(__file__).resolve().parent
own=t/'poc003-pool-batch-performance-v1/poc/POC-03-ats-range/instrumentation'
root=Path('/home/sur/.cache/guize-takeover/poc003-pool-batch-ats-build-common7e-v1')
src=root/'source/trafficserver-9.2.3';out=root/'compile-v1';pkg=root/'pkgroot'
assert os.geteuid()==1000 and not out.exists() and not pkg.exists()
manifest_raw=(own/'patch-manifest.json').read_bytes()
assert hashlib.sha256(manifest_raw).hexdigest()=='35a018339cc0bf54a2fc91cf518a787e1ecf1f4a63d9ce91d155b328ba43ef40'
m=json.loads(manifest_raw)
assert m['patchSha256']=='590f7a4bc9a044cbc6321ae1b1e20462aee681c0b122d6518dc2c1c9fcb072bf'
assert m['payloadPoolBatchPolicy']['requestedElementsPerGrowth']==1
assert m['payloadPoolBatchPolicy']['maximumBufferedBytesAcceptanceThreshold']==8388608
assert hashlib.sha256((own/'ats-live-buffer-accounting.patch').read_bytes()).hexdigest()==m['patchSha256']
for row in m['files']:assert hashlib.sha256((src/row['path']).read_bytes()).hexdigest()==row['beforeSha256']
applied=subprocess.run(['git','apply','--check',str(own/'ats-live-buffer-accounting.patch')],cwd=src,capture_output=True)
(root/'instrumentation-check.raw').write_bytes(applied.stdout+applied.stderr);assert applied.returncode==0
applied=subprocess.run(['git','apply',str(own/'ats-live-buffer-accounting.patch')],cwd=src,capture_output=True)
(root/'instrumentation-apply.raw').write_bytes(applied.stdout+applied.stderr);assert applied.returncode==0
for item in m['additionalHeaders']:
 raw=(own/item['source']).read_bytes();assert hashlib.sha256(raw).hexdigest()==item['sha256']
 (src/item['installed']).write_bytes(raw)
for row in m['files']:assert hashlib.sha256((src/row['path']).read_bytes()).hexdigest()==row['afterSha256']
assert hashlib.sha256((src/'include/tscore/GuizeLiveBufferAccounting.h').read_bytes()).hexdigest()==m['additionalHeaderSha256']
out.mkdir();env=dict(os.environ,CFLAGS='-O2 -g0',CXXFLAGS='-O2 -g0',PYTHONDONTWRITEBYTECODE='1')
record=dict(kind='INSTRUMENTED_ATS_NATIVE_BUILD_NOT_RUNTIME_EXPERIMENT',uid=os.geteuid(),startedAt=datetime.now(timezone.utc).isoformat(),
 buildPurpose='Fresh ordinary-user performance candidate build. Only ioBufAllocator growth request is one element; previous sources/builds retained unchanged. Existing complete retained-plus-logical accounting remains. No ATS service or media experiment.',
 sourcePreparation=json.loads((root/'source-preparation.json').read_bytes()),instrumentation=m,commands=[],atsStarted=False,experimentExecuted=False)
def save():(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
def process_stat(pid):
 fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=pid,state=fields[0],processGroupId=int(fields[2]),sessionId=int(fields[3]),startTicks=int(fields[19]))
def owned_group_members(group):
 members=[]
 for entry in Path('/proc').iterdir():
  if not entry.name.isdecimal():continue
  try:row=process_stat(int(entry.name))
  except (FileNotFoundError,ProcessLookupError,PermissionError):continue
  if row['processGroupId']==group and row['sessionId']==group:
   members.append(row)
 return sorted(members,key=lambda row:row['pid'])
def stop_timed_out_group(child,birth):
 """Keep the unreaped session leader as a birth anchor through group cleanup."""
 import signal
 cleanup=dict(before=owned_group_members(child.pid),signals=[],groupHadLiveMembers=True)
 def send(sig):
  current=process_stat(child.pid)
  assert all(current[key]==birth[key] for key in ('pid','processGroupId','sessionId','startTicks'))
  # No poll/wait has reaped this direct child since TimeoutExpired. Even an
  # exited zombie leader reserves its identity while we signal its group.
  os.killpg(child.pid,sig);cleanup['signals'].append(int(sig))
 def await_no_live(seconds):
  deadline=time.monotonic()+seconds
  while True:
   rows=owned_group_members(child.pid)
   if not any(row['state'] not in ('Z','X') for row in rows):return rows
   if time.monotonic()>=deadline:return rows
   time.sleep(.05)
 send(signal.SIGTERM);remaining=await_no_live(10)
 if any(row['state'] not in ('Z','X') for row in remaining):
  send(signal.SIGKILL);remaining=await_no_live(5)
 cleanup.update(after=remaining,groupHasNoLiveMembers=not any(row['state'] not in ('Z','X') for row in remaining),
                leaderExitCode=child.wait(timeout=5),leaderWaitCompleted=True)
 return cleanup
save()
for label,argv,timeout in [
 ('autoreconf',['autoreconf','-if'],180),
 ('configure',['./configure','--prefix=/usr','--enable-layout=Debian','--disable-tests','--disable-hwloc','--disable-unwind','--enable-experimental-plugins','--with-yaml-cpp=/usr'],180),
 ('make',['make','-j2'],1200),
 ('install',['make','install','DESTDIR='+str(pkg)],180)]:
 start=time.monotonic();began=datetime.now(timezone.utc).isoformat()
 with (out/(label+'.stdout.raw')).open('xb') as stdout,(out/(label+'.stderr.raw')).open('xb') as stderr:
  p=subprocess.Popen(argv,cwd=src,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
  birth=process_stat(p.pid);assert birth['processGroupId']==birth['sessionId']==p.pid
  timed_out=False;cleanup=None
  try:p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   timed_out=True;record[label+'TimedOut']=True;save()
   cleanup=stop_timed_out_group(p,birth)
 row=dict(label=label,argv=argv,pid=p.pid,processGroupId=p.pid,sessionId=p.pid,processBirth=birth,
          startedAt=began,finishedAt=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-start,
          exitCode=p.returncode,waitCompleted=True,timedOut=timed_out,timeoutGroupCleanup=cleanup)
 row['logs']=[dict(file=label+'.'+kind+'.raw',bytes=(out/(label+'.'+kind+'.raw')).stat().st_size,sha256=hashlib.sha256((out/(label+'.'+kind+'.raw')).read_bytes()).hexdigest()) for kind in ['stdout','stderr']]
 record['commands'].append(row);save();print(label,p.returncode,round(row['seconds'],3),flush=True)
 if timed_out or p.returncode:raise SystemExit(1 if timed_out else p.returncode)
artifacts=[]
for path in sorted(pkg.rglob('*')):
 if path.is_file() and not path.is_symlink():artifacts.append(dict(file=str(path.relative_to(pkg)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
record.update(finishedAt=datetime.now(timezone.utc).isoformat(),artifacts=artifacts,buildCompleted=True,
 stockEquivalentPerformanceClaimed=False,fullMediaCoverageProven=False,experimentApproved=False)
save();print('Instrumented runtime build/install finished; no ATS service or experiment started.',flush=True)

import shutil
archive=t/'poc003-pool-batch-ats-build-common7e-v1';archive.mkdir()
for path in out.iterdir():
 if path.is_file():shutil.copyfile(path,archive/path.name)
shutil.copyfile(root/'source-preparation.json',archive/'source-preparation.json')
assert all(hashlib.sha256((own/item['source']).read_bytes()).hexdigest()==item['sha256'] for item in m['additionalHeaders'])
print('Build evidence archived; no service started.',flush=True)

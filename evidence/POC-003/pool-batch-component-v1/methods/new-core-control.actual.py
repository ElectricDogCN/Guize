"""One ordinary new-core component check; never a media performance experiment."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,resource,select,shutil,subprocess,sys,time
T=Path(__file__).resolve().parent
ROOT=Path('/home/sur/.cache/guize-takeover/poc003-pool-batch-ats-build-common7e-v1')
SRC=ROOT/'source/trafficserver-9.2.3';PKG=ROOT/'pkgroot'
OUT=T/'poc003-pool-batch-new-core-canary-v1';NATIVE=ROOT/'pool-batch-canary-v1'
AUTHOR=T/'poc003-pool-batch-performance-v1/poc/POC-03-ats-range'
assert os.getuid()==1000 and not OUT.exists() and not NATIVE.exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
build_raw=(ROOT/'compile-v1/receipt.json').read_bytes();build=json.loads(build_raw)
assert build['buildCompleted'] and len(build['commands'])==4
assert all(x['exitCode']==0 and x['waitCompleted'] and not x['timedOut'] for x in build['commands'])
assert build['instrumentation']['patchSha256']=='590f7a4bc9a044cbc6321ae1b1e20462aee681c0b122d6518dc2c1c9fcb072bf'
assert sha(AUTHOR/'instrumentation/patch-manifest.json')=='35a018339cc0bf54a2fc91cf518a787e1ecf1f4a63d9ce91d155b328ba43ef40'
assert sha(SRC/'iocore/eventsystem/IOBuffer.cc')=='3cca322c0111c68e205a3bc4af7faf4ec7b9e49db7b98d4d9f58d38e1d89db89'
core=PKG/'usr/lib/trafficserver/libtscore.so.9.2.3'
core_sha=next(x['sha256'] for x in build['artifacts'] if x['file']=='usr/lib/trafficserver/libtscore.so.9.2.3')
assert sha(core)==core_sha
assert sha(T/'poc003_pool_batch_new_core_canary_v1.cc')=='8eaaeaea4ad34e9299405b60619f50b69ac81c6ca38c7b2ecafbde2494461265'
header=AUTHOR/'instrumentation/live_buffer_accounting.h'
assert sha(header)=='f771476d0e5bb5124577329744128d83a4a0bdf43f1d10f91145e006848dc7fb'
OUT.mkdir();NATIVE.mkdir(mode=0o700)
shutil.copyfile(T/'poc003_pool_batch_new_core_canary_v1.cc',NATIVE/'driver.cc');shutil.copyfile(header,NATIVE/'live_buffer_accounting.h')
record=dict(kind='ACTUAL_NEW_CORE_ABI_ROUNDING_RETENTION_COMPONENT_CHECK_NOT_MEDIA',startedAt=datetime.now(timezone.utc).isoformat(),uid=os.getuid(),coreSha256=core_sha,buildReceiptSha256=hashlib.sha256(build_raw).hexdigest(),driverSourceSha256=sha(NATIVE/'driver.cc'),commands=[],componentAccepted=False,atsStarted=False,mediaExperimentExecuted=False,fullMedia8MiBAccepted=False,officialCiAccepted=False)
def save():(OUT/'results.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='\n')
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
argv=[shutil.which('g++'),'-std=c++17','-O2','-Wall','-Wextra','-Werror','-pthread','-I'+str(SRC/'include'),'-I'+str(SRC/'lib'),str(NATIVE/'driver.cc'),'-ldl','-o',str(NATIVE/'driver')]
with (OUT/'build.stdout.raw').open('xb') as out,(OUT/'build.stderr.raw').open('xb') as err:
 child=subprocess.Popen(argv,stdout=out,stderr=err,start_new_session=True)
 birth=process_stat(child.pid);assert birth['processGroupId']==birth['sessionId']==child.pid
 timedout=False;cleanup=None
 try:rc=child.wait(timeout=60)
 except subprocess.TimeoutExpired:timedout=True;cleanup=stop_timed_out_group(child,birth);rc=child.returncode
record['commands'].append(dict(label='compile-component-driver',argv=argv,pid=child.pid,birth=birth,actualWaitCompleted=True,exitCode=rc,timedOut=timedout,timeoutCleanup=cleanup));save()
assert rc==0 and not timedout
sys.path.insert(0,str(AUTHOR))
from buffer_probe import process_identity
from durable_peak_probe import capture_peak_journal
journal=NATIVE/'journal';journal.mkdir(mode=0o700)
env=dict(os.environ,LD_LIBRARY_PATH=str(core.parent),GUIZE_POC003_PEAK_JOURNAL_DIR=str(journal),PYTHONDONTWRITEBYTECODE='1')
env.pop('LD_PRELOAD',None);env.pop('LD_AUDIT',None)
def limits():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(512*1048576,512*1048576));resource.setrlimit(resource.RLIMIT_CPU,(10,10));resource.setrlimit(resource.RLIMIT_NOFILE,(256,256));resource.setrlimit(resource.RLIMIT_FSIZE,(8*1048576,8*1048576))
stdout=b'';command=[str(NATIVE/'driver'),str(core)];child=None
try:
 with (OUT/'driver.stderr.raw').open('xb') as err:
  child=subprocess.Popen(command,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,preexec_fn=limits)
  record['driverPid']=child.pid;save()
  assert select.select([child.stdout],[],[],10)[0],'component readiness timeout'
  stdout=child.stdout.readline(4097);assert stdout==b'READY\n'
  identity=process_identity(child);record['driverIdentity']=identity
  record['live']=capture_peak_journal(child,journal,OUT/'live',identity);save()
  child.stdin.write(b'GO\n');child.stdin.flush();child.stdin.close()
  rc=child.wait(timeout=10);stdout+=child.stdout.read(65537);assert len(stdout)<=65536
  record.update(driverActualWaitCompleted=True,driverExitCode=rc);save();assert rc==0
  value=json.loads(stdout.splitlines()[1]);assert len(value['actualCases'])==3 and value['abiHealthy'] and not value['media8MiBAccepted']
  assert [x['typeBytes'] for x in value['actualCases']]==[128,8192,65536]
  assert all(x['requestedChunkItems']==1 and x['actualChunkItems']>=1 and x['backingBytes']>0 for x in value['actualCases'])
  record['finished']=capture_peak_journal(child,journal,OUT/'finished',identity,finished=True)
  assert record['finished']['completeTrackedProcessEpoch']
  record.update(actualPoolCases=value,componentCheckCompleted=True,componentAccepted=False,independentResultReviewRequired=True)
except BaseException as error:
 record.update(failureType=type(error).__name__,failure=str(error)[:1024]);raise
finally:
 if child is not None and child.poll() is None:
  child.kill();child.wait(timeout=10);record['ownedDriverForcedStop']=True
 if child is not None:
  record.update(driverActualWaitCompleted=child.returncode is not None,driverExitCode=child.returncode)
  if child.stdout is not None:stdout+=child.stdout.read(65537-len(stdout))
 with (OUT/'driver.stdout.raw').open('xb') as out:out.write(stdout)
 record.update(coreUnchanged=sha(core)==core_sha,finishedAt=datetime.now(timezone.utc).isoformat());save()
assert record['coreUnchanged']
print(json.dumps(dict(componentCheckCompleted=True,actualWaitCompleted=True,driverExitCode=rc,componentAccepted=False,media8MiBAccepted=False,atsStarted=False,actualPoolCases=record['actualPoolCases'])))

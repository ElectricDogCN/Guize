"""Bounded before-workload environment facts; no ATS invocation or qualification."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,stat,sys,time


def bounded_text(path,maximum=16384,allow_prefix=False):
    if type(maximum) is not int or not 0<maximum<=16384:raise ValueError('fixed metadata read bound required')
    path=Path(path)
    if path.is_symlink():raise ValueError('final observation file must not be a symlink')
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb',buffering=0) as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):raise ValueError('regular kernel/config observation required')
        pieces=[];remaining=maximum+1
        while remaining:
            piece=stream.read(remaining)
            if not piece:break
            pieces.append(piece);remaining-=len(piece)
        raw=b''.join(pieces)
        if len(raw)>maximum and not allow_prefix:raise ValueError('metadata observation exceeds fixed bound')
        truncated=len(raw)>maximum;raw=raw[:maximum]
        after=os.fstat(stream.fileno())
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):raise ValueError('observation descriptor changed')
    return dict(path=str(path),text=raw.decode('utf-8'),prefixOnly=truncated,observedByteCount=len(raw),
                observedBytesSha256=hashlib.sha256(raw).hexdigest())


def capture_before_environment(output,*,proc=Path('/proc'),cgroup=Path('/sys/fs/cgroup'),
        os_release=Path('/usr/lib/os-release'),net=Path('/sys/class/net'),gpu=Path('/dev/dri'),
        workspace=Path('/runlab'),package=Path('/poc'),configuration=Path('/configuration')):
    started=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');monotonic=time.monotonic_ns()
    observations={}
    for name,file,maximum,prefix in [('os',os_release,16384,False),('cpu',proc/'cpuinfo',8192,True),
        ('status',proc/'self/status',16384,False),('stat',proc/'self/stat',16384,False),
        ('cpuLimit',cgroup/'cpu.max',256,False),('memoryLimit',cgroup/'memory.max',256,False),
        ('swapLimit',cgroup/'memory.swap.max',256,False),('pidLimit',cgroup/'pids.max',256,False),
        ('atsVersion',configuration/'current-host-version.stdout.raw',8192,False)]:
        observations[name]=bounded_text(file,maximum,prefix)
    cpu_model=next((line.split(':',1)[1].strip() for line in observations['cpu']['text'].splitlines()
                    if line.startswith('model name') or line.startswith('Hardware')),os.uname().machine)
    cpu_quota=observations['cpuLimit']['text'].strip().split();assert len(cpu_quota)==2
    exposed=sorted(str(p) for p in gpu.iterdir()) if gpu.is_dir() else []
    work_stat,pkg_stat=os.statvfs(workspace),os.statvfs(package)
    version=observations['atsVersion']['text'].strip()
    before_end=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    environment=dict(host_os=dict(isolation='Observed process namespace; parent Docker identity is independently captured',
            osRelease=observations['os']['text'],uid=os.getuid(),pid=os.getpid()),
        kernel=dict(zip(('sysname','nodename','release','version','machine'),os.uname())),
        cpu=dict(model=cpu_model,visibleLogicalCount=os.cpu_count(),quota=cpu_quota[0],period=cpu_quota[1]),
        memory=dict(cgroupLimit=observations['memoryLimit']['text'].strip(),swapLimit=observations['swapLimit']['text'].strip()),
        gpu=dict(exposedDevicePaths=exposed,scope='Observed mapped device paths; physical-host GPU inventory is outside this cache test'),
        driver=dict(cacheWorkload='CPU-only ATS Range/Slice',gpuDevicePathsObserved=exposed),
        runtime=dict(python=sys.version,implementation=sys.implementation.name,executable=sys.executable),
        tool_versions=dict(python=sys.version,atsVersionObservation=version,
            atsVersionObservationScope='Actual prior host --version of the copied package; container ABI and executable mappings are separately verified by owned epochs'),
        network_profile=dict(observedInterfaces=sorted(p.name for p in net.iterdir()),
            plannedLoopbackListenerPorts=[18231,18232,18233],scope='Interfaces observed before listeners; listener binding is attested later by the original ready callback'),
        storage_profile=dict(workspace=str(workspace),availableBytes=work_stat.f_bavail*work_stat.f_frsize,
            packageReadOnly=bool(pkg_stat.f_flag&os.ST_RDONLY),workspaceReadOnly=bool(work_stat.f_flag&os.ST_RDONLY),
            plannedCacheBytes=268435456,scope='Actual filesystem observations; monitored workspace budgets are not filesystem quotas'))
    record=dict(kind='ACTUAL_BEFORE_WORKLOAD_ENVIRONMENT_OBSERVATION_ONLY',capturedStartedAt=started,
        capturedFinishedAt=before_end,startedMonotonicNs=monotonic,finishedMonotonicNs=time.monotonic_ns(),
        environmentCaptured=environment,rawObservations=observations,atsProgramInvoked=False,atsServiceStarted=False,
        mediaRequestsStarted=False,actualExecutionQualificationAccepted=False,formalPocAccepted=False)
    output=Path(output)
    raw=(json.dumps(record,indent=2)+'\n').encode()
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,'wb',buffering=0) as stream:
        view=memoryview(raw)
        while view:
            n=stream.write(view)
            if n is None or n<=0:raise OSError('before environment record made no write progress')
            view=view[n:]
        os.fsync(stream.fileno())
    return record


"""Fresh singleton sandbox orchestration for the exact qualified real revocation CLI; no experiment authority."""
from pathlib import Path
import hashlib
import json
import os
import signal
import stat
import sys
import subprocess
import threading
import time

RUN=Path('/runlab/work')
LAB_FILE=Path('/poc/source/poc/POC-03-ats-range/lab.py')
REPORT=Path('/runlab/warm-cache-revocation-client.json')
COLLECT_FILE=LAB_FILE.with_name('collect.py')
COLLECT_SHA256='1b2220a6afd2e4790b17e091048dca7fcf2772c4bbcea6215beccc3700f6fd71'
TEST_SHA256='987608f169b25327231f0dc64bf41c571f1ab0f1b924bbe66b567cc7fa701457'
START_NS=time.time_ns()
record={'kind':'PRIVATE_PID1_FRESH_MANDATORY_REAL_WARM_CACHE_REVOCATION_CLI_ONLY',
        'pid':os.getpid(),'uid':os.getuid(),'checkpointObserved':False,'clientCompleted':False,'scenarioCompleted':False,
        'scenarioOutcomesAssessed':False,'formalActorBindingAccepted':False,'fullMediaAccepted':False,'untracedLatencyAccepted':False,'formalPocAccepted':False}
client_thread=None
STOP_REQUEST=threading.Event()


def save():
    # This is this method's current progress, not a fabricated source/owner wait.
    raw=(json.dumps(record,indent=2)+'\n').encode()
    fd=os.open(REPORT,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw)


def ordinary_init():
    if (os.getpid()!=1 or os.getuid()!=1000 or os.geteuid()!=1000
            or threading.get_native_id()!=os.getpid() or len(list(Path('/proc/self/task').iterdir()))!=1):
        raise ValueError('private singleton ordinaryUID1000 PID1 required')
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if status.get('Seccomp','').strip()!='2':raise ValueError('actual initial engine seccomp filter required')
    record['initialSecurityStatus']={k:status.get(k,'').strip() for k in ('NoNewPrivs','Seccomp','Seccomp_filters','CapEff','CapBnd')}
    if status['NoNewPrivs'].strip()!='1' or any(int(status[k].strip(),16) for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')):
        raise ValueError('no capabilities and NNP required')
    if any(os.environ.get(k) for k in ('LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT')):
        raise ValueError('image Python must not inherit target library injection')
    if sys.getprofile() is not None or sys.gettrace() is not None:
        raise ValueError('do not replace an unrelated tracing/profiling hook')
    if signal.getsignal(signal.SIGINT) is not signal.default_int_handler:
        raise ValueError('actual Python selfSIGINT handler required')


def client(state):
    child=None
    try:
        hooks={'threadProfile':sys.getprofile(),'threadTrace':sys.gettrace(),
               'defaultThreadProfile':threading.getprofile(),'defaultThreadTrace':threading.gettrace()}
        if any(value is not None for value in hooks.values()):
            raise ValueError('no profiling/tracing hooks during real revocation test')
        record['requestHookObservations']=hooks
        test=LAB_FILE.with_name('test_warm_cache_revocation.py')
        if hashlib.sha256(test.read_bytes()).hexdigest()!=TEST_SHA256:
            raise ValueError('exact qualified mandatory real CLI required')
        output=Path('/runlab/warm-cache-revocation')
        argv=[sys.executable,'-B',str(test),'--run-dir',str(RUN),'--output-dir',str(output)]
        record.update(actualTestCommand=argv,testSha256=TEST_SHA256,collectorOutput=str(output));save()
        with Path('/runlab/revocation-cli.stdout.raw').open('xb') as out,Path('/runlab/revocation-cli.stderr.raw').open('xb') as err:
            child=subprocess.Popen(argv,stdout=out,stderr=err)
            record['actualTestPid']=child.pid;save()
            try:code=child.wait(timeout=120)
            except subprocess.TimeoutExpired:
                record['actualTestDeadlineExpired']=True;save()
                child.terminate()
                try:code=child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill();code=child.wait(timeout=10)
            record.update(actualTestWaitCompleted=True,actualTestExitCode=code);save()
        report=lab.unique_json((output/'revocation-result.json').read_bytes())
        record['actualScenarioReport']=report;save()
        if code!=0 or record.get('actualTestDeadlineExpired') or report.get('status')!='PASS' or report.get('executedScenarios')!=1 or report.get('skippedAssertions')!=0:
            raise ValueError('mandatory real revocation CLI did not pass every assertion')
        record['scenarioCompleted']=True
    except BaseException as error:
        record.update(clientErrorType=type(error).__name__,clientError=str(error)[:512])
    finally:
        record.update(clientCompleted=True,cooperativeStopRequested=True,
                      stopRequestedAtMonotonicNs=time.monotonic_ns());save()
        STOP_REQUEST.set()


def ready_callback(state):
    global client_thread
    if record['checkpointObserved'] or client_thread is not None:raise ValueError('duplicate matrix checkpoint')
    if threading.get_native_id()!=os.getpid():raise ValueError('actual controller main-thread readiness required')
    if any(hook is not None for hook in (sys.getprofile(),sys.gettrace(),threading.getprofile(),threading.gettrace())):
        raise ValueError('readiness must remain free of profiling/tracing hooks')
    cfg=state.cfg
    marker=RUN/'listeners-started.json'
    fd=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());raw=stream.read(4097);after=os.fstat(stream.fileno())
    if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode)!=0o600 or before.st_uid!=1000 or before.st_nlink!=1
            or not 0<len(raw)<=4096 or before.st_mtime_ns<START_NS
            or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
        raise ValueError('fresh bounded private readiness artifact required')
    value=lab.unique_json(raw)
    if (set(value)!={'startedAt','controllerPid','atsPid','bind','ports','formalPocAccepted'}
            or value['controllerPid']!=os.getpid() or value['atsPid']!=state.ats.pid or value['bind']!='127.0.0.1'
            or value['ports']!=[18231,18232,18233] or value['formalPocAccepted'] is not False
            or cfg['runDir']!=str(RUN) or state.epoch_owner is None):
        raise ValueError('actual listeners/owner/State/PID binding required')
    record.update(checkpointObserved=True,checkpointMonotonicNs=time.monotonic_ns(),actualListeners=value,hookKind='explicit pinned serve readiness callback; no tracing or profiling installed')
    record['profileAbsentBeforeClient']=sys.getprofile() is None and sys.gettrace() is None
    save();client_thread=threading.Thread(target=client,args=(state,),name='real-warm-cache-revocation-cli-supervisor',daemon=True);client_thread.start()


def main():
    global lab
    ordinary_init();assert not RUN.exists() and not (RUN/'listeners-started.json').exists()
    if hashlib.sha256(LAB_FILE.read_bytes()).hexdigest()!='310d38b82fc9898711147b2ae560d1f5bb5def38798533a45462489cb98b358f':raise ValueError('exact current readiness lab required')
    sys.path.insert(0,str(LAB_FILE.parent));import lab as module;lab=module
    before_file=Path('/runlab/before-environment.json')
    before_record=capture_before_environment(before_file)
    record.update(beforeEnvironmentCaptured=True,beforeEnvironmentRef='before-environment.json',
        beforeEnvironmentSha256=hashlib.sha256(before_file.read_bytes()).hexdigest(),
        beforeEnvironmentCapturedUntil=before_record['capturedFinishedAt'],
        workloadScopeStartedAt=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
    del before_record
    save()
    lab.prepare('/configuration/config.json',str(RUN));ordinary_init();save()
    try:
        lab.serve(str(RUN),ready_callback=ready_callback,stop_event=STOP_REQUEST);record['serveReturnedNormally']=True
    except BaseException as error:
        record.update(serveReturnedNormally=False,serveErrorType=type(error).__name__,serveError=str(error)[:512])
    finally:
        if client_thread is not None:client_thread.join(timeout=10)
        record['clientThreadStopped']=client_thread is not None and not client_thread.is_alive();save()
    passed=all(record.get(k) is True for k in ('beforeEnvironmentCaptured','checkpointObserved','profileAbsentBeforeClient','clientCompleted','scenarioCompleted','serveReturnedNormally','clientThreadStopped'))
    print(json.dumps({'warmCacheRevocationCompleted':passed,'formalPocAccepted':False}),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()

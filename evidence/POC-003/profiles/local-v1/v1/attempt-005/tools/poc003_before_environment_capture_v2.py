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

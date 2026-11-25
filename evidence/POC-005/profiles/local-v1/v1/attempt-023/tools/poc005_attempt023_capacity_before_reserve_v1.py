"""Read the new D-backed guest and every visible v2 ancestor without relabeling host RAM."""
from datetime import datetime,timezone
from pathlib import Path
import json,os,shutil

def resource_snapshot(parent,phase='before-reservation'):
    parent=Path(parent)
    assert parent==Path('/work') and os.name=='posix' and os.getuid()==1000
    assert os.environ.get('WSL_DISTRO_NAME')=='Guize-Poc005-Neutral-81348fd-v1'
    assert phase in ('before-reservation',)
    host=json.loads(Path('/work/tools-attempt023/backing-resource-'+phase+'.json').read_bytes());now=datetime.now(timezone.utc)
    assert 0<=(now-datetime.fromisoformat(host['observedAt'].replace('Z','+00:00'))).total_seconds()<=120
    assert host['distribution']==os.environ['WSL_DISTRO_NAME'] and host['backingDrive']=='D:' and host['version']==2
    assert host['backingDiskFreeBytes']>=25*1024**3 and host['scannerExperimentApproved'] is False
    memraw=Path('/proc/meminfo').read_text()
    mem={r.split(':',1)[0]:int(r.split()[1])*1024 for r in memraw.splitlines() if len(r.split())>=3 and r.split()[2]=='kB'}
    cgraw=Path('/proc/self/cgroup').read_text();relative=next(r[3:] for r in cgraw.splitlines() if r.startswith('0::'))
    assert relative.startswith('/') and '..' not in Path(relative).parts
    root=Path('/sys/fs/cgroup');here=root/relative.lstrip('/');assert here.resolve().is_relative_to(root.resolve())
    limits=[];remaining=[mem['MemAvailable']]
    while True:
        row=dict(path=str(here),controllers=(here/'cgroup.controllers').read_text().strip(),subtreeControl=(here/'cgroup.subtree_control').read_text().strip())
        memory_files=[here/name for name in ['memory.current','memory.max','memory.high']]
        if not all(path.exists() for path in memory_files):
            # Per the kernel v2 interface, an immediate parent's subtree_control
            # creates these controller files. Confirm actual disabled delegation;
            # never substitute zero/max for an unread or missing finite limit.
            assert here!=root and not any(path.exists() for path in memory_files)
            parent_controllers=(here.parent/'cgroup.subtree_control').read_text().split()
            assert 'memory' not in parent_controllers
            row.update(memoryInterfacesPresent=False,parentMemoryControllerEnabled=False,parentSubtreeControl=parent_controllers)
        else:
            current=int(memory_files[0].read_text());row.update(memoryInterfacesPresent=True,currentBytes=current)
            for name in ['memory.max','memory.high']:
                value=(here/name).read_text().strip();row[name]=value
                if value!='max':remaining.append(max(0,int(value)-current))
        limits.append(row)
        if here==root:break
        here=here.parent
    return dict(kind='ACTUAL_D_BACKED_NATIVE_WSL_RESOURCE_OBSERVATION',observedAt=now.isoformat(),uid=os.getuid(),
        distribution=os.environ['WSL_DISTRO_NAME'],guestMemTotalBytes=mem['MemTotal'],guestMemAvailableBytes=mem['MemAvailable'],
        effectiveAvailableMemoryBytes=min(remaining),cgroupLimits=limits,procCgroup=cgraw,
        effectiveMemoryMethod='minimum actual guest MemAvailable and all visible v2 finite ancestor memory.max/memory.high minus current',
        guestDiskFreeBytes=shutil.disk_usage(parent).free,backingDiskFreeBytes=host['backingDiskFreeBytes'],hostObservation=host,
        physicalPerformanceDomain='Existing Windows host, Ubuntu, this guest and Docker share one domain; original shared lock required',settingsChanged=False)

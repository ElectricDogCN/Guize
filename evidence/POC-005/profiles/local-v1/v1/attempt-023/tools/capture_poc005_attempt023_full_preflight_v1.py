"""Capture the real waiting D-guest process and fresh host facts before approval."""
import argparse,hashlib,json,os,platform,shutil,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path

def capture(root):
    root=root.resolve(strict=True);slot='evidence/POC-005/profiles/local-v1/v1/attempt-023/'
    here=root/slot
    assert root==Path('/work/Guize-attempt023') and os.getuid()==1000 and os.environ.get('WSL_DISTRO_NAME')=='Guize-Poc005-Neutral-81348fd-v1'
    sys.path.insert(0,str(root/'poc/POC-05-metadata-scale'))
    from native_scan_protocol import read_json,write_json,utc
    from native_memory import native_identity as identity
    request,request_sha=read_json(here/'approval-request.json')
    cfg,cfg_sha=read_json(root/request['runtimeConfigRef'],request['runtimeConfigSha256'])
    resource,resource_sha=read_json(root/request['configurationRef'],request['configurationSha256'])
    profile,profile_sha=read_json(here/'profile-configuration.json')
    material,_=read_json(here/'template-materialization.json')
    method=material['assemblyMethod'];method_raw=(root/method['ref']).read_bytes()
    assert len(method_raw)==method['byteCount'] and 'sha256:'+hashlib.sha256(method_raw).hexdigest()==method['sha256']
    assert identity(request['reservation']['nativeProcessId'])==request['reservation']
    source=cfg['sourceRun'];assert identity(source['upstreamIdentity']['nativeProcessId'])==source['upstreamIdentity']
    assert not (root/request['approvalRef']).exists() and not (root/cfg['database']).exists()
    assert not (root/source['artifactPrefix']).exists()
    host,host_sha=read_json(here/'host-observation-before.json')
    backing,backing_sha=read_json(here/'backing-observation-before.json')
    now=datetime.now(timezone.utc)
    assert 0<=(now-utc(host['observedAt'])).total_seconds()<=120
    assert 0<=(now-utc(backing['observedAt'])).total_seconds()<=120
    boundary=resource['configuration']['syntheticHierarchySandbox']
    assert host['physicalHostId']==boundary['physicalHostId'] and host['cpu'] and host['gpu']
    assert backing['distribution']==os.environ['WSL_DISTRO_NAME'] and backing['version']==2 and backing['backingDrive']=='D:'
    assert backing['ownedBackend']==material['ownedBackend'] and backing['backingDiskFreeBytes']>=20*1024**3
    memraw=Path('/proc/meminfo').read_text()
    mem={r.split(':',1)[0]:int(r.split()[1])*1024 for r in memraw.splitlines() if len(r.split())>=3 and r.split()[2]=='kB'}
    cgraw=Path('/proc/self/cgroup').read_text();relative=next(r[3:] for r in cgraw.splitlines() if r.startswith('0::'))
    assert relative.startswith('/') and '..' not in Path(relative).parts
    cgroot=Path('/sys/fs/cgroup');cg=cgroot/relative.lstrip('/');assert cg.resolve().is_relative_to(cgroot.resolve())
    limits=[];available=[mem['MemAvailable']]
    while True:
        row=dict(path=str(cg),controllers=(cg/'cgroup.controllers').read_text().strip(),subtreeControl=(cg/'cgroup.subtree_control').read_text().strip())
        paths=[cg/name for name in ['memory.current','memory.max','memory.high']]
        if not all(p.exists() for p in paths):
            assert cg!=cgroot and not any(p.exists() for p in paths)
            parent=(cg.parent/'cgroup.subtree_control').read_text().split();assert 'memory' not in parent
            row.update(memoryInterfacesPresent=False,parentMemoryControllerEnabled=False,parentSubtreeControl=parent)
        else:
            current=int(paths[0].read_text());row.update(memoryInterfacesPresent=True,currentBytes=current)
            for name in ['memory.max','memory.high']:
                value=(cg/name).read_text().strip();row[name]=value
                if value!='max':available.append(max(0,int(value)-current))
        limits.append(row)
        if cg==cgroot:break
        cg=cg.parent
    disk=shutil.disk_usage(source['localRoot'])
    capacity=dict(guestMemAvailableBytes=mem['MemAvailable'],guestMemTotalBytes=mem['MemTotal'],effectiveAvailableMemoryBytes=min(available),
        cgroupLimits=limits,procCgroup=cgraw,guestDiskFreeBytes=disk.free,backingDiskFreeBytes=backing['backingDiskFreeBytes'],
        backingObservationRef=slot+'backing-observation-before.json',hostFreeMemoryIsSeparatePressureOnly=True)
    assert min(available)>=4*1024**3 and disk.free>=20*1024**3
    cpuinfo=Path('/proc/cpuinfo').read_text();models=sorted({r.split(':',1)[1].strip() for r in cpuinfo.splitlines() if r.startswith('model name')})
    gpu_paths=sorted(str(p) for pattern in ('dev/dri/*','dev/dxg') for p in Path('/').glob(pattern))
    mounts=[line for line in Path('/proc/self/mountinfo').read_text().splitlines() if line.split()[4] in ('/','/sys/fs/cgroup')]
    assert len([r for r in mounts if r.split()[4]=='/' and ' - ext4 ' in r])==1
    mount_ref=slot+'selected-linux-mounts-before.raw';mount_raw=('\n'.join(mounts)+'\n').encode()
    with (root/mount_ref).open('xb') as output:output.write(mount_raw)
    result=dict(kind='actual_full_pre_execution_environment',observedAt=now.isoformat().replace('+00:00','Z'),
        sourceCommit=cfg['context']['subjectVersion'],runtimeConfigSha256=cfg_sha,approvalRequestSha256=request_sha,
        profileConfigurationSha256=profile_sha,metadataResourceSha256=resource_sha,scannerIdentity=request['reservation'],upstreamIdentity=source['upstreamIdentity'],
        host_os=platform.platform(),kernel=platform.version(),cpu=dict(logicalCpuCount=os.cpu_count(),observedModels=models,hostObservationRef=slot+'host-observation-before.json'),
        memory=capacity,gpu=dict(observedDeviceCount=len(gpu_paths),observedDevicePaths=gpu_paths,metadataWorkloadUsesGpu=False,hostObservationRef=slot+'host-observation-before.json'),
        driver=dict(guestKernel=platform.release(),metadataWorkloadUsesGpu=False,hostVideoControllers=host['gpu'],selectedMountInfoRef=mount_ref),
        runtime=dict(python=sys.version,executable=sys.executable,actualCollectorIdentity=identity(os.getpid()),sqlite=sqlite3.sqlite_version,executionAssembler=method),
        tool_versions=cfg['context']['scannerBuild'],network_profile=dict(upstream=source['origin'],gatewayPort=source['gatewayPort'],loopbackOnly=True,providerQuotaUnknown=True),
        storage_profile=dict(root=source['localRoot'],diskTotalBytes=disk.total,diskFreeBytes=disk.free,physicalBackingObservation=backing,
            selectedMountInfoRef=mount_ref,selectedMountInfoBytes=len(mount_raw),selectedMountInfoSha256='sha256:'+hashlib.sha256(mount_raw).hexdigest(),
            artifactBudgetBytes=source['artifactBytes'],artifactFiles=source['artifactFiles'],mountCaptureSelection='Actual root ext4 and cgroup mount rows only; complete mount table not claimed'),
        openlist_version=dict(pinnedRelease='v4.2.6',actualExecutableSha256=source['upstreamIdentity']['executableSha256'],officialArchiveSha256='2f2a5008efe45895292018479cb05556c83e828c3eed68a8b8cd3d35e82f03cb'),
        synthetic_hierarchy_manifest=profile['capturedSettings']['synthetic_hierarchy_manifest'],
        syntheticHierarchySandbox=dict(schemaVersion=1,configurationRef=request['configurationRef'],boundary=boundary),
        hostObservationSha256=host_sha,backingObservationSha256=backing_sha,actualHostCpuLoadSample=host['cpuLoad'],
        physicalIsolation='Shared physical host; original performance-domain lock required. Actual host load is not a production isolation claim.',
        scannerPidReserved=True,workloadHasBeenReleased=False,sourceListingOrProbeExecuted=False,qualificationAccepted=False)
    assert identity(request['reservation']['nativeProcessId'])==request['reservation']
    assert identity(source['upstreamIdentity']['nativeProcessId'])==source['upstreamIdentity']
    write_json(here/'before-environment.json',result)
    print(json.dumps(dict(beforeEnvironmentRef=slot+'before-environment.json',runtimeConfigSha256=cfg_sha,sourceRequestsSent=False,finalApprovalCreated=False)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();capture(args.root)

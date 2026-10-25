"""Actual full pre-execution environment capture; no source listing or approval."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HOST_QUERY = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$pocHostUuid = (Get-CimInstance Win32_ComputerSystemProduct).UUID.Trim().ToLowerInvariant()
$pocHostSha = [System.Security.Cryptography.SHA256]::Create()
try { $pocHostHash = ([BitConverter]::ToString($pocHostSha.ComputeHash([Text.Encoding]::UTF8.GetBytes($pocHostUuid)))).Replace('-','').ToLowerInvariant() }
finally { $pocHostSha.Dispose() }
[ordered]@{
 observedAt = [DateTime]::UtcNow.ToString('o')
 cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed)
 os = (Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,TotalVisibleMemorySize,FreePhysicalMemory)
 gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,DriverDate,AdapterRAM,Status)
 cpuLoad = @(Get-CimInstance Win32_Processor | Select-Object DeviceID,LoadPercentage)
 physicalHostId = 'windows-hardware-sha256:' + $pocHostHash
 physicalHostIdCollector = 'Win32_ComputerSystemProduct.UUID.Trim().ToLowerInvariant(); SHA256 UTF8'
} | ConvertTo-Json -Depth 8
'''


def host_capture():
    proc = subprocess.run(['powershell.exe','-NoProfile','-Command',HOST_QUERY], capture_output=True, timeout=45,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if proc.returncode:
        raise RuntimeError('Actual hardware capture failed; retain stderr privately for diagnosis')
    host = json.loads(proc.stdout)
    if not host['physicalHostId'].startswith('windows-hardware-sha256:') or not host['cpu'] or not host['gpu']:
        raise ValueError('Concrete actual host capture required')
    return host, proc.stdout


def capture(root: Path):
    root = root.resolve(strict=True)
    code = root/'poc/POC-05-metadata-scale'
    sys.path.insert(0,str(code))
    from native_scan_protocol import read_json, write_json
    from windows_native import identity
    prefix='evidence/POC-005/profiles/local-v1/v1/attempt-006/'
    slot=root/prefix
    request,request_sha=read_json(slot/'approval-request.json')
    cfg,cfg_sha=read_json(root/request['runtimeConfigRef'],request['runtimeConfigSha256'])
    metadata,metadata_sha=read_json(root/request['configurationRef'],request['configurationSha256'])
    profile,profile_sha=read_json(slot/'profile-configuration.json')
    material,_=read_json(slot/'template-materialization.json')
    method=material['assemblyMethod']
    if identity(request['reservation']['nativeProcessId'])!=request['reservation']:
        raise ValueError('Exact live stopped scanner required')
    source=cfg['sourceRun']
    if identity(source['upstreamIdentity']['nativeProcessId'])!=source['upstreamIdentity']:
        raise ValueError('Exact source identity required')
    if (root/request['approvalRef']).exists() or (root/cfg['database']).exists():
        raise ValueError('Capture must precede execution approval and any scanner database')
    method_path=root/method['ref']
    if method_path.stat().st_size!=method['byteCount'] or 'sha256:'+hashlib.sha256(method_path.read_bytes()).hexdigest()!=method['sha256']:
        raise ValueError('Actual pre-approved assembly bytes required')
    host,raw=host_capture()
    boundary=metadata['configuration']['syntheticHierarchySandbox']
    if boundary['physicalHostId']!=host['physicalHostId']:
        raise ValueError('Actual physical host must equal approved boundary')
    service=json.loads((Path(__file__).resolve().parent/'poc005-attempt006-windows-openlist-preparation.json').read_bytes())
    fixture=json.loads((Path(__file__).resolve().parent/'poc005-attempt006-windows-native-fixture-preparation.json').read_bytes())
    if service['identity']!=source['upstreamIdentity'] or service['filesystemRoot']!=source['localRoot'] or service['mountId']!=boundary['mountId']:
        raise ValueError('Actual prepared mount/process/root must equal approved boundary')
    if Path(fixture['filesystemRoot']).resolve()!=Path(source['localRoot']).resolve() or fixture['actualFilesystemCounts']!={'file':10000,'directory':500}:
        raise ValueError('Fixed actual v3 hierarchy required')
    if not fixture['exactFullPathInventoryRevalidated'] or not fixture['allPayloadsReread'] or not fixture['allMtimesReread']:
        raise ValueError('Full fixed-input preparation required')
    host_ref=prefix+'host-cim-preflight.json'
    with (root/host_ref).open('xb') as stream:
        stream.write(raw)
    disk=shutil.disk_usage(source['localRoot'])
    record=dict(kind='actual_full_pre_execution_environment',observedAt=datetime.now(timezone.utc).isoformat(),
        sourceCommit=cfg['context']['subjectVersion'],runtimeConfigSha256=cfg_sha,approvalRequestSha256=request_sha,
        profileConfigurationSha256=profile_sha,metadataResourceSha256=metadata_sha,scannerIdentity=request['reservation'],upstreamIdentity=source['upstreamIdentity'],
        host_os=platform.platform(),kernel=platform.version(),cpu=host['cpu'],memory=host['os'],gpu=host['gpu'],
        driver=dict(actualVideoControllerDrivers=host['gpu'],metadataWorkloadUsesGpu=False,filesystem='NTFS native Windows',reportedAdapterRAMNotDedicatedVram=True),
        runtime=dict(python=sys.version,executable=sys.executable,sqlite=sqlite3.sqlite_version),
        tool_versions=dict(python=sys.version,sqlite=sqlite3.sqlite_version,openlist='v4.2.6 pinned official executable',executionAssembler=method),
        network_profile=dict(upstream=source['origin'],gatewayPort=source['gatewayPort'],loopbackOnly=True,providerQuotaUnknown=True),
        storage_profile=dict(root=source['localRoot'],diskTotalBytes=disk.total,diskFreeBytes=disk.free,artifactBudgetBytes=source['artifactBytes'],artifactFiles=source['artifactFiles'],budgetScope='Actual artifact journal, not production capacity or host-wide RSS reservation'),
        openlist_version=dict(pinnedRelease='v4.2.6',actualExecutableSha256=source['upstreamIdentity']['executableSha256'],officialArchiveSha256=service['archiveSha256']),
        synthetic_hierarchy_manifest=profile['capturedSettings']['synthetic_hierarchy_manifest'],
        syntheticHierarchySandbox=dict(schemaVersion=1,configurationRef=request['configurationRef'],boundary=boundary),
        actualHostCpuLoadSample=host['cpuLoad'],rawHostCimRef=host_ref,rawHostCimBytes=len(raw),rawHostCimSha256='sha256:'+hashlib.sha256(raw).hexdigest(),
        physicalIsolation='Shared physical host; no concurrent ATS benchmark scheduled; retained actual host load is not an idle/production isolation claim.',
        scannerPidReserved=True,workloadHasBeenReleased=False,sourceListingOrProbeExecuted=False,qualificationAccepted=False)
    write_json(slot/'before-environment.json',record)
    print(json.dumps(dict(beforeEnvironmentRef=prefix+'before-environment.json',runtimeConfigSha256=cfg_sha,sourceRequestsSent=False,finalApprovalCreated=False)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path)
    parser.add_argument('--host-only-output',type=Path)
    args=parser.parse_args()
    if args.host_only_output:
        if args.root:
            parser.error('Select exactly one capture mode')
        host,raw=host_capture()
        with args.host_only_output.open('xb') as stream: stream.write(raw)
        print(json.dumps(dict(actualHostCaptureSaved=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),sourceRequestsSent=False,scannerReserved=False)))
    elif args.root:
        capture(args.root)
    else:
        parser.error('A capture mode is required')


if __name__=='__main__':
    main()

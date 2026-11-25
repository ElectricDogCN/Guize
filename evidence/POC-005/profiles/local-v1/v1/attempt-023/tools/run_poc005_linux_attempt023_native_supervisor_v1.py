"""Real D-guest parent wait; the frozen controller alone reserves and executes."""
import hashlib,json,os,signal,subprocess,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path

W=Path('/work/Guize-attempt023');T=Path('/work/tools-attempt023');SLOT='evidence/POC-005/profiles/local-v1/v1/attempt-023/'
assert os.getuid()==1000 and os.environ.get('WSL_DISTRO_NAME')=='Guize-Poc005-Neutral-81348fd-v1'
sys.path.insert(0,str(W/'poc/POC-05-metadata-scale'))
from native_scan_protocol import read_json,write_json,utc
from native_memory import native_identity as identity
from poc005_attempt023_capacity_before_reserve_v1 import resource_snapshot
material,_=read_json(W/(SLOT+'template-materialization.json'))
draft,draft_sha=read_json(W/material['draftRef'],material['draftSha256'])
decision,_=read_json(W/material['templateDecisionRef'])
assert decision['decision']=='approved_full_template_only' and decision['fullPreparationAccepted'] and not decision['finalExecutionApproved']
assert decision['reviewer']=='/root/gz022_planning_independent_review'
assert material['source']==decision['source']==draft['runtimeConfig']['context']['subjectVersion']==subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip()
assert utc(decision['validFrom'])<=datetime.now(timezone.utc)<utc(decision['validUntil'])
assert utc(draft['reservationDeadline'])<=utc(decision['validUntil'])
assert identity(draft['runtimeConfig']['sourceRun']['upstreamIdentity']['nativeProcessId'])==draft['runtimeConfig']['sourceRun']['upstreamIdentity']
for method in material['qualificationMethods'].values():
    raw=(W/method['ref']).read_bytes();assert len(raw)==method['byteCount'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==method['sha256']
assert not (W/draft['approvalRef']).exists() and not (W/draft['refs']['manifest']).exists()
capacity=resource_snapshot(Path('/work'))
assert capacity['effectiveAvailableMemoryBytes']>=4*1024**3 and min(capacity['guestDiskFreeBytes'],capacity['backingDiskFreeBytes'])>=20*1024**3
argv=[sys.executable,'-X','utf8','-B',str(W/'poc/POC-05-metadata-scale/run_source_experiment.py'),'--draft',str(W/material['draftRef']),'--sha256',draft_sha]
started=datetime.now(timezone.utc);mono=time.monotonic();deadline=utc(decision['validUntil'])+timedelta(seconds=15)
native_deadline=mono+max(0,(deadline-started).total_seconds());timed_out=False
with (W/(SLOT+'controller.stdout')).open('xb') as out,(W/(SLOT+'controller.stderr')).open('xb') as error:
    assert utc(decision['validFrom'])<=datetime.now(timezone.utc)<utc(decision['validUntil'])
    child=subprocess.Popen(argv,cwd=W,stdin=subprocess.DEVNULL,stdout=out,stderr=error,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},start_new_session=True)
    expected=identity(child.pid)
    write_json(W/(SLOT+'controller-launch.json'),dict(kind='actual_linux_source_controller_launch',source=material['source'],
        startedAt=started.isoformat().replace('+00:00','Z'),identity=expected,supervisorPid=os.getpid(),argv=argv,
        draftRef=material['draftRef'],draftSha256=draft_sha,overallStopDeadline=deadline.isoformat(),approvalGenerated=False))
    print(json.dumps(dict(kind='actual_controller_waiting_for_independent_final_approval',controllerPid=child.pid,supervisorPid=os.getpid(),source=material['source'])),flush=True)
    while True:
        remaining=min(native_deadline-time.monotonic(),(deadline-datetime.now(timezone.utc)).total_seconds())
        if remaining<=0:
            timed_out=True
            if child.poll() is None:assert identity(child.pid)==expected;os.killpg(child.pid,signal.SIGTERM)
            try:code=child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait()
            break
        try:code=child.wait(timeout=min(30,remaining));break
        except subprocess.TimeoutExpired:pass
record=dict(kind='actual_linux_source_controller_execution',source=material['source'],argv=argv,identity=expected,supervisorPid=os.getpid(),
    startedAt=started.isoformat().replace('+00:00','Z'),finishedAt=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    elapsedPerfCounterNs=int((time.monotonic()-mono)*1e9),exitCode=code,actualWaitCompleted=True,overallDeadlineExceeded=timed_out,
    resourceSnapshotBeforeController=capacity,
    stdoutRef=SLOT+'controller.stdout',stderrRef=SLOT+'controller.stderr',finalApprovalFileExisted=(W/draft['approvalRef']).exists(),
    sourceArtifactsDirectoryExisted=(W/draft['runtimeConfig']['sourceRun']['artifactPrefix']).exists(),qualificationAccepted=False,taskCompleted=False)
write_json(W/(SLOT+'controller-execution.json'),record);print(json.dumps(record),flush=True)
raise SystemExit(code)

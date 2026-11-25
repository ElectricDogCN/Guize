"""Bounded idle-Docker A/B diagnostic; restore running state in finally."""
import json, os, subprocess, sys, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

T = Path(__file__).resolve().parent
OUT = T / 'poc005-attempt023-clock-isolation-v1'
assert os.name == 'nt' and not OUT.exists()
OUT.mkdir()
commands = []
record = dict(kind='IDLE_DOCKER_CLOCK_DIAGNOSTIC', scannerExperimentExecuted=False,
              persistentConfigurationChanged=False, sourceMeasurementsStateChanged=False, originalRunningStateRestored=False)
def save():
    (OUT/'result.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
def run(label, argv, timeout=60, required=True):
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill(); out, err = p.communicate()
        (OUT/(label+'.stdout')).write_bytes(out)
        (OUT/(label+'.stderr')).write_bytes(err)
        raise
    (OUT/(label+'.stdout')).write_bytes(out)
    (OUT/(label+'.stderr')).write_bytes(err)
    commands.append(dict(label=label, argv=argv, pid=p.pid, exitCode=p.returncode,
                         actualWaitCompleted=True, observedAt=datetime.now(timezone.utc).isoformat()))
    (OUT/'commands.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    if required:
        assert p.returncode == 0, label
    return p.returncode, out, err


@contextmanager
def ubuntu_keeper():
    code="import json,os,select,subprocess,sys,time\nfrom pathlib import Path\ndef identity():\n p=Path('/proc/self');s=(p/'stat').read_text();i=Path('/proc/1/stat').read_text()\n return dict(pid=os.getpid(),startTicks=s[s.rfind(')')+2:].split()[19],pidNamespace=os.readlink(p/'ns/pid'),nspid=[x for x in (p/'status').read_text().splitlines() if x.startswith('NSpid:')],initStartTicks=i[i.rfind(')')+2:].split()[19],bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip())\ninitial=identity();print(json.dumps(dict(kind='identity',**initial)),flush=True);phase='idle'\nwhile True:\n ready,_,_=select.select([sys.stdin],[],[],5)\n if ready:\n  line=sys.stdin.readline()\n  if not line:break\n  phase=line.strip()\n state=subprocess.run(['systemctl','is-active','systemd-timesyncd'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5).stdout.decode().strip()\n same=identity()==initial\n print(json.dumps(dict(kind='heartbeat',phase=phase,identityUnchanged=same,timesyncState=state,monotonicRawNs=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW))),flush=True)\n assert same and (phase!='observe' or state=='inactive')\n"
    with (OUT/'keeper.stdout').open('xb') as out, (OUT/'keeper.stderr').open('xb') as err:
        keeper=subprocess.Popen(['wsl.exe','--distribution','Ubuntu','--user','root','--exec','python3','-B','-c',code],stdin=subprocess.PIPE,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.perf_counter()+15
            while not (OUT/'keeper.stdout').stat().st_size:
                assert keeper.poll() is None and time.perf_counter()<deadline
                time.sleep(.1)
            record['keeperNativeIdentity']=json.loads((OUT/'keeper.stdout').read_text().splitlines()[0])
            record['keeperFrontendPid']=keeper.pid;save()
            yield keeper
        finally:
            keeper.stdin.close()
            keeper.wait(timeout=20)
            record['keeperActualWaitCompleted']=True
            record['keeperExitCode']=keeper.returncode;save()
            assert keeper.returncode==0

def set_keeper_phase(keeper, phase):
    keeper.stdin.write((phase+'\n').encode());keeper.stdin.flush()
    deadline=time.perf_counter()+15
    while True:
        assert keeper.poll() is None and time.perf_counter()<deadline
        try:
            rows=[json.loads(line) for line in (OUT/'keeper.stdout').read_text().splitlines()]
            if rows[-1].get('phase')==phase:
                assert rows[-1]['identityUnchanged']
                return
        except json.JSONDecodeError:pass
        time.sleep(.1)

@contextmanager
def isolate_clock_for_attempt023():
    with ubuntu_keeper() as keeper:
        rc, out, err = run('initial-status', ['docker','desktop','status'], required=False)
        initially_running = rc == 0 and b'running' in out.lower()
        if initially_running:
            assert not run('running-containers', ['docker','ps','--format','{{.ID}}'])[1].strip()
            assert not run('running-builds', ['docker','buildx','history','ls','--filter','status=running','--format','json'])[1].strip()
        else:
            assert rc == 1 and b'Could not retrieve status' in err and not out.strip()
        assert run('timesync-original', ['wsl.exe','--distribution','Ubuntu','--user','root','--exec','systemctl','is-active','systemd-timesyncd'])[1].strip() == b'active'
        record.update(initiallyRunning=initially_running, activeContainers=0, activeBuilds=0); save()
        try:
            run('timesync-pause', ['wsl.exe','--distribution','Ubuntu','--user','root','--exec','systemctl','stop','systemd-timesyncd'])
            assert run('timesync-paused', ['wsl.exe','--distribution','Ubuntu','--user','root','--exec','systemctl','is-active','systemd-timesyncd'], required=False)[1].strip() == b'inactive'
            run('chrony-before', ['wsl.exe','--system','--exec','chronyc','-n','tracking'])
            if initially_running:run('desktop-stop', ['docker','desktop','stop','--timeout','60'], 90)
            rc, out, err = run('stopped-status', ['docker','desktop','status'], required=False)
            assert rc == 1 and b'Could not retrieve status' in err and not out.strip()
            _, out, _ = run('running-distros', ['wsl.exe','--list','--running','--quiet'])
            names = out.decode('utf-16-le').replace('\x00','').lower()
            assert 'docker-desktop' not in names
            record['dockerConfirmedStopped'] = True; save()
            time.sleep(10)
            assert keeper.poll() is None
            set_keeper_phase(keeper, 'observe')
            run('clock-observation', [sys.executable,str(T/'observe_poc005_attempt023_clock_stability_v1.py')], 285)
            assert keeper.poll() is None
            assert run('timesync-still-paused-after-observation', ['wsl.exe','--distribution','Ubuntu','--user','root','--exec','systemctl','is-active','systemd-timesyncd'], required=False)[1].strip() == b'inactive'
            heartbeat_rows=[json.loads(line) for line in (OUT/'keeper.stdout').read_text().splitlines() if line.strip()]
            observed=[row for row in heartbeat_rows if row.get('phase')=='observe']
            assert len(observed)>=20 and all(row['identityUnchanged'] and row['timesyncState']=='inactive' for row in observed)
            record['continuousInactiveHeartbeatCount']=len(observed)
            record['clockObservationCompleted'] = True; save()
            run('chrony-after', ['wsl.exe','--system','--exec','chronyc','-n','tracking'])
            samples=[json.loads(line) for line in (T/'poc005-attempt023-clock-stability-v1/samples.jsonl').read_text().splitlines()]
            observation=json.loads((T/'poc005-attempt023-clock-stability-v1/result.json').read_text())
            assert len(samples)==3601 and observation['failure'] is None and not observation['discontinuities']
            a,z=samples[1200],samples[3600]
            qpc=z['windowsPerfAtReceiveNs']-a['windowsPerfAtReceiveNs']
            mono=((z['guest']['monotonicBeforeNs']+z['guest']['monotonicAfterNs'])-(a['guest']['monotonicBeforeNs']+a['guest']['monotonicAfterNs']))/2
            raw=z['guest']['monotonicRawNs']-a['guest']['monotonicRawNs']
            assert qpc>110*10**9 and abs(mono/qpc-1)<=0.0001 and abs(raw/qpc-1)<=0.0001
            record['stableSuffix']=dict(firstSequence=1200,lastSequence=3600,windowsQpcNanoseconds=qpc,monotonicPerWindowsSecond=mono/qpc,rawPerWindowsSecond=raw/qpc,maximumAdmissionRateDifferencePpm=100,core2000NanosecondsAnd1MillisecondPoliciesUnchanged=True)
            record['clockQualifiedForThisHeldIsolationWindow']=True;save()
            yield keeper
            assert keeper.poll() is None
    
        finally:
            try:
                if keeper.poll() is None:set_keeper_phase(keeper, 'idle')
            except Exception as e:
                record['keeperIdleAcknowledgmentError']=repr(e);save()
            try:
                run('timesync-restore', ['wsl.exe','--distribution','Ubuntu','--user','root','--exec','systemctl','start','systemd-timesyncd'])
                assert run('timesync-restored', ['wsl.exe','--distribution','Ubuntu','--user','root','--exec','systemctl','is-active','systemd-timesyncd'])[1].strip() == b'active'
                record['originalTimesyncRunningStateRestored'] = True; save()
            except Exception as e:
                record['timesyncRestoreError'] = repr(e); save()
            if initially_running:
                run('desktop-restore', ['docker','desktop','start','--timeout','90'], 120)
                for i in range(12):
                    rc, out, _ = run('restored-status-'+str(i), ['docker','desktop','status'], required=False)
                    if rc == 0 and b'running' in out.lower():
                        run('restored-engine', ['docker','info','--format','{{.ServerVersion}}'])
                        record['originalRunningStateRestored'] = True; save()
                        break
                    time.sleep(5)
            else:
                rc, out, err = run('restored-status-0', ['docker','desktop','status'], required=False)
                assert rc == 1 and b'Could not retrieve status' in err and not out.strip()
                _, out, _ = run('restored-running-distros', ['wsl.exe','--list','--running','--quiet'])
                assert 'docker-desktop' not in out.decode('utf-16-le').replace(chr(0), '').lower()
                record['originalRunningStateRestored'] = True; save()
            assert record['originalRunningStateRestored']
        assert record.get('originalTimesyncRunningStateRestored')
        record['controllerIntervalAndRestorationCompleted']=True;save()
        
    
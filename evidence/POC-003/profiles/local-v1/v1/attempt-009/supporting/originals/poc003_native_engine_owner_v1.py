"""Own one task-only Linux daemon; retain its data and wait for its actual terminal exit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess,time
T=Path(__file__).resolve().parent;D=T/'poc003-native-engine-owner-v1';R=Path('/tmp/guize-poc003-de8ad3f-v1/native-engine-v1');B=R/'bin'
assert os.getuid()==0;D.mkdir();manifest=json.loads((R/'preparation.json').read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert manifest['officialArchive']['sha256']=='cc21815cf1e2efed867dc9c8b96b46ffed8ea176ffab32b0aacb54726ded8f25'
for row in manifest['binaries']:
    p=B/row['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
assert (R/'daemon.json').read_bytes()==b'{}\n' and not (R/'daemon.pid').exists() and not (R/'docker.sock').exists() and not (R/'data').exists()
assert sha(R/'fixed-runtime-image.tar')=='d9d77ead7898dc405018fc066da9983d29ea1666b22c0010de524214718e70ff'
env=dict(os.environ,PATH=str(B)+':/usr/sbin:/usr/bin:/sbin:/bin',DOCKER_HOST='unix://'+str(R/'docker.sock'),DOCKER_CONFIG=str(R/'client-config'),DOCKER_CONTEXT='')
argv=[str(B/'dockerd'),'--config-file',str(R/'daemon.json'),'--data-root',str(R/'data'),'--exec-root',str(R/'exec'),'--pidfile',str(R/'daemon.pid'),'--host','unix://'+str(R/'docker.sock'),'--storage-driver','vfs','--bridge=none','--iptables=false','--ip6tables=false','--ip-forward=false','--ip-masq=false','--userland-proxy=false','--exec-opt','native.cgroupdriver=cgroupfs','--containerd-namespace','guize-poc003','--containerd-plugins-namespace','guize-poc003-plugins']
r=dict(kind='ACTUAL_OWNED_TASK_ONLY_NATIVE_ENGINE',ready=False,commands=[],daemonArgv=argv,globalConfigurationChanged=False,networkTcpListenerCreated=False,systemTimeSet=False,dataRetained=True)
def save():
    temp=D/'results.json.tmp';temp.write_text(json.dumps(r,indent=2)+'\n');temp.replace(D/'results.json')
def command(label,args,timeout=30):
    with (D/(label+'.stdout.raw')).open('xb') as out,(D/(label+'.stderr.raw')).open('xb') as err:
        child=subprocess.Popen([str(B/'docker'),*args],env=env,stdout=out,stderr=err)
        try:code=child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:child.kill();child.wait();raise
    r['commands'].append(dict(label=label,exitCode=code,actualWaitCompleted=True));save();assert code==0,(label,code)
    return (D/(label+'.stdout.raw')).read_bytes()
save();started=time.monotonic();daemon=None
try:
    with (D/'daemon.stdout.raw').open('xb') as out,(D/'daemon.stderr.raw').open('xb') as err:
        daemon=subprocess.Popen(argv,env=env,stdout=out,stderr=err,start_new_session=True)
    r.update(daemonPid=daemon.pid,daemonStartTicks=Path('/proc/'+str(daemon.pid)+'/stat').read_text().split(') ',1)[1].split()[19]);save()
    while not (R/'docker.sock').exists():
        assert daemon.poll() is None,'owned daemon exited during startup';assert time.monotonic()-started<40;time.sleep(.2)
    os.chown(R/'docker.sock',1000,1000);os.chmod(R/'docker.sock',0o600)
    r['version']=json.loads(command('version',['version','--format','{{json .Server}}']))
    assert r['version']['Version']=='29.8.0'
    r['securityOptions']=json.loads(command('security',['info','--format','{{json .SecurityOptions}}']))
    assert 'name=seccomp,profile=builtin' in r['securityOptions']
    command('load-fixed-image',['image','load','--input',str(R/'fixed-runtime-image.tar')],timeout=120)
    image=json.loads(command('fixed-image',['image','inspect',manifest['imageTar']['expectedImageId']]))[0]
    assert image['Id']==manifest['imageTar']['expectedImageId'] and image['Os']=='linux' and image['Architecture']=='amd64'
    r.update(ready=True,imageId=image['Id'],readyAt=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'));save()
    while not (D/'release.json').exists():
        assert daemon.poll() is None,'owned daemon exited while reserved';assert time.monotonic()-started<1860,'native engine reservation deadline';time.sleep(.5)
except BaseException as error:
    r.update(failureType=type(error).__name__,failure=str(error)[:1024]);save();raise
finally:
    if daemon is not None:
        if daemon.poll() is None:daemon.send_signal(signal.SIGTERM)
        try:code=daemon.wait(timeout=25)
        except subprocess.TimeoutExpired:daemon.kill();code=daemon.wait(timeout=5);r['forcedDaemonKill']=True
        r.update(ready=False,daemonActualWaitCompleted=True,daemonExitCode=code,finishedAt=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'));save()
print(json.dumps(dict(nativeEngineClosed=True,actualWaitCompleted=True,exitCode=r['daemonExitCode'],dataRetained=True)))

"""Actual same-source neutral ATS/observer rebuild; never start ATS or media."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,pwd,shutil,socket,subprocess,sys,tarfile,time
from owned_compile_session_v1 import run_owned_session
W=Path('/workspace');I=Path('/inputs');C=Path('/control');SOURCE='de8ad3f21df1578eac80e98d798f7adbcdb07d82';TREE='ce6f3e09ec72b88ddabf49e75d41b4159e36fdb9'
read=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert os.getuid()==os.geteuid()==1000 and pwd.getpwuid(1000).pw_name=='ubuntu' and Path.home()==Path('/home/ubuntu')
assert socket.gethostname()=='guize-poc003-build-de8ad3f' and sorted(p.name for p in Path('/sys/class/net').iterdir())==['lo']
a=read(C/'build-approval.json');m=read(I/'source-manifest.json')
assert a['buildExecutionApproved'] and a['approvedBy']=='/root/independent_review' and not a['mustFix'] and a['maximumActualAttempts']==1
assert (a['source'],a['tree'])==(SOURCE,TREE) and a['builderSha256']==sha(Path(__file__)) and a['ownerHelperSha256']==sha(C/'owned_compile_session_v1.py')
assert a['sourceManifestSha256']==sha(I/'source-manifest.json') and m['testedSource']==dict(commit=SOURCE,tree=TREE)
now=datetime.now(timezone.utc);parse=lambda x:datetime.fromisoformat(x.replace('Z','+00:00'));assert parse(a['validFrom'])<=now<parse(a['validUntil'])
for row in m['sourcePins']:
    p=I/'source'/row['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
assert len(m['sourcePins'])==74 and sha(I/'upstream.tar.xz')=='0e323e1c4c01d1506cfd49d4c6935dbebd125b187d9ba72fe909bd6b10d81110'
assert sha(I/'debian.tar.xz')=='f6db2b2fc572ac6150ea7ff12380d11871a83946a280a12b586978ac8a9ee173'
root=W/'build';root.mkdir();out=root/'compile';out.mkdir();pkg=root/'pkgroot';source=root/'upstream';source.mkdir();debian=root/'packaging';debian.mkdir()
for archive,dest in [(I/'upstream.tar.xz',source),(I/'debian.tar.xz',debian)]:
    with tarfile.open(archive) as tar:
        members=tar.getmembers();assert len(members)<20000 and sum(x.size for x in members)<256*1024**2
        tar.extractall(dest,filter='data')
src=source/'trafficserver-9.2.3';assert (src/'configure').is_file()
record=dict(kind='ACTUAL_FRESH_NEUTRAL_SAME_SOURCE_ATS_BUILD',testedSource=m['testedSource'],uid=os.getuid(),user=pwd.getpwuid(os.getuid()).pw_name,
    hostname=socket.gethostname(),home=str(Path.home()),kernel=dict(zip(('sysname','nodename','release','version','machine'),os.uname())),
    startedAt=now.isoformat(),sourceArchiveSha256=sha(I/'upstream.tar.xz'),debianArchiveSha256=sha(I/'debian.tar.xz'),commands=[],atsStarted=False,experimentExecuted=False,buildCompleted=False)
save=lambda:(out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
def run(label,argv,cwd,timeout):
    assert datetime.now(timezone.utc)<parse(a['validUntil']);old=Path.cwd();os.chdir(cwd)
    row=dict(label=label,argv=argv,cwd=str(cwd),startedAt=datetime.now(timezone.utc).isoformat())
    try:
        with (out/(label+'.stdout.raw')).open('xb') as stdout,(out/(label+'.stderr.raw')).open('xb') as stderr:
            owner=run_owned_session(argv,stdout,stderr,timeout)
    finally:os.chdir(old)
    row.update(owner=owner,actualWaitCompleted=owner['actualWaitCompleted'],exitCode=owner['exitCode'],finishedAt=datetime.now(timezone.utc).isoformat())
    row['logs']=[dict(file=label+'.'+k+'.raw',bytes=(out/(label+'.'+k+'.raw')).stat().st_size,sha256=sha(out/(label+'.'+k+'.raw'))) for k in ['stdout','stderr']]
    record['commands'].append(row);save();print(label,owner['exitCode'],flush=True)
    assert owner['actualWaitCompleted'] and owner['noLiveOwnedMembers'] and owner['leaderReapedAfterGroupClosure'] and not owner['timedOut'] and owner['exitCode']==0
patchroot=debian/'debian/patches';rows=[]
for index,line in enumerate((patchroot/'series').read_text().splitlines()):
    name=line.strip()
    if not name or name.startswith('#'):continue
    path=patchroot/name;assert path.resolve().is_relative_to(patchroot.resolve())
    run('ubuntu-patch-'+str(index),['patch','--batch','-p1','-i',str(path)],src,30);rows.append(dict(file=name,sha256=sha(path),exitCode=0))
assert [{k:x[k] for k in ['file','sha256']} for x in rows]==m['ubuntuPatches']
own=I/'source/poc/POC-03-ats-range/instrumentation';instrumentation=read(own/'patch-manifest.json')
assert sha(own/'patch-manifest.json')==m['instrumentationSha256']=='80c2cc37a6a6ed36738be20eef1e3efa59e69780f3549562ceee7e7a115f0010'
assert instrumentation['payloadPoolBatchPolicy']['requestedElementsPerGrowth']==1 and instrumentation['aggregationCapacityPolicy']['bytesPerVolume']==1048576
assert instrumentation['aggregationCapacityPolicy']['originalLabTargetFragmentSizeBytes']==8192 and instrumentation['payloadPoolBatchPolicy']['maximumBufferedBytesAcceptanceThreshold']==8388608
assert sha(own/'ats-live-buffer-accounting.patch')==instrumentation['patchSha256']
for x in instrumentation['files']:assert sha(src/x['path'])==x['beforeSha256']
run('instrumentation-check',['git','apply','--check',str(own/'ats-live-buffer-accounting.patch')],src,30)
run('instrumentation-apply',['git','apply',str(own/'ats-live-buffer-accounting.patch')],src,30)
for x in instrumentation['additionalHeaders']:
    assert sha(own/x['source'])==x['sha256'];shutil.copyfile(own/x['source'],src/x['installed'])
for x in instrumentation['files']:assert sha(src/x['path'])==x['afterSha256']
prep=dict(kind='ACTUAL_NEW_UPSTREAM_AND_UBUNTU_SOURCE_PREPARATION',sourceRoot=str(src),sourceArchiveSha256=record['sourceArchiveSha256'],patches=rows,atsStarted=False)
(root/'source-preparation.json').write_text(json.dumps(prep,indent=2)+'\n');record.update(sourcePreparation=prep,instrumentation=instrumentation);save()
os.environ.update(CFLAGS='-O2 -g0',CXXFLAGS='-O2 -g0',PYTHONDONTWRITEBYTECODE='1')
for label,argv,timeout in [('autoreconf',['autoreconf','-if'],180),('configure',['./configure','--prefix=/usr','--enable-layout=Debian','--disable-tests','--disable-hwloc','--disable-unwind','--enable-experimental-plugins','--with-yaml-cpp=/usr'],180),('make',['make','-j2'],1200),('install',['make','install','DESTDIR='+str(pkg)],180)]:run(label,argv,src,timeout)
record.update(artifacts=[dict(file=p.relative_to(pkg).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(pkg.rglob('*')) if p.is_file() and not p.is_symlink()],buildCompleted=True,finishedAt=datetime.now(timezone.utc).isoformat(),stockEquivalentPerformanceClaimed=False,fullMediaCoverageProven=False,experimentApproved=False);save()
sdk=pkg/'usr/include';poc=I/'source/poc/POC-03-ats-range'
run('build-exporter',[sys.executable,str(poc/'build_observer.py'),'--include',str(sdk),'--out',str(root/'exporter')],W,120)
run('build-live-observer',[sys.executable,str(poc/'instrumentation/build_live_observer.py'),'--include',str(sdk),'--out',str(root/'live-observer')],W,120)
deps=root/'dependencies';deps.mkdir()
for name in ['libpcre.so.3','libyaml-cpp.so.0.8']:
    p=Path('/usr/lib/x86_64-linux-gnu')/name;assert p.is_file();shutil.copyfile(p.resolve(),deps/name)
record.update(allThreeBuildsCompleted=True,finishedAt=datetime.now(timezone.utc).isoformat());save()
print(json.dumps(dict(buildCompleted=True,allThreeBuildsCompleted=True,atsStarted=False,experimentExecuted=False)),flush=True)

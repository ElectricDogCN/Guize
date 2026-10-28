"""Create a genuinely fresh synthetic1m fixture only through its reviewed wrapper."""
import argparse,gzip,hashlib,itertools,json,os,shutil,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath

t=Path(__file__).resolve().parent;w=t/'poc005-attempt011-runtime-15dcd6c'
parser=argparse.ArgumentParser();parser.add_argument('--source-review',type=Path,required=True);args=parser.parse_args()
assert os.name=='nt' and args.source_review.resolve().parent==t.resolve()
review_raw=args.source_review.read_bytes();review=json.loads(review_raw)
assert hashlib.sha256(review_raw).hexdigest()=='4bda4cbbdd3a611cc4f40c79b1da2b8fd85e5159eb81fabb6fb85193d1abb0b1'
assert all(review[k] for k in ['fullSourceAccepted','latestSourceCiAccepted','unapprovedTemplatePreparationMayProceed']) and not review['mustFix']
source=review['source'];assert source=='15dcd6cd22a576821cdbe0f936002ad9a1be69e3'
git=lambda *a:subprocess.check_output(['git','-c','core.longpaths=true','-C',str(w),*a]).decode().strip()
assert git('rev-parse','HEAD')==source and not git('status','--porcelain','--untracked-files=all')
code=w/'poc/POC-05-metadata-scale';sys.path.insert(0,str(code))
from canonical_metadata import generate_canonical
from metadata_scan import file_sha256
import yaml
task=yaml.safe_load((w/'specs/tasks/POC-005.md').read_text(encoding='utf-8').split('---',2)[1])
assert task['implementer']=='/root' and task['reviewer']=='/root/gz022_planning_independent_review' and task['status']=='in_progress'
assert task['baseSha']=='746e23e582501fa08380c3f3301bdc1774902f7c'
parent=Path.home()/'.codex/local-lab';assert parent.is_dir() and shutil.disk_usage(parent).free>=20*1024**3
memory=subprocess.check_output(['powershell.exe','-NoProfile','-Command','[Console]::Write(([long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory)*1024)'],timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
assert int(memory.strip())>=4*1024**3
target=parent/'poc005-native-windows-v8-1m-attempt011'
assert not target.exists() and target.resolve().parent==parent.resolve()
inputs=w/'evidence/POC-005/profiles/local-v1/v1/inputs-1m-attempt011';assert not inputs.exists()
original=w/'evidence/POC-005/profiles/local-v1/v1/inputs'
reused={'expected-changes.jsonl':'c1eb4e21860fdbb307b28905dffcd9f8a4329e05ef2638ade09690076def56fd',
        'change-profiles.jsonl':'3324eef3cb42ae32e9e21433f2f60d0070d51291659bf7d5a27b422e5754be74',
        'updated-probe.bin':'22250e12fcdfd3b338e9fcad5848a7225a8d39646f3d071ab9dac6dfd4fe0b8d',
        'created-probe.bin':'785b0751fc2c53dc14a4ce3d800e69ef9ce1009eb327ccf458afe09c242c26c9',
        'baseline-probe.bin':'c8f5d0341d54d951a71b136e6e2afcb14d11ed8489a7ae126a8fee0df6ecf193'}
for name,digest in reused.items():assert file_sha256(original/name)==digest
started=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
target.mkdir();root=target/'fixture';root.mkdir();plain=target/'metadata-plain';plain.mkdir();inputs.mkdir()
recipe=generate_canonical(plain/'baseline.jsonl',plain/'profiled.jsonl',file_count=1000000,directory_count=500,maximum_depth=12,seed=20261015)
for name in ['baseline.jsonl','profiled.jsonl']:
    with (plain/name).open('rb') as source_file,(inputs/(name+'.gz')).open('xb') as physical:
        with gzip.GzipFile(filename='',mode='wb',fileobj=physical,mtime=0) as output:shutil.copyfileobj(source_file,output,65536)
for name,digest in reused.items():
    with (original/name).open('rb') as source_file,(inputs/name).open('xb') as output:shutil.copyfileobj(source_file,output,65536)
    assert file_sha256(inputs/name)==digest
expected={p.name:file_sha256(p) for p in sorted(inputs.iterdir())}
assert set(expected)==set(reused)|{'baseline.jsonl.gz','profiled.jsonl.gz'}
probe=(inputs/'baseline-probe.bin').read_bytes()
def extended(path):
    assert path.is_absolute() and path.is_relative_to(target)
    return '\\\\?\\'+str(path)
def mtime(row):
    delta=datetime.fromisoformat(row['modifiedAt'].replace('Z','+00:00'))-datetime(1970,1,1,tzinfo=timezone.utc)
    return (delta.days*86400+delta.seconds)*1000000000+delta.microseconds*1000
def rows():
    with gzip.open(inputs/'profiled.jsonl.gz','rb') as stream:
        while True:
            raw=stream.readline(65537)
            if not raw:break
            assert len(raw)<=65536 and raw.endswith(b'\n')
            row=json.loads(raw);relative=row['path'];parts=PurePosixPath(relative)
            assert relative and not parts.is_absolute() and not any(p in ('.','..') for p in parts.parts)
            assert '\\' not in relative and ':' not in relative and row['kind'] in ('file','directory')
            assert type(row['fileSizeBytes']) is int and 0<=row['fileSizeBytes']<=4096
            yield row
def create_file(row):
    path=root/row['path'];ref=extended(path)
    wanted=probe if row['objectId']=='f-000000003' else bytes(row['fileSizeBytes'])
    assert len(wanted)==row['fileSizeBytes']
    with open(ref,'xb') as output:assert output.write(wanted)==len(wanted)
    ns=mtime(row);os.utime(ref,ns=(ns,ns))
    with open(ref,'rb') as stream:
        before=os.fstat(stream.fileno());actual=stream.read(4097);after=os.fstat(stream.fileno())
    assert actual==wanted and before.st_nlink==after.st_nlink==1 and before.st_mtime_ns==after.st_mtime_ns==ns
    assert all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
    return dict(objectId=row['objectId'],path=row['path'],bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest(),mtimeNs=ns)
counts={'file':0,'directory':0};expected_paths=set();directories=[];target_probe=None
def file_rows():
    global target_probe
    for row in rows():
        assert row['path'] not in expected_paths;expected_paths.add(row['path']);counts[row['kind']]+=1
        path=root/row['path'];assert path.resolve().is_relative_to(root.resolve()) and path!=root and not path.exists()
        if row['kind']=='directory':
            os.mkdir(extended(path));directories.append(row)
        else:
            if row['objectId']=='f-000000003':target_probe=row
            yield row
payload_bytes=0;created=0;payloads=target/'payloads.jsonl.gz'
with payloads.open('xb') as physical:
 with gzip.GzipFile(filename='',mode='wb',fileobj=physical,mtime=0) as journal:
  with ThreadPoolExecutor(max_workers=4) as pool:
   iterator=file_rows()
   while True:
    batch=list(itertools.islice(iterator,32))
    if not batch:break
    for fact in pool.map(create_file,batch):
        journal.write((json.dumps(fact,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())
        created+=1;payload_bytes+=fact['bytes']
        if created%50000==0:print(json.dumps(dict(kind='fixture_preparation_progress_only',createdAndRereadFiles=created,expectedFiles=1000000,scannerStarted=False)),flush=True)
assert target_probe is not None and created==1000000
updates=[json.loads(line) for line in (inputs/'change-profiles.jsonl').read_bytes().splitlines()]
assert updates[0]['path'] not in expected_paths and updates[0]['objectId']=='controlled-created-001'
assert updates[1]['path']==target_probe['path'] and updates[1]['fileSizeBytes']==target_probe['fileSizeBytes']
for row in sorted(directories,key=lambda row:row['depth'],reverse=True):
    ref=extended(root/row['path']);ns=mtime(row);os.utime(ref,ns=(ns,ns));assert os.stat(ref).st_mtime_ns==ns
actual={'file':0,'directory':0};actual_paths=set();pending=[root]
while pending:
    with os.scandir(extended(pending.pop())) as entries:
        for entry in entries:
            assert not entry.is_symlink()
            path=Path(entry.path.removeprefix('\\\\?\\'));relative=path.relative_to(root).as_posix()
            if entry.is_dir(follow_symlinks=False):actual['directory']+=1;pending.append(path)
            else:assert entry.is_file(follow_symlinks=False);actual['file']+=1
            actual_paths.add(relative)
assert actual==counts=={'file':1000000,'directory':500} and payload_bytes==1792000000
assert actual_paths==expected_paths and len(actual_paths)==1000500
for name,digest in expected.items():assert file_sha256(inputs/name)==digest
record=dict(kind='fresh_candidate_native_windows_1m_filesystem_preparation_only',source=source,sourceReviewSha256=hashlib.sha256(review_raw).hexdigest(),
    startedAt=started,completedAt=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),preparationProcessId=os.getpid(),
    filesystemRoot=str(root),storageRoot=str(target),inputRoot=inputs.relative_to(w).as_posix(),inputs=expected,
    actualFilesystemCounts=actual,actualPayloadBytes=payload_bytes,plainGeneratorRecipe=recipe,
    minimumFreeMemoryBeforeBytes=4*1024**3,observedFreeMemoryBeforeBytes=int(memory.strip()),minimumFreeDiskBeforeBytes=20*1024**3,
    compressedInputBytes={p.name:p.stat().st_size for p in inputs.iterdir() if p.name.endswith('.gz')},
    plainMetadataRoot=str(plain),payloadMap=dict(ref=str(payloads),bytes=payloads.stat().st_size,sha256=file_sha256(payloads)),
    maximumParallelFileOperations=4,maximumQueuedFileRows=32,
    allPayloadsReread=True,allMtimesReread=True,exactFullPathInventoryRevalidated=True,olderFixturesPreserved=True,
    sourceApiContacted=False,scannerExperimentExecuted=False,approved=False,qualificationAccepted=False)
for path in [target/'preparation.json',t/'poc005-attempt011-windows-native-fixture-preparation.json']:
    with path.open('x',encoding='utf-8',newline='\n') as output:json.dump(record,output,indent=2);output.write('\n')
print(json.dumps(record),flush=True)

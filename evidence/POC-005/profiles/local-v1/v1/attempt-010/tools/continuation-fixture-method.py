"""Complete only reviewed missing synthetic files; retain interrupted originals."""
import argparse,gzip,hashlib,itertools,json,os,psutil,shutil,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath

t=Path(__file__).resolve().parent;w=t/'poc005-attempt010-runtime-ed8fbf3'
parser=argparse.ArgumentParser();parser.add_argument('--source-review',type=Path,required=True);args=parser.parse_args()
assert os.name=='nt'
sha=lambda data:hashlib.sha256(data).hexdigest()
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
source_raw=args.source_review.read_bytes();source=json.loads(source_raw)
assert args.source_review.resolve().parent==t.resolve()
assert sha(source_raw)=='d0949b495b92d3e9715553ce1ac2154a34203eb7780273827d695407bac99648'
assert source['source']=='ed8fbf32783c2600f75de7a69ef56c6f33b4824b' and source['fullSourceAccepted'] and source['latestSourceCiAccepted'] and source['mustFix']==[]
git=lambda *a:subprocess.check_output(['git','-c','core.longpaths=true','-C',str(w),*a],timeout=30)
assert git('rev-parse','HEAD').decode().strip()==source['source'] and not git('diff','--name-only','HEAD')
decision_raw=(t/'poc005-attempt010-continuation-v1-independent-review.json').read_bytes();decision=json.loads(decision_raw)
assert decision['decision']=='approved_interrupted_resource_completion_only' and decision['mustFix']==[]
audit_root=t/'poc005-attempt010-interrupted-names-audit-20261027'
audit_raw=(audit_root/'results.json').read_bytes();audit=json.loads(audit_raw)
assert sha(audit_raw)==decision['partialAuditSha256'] and audit['actualExistingFileNames']==667845
assert digest(audit_root/'path-inventory.jsonl.gz')==audit['pathInventory']['sha256']
lab=Path.home()/'.codex/local-lab/poc005-native-windows-v7-1m';root=lab/'fixture'
assert lab.resolve()==lab.absolute() and root.resolve()==root.absolute()
assert shutil.disk_usage(lab).free>=20*1024**3 and psutil.virtual_memory().available>=4*1024**3
for pid in (147956,97876):assert not psutil.pid_exists(pid),'Old numeric PID became occupied; stop without touching it'
assert not (lab/'preparation.json').exists() and not (t/'poc005-attempt010-windows-native-fixture-preparation.json').exists()
journal=lab/'payloads.jsonl';assert digest(journal)==audit['oldPayloadJournal']['sha256']
inputs=w/'evidence/POC-005/profiles/local-v1/v1/inputs-1m-attempt010'
expected_inputs={'baseline.jsonl.gz':'ad0e9fc6739de60a4b773437a7a1e7be11ca6f7b8c9cc80388ac6613dd30d388',
 'profiled.jsonl.gz':'c3dcb34521809b954b0f7862707658ce6d4f60c2c13769db47e75b832c638cd8',
 'expected-changes.jsonl':'c1eb4e21860fdbb307b28905dffcd9f8a4329e05ef2638ade09690076def56fd',
 'change-profiles.jsonl':'3324eef3cb42ae32e9e21433f2f60d0070d51291659bf7d5a27b422e5754be74',
 'updated-probe.bin':'22250e12fcdfd3b338e9fcad5848a7225a8d39646f3d071ab9dac6dfd4fe0b8d',
 'created-probe.bin':'785b0751fc2c53dc14a4ce3d800e69ef9ce1009eb327ccf458afe09c242c26c9',
 'baseline-probe.bin':'c8f5d0341d54d951a71b136e6e2afcb14d11ed8489a7ae126a8fee0df6ecf193'}
assert {p.name for p in inputs.iterdir()}==set(expected_inputs)
for name,digest_value in expected_inputs.items():assert digest(inputs/name)==digest_value
probe=(inputs/'baseline-probe.bin').read_bytes()
def extended(path):return '\\\\?\\'+str(path.absolute())
def names():
    files=set();directories=set();pending=[root]
    while pending:
        with os.scandir(extended(pending.pop())) as entries:
            for entry in entries:
                assert not entry.is_symlink()
                path=Path(entry.path.removeprefix('\\\\?\\'));relative=path.relative_to(root).as_posix()
                if entry.is_dir(follow_symlinks=False):directories.add(relative);pending.append(path)
                else:assert entry.is_file(follow_symlinks=False);files.add(relative)
    return files,directories
initial_files=set();initial_dirs=set()
with gzip.open(audit_root/'path-inventory.jsonl.gz','rb') as stream:
    for line in stream:
        row=json.loads(line)
        (initial_files if row['kind']=='file' else initial_dirs).add(row['path'])
assert names()==(initial_files,initial_dirs)
assert len(initial_files)==667845 and len(initial_dirs)==500
new_journal=lab/'payloads-continuation-v1.jsonl.gz';assert not new_journal.exists()
directory_snapshot=lab/'continuation-v1-directory-mtimes-before.json'
directory_before=[dict(path=relative,mtimeNs=os.stat(extended(root/relative)).st_mtime_ns) for relative in sorted(initial_dirs)]
with directory_snapshot.open('x',encoding='utf8',newline='\n') as stream:json.dump(directory_before,stream,indent=2);stream.write('\n')
started=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
expected_paths=set();directories=[];counts={'file':0,'directory':0};metadata_bytes=0
def rows():
    with gzip.open(inputs/'profiled.jsonl.gz','rb') as stream:
        while True:
            raw=stream.readline(65537)
            if not raw:break
            assert len(raw)<=65536 and raw.endswith(b'\n')
            row=json.loads(raw);relative=row['path'];parts=PurePosixPath(relative)
            assert relative and not parts.is_absolute() and not any(p in ('.','..') for p in parts.parts) and '\\' not in relative and ':' not in relative
            assert row['kind'] in ('file','directory') and 0<=row['fileSizeBytes']<=4096
            yield row
def mtime(row):
    delta=datetime.fromisoformat(row['modifiedAt'].replace('Z','+00:00'))-datetime(1970,1,1,tzinfo=timezone.utc)
    return (delta.days*86400+delta.seconds)*1000000000+delta.microseconds*1000
def read_file(row,create):
    path=root/row['path'];ref=extended(path);wanted=probe if row['objectId']=='f-000000003' else bytes(row['fileSizeBytes'])
    ns=mtime(row)
    if create:
        with open(ref,'xb') as output:assert output.write(wanted)==len(wanted)
        os.utime(ref,ns=(ns,ns))
    with open(ref,'rb') as stream:
        before=os.fstat(stream.fileno());actual=stream.read(4097);after=os.fstat(stream.fileno())
    assert actual==wanted and before.st_nlink==after.st_nlink==1 and before.st_mtime_ns==after.st_mtime_ns==ns
    assert all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
    return dict(objectId=row['objectId'],path=row['path'],bytes=len(actual),sha256=sha(actual),mtimeNs=ns,
                origin='new-missing-file' if create else 'retained-interrupted-file')
def existing_rows():
    global metadata_bytes
    for row in rows():
        assert row['path'] not in expected_paths;expected_paths.add(row['path']);counts[row['kind']]+=1
        if row['kind']=='directory':directories.append(row)
        else:
            metadata_bytes+=row['fileSizeBytes']
            if row['path'] in initial_files:yield row
def missing_rows():
    for row in rows():
        if row['kind']=='file' and row['path'] not in initial_files:yield row
completed={'existing':0,'created':0};actual_bytes=0
with new_journal.open('xb') as physical:
 with gzip.GzipFile(filename='',mode='wb',fileobj=physical,mtime=0) as output:
  with ThreadPoolExecutor(max_workers=4) as pool:
   for phase,iterator,create in [('existing',existing_rows(),False),('created',missing_rows(),True)]:
    # No fixture write is submitted until the complete existing-file pass succeeded.
    if create:
        assert completed['existing']==667845 and counts=={'file':1000000,'directory':500}
        assert metadata_bytes==1792000000 and initial_dirs=={row['path'] for row in directories}
        assert initial_files<=expected_paths
        assert digest(inputs/'profiled.jsonl.gz')==expected_inputs['profiled.jsonl.gz']
    while True:
        batch=list(itertools.islice(iterator,32))
        if not batch:break
        for fact in pool.map(lambda row:read_file(row,create),batch):
            output.write((json.dumps(fact,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())
            completed[phase]+=1;actual_bytes+=fact['bytes']
            if completed[phase]%50000==0:print(json.dumps(dict(kind='resource_completion_progress_only',phase=phase,files=completed[phase],scannerStarted=False)),flush=True)
assert completed=={'existing':667845,'created':332155} and actual_bytes==1792000000
actual_files,actual_dirs=names()
assert actual_files|actual_dirs==expected_paths and len(actual_files)==1000000 and len(actual_dirs)==500
# Directory mtimes were unfinished by the original interrupted operation. Finish only that declared metadata.
for row in sorted(directories,key=lambda value:value['depth'],reverse=True):
    ref=extended(root/row['path']);ns=mtime(row)
    os.utime(ref,ns=(ns,ns));assert os.stat(ref).st_mtime_ns==ns
assert digest(journal)==audit['oldPayloadJournal']['sha256']
for name,digest_value in expected_inputs.items():assert digest(inputs/name)==digest_value
record=dict(kind='candidate_native_windows_1m_filesystem_preparation_after_reviewed_interruption_completion',source=source['source'],
 sourceReviewSha256=sha(source_raw),continuationReviewSha256=sha(decision_raw),partialNameAuditSha256=sha(audit_raw),
 startedAt=started,completedAt=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),preparationProcessId=os.getpid(),
 filesystemRoot=str(root),storageRoot=str(lab),inputRoot=inputs.relative_to(w).as_posix(),inputs=expected_inputs,
 actualFilesystemCounts={'file':len(actual_files),'directory':len(actual_dirs)},actualPayloadBytes=actual_bytes,
 actualExistingFilesReread=completed['existing'],actualMissingFilesCreatedAndReread=completed['created'],
 allPayloadsReread=True,allMtimesReread=True,exactFullPathInventoryRevalidated=True,olderFixturesPreserved=True,
 existingFileContentsAndMtimesNotRewritten=True,existingDirectoriesCanonicalMtimesCompleted=True,
 directoryMtimesBefore=dict(ref=str(directory_snapshot),bytes=directory_snapshot.stat().st_size,sha256=digest(directory_snapshot)),
 interruptedOriginalJournalPreserved=audit['oldPayloadJournal'],originalRunStillHasNoTerminalReceipt=True,
 payloadMap=dict(ref=str(new_journal),bytes=new_journal.stat().st_size,sha256=digest(new_journal)),
 compressedInputBytes={name:(inputs/name).stat().st_size for name in expected_inputs if name.endswith('.gz')},
 plainMetadataRoot=str(lab/'metadata-plain'),generationWasNotRepeated=True,
 minimumFreeDiskBeforeBytes=20*1024**3,minimumFreeMemoryBeforeBytes=4*1024**3,
 sourceApiContacted=False,scannerExperimentExecuted=False,approved=False,qualificationAccepted=False)
for path in (lab/'preparation.json',t/'poc005-attempt010-windows-native-fixture-preparation.json'):
    with path.open('x',encoding='utf8',newline='\n') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(record),flush=True)

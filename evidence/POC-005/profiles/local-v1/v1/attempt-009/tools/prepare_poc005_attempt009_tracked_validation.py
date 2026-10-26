"""Commit only actual Own-profile evidence and export a clean qualification context."""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

t=Path(__file__).resolve().parent
w=t/'poc005-attempt009-runtime-c98c93f'
source='c98c93f835ea5c6bfcf19eb1256cd66d75efc4b4'
branch='chore/POC-005-metadata-scale'
prefix='evidence/POC-005/profiles/local-v1/v1/attempt-009/'
slot=w/prefix
input_prefix='evidence/POC-005/profiles/local-v1/v1/inputs-100k-attempt009/'
input_names=['baseline.jsonl.gz','profiled.jsonl.gz','expected-changes.jsonl','change-profiles.jsonl','updated-probe.bin','created-probe.bin','baseline-probe.bin']


def git(*args,input=None):
    return subprocess.check_output(['git','-c','core.longpaths=true','-c','core.autocrlf=false','-C',str(w),*args],input=input)


dec=lambda *args:git(*args).decode('utf-8').strip()
assert dec('rev-parse','HEAD')==source and dec('branch','--show-current')==branch
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
execution=json.loads((slot/'controller-execution.json').read_bytes())
assert execution['exitCode']==0 and execution['actualWaitCompleted'] and not execution['overallDeadlineExceeded']
assembled=json.loads((slot/'execution-candidate.json').read_bytes())
selection=json.loads((slot/'raw-selection.json').read_bytes())
assert assembled['environmentCaptured']['testedSource']=={'commit':source,'tree':'487a8d3b40f59c3939f79e5430cc31ccbf8fbace'}
assert not selection['fullQualificationValidated'] and not selection['qualificationAccepted']
assert (slot/'.gitattributes').read_bytes()==b'* -text whitespace=cr-at-eol\n'
referenced=set(assembled['rawOutputRefs'])
referenced.add(assembled['environmentCaptured']['inputSampleArtifacts'][0]['inputArtifactRef'])
referenced.add(assembled['environmentCaptured']['acceptanceProfileConfigurationRef'])
referenced.update(r['configurationRef'] for r in assembled['resources'])
referenced.update(s['approvalRef'] for s in assembled['samples'])
referenced.add('evidence/POC-005/profiles/local-v1/v1/attempt-009/execution-candidate.json')
untracked=set(dec('ls-files','--others','--exclude-standard').splitlines())
assert all(path.startswith((prefix,input_prefix)) for path in untracked)
assert all(not (w/ref).is_symlink() and (w/ref).is_file() for ref in referenced)
files=sorted([path for path in slot.rglob('*') if path.is_file()]+[w/input_prefix/name for name in input_names])
assert all(not path.is_symlink() and (path.resolve().is_relative_to(slot.resolve()) or path.relative_to(w).as_posix() in {input_prefix+name for name in input_names}) for path in files)
databases=[path for path in files if '.sqlite' in path.name]
owned=[path for path in files if path not in databases]
assert all(path.stat().st_size<64*1024*1024 for path in owned)
paths=[path.relative_to(w).as_posix() for path in owned]
assert paths==sorted(set(paths))
assert all(path.startswith((prefix,input_prefix)) and '\n' not in path and '\r' not in path for path in paths)
inventory_ref=prefix+'evidence-delivery-inventory.json'
assert not (w/inventory_ref).exists()
record=dict(kind='actual_own_profile_evidence_delivery_inventory',sourceRuntime=source,branch=branch,
    preparedAt=datetime.now(timezone.utc).isoformat(),paths=sorted(paths+[inventory_ref]),
    databaseOriginalsRetainedLocally=[p.relative_to(w).as_posix() for p in databases],
    referencedPaths=sorted(referenced),fullQualificationValidated=False,taskCompleted=False)
with (w/inventory_ref).open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(record,indent=2)+'\n')
paths=record['paths']
# Pass a bounded stdin path list; never build one oversized shell command.
for offset in range(0,len(paths),100):
    git('add','--',*paths[offset:offset+100])
assert dec('diff','--cached','--name-only').splitlines()==paths
assert not git('diff','--name-only')
stage={}
for entry in git('ls-files','--stage','-z','--',prefix,input_prefix).split(b'\0'):
    if not entry:continue
    info,name=entry.split(b'\t',1)
    mode,sha,stage_number=info.decode().split()
    assert mode=='100644' and stage_number=='0'
    stage[name.decode('utf-8')]=sha
actual=git('hash-object','--no-filters','--stdin-paths',input=('\n'.join(paths)+'\n').encode()).decode().splitlines()
assert len(actual)==len(paths) and set(stage)==set(paths)
assert all(stage[path]==sha for path,sha in zip(paths,actual)), 'Actual raw bytes differ from staged Git blobs'
git('commit','-m','chore(POC-005): retain actual attempt009 execution evidence','-m','Refs #132. Evidence: '+prefix)
head=dec('rev-parse','HEAD')
assert dec('show','-s','--format=%P',head)==source
assert dec('diff','--name-only',source,head).splitlines()==paths
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
bundle=t/('poc005-attempt009-evidence-'+head[:7]+'.bundle')
assert not bundle.exists()
git('bundle','create',str(bundle),branch)
clone=t/('poc005-attempt009-validation-'+head[:7])
assert not clone.exists()
subprocess.run(['git','-c','core.longpaths=true','clone','--quiet','--branch',branch,'--config','core.longpaths=true','--config','core.autocrlf=false',str(bundle),str(clone)],check=True)
clone_git=lambda *args:subprocess.check_output(['git','-c','core.longpaths=true','-c','core.autocrlf=false','-C',str(clone),*args],text=True).strip()
assert clone_git('rev-parse','HEAD')==head and not clone_git('status','--porcelain=v1','--untracked-files=all')
assert not (clone/'.git/objects/info/alternates').exists()
subprocess.run(['git','-c','core.longpaths=true','-C',str(clone),'merge-base','--is-ancestor',source,head],check=True)
receipt=dict(kind='actual_tracked_immutable_qualification_context',sourceRuntime=source,validationContextCommit=head,
    validationContextTree=clone_git('rev-parse','HEAD^{tree}'),parent=source,branch=branch,changedPaths=paths,
    rawBytesEqualStagedBlobs=True,onlyOwnProfileEvidenceChanged=True,clone=str(clone),cloneClean=True,noAlternates=True,
    bundle=bundle.name,bundleBytes=bundle.stat().st_size,bundleSha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
    allReferencedInputsAndRecordsTracked=True,fullQualificationValidated=False,published=False,taskCompleted=False)
with (t/'poc005-attempt009-tracked-validation-context.json').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(validationContextCommit=head,clone=str(clone),pathCount=len(paths),cloneClean=True,rawBytesEqualStagedBlobs=True,published=False)),flush=True)

from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
T=Path(__file__).resolve().parent;W=T/'poc003-pool-batch-performance-v1';PREFIX='evidence/POC-003/profiles/local-v1/v1/attempt-005/'
O=T/'poc003-common-main1b5c68b-attempt005-staged-byte-verification-v1';assert not O.exists();O.mkdir()
git=lambda *a:subprocess.check_output(['git','-C',str(W),*a])
assert git('rev-parse','HEAD').decode().strip()=='1b5c68bab02d98f8e11286d80033585090c7af99'
changed=git('diff','--cached','--name-only','-z').decode().split('\0');changed=[p for p in changed if p];assert len(changed)==746 and all(p.startswith(PREFIX) for p in changed)
entries=git('ls-files','--stage','-z','--',PREFIX).decode().split('\0');proof=[];total=0
for raw in entries:
 if not raw:continue
 identity,ref=raw.split('\t',1);mode,oid,stage=identity.split();assert stage=='0' and mode=='100644'
 p=W/ref;size=p.stat().st_size;assert p.is_file() and not p.is_symlink() and size<=67108864
 blob=hashlib.sha1(b'blob '+str(size).encode()+b'\0');digest=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(65536),b''):blob.update(block);digest.update(block)
 assert blob.hexdigest()==oid,ref
 total+=size;proof.append(dict(ref=ref,byteCount=size,gitBlob=oid,sha256=digest.hexdigest()))
assert len(proof)==746 and set(x['ref'] for x in proof)==set(changed)
r=dict(kind='ACTUAL_TRACKED_OWN_PROFILE_STAGED_BYTE_VERIFICATION',source='1b5c68bab02d98f8e11286d80033585090c7af99',files=len(proof),totalBytes=total,gitBlobMatchesActualBytes=True,sourcePathsChanged=False,observedAt=datetime.now(timezone.utc).isoformat(),filesVerified=proof,formalPocAccepted=False)
(O/'results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='filesVerified'}))

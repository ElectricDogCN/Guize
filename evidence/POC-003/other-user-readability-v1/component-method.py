from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parent
out=root/'poc003-readability-other-user-components-v1';out.mkdir()
w=root/'poc003-pool-batch-performance-v1/poc/POC-03-ats-range'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pins={n:sha(w/n) for n in ['collect.py','cache_probe.py','test_request_readability.py']}
old=json.loads((root/'poc003-readability-capture-components-v2/results.json').read_bytes())
argv=[a.replace('poc003-readability-capture-components-v2/','poc003-readability-other-user-components-v1/') for a in old['argv']]
result=dict(kind='OFFLINE_AND_NATIVE_FILESYSTEM_OTHER_USER_TARGET_COMPONENTS_ONLY',sourceBase='6ee3e04cb065f000516259624804ac776146fa46',workingTreeDeltaUncommitted=True,sourcePins=pins,argv=argv,startedAt=datetime.now(timezone.utc).isoformat(),realAtsExperimentExecuted=False,formalPocAccepted=False)
with (out/'tests.stdout.raw').open('xb') as stdout,(out/'tests.stderr.raw').open('xb') as stderr:
 child=subprocess.Popen(argv,stdout=stdout,stderr=stderr);code=child.wait()
result.update(pid=child.pid,actualWaitCompleted=True,exitCode=code,finishedAt=datetime.now(timezone.utc).isoformat(),sourceFilesUnchanged=pins=={n:sha(w/n) for n in pins})
if (out/'junit.xml').exists():
 suite=ET.parse(out/'junit.xml').getroot();result['junit']={k:sum(int(x.get(k,'0')) for x in suite.iter('testsuite')) for k in ['tests','failures','errors','skipped']}
for n in ['tests.stdout.raw','tests.stderr.raw','junit.xml']:
 if (out/n).exists():result[n]=dict(bytes=(out/n).stat().st_size,sha256=sha(out/n))
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
assert code==0 and result['sourceFilesUnchanged'] and result['junit']==dict(tests=27,failures=0,errors=0,skipped=0)

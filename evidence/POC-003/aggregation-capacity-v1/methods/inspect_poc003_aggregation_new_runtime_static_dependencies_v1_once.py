"""Read-only ELF dependency delta for the already-built aggregation package; no binary execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,subprocess
T=Path(__file__).resolve().parent;P=Path('/home/sur/.cache/guize-takeover/poc003-aggregation-ats-build-common2e-v1/pkgroot')
assert os.name=='posix' and os.getuid()==1000
old=json.loads((T/'poc003-owner-dependency-closure-readonly-v1/results.json').read_bytes())
br=T/'poc003-aggregation-ats-build-common2e-v1/receipt.json';assert hashlib.sha256(br.read_bytes()).hexdigest()=='9995d8a8fe286c9908062d142c61231cd40876980412a815f597fa927de32026'
build=json.loads(br.read_bytes());assert build['buildCompleted'] and not build['atsStarted']
expected={x['file']:x for x in build['artifacts']};assert len(expected)==245
O=T/'poc003-aggregation-new-runtime-static-dependency-delta-v1';O.mkdir();commands=[];rows=[]
for i,prior in enumerate(old['components'][:6]):
 name=prior['path'].split('/pkgroot/',1)[1];file=P/name;raw=file.read_bytes()
 assert len(raw)==expected[name]['bytes'] and hashlib.sha256(raw).hexdigest()==expected[name]['sha256']
 values={}
 for label,option in [('dynamic','-d'),('versions','-V')]:
  argv=['readelf',option,str(file)]
  with (O/(str(i)+'-'+label+'.stdout.raw')).open('xb') as stdout,(O/(str(i)+'-'+label+'.stderr.raw')).open('xb') as stderr:
   child=subprocess.Popen(argv,stdout=stdout,stderr=stderr);code=child.wait()
  commands.append(dict(argv=argv,pid=child.pid,actualWaitCompleted=True,exitCode=code));assert code==0
  values[label]=(O/(str(i)+'-'+label+'.stdout.raw')).read_text()
 actual=dict(path=str(file),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),needed=re.findall(r'Shared library: \[([^\]]+)\]',values['dynamic']),soname=re.findall(r'Library soname: \[([^\]]+)\]',values['dynamic']),versionNames=sorted(set(re.findall(r'Name: (\S+)',values['versions']))))
 assert all(actual[k]==prior[k] for k in ['needed','soname','versionNames']),name
 rows.append(dict(actual=actual,priorPath=prior['path'],priorSha256=prior['sha256'],staticDependencyNamesAndVersionsUnchanged=True))
result=dict(kind='READONLY_NEW_PACKAGE_ELF_DEPENDENCY_DELTA_NOT_RUNTIME_APPROVAL',observedAt=datetime.now(timezone.utc).isoformat(),image=old['image'],buildReceiptSha256=hashlib.sha256(br.read_bytes()).hexdigest(),componentCount=len(rows),components=rows,commands=commands,atsExecuted=False,containerCreated=False,dynamicAbiProven=False,formalPocAccepted=False)
(O/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(components=len(rows),commands=len(commands),allActualWaitZero=True,staticDependencyNamesAndVersionsUnchanged=True,atsExecuted=False)))

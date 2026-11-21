"""Prospective original15 assembler. Requires newM before-run authority and actual owned run.
No historical raw result is eligible. No result approval or profile locator is issued.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys
import jsonschema,yaml
from poc003_typed_record_assembly_v2 import assemble_typed_records
from poc003_request_cache_provenance_v2 import NativeRequestIndex,utc
from poc003_diagnostic_metric_conditions_v1 import derive_diagnostic_conditions

T=Path(__file__).resolve().parent
SOURCE='1b5c68bab02d98f8e11286d80033585090c7af99'
TREE='f94ed8da8d83391f2474365af848bf267a0dc8d1'
PREFIX='evidence/POC-003/profiles/local-v1/v1/attempt-005'
SCOPE='COMMON_MAIN1B5C68B_FULL_ORIGINAL15_MATRIX_AND_CANONICAL_ASSEMBLY'
P=Path('/home/sur/.cache/guize-takeover/poc003-common-main1b5c68b-inputs-v1')
D=Path('/home/sur/.cache/guize-takeover/poc003-common-main1b5c68b-full-original-matrix-v1/data')
RUN=T/'poc003-common-main1b5c68b-full-original-matrix-v1/results.json'
HELPERS={
 'poc003_typed_record_assembly_v2.py':'1e8d327dec99d7889eda3f1ebc8eea5ef87903703ca85926249e0d25fa19bd45',
 'poc003_request_cache_decisions_v2.py':'4b8a187fe0ff4d6826d58c3906fc206a13535a7f02ab5add43ee20fc0e3ebcdf',
 'poc003_canonical_record_materializer_v1.py':'b088bb13f425a65beb5f75cd98a4210c92edbd19b92a29017ed342212228ae5e',
 'poc003_canonical_derivation_v3.py':'1566bd295b53f6a4386c3527ee3d5edec978ff32ce26a1731d5822d747a6b2c9',
 'poc003_request_cache_provenance_v2.py':'167c1712170eb53cb0aed47f75ac27502a7f27dc9b255fc414fc5e9eb9e1bc56',
 'poc003_diagnostic_metric_conditions_v1.py':'58bdded9ebc4e319e5ac39797e0944f21c6dda70f1cfd9fe7458bc895429f789',
 'poc003_runtime_binding_authentication_v1.py':'6368b0b8d6bc0ac05440498be7645732602aa28af0ea972bdef49991798baf10',
 'poc003_native_epoch_association_v3.py':'ed431101228320babfce057619d5680a06c4e8da658c35b79b80eca7687cf7a9'}
read=lambda p:json.loads(Path(p).read_bytes())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def need(ok,msg):
 if not ok:raise ValueError(msg)
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,indent=2)+'\n')
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()

def verify_called_source(repo):
    paths=['poc/POC-03-ats-range','specs/poc','scripts/check-program-lifecycle-guards.py','scripts/poc-contract-repair-admission.py']
    names=git(repo,'ls-tree','-r','--name-only',SOURCE,'--',*paths).splitlines()
    need(names,'actual tested source file list required')
    for name in names:
        p=repo/name
        need(p.is_file() and not p.is_symlink(),'called source must be a regular tested file '+name)
        expected=subprocess.check_output(['git','-C',str(repo),'show',SOURCE+':'+name])
        need(p.read_bytes()==expected,'called source differs from tested M '+name)
    need(not git(repo,'ls-files','--others','--exclude-standard','--',*paths),'untracked source modules are ineligible')

def reject_actual_secrets(path,needles):
    need(all(isinstance(x,bytes) and 24<=len(x)<=256 for x in needles),'actual private credentials must be bounded')
    overlap=max(map(len,needles))-1;tail=b''
    with Path(path).open('rb') as f:
        while True:
            block=f.read(65536)
            if not block:break
            block=tail+block
            need(not any(secret in block for secret in needles),'credential-bearing original remains private; no redacted replacement issued')
            tail=block[-overlap:]

def authenticate(repo,approval_path,approval_sha):
 need(os.name=='posix' and os.getuid()==1000,'native guest UID1000 required')
 need(sha(approval_path)==approval_sha,'exact independent authority bytes required')
 a=read(approval_path)
 verify_called_source(repo)
 need(a['scope']==SCOPE and a['fullOriginalMatrixExecutionApproved'] is True and a['approvedBy']=='/root/independent_review' and not a['mustFix'],'new full scope authority required')
 need((a['source'],a['tree'])==(SOURCE,TREE),'new common source authority required')
 need(a['assemblerSha256']==sha(__file__),'prospective exact assembler binding required')
 for n,h in HELPERS.items():need(sha(T/n)==h,'assembler helper drift '+n)
 r=read(RUN)
 need(r['approvalSha256']==approval_sha and r['source']==SOURCE and r['methodSha256']==a['methodSha256'] and r['entrySha256']==a['entrySha256'],'actual run custody mismatch')
 need(r['rawMatrixCollectionCompleted'] and r['sourceUnchanged'] and r['derivedTemplateBytesUnchanged'],'actual complete unchanged run required')
 need(r['attachedCliWaitCompleted'] and r['engineWaitCompleted'] and r['attachedCliExitCode']==r['engineExitCode']==0 and not r['externalCleanup'],'actual terminal owned run required')
 need(not r['finalContainerState']['Running'] and r['finalContainerState']['Pid']==0,'owned container must be terminal')
 need(r['before']==r['after']==dict(head=SOURCE,tree=TREE,status=''),'runtime clean source binding required')
 need(git(repo,'show','-s','--format=%T',SOURCE)==TREE,'actual tested Git tree mismatch')
 subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',SOURCE,'HEAD'],check=True,capture_output=True)
 need(sha(P/'package-manifest.json')==a['packageManifestSha256'],'immutable input manifest changed')
 manifest=read(P/'package-manifest.json');need(manifest['source']==SOURCE,'package source mismatch')
 entries={x['path']:x for x in manifest['entries']}
 for n,e in entries.items():
  p=P/n
  if e['kind']=='symlink':need(p.is_symlink() and os.readlink(p)==e['target'] and p.resolve().is_relative_to(P),'package link drift')
  else:need(not p.is_symlink() and p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],'package content drift '+n)
 before=read(D/'before-environment.json');client=r['clientReport'];start=utc(client['workloadScopeStartedAt']);end=utc(r['finishedAt'])
 need(client['beforeEnvironmentCaptured'] and client['beforeEnvironmentSha256']==sha(D/'before-environment.json'),'actual before capture binding required')
 need(utc(before['capturedFinishedAt'])<=start<end and utc(a['approvedAt'])<=start and utc(a['validFrom'])<=start<end<=utc(a['validUntil']),'before approval/window ordering mismatch')
 need(before['environmentCaptured']['host_os']['uid']==1000 and before['environmentCaptured']['host_os']['pid']==1,'actual namespace environment mismatch')
 controls={}
 for n,e in a['beforeControlFiles'].items():
  p=approval_path.parent/n
  need(sha(p)==e['sha256'] and p.stat().st_size==e['bytes'],'before control bytes drift '+n)
  controls[n]=read(p)
 need(set(controls)=={'profile-configuration.json','resource-configuration.json','resource-booking.json','sample-approval.json','changed-sample-approval.json'},'all five independent before controls required')
 profile=controls['profile-configuration.json'];resource=controls['resource-configuration.json'];booking=controls['resource-booking.json'];sample=controls['sample-approval.json'];changed=controls['changed-sample-approval.json']
 need(profile['testedSource']==dict(commit=SOURCE,tree=TREE) and profile['decision']=='approved' and profile['approvedBy']==a['approvedBy'] and utc(profile['approvedAt'])<=start,'actual full profile approval mismatch')
 for item in (resource,booking):
  need(item['approvedBy']==a['approvedBy'] and item['status']=='approved' and utc(item['approvedAt'])<=start and utc(item['validFrom'])<=start<end<=utc(item['validUntil']),'resource/booking before authority mismatch')
 for item in (sample,changed):need(item['decision']=='approved' and item['approver']==a['approvedBy'] and utc(item['approvedAt'])<=start,'independent sample before authority mismatch')
 need(resource['configuration']['fullOriginal15QualificationApproved'] is True,'raw-only authority ineligible')
 return a,r,before,controls,entries,start,end

def assemble(repo,approval_path,approval_sha):
 a,r,before,controls,entries,start,end=authenticate(repo,approval_path,approval_sha)
 target=repo/PREFIX;need(not target.exists(),'new Own profile attempt required')
 W=D/'work';C=D/'original-matrix';cfg=read(W/'settings.private.json');collection=read(C/'collection.json')
 # Consume existing producer runtime bindings; never run a new runtime probe here.
 from poc003_runtime_binding_authentication_v1 import authenticate_runtime_bindings
 profile_path=P/'source/poc/POC-03-ats-range/python-runtime-profile.json'
 runtime_auth,runtime_paths=authenticate_runtime_bindings(D,collection,read(W/'media-request-window-closed.json'),before,profile_path.read_bytes(),start.isoformat(),end.isoformat())
 target.mkdir(parents=True)
 # Private credential-bearing settings and lab-guard.conf are never published.
 sys.path.insert(0,str(repo/'poc/POC-03-ats-range'))
 from media_capacity import complete_serial_native_epochs,closed_request_peaks,conservative_total
 required={str(Path(cfg['pkgroot'])/n):h for n,h in cfg['instrumentedRuntime']['components'].items()}
 for n,h in cfg['instrumentedRuntime']['components'].items():need(entries['runtime/pkgroot/'+n]['sha256']==h,'actual loaded instrumented component mismatch')
 for row in cfg['plugins'].values():
  need(entries[Path(row['path']).relative_to('/poc').as_posix()]['sha256']==row['sha256'],'actual plugin mismatch');required[row['path']]=row['sha256']
 required.update({str(Path('/runlab/work')/n):h for n,h in cfg['epochConfiguration'].items()})
 for n in ('epoch_owner.py','instrumentation/single_exec_gate.py','instrumentation/single_exec_filter.py'):
  need(entries['source/poc/POC-03-ats-range/'+n]['sha256']==cfg['implementationSources'][n],'actual execution source mismatch');required['/poc/source/poc/POC-03-ats-range/'+n]=cfg['implementationSources'][n]
 required[cfg['executionInterpreter']['path']]=cfg['executionInterpreter']['sha256'];need(len(required)==18,'complete18 component mapping required')
 native=complete_serial_native_epochs(W,read(W/'execution-owner-wait.json'),required,expected_count=26)
 peaks=closed_request_peaks(read(W/'media-request-window-closed.json'),collection);capacity=conservative_total(peaks,native['maximumTrackedCapacityBytes'])
 need(len(r['actualTargetClosures'])==26 and all(c['actualWaitCompleted'] and c['accepted'] and c['exitCode']==0 for c in r['actualTargetClosures']),'all26 closures required')
 policy=controls['resource-configuration.json']['configuration']['rangeMatrixPolicy'];base=controls['sample-approval.json']
 need(all(k in cfg for k in ('secret','controlKey','users')),'actual private credential set required')
 secret_needles=[cfg['secret'].encode(),cfg['controlKey'].encode(),*[v.encode() for v in cfg['users'].values()]]
 identities=cfg['inputs'];sources={v:P/Path(row['path']).relative_to('/poc') for v,row in identities.items()}
 for v,p in sources.items():need(p.stat().st_size==identities[v]['sizeBytes']==67108864 and sha(p)==identities[v]['sha256'],'actual source bytes mismatch')
 need(base['checksum']=='sha256:'+identities[policy['baseVersion']]['sha256'],'approved base input mismatch')
 need(controls['changed-sample-approval.json']['checksum']==policy['updatedInputSha256']=='sha256:'+identities[policy['updatedVersion']]['sha256'],'approved updated input mismatch')
 need(policy['maximumBufferedBytes']==8388608 and policy['sliceBytes']==1048576 and policy['maximumRetries']==0 and policy['latencySampleCount']==4 and policy['concurrentUsers']==2,'original numeric policy required')
 raw={};copied=0
 def retain(p,ref,kind):
  nonlocal copied
  p=Path(p);need(p.is_file() and not p.is_symlink(),'regular retained raw required')
  reject_actual_secrets(p,secret_needles)
  if ref in raw:need(raw[ref]['sha256']=='sha256:'+sha(p),'raw identity conflict');return ref
  need(ref.startswith(PREFIX+'/raw/'),'raw boundary mismatch');q=repo/ref;q.parent.mkdir(parents=True,exist_ok=True)
  need(not q.exists(),'new retained file required');copied+=p.stat().st_size;need(copied<=2147483648,'retained evidence total2GiB guard')
  with p.open('rb') as src,q.open('xb') as dst:shutil.copyfileobj(src,dst,65536)
  need(sha(q)==sha(p),'retained bytes changed')
  raw[ref]=dict(ref=ref,artifactType=kind,byteCount=q.stat().st_size,sha256='sha256:'+sha(q));return ref
 def artifact_ref(p):return retain(p,PREFIX+'/raw/original-matrix/'+Path(p).resolve().relative_to(C.resolve()).as_posix(),'produced_media')
 record_ref=lambda name:PREFIX+'/raw/typed/'+name+'.json'
 for n in controls:shutil.copyfile(approval_path.parent/n,target/n)
 shutil.copyfile(approval_path,target/'independent-execution-approval.json')
 for v,p in sources.items():
  dst=target/'inputs'/('base.bin' if v==policy['baseVersion'] else 'changed.bin');dst.parent.mkdir(exist_ok=True)
  with p.open('rb') as src,dst.open('xb') as out:shutil.copyfileobj(src,out,65536)
  need(sha(dst)==identities[v]['sha256'],'retained immutable input mismatch')
 tool=before['environmentCaptured']['tool_versions'];need(tool==a['expectedToolVersions'],'actual before subject differs from approved immutable interpreter/version')
 common=dict(configurationRef=PREFIX+'/resource-configuration.json',inputSamples=[dict(id=base['sampleId'],immutableId=base['immutableId'],checksum=base['checksum'])],inputSampleId=base['sampleId'],subjectVersion=json.dumps(tool,sort_keys=True,separators=(',',':')),acceptanceProfile=controls['profile-configuration.json']['acceptanceProfile'],assetId=policy['assetId'],aclVersion=policy['aclVersion'])
 sidecars={row['requestId']:read(C/row['observationRef']) for row in collection['nativeReadabilityObservations']}
 index=NativeRequestIndex(W/'cache-observer')
 from poc003_native_epoch_association_v3 import associate_native_processes
 association=associate_native_processes(native,index,collection,sidecars)
 assembled=assemble_typed_records(common,dict(policy,originURL='http://127.0.0.1:18231'),collection,C,sources,identities,sidecars,index,capacity['maximumBufferedBytes'],artifact_ref,record_ref)
 association=associate_native_processes(native,index,collection,sidecars,assembled)
 for ref,value in assembled['records'].items():
  need(not any(secret in json.dumps(value).encode() for secret in secret_needles),'generated record contains actual credential')
  write(repo/ref,value);raw[ref]=dict(ref=ref,artifactType='measurement_output',byteCount=(repo/ref).stat().st_size,sha256='sha256:'+sha(repo/ref))
 observations=derive_diagnostic_conditions(assembled,collection,dict(policy,originURL='http://127.0.0.1:18231'),sources,identities,lambda ref:repo/ref,capacity['maximumBufferedBytes'])
 # Publish only explicitly selected actual observations; never credential files.
 for p in [C/'collection.json',D/'before-environment.json',W/'execution-owner-wait.json',W/'media-request-window-closed.json',*runtime_paths]:
  retain(p,PREFIX+'/raw/observed/'+p.relative_to(D).as_posix(),'scope_observation')
 for row in collection['nativeReadabilityObservations']:
  p=C/row['observationRef'];retain(p,PREFIX+'/raw/observed/original-matrix/'+row['observationRef'],'scope_observation')
 for dirname in ('process-epochs','cache-observer'):
  for p in sorted((W/dirname).rglob('*')):
   if p.is_file() and not p.is_symlink():retain(p,PREFIX+'/raw/observed/work/'+p.relative_to(W).as_posix(),'command_output')
 retain(RUN,PREFIX+'/raw/observed/run-result.json','command_output')
 outlog=RUN.parent/'start.stdout.raw';retain(outlog,PREFIX+'/raw/observed/start.stdout.raw','command_output')
 values={'range_correctness':observations['rangeCaseValidationPercent'],**observations['gateDiagnostics']}
 values.update(assembled['latencyDerivations'])
 plan=yaml.safe_load((repo/'specs/poc/plans/POC-003.yaml').read_bytes());measures=plan['localValidation']['protocol']['measurements']
 need(set(values)=={x['id'] for x in measures},'exact original15 actual measurements required')
 env={k:before['environmentCaptured'][k] for k in plan['localValidation']['captureBeforeExecution']}
 env.update(acceptanceProfile=common['acceptanceProfile'],acceptanceProfileConfigurationRef=PREFIX+'/profile-configuration.json',testedSource=dict(commit=SOURCE,tree=TREE),executionWindow=dict(startedAt=start.isoformat().replace('+00:00','Z'),finishedAt=end.isoformat().replace('+00:00','Z')),rawExecutionArtifacts=list(raw.values()),inputSampleArtifacts=[dict(sampleId=base['sampleId'],immutableId=base['immutableId'],inputArtifactRef=PREFIX+'/inputs/base.bin',byteCount=67108864,sha256=base['checksum'])],rangeMatrixRef=assembled['reportRef'])
 record=dict(schemaVersion=1,pocId='POC-03',taskId='POC-003',evidencePath='evidence/POC-003',executor='/root',resources=[dict(id='RES-ATS-SANDBOX',configurationRef=PREFIX+'/resource-configuration.json',bookingRef=PREFIX+'/resource-booking.json')],environmentCaptured=env,commands=[dict(command='docker start --attach '+r['containerId'],expectedExitCodes=[0],exitCode=r['attachedCliExitCode'],outputRef=PREFIX+'/raw/observed/start.stdout.raw')],rawOutputRefs=list(raw),samples=[dict(id=base['sampleId'],immutableId=base['immutableId'],checksum=base['checksum'],approved=True,approvalRef=PREFIX+'/sample-approval.json')],measurements=[dict(id=x['id'],actual=values[x['id']]) for x in measures],provenance={},complianceReviews=[],notes='Actual approved newM original15 matrix only. Formal frozen qualification and independent final Review remain required; independent warm-cache revocation is separately executed. No production or fullV1 acceptance is issued by assembly.')
 defs=yaml.safe_load((repo/'specs/poc/program.schema.yaml').read_bytes())['$defs'];names={'range_origin_access_observation':'rangeOriginAccessObservation','range_request_observation':'rangeRequestObservation','range_source_update':'rangeSourceUpdate','range_cache_lifecycle':'rangeCacheLifecycle','range_matrix_report':'rangeMatrixReport'}
 for value,schema in [(record,yaml.safe_load((repo/'specs/poc/execution-record.schema.yaml').read_bytes())),*[(v,dict(defs[names[v['kind']]],**{'$defs':defs})) for v in assembled['records'].values()]]:
  jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).validate(value)
 write(target/'execution.json',record)
 write(target/'assembly-provenance.json',dict(source=dict(commit=SOURCE,tree=TREE),authoritySha256=approval_sha,runSha256=sha(RUN),actual26NativeClosureDerivation=native,runtimeBindingAuthentication=runtime_auth,nativeEpochAssociations=association,closedRequestPeaks=peaks,completeConservativeCapacity=capacity,observations=observations,typedRecordCount=57,rawCount=len(raw),rawBytes=copied,privateSettingsPublished=False,fullQualificationValidated=False,formalPocAccepted=False))
 return record

def validate(repo):
 verify_called_source(repo)
 spec=importlib.util.spec_from_file_location('frozen_poc_check',repo/'specs/poc/check_program.py');check=importlib.util.module_from_spec(spec);sys.modules[spec.name]=check;spec.loader.exec_module(check)
 program=yaml.safe_load((repo/'specs/poc/program.schema.yaml').read_bytes());defs=program['$defs'];plan=yaml.safe_load((repo/'specs/poc/plans/POC-003.yaml').read_bytes());execution=read(repo/PREFIX/'execution.json')
 resources=yaml.safe_load((repo/'specs/poc/resources.yaml').read_bytes());catalog={x['id']:x for x in resources['resources']}
 errors=[]
 check.validate_execution(repo,plan,'/root',execution,catalog,yaml.safe_load((repo/'specs/poc/execution-record.schema.yaml').read_bytes()),yaml.safe_load((repo/'specs/poc/sample-approval.schema.yaml').read_bytes()),'pass',errors,reference_prefix=PREFIX,record_definitions=defs,task_reviewer='/root/independent_review',record_refs={PREFIX+'/execution.json'})
 return errors

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--approval',type=Path);p.add_argument('--approval-sha256');p.add_argument('--validate',action='store_true');a=p.parse_args()
 if a.validate:
  errors=validate(a.repo);print(json.dumps(dict(frozenExecutionErrors=errors,fullQualificationValidated=not errors,formalPocAccepted=False)));raise SystemExit(bool(errors))
 need(a.approval is not None and a.approval_sha256,'before-run authority required');record=assemble(a.repo,a.approval,a.approval_sha256);print(json.dumps(dict(originalMeasurements=len(record['measurements']),formalPocAccepted=False)))
if __name__=='__main__':main()

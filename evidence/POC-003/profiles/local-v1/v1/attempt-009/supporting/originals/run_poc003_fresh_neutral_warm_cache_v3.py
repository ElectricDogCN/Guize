"""Prospective once-only source R independent fresh warm-cache revocation; fresh exact approval required."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,shutil,stat,subprocess,time

ROOT=Path(__file__).resolve().parent
SOURCE='de8ad3f21df1578eac80e98d798f7adbcdb07d82'
TREE='ce6f3e09ec72b88ddabf49e75d41b4159e36fdb9'
IMAGE='sha256:df18428df8a0f9189c84e7424d214b4c50092af1f9dca5842a00c41c39bda316'
NEUTRAL=Path('/tmp/guize-poc003-de8ad3f-v1')
PACKAGE=NEUTRAL/'runtime-package-v2'
CONFIG=NEUTRAL/'configuration-draft-v1'
PRIVATE=NEUTRAL/'warm-cache-v2'
OUT=NEUTRAL/'warm-cache-supervision-v2'
NAME='guize-poc003-warm-de8ad3f-v2'
LABEL='guize.poc003.fresh-neutral-warm-method'



def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()


def utc(text):return datetime.fromisoformat(text.replace('Z','+00:00'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--approval-sha256',required=True);parser.add_argument('--source-repo',type=Path,required=True)
    args=parser.parse_args();assert os.name=='posix' and os.getuid()==1000
    REPO=args.source_repo
    os.environ['PATH']=str(Path.home()/'.cache/guize-takeover/git-lfs-3.8.1-private-v1')+':'+os.environ['PATH']
    import fcntl
    lock=(Path.home()/'.cache/guize-takeover/guize-performance-domain.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    method_sha=sha(__file__);entry=ROOT/'poc003_fresh_neutral_warm_cache_entry_v1.py';entry_sha=sha(entry)
    assert sha(args.approval)==args.approval_sha256
    approval=json.loads(args.approval.read_bytes())
    assert approval['freshWarmCacheRevocationExecutionApproved'] is True and approval['approvedBy']=='/root/independent_review'
    assert approval['methodSha256']==method_sha and approval['entrySha256']==entry_sha and not approval['mustFix']
    assert approval['scope']=='FRESH_NEUTRAL_SOURCE_R_INDEPENDENT_WARM_CACHE_REVOCATION_ONLY'
    start=datetime.now(timezone.utc);valid_from,valid_until=[utc(approval[k]) for k in ('validFrom','validUntil')]
    assert valid_from<=start<valid_until and (valid_until-start).total_seconds()>=900
    assert approval['maximumActualAttempts']==1 and approval['source']==SOURCE and approval['tree']==TREE
    assert sha(PACKAGE/'package-manifest.json')=='8690aeadbbd27299e34ea3d4827e630c6f6f4b839e11a8d7606232ffe603f04f'
    assert sha(CONFIG/'configuration-manifest.json')=='704c83508b73d01f03177ce07857190e60b1f8c1277dd1345262e75dcba2910b'
    for name,expected,flag in [
        ('poc003-post-completion228-resume-v1-final-source-independent-review.json','bd5201a0948fe51655574f959f79bdf6076921ab41c3887dd456726d099366a0','sourceQualified'),
        ('poc003-fresh-runtime-package-version-result-independent-review-v1.json','d69b69d956a0fb995421caddfc2d81b37c90935a75015651078237c9f056dcfd','runtimePackagePreparationAccepted'),
        ('poc003-fresh-config-draft-independent-review-v1.json','4618153efdd900d4a9bcdcfce1a13dc4403e8e548f002ecfec9fc57e5db5c521','configurationDraftAccepted')]:
        path=ROOT/name;assert sha(path)==expected;doc=json.loads(path.read_bytes());assert doc['source']==SOURCE and doc['tree']==TREE and doc[flag] and not doc['mustFix']
    from jsonschema import Draft202012Validator,FormatChecker
    import yaml
    registry=yaml.safe_load((REPO/'specs/coordination/active-work.yaml').read_bytes())
    own=next(row for row in registry['tasks'] if row['taskId']=='POC-003')
    assert own['status']=='in_progress' and own['agentRole']=='implementer' and own['branch']=='chore/POC-003-qualified-lfs-evidence-v2'
    assert own['baseSha']=='760f6c5838597d1d66c0a536ecbf440ef5a7dfec' and own['implementer']=='/root' and own['reviewer']=='/root/independent_review' and own['integrationOrder']==2
    assert own['exclusivePaths']==['poc/POC-03-ats-range/**','evidence/POC-003/**'] and own['sharedPaths']==['adr/**','specs/poc/results-index.yaml']
    assert start<utc(own['lease']['expiresAt']) and valid_until<=utc(own['lease']['expiresAt'])
    assert yaml.safe_load((REPO/'specs/coordination/program-plan.yaml').read_bytes())['status']=='active'
    definitions=yaml.safe_load((REPO/'specs/poc/program.schema.yaml').read_bytes())['$defs']
    validator=lambda definition:Draft202012Validator(dict(definition,**{'$defs':definitions}),format_checker=FormatChecker())
    controls={}
    for name in ['sample-approval.json','changed-sample-approval.json','resource-configuration.json','resource-booking.json','profile-configuration.json']:
        path=args.approval.parent/name;raw=path.read_bytes();pin=approval['beforeControlFiles'][name];assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'];controls[name]=json.loads(raw)
        assert controls[name]['pocId']=='POC-03' and controls[name]['taskId']=='POC-003' and utc(controls[name]['approvedAt'])<=start
    for name,key in [('sample-approval.json','base'),('changed-sample-approval.json','changedVersion')]:
        doc=controls[name];validator(yaml.safe_load((REPO/'specs/poc/sample-approval.schema.yaml').read_bytes())).validate(doc)
        pair=json.loads((PACKAGE/'fixtures/manifest.json').read_bytes());assert doc['decision']=='approved' and doc['approver']=='/root/independent_review' and doc['sampleId']=='SAMPLE-RANGE-LARGEFILE' and doc['checksum']=='sha256:'+pair[key]['sha256']
    for name,key in [('resource-configuration.json','resourceConfiguration'),('resource-booking.json','resourceBooking')]:
        doc=controls[name];validator(definitions[key]).validate(doc);assert doc['status']=='approved' and doc['approvedBy']=='/root/independent_review' and doc['resourceId']=='RES-ATS-SANDBOX' and utc(doc['validFrom'])<=start and utc(doc['validUntil'])>=valid_until
    assert controls['resource-configuration.json']['configuration']['scope']=='FRESH_R_INDEPENDENT_FRESH_WARM_ONLY'
    profile=controls['profile-configuration.json'];validator(definitions['profileConfiguration']).validate(profile)
    assert profile['decision']=='approved' and profile['approvedBy']=='/root/independent_review'
    assert profile['testedSource']==dict(commit=SOURCE,tree=TREE) and profile['capturedSettings']=={} and profile['numericDomainReviewRefs']=={}
    assert len(profile['measurementIds'])==len(set(profile['measurementIds']))==15
    import importlib.util,sys
    spec=importlib.util.spec_from_file_location('frozen_run_authority_semantics',REPO/'specs/poc/check_program.py')
    frozen=importlib.util.module_from_spec(spec);sys.modules[spec.name]=frozen;spec.loader.exec_module(frozen)
    for doc in [approval,*controls.values()]:
        for field in ['approvedAt','validFrom','validUntil']:
            if field in doc:assert frozen.valid_utc_timestamp(doc[field]),'frozen UTC authority admission: '+field
    plan=yaml.safe_load((REPO/'specs/poc/plans/POC-003.yaml').read_bytes())
    assert set(profile['measurementIds'])=={m['id'] for m in plan['localValidation']['protocol']['measurements']}
    validator(definitions['rangeMatrixPolicy']).validate(controls['resource-configuration.json']['configuration']['rangeMatrixPolicy'])

    compat_path=ROOT/approval['compatibilityReviewFile']
    assert compat_path.parent==ROOT and sha(compat_path)==approval['compatibilityReviewSha256']
    compat=json.loads(compat_path.read_bytes());assert compat['source']==SOURCE and compat['controlCompatibilityAccepted'] and not compat['mustFix']
    assert sha(ROOT/'poc003_common_main7e405b6_revocation_failure_records_v1.py')==approval['diagnosticHelperSha256']
    assert sha(ROOT/'poc003_disk_guard_atomic_publication_v1.py')==approval['diskGuardMethodSha256']=='b2a992db574b68a92a6535c34438c511654f2095d7aab89a8197e35d787e3c35'
    from poc003_common_main7e405b6_revocation_failure_records_v1 import retain_revocation_outcomes
    from poc003_disk_guard_atomic_publication_v1 import writable_disk_guard
    fresh=json.loads((ROOT/'poc003-fresh-warm-v2-start-official.json').read_bytes());observed=utc(fresh['retrievedAt']);assert 0<=(start-observed).total_seconds()<120
    assert fresh['main']['object']['sha']=='a3a57bade4dd3b25cd417d2cb5e0e3d1e14d792c' and fresh['issue']['number']==131 and fresh['issue']['state']=='open' and fresh['pr']['number']==229 and fresh['pr']['head']['sha']==SOURCE and not fresh['pr']['merged']
    assert fresh['run']['id']==43314288604 and fresh['run']['head_sha']==SOURCE and fresh['run']['conclusion']=='success'
    resource_path=ROOT/'poc003-fresh-warm-v2-start-resources-v1/results.json';resource=json.loads(resource_path.read_bytes())
    assert 0<=(start-utc(resource['observedAt'])).total_seconds()<120 and resource['completed'] and resource['proposedNameAbsent'] and resource['proposedContainerName']==NAME and resource['runningContainerIds']==[] and resource['disk']['free']>=4*1024**3
    assert resource['packageManifestSha256']==sha(PACKAGE/'package-manifest.json') and resource['configurationManifestSha256']==sha(CONFIG/'configuration-manifest.json')
    supplement_path=ROOT/approval['runtimeSupplementReviewFile']
    assert supplement_path.parent==ROOT and sha(supplement_path)==approval['runtimeSupplementReviewSha256']
    supplement=json.loads(supplement_path.read_bytes());assert supplement['source']==SOURCE and supplement['runtimeSupplementPackageAccepted'] and not supplement['mustFix']
    baseline=NEUTRAL/'runtime-package-v1/package-manifest.json'
    assert sha(baseline)=='9406b969f4d22e2dc6ee1e4e1aaed19d179672c20c74f2d1a89571bead0e9b44'
    assert json.loads((CONFIG/'configuration-manifest.json').read_bytes())['packageManifestSha256']==sha(baseline)
    def verify_package():
        manifest=json.loads((PACKAGE/'package-manifest.json').read_bytes())
        declared={row['path']:row for row in manifest['entries']}
        actual={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if not p.is_dir() or p.is_symlink()}
        assert actual==set(declared)|{'package-manifest.json'}
        for name,row in declared.items():
            p=PACKAGE/name
            if row['kind']=='symlink':
                assert p.is_symlink() and os.readlink(p)==row['target'] and p.resolve(strict=True).is_relative_to(PACKAGE)
            else:
                assert p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'] and not stat.S_IMODE(p.stat().st_mode)&0o222
        assert manifest['source']==SOURCE and manifest['regularLogicalBytes']==156319530
        parent=json.loads(baseline.read_bytes());parent_entries={r['path']:r for r in parent['entries']}
        assert manifest['parentPackageManifestSha256']==sha(baseline) and manifest['configurationSourcePackageManifestSha256']==sha(baseline)
        assert set(declared)-set(parent_entries)=={'dependencies/libmaxminddb.so.0','receipts/maxmind-dependency-acquisition.original.json'}
        assert all(declared[name]==row for name,row in parent_entries.items())
        assert declared['dependencies/libmaxminddb.so.0']['sha256']=='1d5dccc962dc80967d2fe62a7d9254eb99b2ab885587e1f160b76b1c87d44833'


    verify_package()
    git=lambda *a:subprocess.check_output(['git','-C',str(REPO),*a]).decode().strip()
    before={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain=v1','--untracked-files=all')}
    assert before=={'head':SOURCE,'tree':TREE,'status':''}
    assert not OUT.exists() and not PRIVATE.exists() and not PRIVATE.is_symlink() and PRIVATE.parent.resolve()==PRIVATE.parent
    OUT.mkdir();authority=OUT/'authority';authority.mkdir()
    for name in controls:shutil.copyfile(args.approval.parent/name,authority/name)
    shutil.copyfile(args.approval,authority/'warm-approval.json')
    PRIVATE.mkdir(mode=0o700);writable=PRIVATE/'data';writable.mkdir(mode=0o700);configuration=PRIVATE/'configuration';configuration.mkdir(mode=0o700)
    cm=json.loads((CONFIG/'configuration-manifest.json').read_bytes())
    for row in cm['files']:
        p=CONFIG/row['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        target=configuration/('bootstrap.original.py' if row['path']=='entry.py' else row['path']);shutil.copyfile(p,target);target.chmod(0o444)
    shutil.copyfile(entry,configuration/'entry.py');(configuration/'entry.py').chmod(0o444);configuration.chmod(0o555)
    result={'kind':'ACTUAL_FRESH_R_INDEPENDENT_WARM_REVOCATION_NOT_YET_FORMAL_POC','source':SOURCE,'before':before,
            'methodSha256':method_sha,'entrySha256':entry_sha,'approvalRef':'authority/warm-approval.json','approvalSha256':args.approval_sha256,
            'startedAt':start.isoformat(),'commands':[],'containerId':None,'externalCleanup':[],
            'warmCacheRevocationCompleted':False,'fullMediaAccepted':False,'untracedLatencyAccepted':False,
            'formalActorBindingAccepted':False,'formalPocAccepted':False,'runtimeFilesRetained':True,
            'diskQuotaKind':'active_stat_guard_terminates_owned_container_not_filesystem_quota'}
    save=lambda:(OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    save()
    run_deadline=None
    cleanup_deadline=None
    in_cleanup=False
    def command(label,argv,allow_absent=False,timeout=45):
        row={'label':label,'argv':argv,'startedAt':datetime.now(timezone.utc).isoformat()}
        active_deadline=cleanup_deadline if in_cleanup else run_deadline
        remaining=(active_deadline-time.monotonic()) if active_deadline is not None else timeout+2
        if remaining<=1:raise TimeoutError('shared outer deadline before '+label)
        budget=min(timeout,remaining-1);row['waitBudgetSeconds']=budget;timed_out=False;code=None
        with (OUT/(label+'.stdout.raw')).open('xb') as stdout,(OUT/(label+'.stderr.raw')).open('xb') as stderr:
            p=subprocess.Popen(argv,stdout=stdout,stderr=stderr);row['pid']=p.pid
            try:code=p.wait(timeout=budget)
            except subprocess.TimeoutExpired:
                timed_out=True;row['clientTimeout']=True
                if p.poll() is None:
                    try:p.kill()
                    except ProcessLookupError:pass
                reserve=min(1,max(.001,active_deadline-time.monotonic())) if active_deadline is not None else 1
                try:code=p.wait(timeout=reserve)
                except subprocess.TimeoutExpired:row['clientWaitTerminalUnknown']=True
        row.update(exitCode=code,actualWaitCompleted=code is not None,finishedAt=datetime.now(timezone.utc).isoformat());result['commands'].append(row);save()
        raw=(OUT/(label+'.stdout.raw')).read_bytes();err=(OUT/(label+'.stderr.raw')).read_bytes()
        assert len(raw)<=1048576 and len(err)<=65536,label+' output budget'
        row.update(stdoutBytes=len(raw),stdoutSha256=hashlib.sha256(raw).hexdigest(),stderrBytes=len(err),stderrSha256=hashlib.sha256(err).hexdigest());save()
        if timed_out:raise TimeoutError(label+' actual CLI deadline exceeded, regardless of raced exit')
        if code:
            if allow_absent and code==1 and (b'No such object' in err or b'No such container' in err):return None
            raise RuntimeError(label+' actual CLI exit '+str(code))
        return raw
    assert command('fresh-name',['docker','container','inspect',NAME],True) is None
    image=json.loads(command('image',['docker','image','inspect',IMAGE]))[0];assert image['Id']==IMAGE and image['Os']=='linux' and image['Architecture']=='amd64'
    security=json.loads(command('engine-security',['docker','info','--format','{{json .SecurityOptions}}']))
    assert 'name=seccomp,profile=builtin' in security,'actual engine builtin seccomp required'
    result['engineSecurityOptions']=security
    template=PRIVATE/'ats-etc-template'
    original_template=PACKAGE/'runtime/pkgroot/etc/trafficserver'
    shutil.copytree(original_template,template,symlinks=True)
    original_manifest=json.loads((PACKAGE/'package-manifest.json').read_bytes())
    original_entries={row['path']:row for row in original_manifest['entries']};template_pins={}
    for p in sorted(template.rglob('*')):
        assert not p.is_symlink(),'unexpected config template symlink'
        if p.is_file():
            rel=p.relative_to(template).as_posix();pin=original_entries['runtime/pkgroot/etc/trafficserver/'+rel]
            assert pin['kind']=='regular' and p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256']
            p.chmod(0o644|(p.stat().st_mode&0o111));template_pins[rel]=pin['sha256']
        elif p.is_dir():p.chmod(0o755)
    template.chmod(0o755)
    result['derivedTemplate']={'originalPackageUnchanged':True,'bytesUnchanged':True,'modeDerivation':'directories0755,files0644 retaining execute bits; extra read-only nested bind', 'files':template_pins};save()
    mounts=[(PACKAGE,'/poc',True),(configuration,'/configuration',True),(template,'/poc/runtime/pkgroot/etc/trafficserver',True),
            (PACKAGE/'identity/passwd','/etc/passwd',True),(PACKAGE/'identity/group','/etc/group',True),(PACKAGE/'identity/home','/home/poc',True),(writable,'/runlab',False)]
    create=['docker','create','--pull=never','--name',NAME,'--hostname','guize-poc003-warm-de8ad3f-v2','--label',LABEL+'='+method_sha,'--label','guize.poc003.source='+SOURCE,
            '--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--network','none','--ipc','private','--cgroupns','private',
            '--memory','512m','--memory-swap','512m','--cpus','1','--pids-limit','64','--ulimit','nofile=256:256',
            '--log-driver','none','--stop-signal','SIGINT','--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTHONNOUSERSITE=1',
            '--env','LC_ALL=C.UTF-8','--env','PYTHONCOERCECLOCALE=0','--env','HOME=/home/poc','--env','USER=poc','--env','LOGNAME=poc','--workdir','/runlab','--entrypoint','/usr/local/bin/python3']
    for source,target,ro in mounts:create+=['--mount','type=bind,source='+str(source)+',target='+target+(',readonly' if ro else '')]
    create += [IMAGE,'-B','/configuration/entry.py']
    cid=None;attached=None;cleanup_attempted=False
    def inspect(label,timeout=45):
        row=json.loads(command(label,['docker','container','inspect',cid],timeout=timeout))[0]
        assert row['Id']==cid and row['Image']==IMAGE and row['Config']['Labels'].get(LABEL)==method_sha
        return row
    def disk_guard():
        return writable_disk_guard(writable,[OUT/'start.stdout.raw',OUT/'start.stderr.raw'],run_deadline)
    def cleanup_owned():
        nonlocal cleanup_attempted,cleanup_deadline,in_cleanup
        if cleanup_attempted or cid is None:return
        cleanup_attempted=True
        cleanup_deadline=time.monotonic()+60
        in_cleanup=True
        result.update(cleanupBudgetSeconds=60,cleanupStartedAt=datetime.now(timezone.utc).isoformat());save()
        live=inspect('cleanup-bound-identity',timeout=5)
        if live['State']['Running']:
            command('cleanup-sigint',['docker','kill','--signal','SIGINT',cid],timeout=5);result['externalCleanup'].append('actual owned-container SIGINT');save()
            try:command('cleanup-graceful-engine-wait',['docker','wait',cid],timeout=20)
            except Exception:
                live=inspect('cleanup-kill-identity',timeout=5)
                if live['State']['Running']:
                    command('cleanup-sigkill',['docker','kill','--signal','SIGKILL',cid],timeout=5);result['externalCleanup'].append('actual owned-container SIGKILL');save()
                command('cleanup-final-engine-wait',['docker','wait',cid],timeout=10)
        if attached is not None:
            try:attached.wait(timeout=min(5,max(.001,cleanup_deadline-time.monotonic())))
            except subprocess.TimeoutExpired:
                attached.kill();attached.wait(timeout=min(1,max(.001,cleanup_deadline-time.monotonic())));result['externalCleanup'].append('own attach CLI killed after namespace cleanup')
            result.update(attachedCliExitCode=attached.returncode,attachedCliWaitCompleted=True)
        final=inspect('cleanup-final-inspect',timeout=5)
        result['cleanupFinalContainerState']=final['State'];save()
        assert not final['State']['Running'] and final['State']['Pid']==0
    try:
        assert 0<=(datetime.now(timezone.utc)-observed).total_seconds()<120 and 0<=(datetime.now(timezone.utc)-utc(resource['observedAt'])).total_seconds()<120
        assert datetime.now(timezone.utc)<utc(own['lease']['expiresAt'])
        cid=command('create',create).decode().strip();assert len(cid)==64 and all(c in '0123456789abcdef' for c in cid)
        result['containerId']=cid;save();created=inspect('created-inspect');h=created['HostConfig'];cfg=created['Config']
        assert not created['State']['Running'] and created['State']['Pid']==0
        assert h['Memory']==h['MemorySwap']==536870912 and h['NanoCpus']==1000000000 and h['PidsLimit']==64
        assert cfg['User']=='1000:1000' and not cfg['Tty'] and not cfg['OpenStdin'] and cfg['Entrypoint']==['/usr/local/bin/python3'] and cfg['Cmd']==['-B','/configuration/entry.py']
        assert h['ReadonlyRootfs'] and not h['Privileged'] and h.get('Init') in (False,None) and not h.get('AutoRemove')
        assert h['NetworkMode']=='none' and h['IpcMode']=='private' and h['CgroupnsMode']=='private' and h.get('PidMode') in ('',None)
        assert h.get('CapAdd') in ([],None) and h['CapDrop']==['ALL'] and h['SecurityOpt']==['no-new-privileges']
        assert not h.get('Devices') and not h.get('DeviceRequests') and not h.get('PortBindings') and h['LogConfig']['Type']=='none'
        assert h['Ulimits']==[{'Name':'nofile','Hard':256,'Soft':256}]
        actual_mounts={(m['Source'],m['Destination'],not m['RW']) for m in created['Mounts']}
        assert actual_mounts=={(str(s),d,ro) for s,d,ro in mounts}
        assert not any(k.split('=',1)[0] in {'LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT'} for k in cfg['Env'])
        assert datetime.now(timezone.utc)<valid_until and (valid_until-datetime.now(timezone.utc)).total_seconds()>=900
        tick=time.monotonic();deadline=tick+840;run_deadline=tick+840
        result['sharedOuterBudgetSeconds']=900;save()
        with (OUT/'start.stdout.raw').open('xb') as stdout,(OUT/'start.stderr.raw').open('xb') as stderr:
            attached=subprocess.Popen(['docker','start','--attach',cid],stdout=stdout,stderr=stderr)
            result['attachedClientPid']=attached.pid;result['actualStartRequestedAt']=datetime.now(timezone.utc).isoformat();save()
            try:
                while attached.poll() is None:
                    if time.monotonic()>=deadline:raise TimeoutError('original bounded namespace wall deadline')
                    result['lastDiskObservation']=disk_guard();save();time.sleep(.2)
                code=attached.wait();result.update(attachedCliExitCode=code,attachedCliWaitCompleted=True)
            except BaseException as error:
                result.update(runtimeErrorType=type(error).__name__,runtimeError=str(error)[:512]);save()
                cleanup_owned()
                raise
        engine_exit=int(command('engine-wait',['docker','wait',cid],timeout=45).decode().strip())
        final=inspect('final-inspect',timeout=5);assert not final['State']['Running'] and final['State']['Pid']==0 and final['State']['ExitCode']==engine_exit
        result.update(engineWaitCompleted=True,engineExitCode=engine_exit,finalContainerState=final['State'],finalDiskObservation=disk_guard())
        # Keep the full actual inventory, including unexpected extra epochs.
        closure_paths=sorted((writable/'work/process-epochs').glob('epoch-*/closure.json'))
        result['actualClosureArtifactPaths']=[p.relative_to(writable).as_posix() for p in closure_paths]
        try:
            retain_revocation_outcomes(result,writable)
        finally:
            save()
        client=result['clientReport'];owner=result['actualOwnerWait']
        closures=[json.loads(p.read_bytes()) for p in closure_paths]
        result.update(actualTargetClosures=closures)
        assert not result.get('runtimeError') and not result['externalCleanup'] and result['attachedCliExitCode']==engine_exit==0
        assert all(client.get(k) is True for k in ('beforeEnvironmentCaptured','checkpointObserved','profileAbsentBeforeClient','clientCompleted','scenarioCompleted','serveReturnedNormally','clientThreadStopped'))
        assert client['actualTestWaitCompleted'] and client['actualTestExitCode']==0 and not client.get('actualTestDeadlineExpired')
        report=json.loads((writable/'warm-cache-revocation/revocation-result.json').read_bytes())
        assert report==client['actualScenarioReport'] and report['status']=='PASS' and report['executedScenarios']==1 and report['skippedAssertions']==0
        assert owner['actualOwnerWaitCompleted'] and owner['ownerExitCode']==0
        summary=owner['targetClosureSummary'];assert summary['epochCount']==summary['closedEpochCount']==summary['acceptedCount']==2 and summary['allAccepted']
        assert len(closures)==2 and all(r['accepted'] and r['actualWaitCompleted'] and r['exitCode']==0 for r in closures)
        assert sum(r['label'].startswith('clear-cache-') for r in closures)==0 and sum(r['label']=='verify-config' for r in closures)==1
        result['actualScenarioReport']=report
        after={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain=v1','--untracked-files=all')};assert after==before
        assert sha(PACKAGE/'package-manifest.json')==result.get('packageManifestSha256','8690aeadbbd27299e34ea3d4827e630c6f6f4b839e11a8d7606232ffe603f04f')
        verify_package()
        assert all(sha(template/rel)==pin for rel,pin in template_pins.items())
        result.update(after=after,sourceUnchanged=True,derivedTemplateBytesUnchanged=True,warmCacheRevocationCompleted=True)
    except BaseException as error:
        result.update(failureType=type(error).__name__,failure=str(error)[:1024]);save()
        try:cleanup_owned()
        except BaseException as cleanup_error:
            result.update(cleanupErrorType=type(cleanup_error).__name__,cleanupError=str(cleanup_error)[:512]);save()
        raise
    finally:
        result['finishedAt']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'source':SOURCE,'warmCacheRevocationCompleted':True,'containerId':cid,'engineExitCode':result['engineExitCode'],
                      'ownerActualWaitCompleted':True,'targetEpochs':2,'formalPocAccepted':False}),flush=True)


if __name__=='__main__':main()

"""Prospective newM original matrix for complete original15 qualification; exact before controls and caller required."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,shutil,stat,subprocess,time

ROOT=Path(__file__).resolve().parent
SOURCE='1b5c68bab02d98f8e11286d80033585090c7af99'
IMAGE='sha256:df18428df8a0f9189c84e7424d214b4c50092af1f9dca5842a00c41c39bda316'
PACKAGE=Path('/home/sur/.cache/guize-takeover/poc003-common-main1b5c68b-inputs-v1')
CONFIG=Path('/home/sur/.cache/guize-takeover/poc003-common-main1b5c68b-full-original-matrix-config-v1')
PRIVATE=Path('/home/sur/.cache/guize-takeover/poc003-common-main1b5c68b-full-original-matrix-v1')
REPO=Path('/home/sur/.cache/guize-takeover/poc003-aggregation-pr183-main-seven-1b5c68b')
OUT=ROOT/'poc003-common-main1b5c68b-full-original-matrix-v1'
NAME='guize-poc003-common-main1b5c68b-full-original-matrix-v1'
LABEL='guize.poc003.small-fragment-original-matrix-method'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()


def utc(text):return datetime.fromisoformat(text.replace('Z','+00:00'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--approval-sha256',required=True)
    args=parser.parse_args();assert os.name=='posix' and os.getuid()==1000
    method_sha=sha(__file__);entry=ROOT/'poc003_full_original_matrix_before_env_entry_v1.py';entry_sha=sha(entry)
    assert sha(args.approval)==args.approval_sha256
    approval=json.loads(args.approval.read_bytes())
    assert approval['fullOriginalMatrixExecutionApproved'] is True and approval['approvedBy']=='/root/independent_review'
    assert approval['methodSha256']==method_sha and approval['entrySha256']==entry_sha and not approval['mustFix']
    assert approval['scope']=='COMMON_MAIN1B5C68B_FULL_ORIGINAL15_MATRIX_AND_CANONICAL_ASSEMBLY'
    assert approval['source']==SOURCE and approval['tree']=='f94ed8da8d83391f2474365af848bf267a0dc8d1'
    assert approval['maximumActualAttempts']==1 and approval['assemblerSha256']==sha(ROOT/'poc003_full_execution_assembler_v7.py')
    before_names={'profile-configuration.json','resource-configuration.json','resource-booking.json','sample-approval.json','changed-sample-approval.json'}
    assert set(approval['beforeControlFiles'])==before_names
    now=datetime.now(timezone.utc)
    for name,pin in approval['beforeControlFiles'].items():
        f=args.approval.parent/name;assert not f.is_symlink() and f.stat().st_size==pin['bytes'] and sha(f)==pin['sha256']
        doc=json.loads(f.read_bytes());assert (doc['pocId'],doc['taskId'])==('POC-03','POC-003')
        assert utc(doc['approvedAt'])<=now
        if name in {'sample-approval.json','changed-sample-approval.json'}:assert doc['decision']=='approved' and doc['approver']==approval['approvedBy']
        elif name=='profile-configuration.json':
            assert doc['decision']=='approved' and doc['approvedBy']==approval['approvedBy'] and doc['testedSource']==dict(commit=SOURCE,tree='f94ed8da8d83391f2474365af848bf267a0dc8d1')
            assert len(doc['measurementIds'])==len(set(doc['measurementIds']))==15 and doc['capturedSettings']=={} and doc['numericDomainReviewRefs']=={}
        else:
            assert doc['approvedBy']==approval['approvedBy'] and doc['status']=='approved' and utc(doc['validFrom'])<=now<utc(doc['validUntil']) and utc(doc['validUntil'])>=utc(approval['validUntil'])
    full_resource=json.loads((args.approval.parent/'resource-configuration.json').read_bytes())
    assert full_resource['configuration']['fullOriginal15QualificationApproved'] is True
    import fcntl
    lock_path=Path('/home/sur/.cache/guize-takeover/guize-performance-domain.lock')
    lock_fd=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    assert stat.S_ISREG(os.fstat(lock_fd).st_mode) and os.fstat(lock_fd).st_uid==1000
    fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    start=datetime.now(timezone.utc);valid_from,valid_until=[utc(approval[k]) for k in ('validFrom','validUntil')]
    assert valid_from<=start<valid_until and (valid_until-start).total_seconds()>=900
    assert sha(PACKAGE/'package-manifest.json')==approval['packageManifestSha256']
    assert sha(CONFIG/'configuration-manifest.json')==approval['configurationManifestSha256']
    for name,pin in [('poc003-common-main1b5c68b-input-package-v1-independent-review.json',approval['inputReviewSha256']),
                     ('poc003-common-main1b5c68b-full-original-matrix-config-v1-independent-review.json',approval['configurationReviewSha256'])]:assert sha(ROOT/name)==pin
    for name,pin in [('poc003-aggregation-pr183-final-actual-main-independent-review.json',approval['qualificationReviewSha256']),
                     ('poc003-small-fragment-compat-source07-v2-result-independent-review.json','82bf7b14d4ebfdd782d67d49e889013b1a4b308b0aff5056bf4280dbc195c99f')]:
        assert sha(ROOT/name)==pin
    qualified=json.loads((ROOT/'poc003-aggregation-pr183-final-actual-main-independent-review.json').read_bytes())
    assert qualified['actualMain']==SOURCE and qualified['tree']=='f94ed8da8d83391f2474365af848bf267a0dc8d1' and qualified['source']=='34223eb00edde06c1a0fda03b6e88f70bca6f279' and qualified['base']=='2e8655e5b6d59261a4d1597d999dd7530875c1c7'
    assert qualified['actualImplementationMainAccepted'] and qualified['fullMainCiAccepted'] and qualified['ownMainSevenAccepted'] and not qualified['mustFix']
    control=json.loads((ROOT/'poc003-small-fragment-compat-source07-v2-result-independent-review.json').read_bytes())
    assert control['controlCompatibilityAccepted'] and not control['mustFix']
    assert sha(ROOT/'poc003_matrix_failure_records_v2.py')==approval['diagnosticHelperSha256']
    from poc003_matrix_failure_records_v2 import retain_matrix_outcomes
    config_review=json.loads((ROOT/'poc003-common-main1b5c68b-full-original-matrix-config-v1-independent-review.json').read_bytes())
    assert config_review['derivedConfigurationAccepted'] and not config_review['mustFix']
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
        assert manifest['source']==SOURCE and manifest['regularLogicalBytes']==approval['inputLogicalBytes']<=256*1024*1024
    verify_package()
    git=lambda *a:subprocess.check_output(['git','-C',str(REPO),*a]).decode().strip()
    before={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain=v1','--untracked-files=all')}
    assert before=={'head':SOURCE,'tree':'f94ed8da8d83391f2474365af848bf267a0dc8d1','status':''}
    assert not OUT.exists() and not PRIVATE.exists() and not PRIVATE.is_symlink() and PRIVATE.parent.resolve()==PRIVATE.parent
    OUT.mkdir();PRIVATE.mkdir(mode=0o700);writable=PRIVATE/'data';writable.mkdir(mode=0o700);configuration=PRIVATE/'configuration';configuration.mkdir(mode=0o700)
    cm=json.loads((CONFIG/'configuration-manifest.json').read_bytes())
    for row in cm['files']:
        p=CONFIG/row['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        target=configuration/('bootstrap.original.py' if row['path']=='entry.py' else row['path']);shutil.copyfile(p,target);target.chmod(0o444)
    shutil.copyfile(entry,configuration/'entry.py');(configuration/'entry.py').chmod(0o444);configuration.chmod(0o555)
    result={'kind':'ACTUAL_APPROVED_COMMON_MAIN1B5C68B_FULL_ORIGINAL_MATRIX_COLLECTION','source':SOURCE,'before':before,
            'methodSha256':method_sha,'entrySha256':entry_sha,'approvalRef':str(args.approval),'approvalSha256':args.approval_sha256,
            'startedAt':start.isoformat(),'commands':[],'containerId':None,'externalCleanup':[],
            'rawMatrixCollectionCompleted':False,'fullMediaAccepted':False,'untracedLatencyAccepted':False,
            'formalActorBindingAccepted':False,'formalPocAccepted':False,'runtimeFilesRetained':True,
            'diskQuotaKind':'active_stat_guard_terminates_owned_container_not_filesystem_quota'}
    save=lambda:(OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    save()
    overall_deadline=None
    def command(label,argv,allow_absent=False,timeout=45):
        row={'label':label,'argv':argv,'startedAt':datetime.now(timezone.utc).isoformat()}
        remaining=(overall_deadline-time.monotonic()) if overall_deadline is not None else timeout+2
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
                reserve=min(1,max(.001,overall_deadline-time.monotonic())) if overall_deadline is not None else 1
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
            (PACKAGE/'identity/passwd','/etc/passwd',True),(PACKAGE/'identity/group','/etc/group',True),(writable,'/runlab',False)]
    create=['docker','create','--pull=never','--name',NAME,'--label',LABEL+'='+method_sha,'--label','guize.poc003.source='+SOURCE,
            '--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--network','none','--ipc','private','--cgroupns','private',
            '--memory','512m','--memory-swap','512m','--cpus','1','--pids-limit','64','--ulimit','nofile=256:256',
            '--log-driver','none','--stop-signal','SIGINT','--env','PYTHONDONTWRITEBYTECODE=1','--env','PYTHONNOUSERSITE=1',
            '--env','LC_ALL=C.UTF-8','--env','PYTHONCOERCECLOCALE=0','--workdir','/runlab','--entrypoint','/usr/local/bin/python3']
    for source,target,ro in mounts:create+=['--mount','type=bind,source='+str(source)+',target='+target+(',readonly' if ro else '')]
    create += [IMAGE,'-B','/configuration/entry.py']
    cid=None;attached=None;cleanup_attempted=False
    def inspect(label,timeout=45):
        row=json.loads(command(label,['docker','container','inspect',cid],timeout=timeout))[0]
        assert row['Id']==cid and row['Image']==IMAGE and row['Config']['Labels'].get(LABEL)==method_sha
        return row
    def disk_guard():
        total=other=count=0
        for p in writable.rglob('*'):
            if p.is_symlink():raise ValueError('unexpected writable symlink')
            s=p.lstat()
            if stat.S_ISREG(s.st_mode):
                count+=1;total+=s.st_size
                if '/cache/' not in str(p):
                    other+=s.st_size
                    if s.st_size>128*1024*1024:raise ValueError('noncache file budget')
        if count>5000 or total>2*1024*1024*1024 or other>1792*1024*1024:raise ValueError('private writable byte/file budget')
        for p in [OUT/'start.stdout.raw',OUT/'start.stderr.raw']:
            if p.exists() and p.stat().st_size>16*1024*1024:raise ValueError('attached raw output budget')
        return {'files':count,'logicalBytes':total,'nonCacheLogicalBytes':other}
    def cleanup_owned():
        nonlocal cleanup_attempted
        if cleanup_attempted or cid is None:return
        cleanup_attempted=True
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
            try:attached.wait(timeout=min(5,max(.001,overall_deadline-time.monotonic())))
            except subprocess.TimeoutExpired:
                attached.kill();attached.wait(timeout=min(1,max(.001,overall_deadline-time.monotonic())));result['externalCleanup'].append('own attach CLI killed after namespace cleanup')
            result.update(attachedCliExitCode=attached.returncode,attachedCliWaitCompleted=True)
        final=inspect('cleanup-final-inspect',timeout=5)
        result['cleanupFinalContainerState']=final['State'];save()
        assert not final['State']['Running'] and final['State']['Pid']==0
    try:
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
        tick=time.monotonic();deadline=tick+840;overall_deadline=tick+900
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
        engine_exit=int(command('engine-wait',['docker','wait',cid],timeout=45).decode().strip())
        final=inspect('final-inspect',timeout=5);assert not final['State']['Running'] and final['State']['Pid']==0 and final['State']['ExitCode']==engine_exit
        result.update(engineWaitCompleted=True,engineExitCode=engine_exit,finalContainerState=final['State'],finalDiskObservation=disk_guard())
        # Keep the full actual inventory, including unexpected extra epochs.
        closure_paths=sorted((writable/'work/process-epochs').glob('epoch-*/closure.json'))
        result['actualClosureArtifactPaths']=[p.relative_to(writable).as_posix() for p in closure_paths]
        try:
            retain_matrix_outcomes(result,writable)
        finally:
            save()
        client=result['clientReport'];owner=result['actualOwnerWait']
        closures=[json.loads(p.read_bytes()) for p in closure_paths]
        result.update(actualTargetClosures=closures)
        assert not result.get('runtimeError') and not result['externalCleanup'] and result['attachedCliExitCode']==engine_exit==0
        assert all(client.get(k) is True for k in ('beforeEnvironmentCaptured','checkpointObserved','profileAbsentBeforeClient','clientCompleted','rawCollectionCompleted','serveReturnedNormally','clientThreadStopped'))
        assert client['rawRequestCount']==101 and client['rawCacheStages']==6 and client['rawCollectionStatus']=='RAW_COLLECTION_COMPLETED_UNASSESSED'
        collection=json.loads((writable/'original-matrix/collection.json').read_bytes())
        assert not collection['missingCases'] and len(collection['collectedCases'])==21 and len(collection['rows'])==101 and len(collection['cacheStages'])==6
        assert {row['stage'] for row in collection['cacheStages']}=={'before','filled','interrupted','recovered','updated','cleanup'}
        assert collection['formalPocAccepted'] is False and collection['canonicalRecordsGenerated'] is False
        result['collectionSummary']={k:collection[k] for k in ('status','collectedCases','missingCases','totalResponseBodyBytes')}
        assert owner['actualOwnerWaitCompleted'] and owner['ownerExitCode']==0
        summary=owner['targetClosureSummary'];assert summary['epochCount']==summary['closedEpochCount']==summary['acceptedCount']==26 and summary['allAccepted']
        assert len(closures)==26 and all(r['accepted'] and r['actualWaitCompleted'] for r in closures)
        assert all(r['exitCode']==0 for r in closures)
        assert sum(r['label'].startswith('clear-cache-') for r in closures)==12 and sum(r['label']=='verify-config' for r in closures)==1
        after={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain=v1','--untracked-files=all')};assert after==before
        assert sha(PACKAGE/'package-manifest.json')==result.get('packageManifestSha256',approval['packageManifestSha256'])
        assert all(sha(template/rel)==pin for rel,pin in template_pins.items())
        verify_package()
        result.update(after=after,sourceUnchanged=True,derivedTemplateBytesUnchanged=True,rawMatrixCollectionCompleted=True)
    except BaseException as error:
        result.update(failureType=type(error).__name__,failure=str(error)[:1024]);save()
        try:cleanup_owned()
        except BaseException as cleanup_error:
            result.update(cleanupErrorType=type(cleanup_error).__name__,cleanupError=str(cleanup_error)[:512]);save()
        raise
    finally:
        result['finishedAt']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'source':SOURCE,'rawMatrixCollectionCompleted':True,'containerId':cid,'engineExitCode':result['engineExitCode'],
                      'ownerActualWaitCompleted':True,'targetEpochs':26,'formalPocAccepted':False}),flush=True)


if __name__=='__main__':main()

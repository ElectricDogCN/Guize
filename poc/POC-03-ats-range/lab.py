#!/usr/bin/env python3
"""Isolated POC sandbox. Execute only after independent input/resource approval."""
from __future__ import annotations
import argparse,copy,hashlib,hmac,http.client,http.server,json,os,re,secrets,shutil,socket
import signal,subprocess,sys,threading,time,urllib.parse
from datetime import datetime,timedelta,timezone
from pathlib import Path
from grants import Grant
from input_profile import prepare_input_pair

HERE=Path(__file__).resolve().parent
EPOCH_CONFIGURATION_FILES=('etc/records.config','etc/remap.config','etc/plugin.config',
    'etc/storage.config','etc/lab-guard.conf','etc/poc003-empty-ssl-multicert.config','runroot.yaml')
PINNED={
 "base":("guize-range-local64m-base-v1.bin","938a8bc3e0a64184f1551bff0c500dc891366ead8f30f8f83753587e763c1c26"),
 "changed":("guize-range-local64m-changed-v1.bin","643d769e1b5120a7c52d63df3d266f67a4177050180858480feb4e686e2fdda1")}
CASES={'range_start','range_middle','range_end','suffix','unsatisfiable','if_match','if_stale',
       'miss','fill','hit','updated','interrupted','partial_read','recovered','stream',
       'other_user','denied_user','latency_hot','latency_cold','latency_slow','latency_multi'}
def utc():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb',buffering=0) as stream,memoryview(bytearray(1048576)) as backing:
        if backing.obj.__alloc__()!=len(backing)+1:raise OSError('unqualified fixed hash backing capacity')
        while True:
            count=stream.readinto(backing)
            if type(count) is not int or not 0<=count<=len(backing):raise OSError('invalid raw input read count')
            if not count:break
            with backing[:count] as block:h.update(block)
    return h.hexdigest()
def write_json(path,value):
    data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(data)

def raw_writer(path):
    return open(path,'xb',opener=lambda name,flags:os.open(name,flags|os.O_CLOEXEC,0o600))
def unique_json(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            if key in result:raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    def constant(value):raise ValueError('nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)
def interval(value,size,if_range='',etag=''):
    """Single byte range only; stale If-Range selects the full representation."""
    if not value or if_range and if_range!=etag:return 200,0,size-1
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not match or len(value)>80:raise ValueError('unsupported/malformed single Range')
    first,last=match.groups()
    if not first:
        if not last or int(last)<=0:return 416,0,-1
        return 206,max(0,size-int(last)),size-1
    start=int(first);end=int(last) if last else size-1
    if start>=size or end<start:return 416,0,-1
    return 206,start,min(size-1,end)
def context(acl,user):return hashlib.sha256((acl+'\0'+user).encode()).hexdigest()[:32]
def sign(secret,path,request_id,expiry):
    return hmac.new(secret.encode(),(path+'\n'+request_id+'\n'+str(expiry)).encode(),hashlib.sha256).hexdigest()
def selfcheck():
    expected=[('', '',(200,0,15)),('bytes=0-7','',(206,0,7)),('bytes=8-99','',(206,8,15)),
      ('bytes=-8','',(206,8,15)),('bytes=16-23','',(416,0,-1)),('bytes=0-7','"old"',(200,0,15)),
      ('bytes=0-7','"current"',(206,0,7)),('bytes=-0','',(416,0,-1))]
    for value,condition,result in expected:assert interval(value,16,condition,'"current"')==result
    for value in ('bytes=0-1,4-5','bytes=','items=0-7','bytes=a-b','bytes=--1'):
        try:interval(value,16)
        except ValueError:pass
        else:raise AssertionError(value)
    assert context('acl','a')!=context('acl','b')
    assert sign('secret','/a','r',1)!=sign('secret','/b','r',1)
    try:unique_json('{"a":1,"a":2}')
    except ValueError:pass
    else:raise AssertionError('duplicate JSON accepted')
    return dict(kind='OFFLINE_PARSER_CHECK_ONLY',checks=16,listenersStarted=False,atsStarted=False,pocExecuted=False)

def prepare(config_path,run):
    if os.name!='posix' or os.geteuid()==0:raise ValueError('WSL/Linux ordinary user required')
    config_path=Path(config_path).resolve();cfg=unique_json(config_path.read_text())
    manifest_path=(config_path.parent/cfg['fixtureManifest']).resolve()
    receipt_path=(config_path.parent/cfg['runtimeReceipt']).resolve()
    with manifest_path.open('rb') as manifest_stream:
        manifest_raw=manifest_stream.read(65537)
    if len(manifest_raw)>65536:raise ValueError('fixture manifest exceeds 64KiB')
    receipt=unique_json(receipt_path.read_text())
    if receipt['status']!='ready_for_future_poc_environment':raise ValueError('runtime not prepared')
    prefix=Path(receipt['prefix']).resolve();pkg=prefix/'pkgroot'
    if receipt['versions']['traffic_server']['returncode']!=0 or '9.2.3' not in receipt['versions']['traffic_server']['stdout']:raise ValueError('expected prepared ATS9.2.3')
    ports=[cfg[key] for key in ('originPort','atsPort','entryPort')]
    if len(set(ports))!=3 or any(type(p)!=int or not 1024<p<65536 for p in ports):raise ValueError('distinct unprivileged ports')
    if cfg['originPort']!=18231:raise ValueError('exporter protected-origin allowlist requires port18231')
    if cfg['chunkBytes']!=65536 or cfg['cacheMiB']!=256 or cfg['maximumRetries']!=0:raise ValueError('bounded initial profile')
    if not 1<=cfg['maximumRunSeconds']<=1800 or not 2<=cfg['latencySampleCount']<=20 or cfg['latencySampleCount']%2 or cfg['concurrentUsers']!=2:raise ValueError('bounded workload')
    if cfg['slowOriginDelayMs']!=250 or cfg['slowOriginBandwidthBytesPerSecond']!=1048576 or cfg['faultAfterBytes']!=4:raise ValueError('bounded controlled-origin profile')
    python_binding=None
    if cfg.get('liveBufferObserver') is not None:
        from python_runtime import verify_runtime_file
        python_binding=verify_runtime_file(HERE/'python-runtime-profile.json')
        cfg['pythonRuntimeProfileSha256']=python_binding['profileSha256']
    inputs=prepare_input_pair(cfg,manifest_path,manifest_raw,PINNED)
    plugins={}
    for name in ('slice.so','cache_range_requests.so','header_rewrite.so'):
        path=pkg/'usr/lib/trafficserver/modules'/name
        if not path.is_file():raise ValueError('required existing plugin missing: '+name)
        if name in receipt['plugins'] and digest(path)!=receipt['plugins'][name]['sha256']:raise ValueError('pinned plugin changed')
        plugins[name]=dict(path=str(path),sha256=digest(path))
    exporter=Path(cfg['exportPluginPath']).resolve()
    if not exporter.is_file() or digest(exporter)!=cfg['exportPluginSha256']:
        raise ValueError('exact independently reviewed cache observer build required')
    build_path=Path(cfg['exportBuildReceipt']).resolve();build=unique_json(build_path.read_text())
    if build['exitCode']!=0 or build['sourceSha256']!=digest(HERE/'cache_export.cc') or build['pluginSha256']!=cfg['exportPluginSha256']:
        raise ValueError('observer build receipt must bind actual source and binary')
    plugins['cache_export.so']=dict(path=str(exporter),sha256=cfg['exportPluginSha256'])
    live=cfg.get('liveBufferObserver')
    if live is not None:
        runtime=receipt.get('instrumentedLiveBuffer')
        if not isinstance(live,dict) or not isinstance(runtime,dict):raise ValueError('instrumented runtime and observer required together')
        live_plugin=Path(live['path']).resolve();live_receipt_path=Path(live['buildReceipt']).resolve()
        live_build=unique_json(live_receipt_path.read_text());core_build_path=Path(runtime['buildReceiptPath'])
        core_build=unique_json(core_build_path.read_text())
        if (digest(live_plugin)!=live['sha256'] or live_build['pluginSha256']!=live['sha256'] or live_build['exitCode']!=0
                or live_build['sourceSha256']!=digest(HERE/'instrumentation/live_buffer_observer.cc')
                or live_build['ledgerHeaderSha256']!=digest(HERE/'instrumentation/live_buffer_accounting.h')
                or live_build['ledgerHeaderSha256']!=runtime['ledgerHeaderSha256']
                or digest(core_build_path)!=runtime['buildReceiptSha256'] or not core_build['buildCompleted']
                or core_build['instrumentation']['additionalHeaderSha256']!=runtime['ledgerHeaderSha256']):
            raise ValueError('exact instrumented core/observer build mismatch')
        journal_sha=digest(HERE/'instrumentation/live_peak_journal.h')
        if core_build['instrumentation']!=unique_json((HERE/'instrumentation/patch-manifest.json').read_text()):
            raise ValueError('exact current core patch and all installed accounting headers required')
        if (runtime.get('journalHeaderSha256')!=journal_sha or live_build.get('journalHeaderSha256')!=journal_sha
                or core_build['instrumentation'].get('journalHeaderSha256')!=journal_sha
                or live_build.get('accountingWindow')!='process-lifetime'):
            raise ValueError('durable process-lifetime core and observer builds required')
        required={'usr/bin/traffic_server','usr/lib/trafficserver/libtscore.so.9.2.3',
                  'usr/lib/trafficserver/modules/slice.so','usr/lib/trafficserver/modules/cache_range_requests.so',
                  'usr/lib/trafficserver/modules/header_rewrite.so'}
        if set(runtime['components'])!=required:raise ValueError('complete controlled runtime component identities required')
        for name,sha in runtime['components'].items():
            if digest(pkg/name)!=sha:raise ValueError('instrumented runtime component changed')
        live.update(ledgerHeaderSha256=live_build['ledgerHeaderSha256'],observerSourceSha256=live_build['sourceSha256'],
                    buildReceiptSha256=digest(live_receipt_path))
        plugins['live_buffer_observer.so']=dict(path=str(live_plugin),sha256=live['sha256'])
    run=Path(run).absolute()
    if run.exists() or run.is_symlink() or run.parent.resolve()!=run.parent:raise ValueError('new explicit nonsymlink run directory required')
    run.mkdir(mode=0o700)
    for name in ('cache','log','run','commands','cache-observer'): (run/name).mkdir(mode=0o700)
    if live is not None:(run/'process-epochs').mkdir(mode=0o700)
    if python_binding is not None:
        from python_runtime import write_binding
        write_binding(run/'python-runtime-binding.prepare.json',python_binding)
    shutil.copytree(pkg/'etc/trafficserver',run/'etc')
    # Generated lab secrets are private runtime controls, never sample approvals.
    cfg.update(kind='UNAPPROVED_POC003_STANDALONE_LAB',createdAt=utc(),runDir=str(run),inputs=inputs,
      runtimePrefix=str(prefix),pkgroot=str(pkg),runtimeReceipt=str(receipt_path),runtimeReceiptSha256=digest(receipt_path),
      inputManifest=str(manifest_path),inputManifestSha256=hashlib.sha256(manifest_raw).hexdigest(),plugins=plugins,
      ldLibraryPath=receipt['LD_LIBRARY_PATH'],secret=secrets.token_hex(32),controlKey=secrets.token_hex(32),
      users={'lab-user-a':secrets.token_hex(24),'lab-user-b':secrets.token_hex(24),'lab-denied-user':secrets.token_hex(24)},
      formalApproval=False,pocExecuted=False)
    cfg['implementationSources']={name:digest(HERE/name) for name in
        ('lab.py','grants.py','input_profile.py','collect.py','cache_probe.py','http_timing.py','buffer_probe.py','cache_export.cc','test_warm_cache_revocation.py')}
    cfg['exportBuildReceiptSha256']=digest(build_path)
    if live is not None:
        cfg['instrumentedRuntime']=receipt['instrumentedLiveBuffer']
        for name in ('python_runtime.py','crypto_runtime.py','python-runtime-profile.json'):cfg['implementationSources'][name]=digest(HERE/name)
        for name in ('owned_epoch.py','epoch_owner.py','instrumentation/exec_gate.py','instrumentation/single_exec_gate.py','instrumentation/single_exec_filter.py','live_buffer_probe.py','durable_peak_probe.py','instrumentation/live_peak_journal.h','instrumentation/live_pool_capacity.h','instrumentation/patch-manifest.json','instrumentation/ats-live-buffer-accounting.patch','instrumentation/live_buffer_accounting.h','instrumentation/live_buffer_observer.cc'):
            cfg['implementationSources'][name]=digest(HERE/name)
        interpreter=Path(sys.executable).resolve(strict=True)
        cfg['executionInterpreter']={'path':str(interpreter),'sha256':digest(interpreter)}
    now=datetime.now(timezone.utc)
    cfg['grants']={user:dict(grantId='poc003-grant-'+user,principalId=user,
        validFrom=(now-timedelta(seconds=5)).isoformat().replace('+00:00','Z'),
        validUntil=(now+timedelta(seconds=cfg['maximumRunSeconds']+300)).isoformat().replace('+00:00','Z'))
        for user in cfg['users']}
    envdir=run/'etc';user=subprocess.check_output(['id','-un'],text=True).strip()
    settings={
      'proxy.config.body_factory.template_sets_dir':('STRING',str(envdir/'body_factory')),
      'proxy.config.http.server_ports':('STRING',str(cfg['atsPort'])+':ip-in=127.0.0.1'),
      'proxy.config.admin.user_id':('STRING',user),'proxy.config.reverse_proxy.enabled':('INT','1'),
      'proxy.config.url_remap.remap_required':('INT','1'),'proxy.config.http.cache.http':('INT','1'),
      'proxy.config.cache.ram_cache.size':('INT','0'),
      'proxy.config.http.insert_response_via_str':('INT','3'),
      'proxy.config.http.connect_attempts_max_retries':('INT','0'),
      'proxy.config.http.connect_attempts_max_retries_dead_server':('INT','0')}
    # This fixed diagnostic uses installed DSOs, so do not create/unlink remap
    # reload copies that cannot be independently hashed through installed paths.
    if live is not None:
        settings['proxy.config.plugin.dynamic_reload_mode']=('INT','0')
        settings['proxy.config.crash_log_helper']=('STRING','NULL')
        empty_tls=envdir/'poc003-empty-ssl-multicert.config'
        empty_tls.write_text('# No certificate/key/dialog entries in this plain-HTTP diagnostic.\n',encoding='utf-8')
        settings['proxy.config.ssl.server.multicert.filename']=('STRING',str(empty_tls))
    records=envdir/'records.config';lines=records.read_text().splitlines()
    lines=[line for line in lines if not(len(line.split())>=2 and line.split()[0]=='CONFIG' and line.split()[1] in settings)]
    records.write_text('\n'.join(lines+[f'CONFIG {key} {kind} {value}' for key,(kind,value) in settings.items()])+'\n')
    (envdir/'storage.config').write_text(str(run/'cache')+' 256M\n')
    (envdir/'remap.config').write_text(f"map http://ats.local/ http://127.0.0.1:{cfg['originPort']}/ @plugin=slice.so @pparam=--blockbytes=1048576 @plugin=cache_range_requests.so @pparam=--consider-ims\n")
    # ATS9.2.3 implementation supports set-status at READ_REQUEST_HDR_HOOK,
    # before cache lookup; prevent direct ATS access even after cache warming.
    (envdir/'plugin.config').write_text('header_rewrite.so '+str(envdir/'lab-guard.conf')+'\n'+
        str(exporter)+' '+str(run/'cache-observer')+'\n'+
        (str(live_plugin)+' '+str(run/'cache-observer')+'\n' if live is not None else ''))
    (envdir/'lab-guard.conf').write_text(
      'cond %{READ_REQUEST_HDR_HOOK}\ncond %{CLIENT-HEADER:X-Lab-ATS-Key} ='+cfg['secret']+' [NOT]\nset-status 403 [L]\n'
      'cond %{SEND_RESPONSE_HDR_HOOK}\nset-header X-Lab-ATS-Cache %{CACHE}\n')
    layout={'prefix':str(run),'exec_prefix':str(pkg/'usr'),'bindir':str(pkg/'usr/bin'),'sbindir':str(pkg/'usr/bin'),
      'sysconfdir':str(envdir),'datadir':str(pkg/'usr/share/trafficserver'),'includedir':str(pkg/'usr/include'),
      'libdir':str(pkg/'usr/lib'),'libexecdir':str(pkg/'usr/lib/trafficserver/modules'),
      'localstatedir':str(run),'runtimedir':str(run/'run'),'logdir':str(run/'log'),'cachedir':str(run/'cache')}
    (run/'runroot.yaml').write_text('\n'.join(key+': '+json.dumps(value) for key,value in layout.items())+'\n')
    for file in envdir.iterdir():
        if file.is_file():file.chmod(0o600)
    if live is not None:cfg['epochConfiguration']={name:digest(run/name) for name in EPOCH_CONFIGURATION_FILES}
    write_json(run/'settings.private.json',cfg)
    write_json(run/'owner.json',dict(uid=os.getuid(),runDir=str(run),kind=cfg['kind']))
    return dict(status='CONFIGURED_NOT_STARTED',runDir=str(run),atsStarted=False,listenersStarted=False,pocExecuted=False)

class State:
    def __init__(self,run):
        self.run=Path(run).resolve();self.cfg=unique_json((self.run/'settings.private.json').read_text())
        owner=unique_json((self.run/'owner.json').read_text())
        if os.geteuid()==0 or owner['uid']!=os.getuid() or owner['runDir']!=str(self.run):raise ValueError('wrong sandbox owner')
        self.python_runtime_binding=None
        if self.cfg.get('liveBufferObserver') is not None:
            from python_runtime import verify_runtime_file,write_binding
            if self.cfg.get('pythonRuntimeProfileSha256')!=digest(HERE/'python-runtime-profile.json'):
                raise ValueError('prepared Python runtime profile changed or missing')
            self.python_runtime_binding=verify_runtime_file(HERE/'python-runtime-profile.json')
            write_binding(self.run/'python-runtime-binding.controller.json',self.python_runtime_binding)
        if any(digest(HERE/name)!=sha for name,sha in self.cfg['implementationSources'].items()):
            raise ValueError('implementation changed after sandbox preparation')
        self.lock=threading.RLock();self.loglock=threading.Lock();self.version='base';self.fault='none'
        self.origin_rows={};self.active_origin={};self.gateway_rows={};self.gateway_active=0;self.ats=None;self.ats_logs=[]
        self.origin_active_peak=0;self.gateway_active_peak=0
        self.media_window_started_at=utc()
        self.allocator_dumps=0;self.live_snapshots=0;self.cache_ready=None
        self.ats_epoch=None;self.owned_epochs=[];self.epoch_closures=[]
        self.epoch_owner=None
        self.grants={user:Grant(row['grantId'],row['principalId'],row['validFrom'],row['validUntil'])
                     for user,row in self.cfg['grants'].items()}
        if set(self.grants)!=set(self.cfg['users']) or any(g.principal!=u for u,g in self.grants.items()):
            raise ValueError('exact configured principal grants required')
        self.stop_event=threading.Event();self.started=time.monotonic()
        for name,row in self.cfg['inputs'].items():
            if Path(row['path']).stat().st_size!=row['sizeBytes'] or digest(row['path'])!=row['sha256']:raise ValueError('input changed after preparation')
        for row in self.cfg['plugins'].values():
            if digest(row['path'])!=row['sha256']:raise ValueError('plugin changed after preparation')
        for name,sha in self.cfg.get('instrumentedRuntime',{}).get('components',{}).items():
            if digest(Path(self.cfg['pkgroot'])/name)!=sha:raise ValueError('instrumented core changed after preparation')
        if self.cfg.get('liveBufferObserver') is not None:
            if set(self.cfg.get('epochConfiguration',{}))!=set(EPOCH_CONFIGURATION_FILES):
                raise ValueError('exact effective epoch configuration pins required')
            for name,sha in self.cfg['epochConfiguration'].items():
                if digest(self.run/name)!=sha:raise ValueError('effective epoch configuration changed')
    def log(self,name,row):
        with self.loglock:
            with (self.run/(name+'.jsonl')).open('a',encoding='utf8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n');out.flush()
    def ats_command(self,args,label):
        command=[str(Path(self.cfg['pkgroot'])/'usr/bin/traffic_server'),'--run-root='+str(self.run),*args]
        if not re.fullmatch('[A-Za-z0-9_-]{1,80}',label):raise ValueError('bounded command label required')
        with self.lock:
            started=utc()
            if self.cfg.get('liveBufferObserver') is None:
                result=subprocess.run(command,env=self.ats_environment(),cwd=self.run,capture_output=True,timeout=30)
                (self.run/'commands'/(label+'.stdout.raw')).write_bytes(result.stdout)
                (self.run/'commands'/(label+'.stderr.raw')).write_bytes(result.stderr)
                self.log('controller',dict(action=label,startedAt=started,finishedAt=utc(),argv=command,exitCode=result.returncode))
                if result.returncode:raise RuntimeError(label+' failed; raw retained')
                return
            if self.epoch_owner is None or args not in (['-C','verify_config'],['-C','clear_cache']):
                raise ValueError('single-thread owner and fixed ATS helper required')
            with raw_writer(self.run/'commands'/(label+'.stdout.raw')) as out,raw_writer(self.run/'commands'/(label+'.stderr.raw')) as err:
                result=self.epoch_owner.call('launch',operation=args[1],label=label,descriptors=(out.fileno(),err.fileno()))
            self.owned_epochs.append(result['description']);closure=result['closure'];code=result['exitCode']
            self.epoch_closures.append(closure);self.log('controller',closure)
            self.log('controller',dict(action=label,startedAt=started,finishedAt=utc(),argv=command,exitCode=code))
            if code or not closure['accepted']:raise RuntimeError(label+' epoch failed; raw retained')
    def _launch_epoch(self,command,label,out,err):
        expected=[str(Path(self.cfg['pkgroot'])/'usr/bin/traffic_server'),'--run-root='+str(self.run),'-n','2']
        if self.epoch_owner is None or command!=expected:raise ValueError('fixed ATS service through owner required')
        epoch=self.epoch_owner.call('launch',operation='start',label=label,descriptors=(out.fileno(),err.fileno()))
        self.owned_epochs.append(epoch)
        self.log('controller',dict(action='owned-epoch-released',label=label,pid=epoch['birth']['pid'],
            birth=epoch['birth'],epochRef=str(Path(epoch['output']).parent.relative_to(self.run))))
        return epoch
    def _finish_epoch(self,epoch,label,*,stop=False):
        row=self.epoch_owner.call('finish',token=epoch['token'],label=label,stop=stop)
        self.epoch_closures.append(row);self.log('controller',row)
        return row
    def ats_environment(self,journal_directory=None):
        env=dict(os.environ,LD_LIBRARY_PATH=self.cfg['ldLibraryPath'],TS_RUNROOT=str(self.run/'runroot.yaml'),
                 PROXY_DPRINTF_LEVEL='0')
        env.pop('LD_PRELOAD',None);env.pop('LD_AUDIT',None)
        env.pop('GUIZE_POC003_PEAK_JOURNAL_DIR',None)
        if self.cfg.get('liveBufferObserver') is not None:
            if journal_directory is None:raise ValueError('fresh per-launch journal directory required')
            env['GUIZE_POC003_PEAK_JOURNAL_DIR']=str(journal_directory)
        return env
    def start_ats(self):
        with self.lock:return self._start_ats()
    def _start_ats(self):
        if self.ats is not None:raise ValueError('ATS child already exists')
        number=len(self.ats_logs);out=raw_writer(self.run/'log'/f'ats-{number}.stdout.raw');err=raw_writer(self.run/'log'/f'ats-{number}.stderr.raw')
        self.cache_ready=None;self.ats_logs.append((out,err))
        try:
            command=[str(Path(self.cfg['pkgroot'])/'usr/bin/traffic_server'),'--run-root='+str(self.run),'-n','2']
            if self.cfg.get('liveBufferObserver') is not None:
                self.ats_epoch=self._launch_epoch(command,'ats-start-'+str(number),out,err)
                from epoch_owner import OwnerTarget
                self.ats=OwnerTarget(self.epoch_owner,self.ats_epoch)
            else:self.ats=subprocess.Popen(command,env=self.ats_environment(),cwd=self.run,stdout=out,stderr=err)
            self.log('controller',dict(action='ats-start',at=utc(),pid=self.ats.pid))
            return self._await_ats_ready(number)
        except BaseException:
            try:self.stop_ats()
            finally:
                for stream in (out,err):
                    if not stream.closed:stream.close()
            raise
    def _await_ats_ready(self,number):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if self.ats.poll() is not None:raise RuntimeError('ATS exited before readiness; raw retained')
            try:
                ready=self.run/'cache-observer'/('cache-export-'+str(self.ats.pid))/'cache-ready.json'
                if ready.is_file() and not ready.is_symlink():
                    observation=unique_json(ready.read_text())
                    if (observation.get('atsPid')!=self.ats.pid or observation.get('cacheReady') is not True
                            or observation.get('httpCacheReady') is not True):
                        raise ValueError('wrong native cache readiness')
                    with socket.create_connection(('127.0.0.1',self.cfg['atsPort']),timeout=.2):
                        self.cache_ready=observation
                        self.log('controller',dict(action='native-http-cache-ready',**observation))
                    if self.ats_epoch is not None:self.epoch_owner.call('identity',token=self.ats_epoch['token'])
                    if self.cfg.get('liveBufferObserver') is not None:self.live_buffer_snapshot('live-window-ready-'+str(number))
                    return
            except OSError:time.sleep(.1)
            time.sleep(.05)
        raise TimeoutError('ATS native HTTP cache and TCP readiness deadline')
    def live_buffer_snapshot(self,label,after_ns=0):
        live=self.cfg.get('liveBufferObserver')
        if (live is None or self.ats is None or self.ats_epoch is None or self.cache_ready is None or self.cache_ready['atsPid']!=self.ats.pid
                or self.gateway_active or any(self.active_origin.values()) or self.live_snapshots>=16
                or type(after_ns)!=int or not 0<=after_ns<=time.monotonic_ns()
                or not re.fullmatch('[A-Za-z0-9_-]{1,80}',label)):
            raise ValueError('owned ready instrumented ATS and explicit output label required')
        self.live_snapshots+=1
        output=self.run/label
        row=self.epoch_owner.call('live_snapshot',token=self.ats_epoch['token'],label=label,after_ns=after_ns)
        row.update(action='live-buffer-snapshot',observedAt=utc())
        write_json(output/'observation.json',row);return row
    def allocator_dump(self):
        with self.lock:
            if (self.ats is None or self.cache_ready is None or self.cache_ready['atsPid']!=self.ats.pid
                    or self.gateway_active or any(self.active_origin.values()) or self.allocator_dumps>=16):
                raise ValueError('owned ready ATS, idle gateway/origin and diagnostic quota required')
            number=self.allocator_dumps;self.allocator_dumps+=1
            output=self.run/('allocator-dump-'+str(number))
            if self.cfg.get('liveBufferObserver') is None:
                from buffer_probe import capture_dump
                row=capture_dump(self.ats,self.ats_logs[-1][1],output)
            else:
                if self.ats_epoch is None or self.epoch_owner is None:raise ValueError('owned instrumented ATS required')
                row=self.epoch_owner.call('allocator_dump',token=self.ats_epoch['token'])
            row.update(action='allocator-dump',observedAt=utc(),outputDir=str(output),
                       nativeCacheReady=self.cache_ready,activeOriginRequests=0,activeGatewayRequests=0)
            write_json(output/'diagnostic.json',row);return row
    def stop_ats(self):
        with self.lock:
            if self.ats is None and self.ats_epoch is None:return
            child=self.ats;epoch=self.ats_epoch;closure=None
            try:
                if epoch is not None:
                    closure=self._finish_epoch(epoch,'ats-stop',stop=True)
                elif child.poll() is None:
                    child.terminate()
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
                self.log('controller',dict(action='ats-stop-owned-child',at=utc(),pid=child.pid,
                    exitCode=closure['exitCode'] if closure is not None else child.returncode))
            finally:
                self.ats=None;self.ats_epoch=None;self.cache_ready=None
                for streams in self.ats_logs:
                    for stream in streams:
                        if not stream.closed:stream.close()
            if closure is not None and not closure['accepted']:raise RuntimeError('ATS final epoch rejected; raw retained')
    def clear_cache(self):
        with self.lock:
            if self.gateway_active or any(self.active_origin.values()):raise ValueError('cannot purge with active requests')
            self.stop_ats();self.ats_command(['-C','clear_cache'],'clear-cache-'+str(len(self.ats_logs)));self.start_ats()
            row=dict(action='cache-cleared-by-owned-ATS-command',at=utc());self.log('controller',row);return row
    def witness(self,request_id):
        with self.lock:
            # Each native transaction has scalar fields. Copy each dictionary
            # atomically while an active request may still add timing fields.
            rows=[dict(row) for row in self.origin_rows.get(request_id,[])]
            return dict(requestId=request_id,observedAt=utc(),originRequestCount=len(rows),
              objectReadCount=sum(r['objectReadCount'] for r in rows),objectReadBytes=sum(r['objectReadBytes'] for r in rows),
              activeOriginRequests=self.active_origin.get(request_id,0),originTransactions=rows,
              gatewayTransactions=[dict(row) for row in self.gateway_rows.get(request_id,[])])
    def snapshot(self,stage):
        files=[]
        for path in sorted((self.run/'cache').iterdir()):
            if path.is_file() and not path.is_symlink():
                stat=path.stat();files.append(dict(name=path.name,logicalBytes=stat.st_size,allocatedBytes=getattr(stat,'st_blocks',0)*512))
        row=dict(stage=stage,observedAt=utc(),sourceVersion=self.version,atsPid=self.ats.pid if self.ats else None,cacheFiles=files,
                 nativeCacheReady=self.cache_ready,
                 allocatedDiskBytes=sum(r['allocatedBytes'] for r in files),canonicalCacheObjectExported=False,
                 activeOriginRequests=sum(self.active_origin.values()),activeGatewayRequests=self.gateway_active,
                 originRequestCount=sum(len(rows) for rows in self.origin_rows.values()),
                 originObjectReadBytes=sum(row['objectReadBytes'] for rows in self.origin_rows.values() for row in rows))
        row['requestConcurrency']=self.media_concurrency()
        self.log('cache-disk-snapshots',row);return row

    def media_concurrency(self):
        with self.lock:
            return dict(kind='SYNCHRONOUS_REQUEST_INTERVAL_HIGH_WATER_NOT_MEMORY_SAMPLING',
                scope='Controller initialization through this lock-held snapshot; not a closed full-run claim',
                activeOrigin=sum(self.active_origin.values()),peakOrigin=self.origin_active_peak,
                activeGateway=self.gateway_active,peakGateway=self.gateway_active_peak)

    def close_media_window(self,http_windows):
        """Seal request counters only after owned HTTP workers and ATS teardown."""
        with self.lock:
            if (not http_windows or any(not row['closed'] or row['active']!=0
                    or row['admitted']!=row['finished'] for row in http_windows)
                    or self.ats is not None or self.ats_epoch is not None
                    or self.gateway_active or any(self.active_origin.values())):
                raise ValueError('controller media request window is not closed')
            row=dict(kind='CLOSED_CONTROLLER_REQUEST_WINDOW_NOT_AGGREGATE_MEMORY',
                startedAt=self.media_window_started_at,closedAt=utc(),closed=True,
                httpRequestWindows=http_windows,requestConcurrency=self.media_concurrency(),
                sourceQualified=False,aggregateCapacityProofComplete=False,formalPocAccepted=False)
            row['requestConcurrency']['scope']='Controller initialization through closed owned HTTP workers and ATS teardown'
            if getattr(self,'python_runtime_binding',None) is not None:
                row['pythonRuntimeBinding']=dict(ref='python-runtime-binding.controller.json',
                    sha256=digest(self.run/'python-runtime-binding.controller.json'),
                    pid=self.python_runtime_binding['pid'],processStartTicks=self.python_runtime_binding['processStartTicks'])
            with (self.run/'media-request-window-closed.json').open('x',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
            return row

class Server(http.server.ThreadingHTTPServer):
    # Rebind an owned stopped sandbox after TCP TIME_WAIT, while normal bind
    # still refuses another live listener. SO_REUSEPORT is never enabled.
    daemon_threads=True;allow_reuse_address=True
    def __init__(self,address,handler,state):
        self.state=state
        self.request_condition=threading.Condition()
        self.owned_requests={};self.requests_admitted=0;self.requests_finished=0
        self.request_peak=0;self.request_admission_closed=False;self.request_window_started_at=utc()
        super().__init__(address,handler)
    def process_request(self,request,client_address):
        # Reserve synchronously before ThreadingMixIn starts a worker. A worker
        # delayed before its first instruction must still prevent false closure.
        with self.request_condition:
            if self.request_admission_closed:
                self.shutdown_request(request);return
            self.owned_requests[id(request)]=request;self.requests_admitted+=1
            self.request_peak=max(self.request_peak,len(self.owned_requests))
        try:super().process_request(request,client_address)
        except BaseException:
            self._finish_owned_request(request);raise
    def _finish_owned_request(self,request):
        with self.request_condition:
            del self.owned_requests[id(request)];self.requests_finished+=1
            self.request_condition.notify_all()
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self._finish_owned_request(request)
    def shutdown_request(self,request):
        # Serialize normal worker teardown with the controller's descriptor
        # transfer. shutdown/close release the GIL and must have one owner.
        with self.request_condition:super().shutdown_request(request)
    def close_request_window(self,timeout=10):
        # Caller has stopped acceptance with shutdown()/server_close(). Close
        # only these owned sockets, then observe every admitted worker finish.
        with self.request_condition:
            self.request_admission_closed=True
            owned=list(self.owned_requests.values())
        for request in owned:
            with self.request_condition:
                if self.owned_requests.get(id(request)) is not request:continue
                try:request.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                # HTTP rfile keeps a makefile reference. On Windows close()
                # alone may defer native close and leave recv blocked. Hold
                # the worker teardown lock across the entire native sequence.
                descriptor=request.detach()
                if descriptor>=0:socket.close(descriptor)
        deadline=time.monotonic()+timeout
        with self.request_condition:
            while self.owned_requests:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('owned HTTP request workers are not closed')
                self.request_condition.wait(remaining)
            if self.requests_admitted!=self.requests_finished:raise RuntimeError('HTTP request lifetime imbalance')
            return dict(kind='ACTUAL_OWNED_HTTP_REQUEST_THREAD_WINDOW',startedAt=self.request_window_started_at,
                closedAt=utc(),closed=True,admitted=self.requests_admitted,finished=self.requests_finished,
                active=0,peak=self.request_peak,listenerPort=self.server_address[1])
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    @property
    def state(self):return self.server.state
    def empty(self,status):
        self.send_response(status);self.send_header('Content-Length','0');self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers();self.close_connection=True

class Origin(Handler):
    def do_HEAD(self):self.handle_media(head=True)
    def do_GET(self):self.handle_media(head=False)
    def handle_media(self,head):
        state=self.state;cfg=state.cfg;rid=self.headers.get('X-Lab-Request-ID','')
        if not re.fullmatch(r'[a-f0-9]{32}',rid):rid='unbound-'+secrets.token_hex(8)
        txn=secrets.token_hex(8);row=dict(originTransactionId=txn,requestId=rid,startedAt=utc(),finishedAt=None,
          path=self.path,range=self.headers.get('Range',''),ifRange=self.headers.get('If-Range',''),
          authorized=False,objectReadCount=0,objectReadBytes=0,statusCode=None,fault=None,
          sourceVersion=None,sourceSha256=None,transportError=None)
        with state.lock:
            if sum(len(v) for v in state.origin_rows.values())>=cfg['maximumOriginRequests']:self.empty(503);return
            state.origin_rows.setdefault(rid,[]).append(row);state.active_origin[rid]=state.active_origin.get(rid,0)+1
            state.origin_active_peak=max(state.origin_active_peak,sum(state.active_origin.values()))
        block=None;stream=None;prefix_digest=None
        state.log('origin-start',dict(row))
        try:
            # No stat/open/read of protected files before this independent check.
            match=re.fullmatch(r'/ctx/([a-f0-9]{32})/(base|changed)/object\.bin',self.path)
            expiry=self.headers.get('X-Lab-Origin-Expiry','')
            allowed_contexts={context(cfg['aclVersion'],user) for user in ('lab-user-a','lab-user-b')}
            valid=match and match[1] in allowed_contexts and expiry.isdigit() and time.time()<=int(expiry)<=time.time()+301
            valid=valid and hmac.compare_digest(self.headers.get('X-Lab-Origin-Signature',''),sign(cfg['secret'],self.path,rid,int(expiry)))
            if not valid:row['statusCode']=403;self.empty(403);return
            row['authorized']=True;version=match[2];source=cfg['inputs'][version];etag=source['etag']
            if self.headers.get('If-Match') and self.headers['If-Match']!=etag:row['statusCode']=412;self.empty(412);return
            if not self.headers.get('Range') and self.headers.get('If-None-Match')==etag:
                row['statusCode']=304;self.send_response(304);self.send_header('ETag',etag);self.send_header('Content-Length','0');self.end_headers();return
            try:status,start,end=interval(self.headers.get('Range',''),source['sizeBytes'],self.headers.get('If-Range',''),etag)
            except ValueError:row['statusCode']=400;self.empty(400);return
            row.update(statusCode=status,sourceVersion=version,sourceSha256=source['sha256'])
            if status==416:
                self.send_response(416);self.send_header('ETag',etag);self.send_header('Content-Range','bytes */'+str(source['sizeBytes']));self.send_header('Content-Length','0');self.end_headers();return
            with state.lock:fault=state.fault
            row['fault']=fault;length=end-start+1
            if fault=='unavailable':row['statusCode']=503;self.empty(503);return
            if fault=='slow':time.sleep(cfg['slowOriginDelayMs']/1000)
            self.send_response(status);self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Length',str(length));self.send_header('ETag',etag)
            self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','public, max-age=3600')
            self.send_header('Last-Modified','Mon, 19 Oct 2026 00:00:00 GMT')
            if status==206:self.send_header('Content-Range',f"bytes {start}-{end}/{source['sizeBytes']}")
            self.end_headers()
            if head:return
            remaining=min(length,cfg['faultAfterBytes']) if fault=='truncate' else length
            with Path(source['path']).open('rb',buffering=0) as stream,memoryview(bytearray(cfg['chunkBytes'])) as backing:
                row.update(sourceReadMode='raw-readinto',sourceBackingCapacityBytes=backing.obj.__alloc__())
                if row['sourceBackingCapacityBytes']!=len(backing)+1:raise OSError('unqualified fixed source backing capacity')
                stream.seek(start)
                while remaining:
                    with backing[:min(cfg['chunkBytes'],remaining)] as target:
                        count=stream.readinto(target)
                        if type(count) is not int or not 0<=count<=len(target):raise OSError('invalid raw source read count')
                        row['objectReadCount']+=1;row['objectReadBytes']+=count
                        if not count:raise OSError('source shortened')
                        with target[:count] as block:
                            self.wfile.write(block);self.wfile.flush();remaining-=count
                            if fault=='truncate':prefix_digest=hashlib.sha256(block).hexdigest()
                            if fault=='slow':time.sleep(count/cfg['slowOriginBandwidthBytesPerSecond'])
            if fault=='truncate':
                row.update(prefixFlushedAt=utc(),prefixFlushedBytes=row['objectReadBytes'],expectedResponseBytes=length,
                  prefixSha256=prefix_digest,holdSeconds=2)
                state.log('origin-prefix-flushed',dict(row))
                time.sleep(2)
                row['truncateCloseAt']=utc();self.close_connection=True;self.connection.shutdown(socket.SHUT_WR)
        except (OSError,TimeoutError) as error:row['transportError']=type(error).__name__;self.close_connection=True
        finally:
            # End returned media and closed input buffering before the active
            # interval ends or a terminal log can block this frame.
            block=None;stream=None
            row['finishedAt']=utc()
            with state.lock:state.active_origin[rid]-=1
            state.log('origin-access',dict(row))

class Gateway(Handler):
    def do_HEAD(self):self.media(head=True)
    def do_GET(self):self.media(head=False)
    def do_POST(self):
        cfg=self.state.cfg
        if self.path!='/control' or not hmac.compare_digest(self.headers.get('X-Lab-Control',''),cfg['controlKey']):self.empty(403);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096:raise ValueError('control byte bound')
            data=unique_json(self.rfile.read(length));action=data.get('action')
            with self.state.lock:
                if action=='witness':result=self.state.witness(data['requestId'])
                elif action=='snapshot':result=self.state.snapshot(data['stage'])
                elif action=='allocator-dump':result=self.state.allocator_dump()
                elif action=='live-buffer-snapshot':
                    result=self.state.live_buffer_snapshot('live-measurement-'+str(self.state.live_snapshots),data['afterMonotonicNs'])
                elif action in ('grant-state','revoke-grant'):
                    matches=[(user,grant) for user,grant in self.state.grants.items() if grant.grant_id==data['grantId']]
                    if len(matches)!=1:raise ValueError('unknown grant')
                    user,grant=matches[0];observed=utc()
                    if action=='revoke-grant':
                        grant=grant.revoke(observed);self.state.grants[user]=grant
                    result=dict(action=action,observedAt=observed,grant=grant.observation(user,observed))
                elif action=='fault':
                    if data['mode'] not in ('none','truncate','unavailable','slow'):raise ValueError('fault mode')
                    self.state.fault=data['mode'];result=dict(action=action,mode=data['mode'],observedAt=utc())
                elif action=='version':
                    if data['version'] not in PINNED or self.state.gateway_active or any(self.state.active_origin.values()):raise ValueError('version/active requests')
                    before=self.state.version;self.state.version=data['version']
                    result=dict(action=action,before=before,after=self.state.version,observedAt=utc(),beforeSha256=cfg['inputs'][before]['sha256'],afterSha256=cfg['inputs'][self.state.version]['sha256'])
                elif action=='clear-cache':result=None
                else:raise ValueError('unknown control operation')
            if action=='clear-cache':result=self.state.clear_cache()
            self.state.log('controller',result);raw=json.dumps(result).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        except (ValueError,KeyError,OSError,RuntimeError) as error:
            self.state.log('controller',dict(action='control-error',at=utc(),errorType=type(error).__name__,error=str(error)));self.empty(409)
    def media(self,head):
        state=self.state;cfg=state.cfg;started=utc();rid=self.headers.get('X-Lab-Request-ID','')
        if not re.fullmatch(r'[a-f0-9]{32}',rid):self.empty(400);return
        case=self.headers.get('X-Lab-Case','')
        if self.path!='/media/object.bin' or case not in CASES|{'slice','prime','bypass','revocation'}:self.empty(404);return
        token=self.headers.get('Authorization','');user=next((u for u,key in cfg['users'].items() if hmac.compare_digest(token,'Bearer '+key)),None)
        with state.lock:
            version=state.version;state.gateway_active+=1
            state.gateway_active_peak=max(state.gateway_active_peak,state.gateway_active)
        row=dict(requestId=rid,case=case,startedAt=started,userId=user or 'unknown',sourceVersion=version,
          aclVersion=cfg['aclVersion'],requestRange=self.headers.get('Range',''),ifRange=self.headers.get('If-Range',''),
          atsRequestSent=False,responseByteCount=0,gatewayChunkPeak=0)
        with state.lock:state.gateway_rows.setdefault(rid,[]).append(row)
        connection=None;response=None;block=None
        try:
            # Denied cache HIT requests never contact ATS or open/read a source object.
            if user not in ('lab-user-a','lab-user-b'):
                row.update(statusCode=403,denialReason='acl_denied' if user else 'invalid_credentials');self.empty(403);return
            with state.lock:
                checked=utc();grant=state.grants[user];observation=grant.observation(user,checked)
            row['grantObservation']=observation
            if observation['reason']!='allowed':
                row.update(statusCode=403,denialReason=observation['reason']);self.empty(403);return
            path=f"/ctx/{context(cfg['aclVersion'],user)}/{version}/object.bin";row['cacheContextPath']=path
            # The governed immutable version already provides the exact length
            # and validator. Resolve an impossible interval here, before ATS can
            # substitute an HTML error body or an incomplete Content-Range.
            try:
                range_status,_,_=interval(self.headers.get('Range',''),cfg['inputs'][version]['sizeBytes'],
                                          self.headers.get('If-Range',''),cfg['inputs'][version]['etag'])
            except ValueError:
                row.update(statusCode=400,denialReason='unsupported_range');self.empty(400);return
            if range_status==416:
                row.update(statusCode=416,rangeResolution='unsatisfiable_against_governed_immutable_version',
                           transportCompleted=True,mediaTransferCompleted=False)
                self.send_response(416);self.send_header('Content-Length','0')
                self.send_header('Content-Range','bytes */'+str(cfg['inputs'][version]['sizeBytes']))
                self.send_header('ETag',cfg['inputs'][version]['etag'])
                self.send_header('X-Lab-Request-ID',rid);self.send_header('X-Lab-Source-Version',version)
                self.send_header('X-Lab-Cache-Context',context(cfg['aclVersion'],user))
                self.send_header('Connection','close');self.end_headers();self.close_connection=True;return
            expiry=int(time.time())+300
            headers={'Host':'ats.local','Accept-Encoding':'identity','Connection':'close','X-Lab-ATS-Key':cfg['secret'],
              'X-Lab-Request-ID':rid,'X-Lab-Origin-Expiry':str(expiry),'X-Lab-Origin-Signature':sign(cfg['secret'],path,rid,expiry)}
            # Evaluate the immutable version's validator before a warm Range lookup.
            # Slice/CRR may satisfy that lookup without contacting the origin.
            stale_if_range=bool(self.headers.get('If-Range') and self.headers['If-Range']!=cfg['inputs'][version]['etag'])
            for name in ('Range','If-Range'):
                if self.headers.get(name) and not stale_if_range:headers[name]=self.headers[name]
            connection=http.client.HTTPConnection('127.0.0.1',cfg['atsPort'],timeout=10)
            row['atsRequestSent']=True;connection.request('HEAD' if head else 'GET',path,headers=headers)
            response=connection.getresponse();row['statusCode']=response.status
            row.update(atsResponseHeadersAt=utc(),atsExpectedBodyBytes=response.length,upstreamReadTimeoutSeconds=10,transportCompleted=bool(head))
            self.send_response(response.status)
            for name in ('Content-Type','Content-Length','Content-Range','ETag','Accept-Ranges','Via','X-Lab-ATS-Cache','Last-Modified'):
                if response.getheader(name) is not None:self.send_header(name,response.getheader(name))
            self.send_header('X-Lab-Request-ID',rid);self.send_header('X-Lab-Source-Version',version)
            self.send_header('X-Lab-Cache-Context',context(cfg['aclVersion'],user));self.send_header('Connection','close');self.end_headers()
            if not head:
                while True:
                    try:
                        incomplete=False
                        try:block=response.read1(cfg['chunkBytes'])
                        except http.client.IncompleteRead as error:block=error.partial;incomplete=True
                        if block:
                            self.wfile.write(block);self.wfile.flush();row['responseByteCount']+=len(block);row['gatewayChunkPeak']=max(row['gatewayChunkPeak'],len(block))
                            if 'firstBodyChunkAt' not in row:row['firstBodyChunkAt']=utc()
                        if incomplete or not block:
                            row['transportCompleted']=not incomplete and response.length in (None,0)
                            if not row['transportCompleted']:row.update(atsIncompleteRead=True,transportError='IncompleteRead')
                            break
                    finally:block=None
            self.close_connection=True
        except (OSError,http.client.HTTPException) as error:
            row['transportError']=type(error).__name__;self.close_connection=True
            if response is not None and not head:row.update(atsIncompleteRead=True,transportCompleted=False)
            if 'statusCode' not in row:
                row['statusCode']=502
                try:self.empty(502)
                except OSError:pass
        finally:
            block=None
            if response is not None:response.close()
            if connection:connection.close()
            response=None;connection=None
            row['finishedAt']=utc()
            with state.lock:state.gateway_active-=1
            state.log('gateway-access',row)

def serve(run,*,ready_callback=None):
    # A reviewed in-process supervisor can start its client after singleton
    # owner setup without installing a Python tracing/profiling hook. The CLI
    # supplies no callback; this is not a configuration-selected capability.
    if ready_callback is not None and not callable(ready_callback):
        raise TypeError('readiness callback must be callable')
    state=State(run);cfg=state.cfg;servers=[];threads=[]
    # Bind explicitly only after this subcommand; port conflicts fail rather than reuse.
    try:
        if cfg.get('liveBufferObserver') is not None:
            from epoch_owner import EpochOwner
            state.epoch_owner=EpochOwner(state.run,cfg)
        state.ats_command(['-C','verify_config'],'verify-config')
        origin=Server(('127.0.0.1',cfg['originPort']),Origin,state);servers.append(origin)
        thread=threading.Thread(target=origin.serve_forever,daemon=True);thread.start();threads.append(thread)
        state.start_ats()
        gateway=Server(('127.0.0.1',cfg['entryPort']),Gateway,state);servers.append(gateway)
        thread=threading.Thread(target=gateway.serve_forever,daemon=True);thread.start();threads.append(thread)
        write_json(state.run/'listeners-started.json',dict(startedAt=utc(),controllerPid=os.getpid(),atsPid=state.ats.pid,
            bind='127.0.0.1',ports=[cfg[k] for k in ('originPort','atsPort','entryPort')],formalPocAccepted=False))
        print(json.dumps(dict(status='LAB_RUNNING_NOT_ACCEPTED',entryPort=cfg['entryPort'],runDir=str(state.run))),flush=True)
        if ready_callback is not None:ready_callback(state)
        while time.monotonic()-state.started<cfg['maximumRunSeconds']:
            if state.epoch_owner is not None:state.epoch_owner.check_alive()
            # clear_cache holds this lock across the owned stop/clear/start interval.
            # Never let an HTTP request holding the lock stop PID1's owner watch.
            if not state.lock.acquire(timeout=.05):continue
            try:
                child=state.ats
                if child is None or child.poll() is not None:raise RuntimeError('ATS child exited; raw retained')
                child_pid=child.pid
            finally:state.lock.release()
            try:
                status=Path('/proc')/str(child_pid)/'status'
                values={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status.read_text().splitlines() if line.startswith(('VmRSS:','VmHWM:'))}
                state.log('ats-process-memory',dict(observedAt=utc(),pid=child_pid,**values))
            except OSError:pass
            time.sleep(.05)
    except KeyboardInterrupt:pass
    finally:
        windows=[];closure_errors=[]
        for server in reversed(servers):
            try:
                server.shutdown();server.server_close();windows.append(server.close_request_window())
            except BaseException as error:
                closure_errors.append(dict(component='HTTP',errorType=type(error).__name__,error=str(error)))
        try:state.stop_ats()
        except BaseException as error:
            closure_errors.append(dict(component='ATS',errorType=type(error).__name__,error=str(error)))
        if state.epoch_owner is not None:
            try:state.epoch_owner.shutdown()
            except BaseException as error:
                closure_errors.append(dict(component='epoch-owner',errorType=type(error).__name__,error=str(error)))
        if closure_errors:
            write_json(state.run/'media-request-window-closure.failed.json',dict(closed=False,errors=closure_errors,httpWindows=windows))
            state.log('controller',dict(action='lab-stop',at=utc(),requestWindowClosed=False))
            raise RuntimeError('lab request window closure failed; actual records retained')
        state.close_media_window(windows)
        state.log('controller',dict(action='lab-stop',at=utc(),requestWindowClosed=True))

def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('selfcheck')
    command=commands.add_parser('prepare');command.add_argument('--config',default=str(HERE/'config.example.json'));command.add_argument('--run-dir',required=True)
    command=commands.add_parser('serve');command.add_argument('--run-dir',required=True)
    args=parser.parse_args()
    if args.command=='selfcheck':print(json.dumps(selfcheck()))
    elif args.command=='prepare':print(json.dumps(prepare(args.config,args.run_dir)))
    else:serve(args.run_dir)
if __name__=='__main__':main()

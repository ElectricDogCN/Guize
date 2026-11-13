"""Prospective v2 hook-free small-fragment control; initializes request recording before the client."""
from pathlib import Path
import hashlib
import http.client
import json
import os
import signal
import stat
import sys
import threading
import time

RUN=Path('/runlab/work')
LAB_FILE=Path('/poc/source/poc/POC-03-ats-range/lab.py')
REPORT=Path('/runlab/compatibility-client.json')
START_NS=time.time_ns()
record={'kind':'PRIVATE_PID1_HOOK_FREE_SMALL_FRAGMENT_RUNTIME_CONTROL_ONLY',
        'pid':os.getpid(),'uid':os.getuid(),'checkpointObserved':False,'clientCompleted':False,'clientSuccessful':False,
        'scenarioOutcomesAssessed':False,'formalActorBindingAccepted':False,'fullMediaAccepted':False,'untracedLatencyAccepted':False,'formalPocAccepted':False}
record['requests']=[]
client_thread=None


def save():
    # This is this method's current progress, not a fabricated source/owner wait.
    raw=(json.dumps(record,indent=2)+'\n').encode()
    fd=os.open(REPORT,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw)


def ordinary_init():
    if (os.getpid()!=1 or os.getuid()!=1000 or os.geteuid()!=1000
            or threading.get_native_id()!=os.getpid() or len(list(Path('/proc/self/task').iterdir()))!=1):
        raise ValueError('private singleton ordinaryUID1000 PID1 required')
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if status.get('Seccomp','').strip()!='2':raise ValueError('actual initial engine seccomp filter required')
    record['initialSecurityStatus']={k:status.get(k,'').strip() for k in ('NoNewPrivs','Seccomp','Seccomp_filters','CapEff','CapBnd')}
    if status['NoNewPrivs'].strip()!='1' or any(int(status[k].strip(),16) for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')):
        raise ValueError('no capabilities and NNP required')
    if any(os.environ.get(k) for k in ('LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT')):
        raise ValueError('image Python must not inherit target library injection')
    if sys.getprofile() is not None or sys.gettrace() is not None:
        raise ValueError('do not replace an unrelated tracing/profiling hook')
    if signal.getsignal(signal.SIGINT) is not signal.default_int_handler:
        raise ValueError('actual Python selfSIGINT handler required')


def client(state):
    deadline=time.monotonic()+180
    actions=[{'action':'snapshot','stage':'compatibility-before'},
             {'action':'live-buffer-snapshot','afterMonotonicNs':0},
             {'action':'allocator-dump'},{'action':'clear-cache'},
             {'action':'snapshot','stage':'compatibility-after'},
             {'action':'live-buffer-snapshot','afterMonotonicNs':0},{'action':'allocator-dump'}]
    snapshots=[]
    try:
        if any(hook is not None for hook in (sys.getprofile(),sys.gettrace(),threading.getprofile(),threading.gettrace())):
            raise ValueError("compatibility client must have no profiling/tracing hooks")
        for index,body in enumerate(actions):
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('finite client deadline')
            conn=http.client.HTTPConnection('127.0.0.1',18233,timeout=min(90,remaining))
            request=json.dumps(body,separators=(',',':')).encode();assert len(request)<=4096
            row={'ordinal':index,'action':body['action'],'startedMonotonicNs':time.monotonic_ns()}
            response=None
            try:
                # The private key is deliberately neither recorded nor printed.
                conn.request('POST','/control',body=request,headers={'X-Lab-Control':state.cfg['controlKey'],'Content-Type':'application/json','Connection':'close'})
                response=conn.getresponse();raw=response.read(4*1024*1024+1)
                row.update(statusCode=response.status,responseBytes=len(raw),responseSha256=hashlib.sha256(raw).hexdigest())
                if len(raw)>4*1024*1024:raise ValueError('control response bound')
                path=Path('/runlab')/('control-response-'+str(index)+'.json')
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC,0o600)
                with os.fdopen(fd,'wb') as stream:stream.write(raw)
                row['responseRef']=str(path)
                if response.status!=200:raise ValueError('actual control rejected: '+str(response.status))
                value=lab.unique_json(raw)
                if type(value) is not dict:raise ValueError('control object required')
                if body['action']=='snapshot':
                    if value.get('stage')!=body['stage'] or value.get('atsPid')!=state.ats.pid:raise ValueError('snapshot current target mismatch')
                    ready=value.get('nativeCacheReady') or {}
                    if ready.get('cacheReady') is not True or ready.get('httpCacheReady') is not True or ready.get('atsPid')!=state.ats.pid:
                        raise ValueError('real cache readiness required')
                    snapshots.append({'pid':value['atsPid'],'birth':dict(state.ats.description['birth'])})
                elif value.get('action')!=('cache-cleared-by-owned-ATS-command' if body['action']=='clear-cache' else body['action']):
                    raise ValueError('wrong control response action')
            finally:
                if response is not None:response.close()
                conn.close();row['finishedMonotonicNs']=time.monotonic_ns();record['requests'].append(row);save()
        if len(snapshots)!=2 or snapshots[0]['birth']==snapshots[1]['birth']:raise ValueError('real owned restart required')
        record.update(clientSuccessful=True,actualTargetSnapshots=snapshots)
    except BaseException as error:
        record.update(clientErrorType=type(error).__name__,clientError=str(error)[:512])
    finally:
        record.update(clientCompleted=True,selfSigintRequested=True,selfSigintTargetPid=os.getpid(),selfSigintAtMonotonicNs=time.monotonic_ns());save()
        # Only this exact private PID1 receives the signal, after responses close.
        os.kill(os.getpid(),signal.SIGINT)


def ready_callback(state):
    global client_thread
    if record['checkpointObserved'] or client_thread is not None:raise ValueError('duplicate compatibility checkpoint')
    if threading.get_native_id()!=os.getpid():raise ValueError('actual controller main-thread readiness required')
    if any(hook is not None for hook in (sys.getprofile(),sys.gettrace(),threading.getprofile(),threading.gettrace())):
        raise ValueError('readiness must remain free of profiling/tracing hooks')
    cfg=state.cfg
    marker=RUN/'listeners-started.json'
    fd=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());raw=stream.read(4097);after=os.fstat(stream.fileno())
    if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode)!=0o600 or before.st_uid!=1000 or before.st_nlink!=1
            or not 0<len(raw)<=4096 or before.st_mtime_ns<START_NS
            or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
        raise ValueError('fresh bounded private readiness artifact required')
    value=lab.unique_json(raw)
    if (set(value)!={'startedAt','controllerPid','atsPid','bind','ports','formalPocAccepted'}
            or value['controllerPid']!=os.getpid() or value['atsPid']!=state.ats.pid or value['bind']!='127.0.0.1'
            or value['ports']!=[18231,18232,18233] or value['formalPocAccepted'] is not False
            or cfg['runDir']!=str(RUN) or state.epoch_owner is None):
        raise ValueError('actual listeners/owner/State/PID binding required')
    record.update(checkpointObserved=True,checkpointMonotonicNs=time.monotonic_ns(),actualListeners=value,hookKind='explicit pinned serve readiness callback; no tracing or profiling installed')
    record['profileAbsentBeforeClient']=sys.getprofile() is None and sys.gettrace() is None
    save();client_thread=threading.Thread(target=client,args=(state,),name='small-fragment-control-client',daemon=True);client_thread.start()


def main():
    global lab
    ordinary_init();assert not RUN.exists() and not (RUN/'listeners-started.json').exists()
    if hashlib.sha256(LAB_FILE.read_bytes()).hexdigest()!='cc302d0c255f3950f51df990f4762acc7aa863a5661449daf980efb475b968c5':raise ValueError('exact current readiness lab required')
    sys.path.insert(0,str(LAB_FILE.parent));import lab as module;lab=module
    lab.prepare('/configuration/config.json',str(RUN));ordinary_init();save()
    try:
        lab.serve(str(RUN),ready_callback=ready_callback);record['serveReturnedNormally']=True
    except BaseException as error:
        record.update(serveReturnedNormally=False,serveErrorType=type(error).__name__,serveError=str(error)[:512])
    finally:
        if client_thread is not None:client_thread.join(timeout=10)
        record['clientThreadStopped']=client_thread is not None and not client_thread.is_alive();save()
    passed=all(record.get(k) is True for k in ('checkpointObserved','profileAbsentBeforeClient','clientCompleted','clientSuccessful','serveReturnedNormally','clientThreadStopped'))
    print(json.dumps({'compatibilityClientPassed':passed,'formalPocAccepted':False}),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()

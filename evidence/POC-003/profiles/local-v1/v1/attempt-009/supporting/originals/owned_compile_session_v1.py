"""Close one ordinary compiler session while its original leader stays unreaped."""
import os
from pathlib import Path
import signal
import subprocess
import time


def process(pid):
    try:
        path=Path('/proc')/str(pid)
        fields=(path/'stat').read_text().rsplit(') ',1)[1].split()
        return dict(pid=pid,uid=path.stat().st_uid,state=fields[0],ppid=int(fields[1]),
                    pgid=int(fields[2]),sid=int(fields[3]),birth=int(fields[19]))
    except (FileNotFoundError,ProcessLookupError):
        return None


def run_owned_session(argv, stdout, stderr, timeout_seconds, *, term_grace=2, kill_grace=5, update=None):
    assert os.getuid()==1000 and timeout_seconds>0
    child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
    anchor=process(child.pid)
    assert anchor and anchor['uid']==1000 and anchor['pgid']==anchor['sid']==child.pid
    result=dict(pid=child.pid,anchor=anchor,actualWaitCompleted=False,exitCode=None,
                timedOut=False,signals=[],observedMembers=[],noLiveOwnedMembers=False)
    publish=lambda:update(dict(result)) if update else None
    publish()

    def live_members():
        # WNOWAIT retains this exact leader (including its zombie) until all
        # signaling finishes, preventing numeric PGID/SID reuse in the interval.
        held=process(child.pid)
        assert held and all(held[k]==anchor[k] for k in ('pid','uid','pgid','sid','birth'))
        live=[]
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():continue
            member=process(int(path.name))
            if member and member['pgid']==anchor['pgid'] and member['sid']==anchor['sid']:
                assert member['uid']==1000 and member['birth']>=anchor['birth']
                if member['state'] not in {'Z','X'}:live.append(member)
        for member in live:
            if member not in result['observedMembers']:result['observedMembers'].append(member)
        return live

    deadline=time.monotonic()+timeout_seconds
    observed=None
    while observed is None:
        observed=os.waitid(os.P_PID,child.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
        if observed is not None:break
        if time.monotonic()>=deadline:
            result['timedOut']=True;break
        time.sleep(0.05)
    result['leaderExitObservedWithoutReap']=None if observed is None else dict(code=observed.si_code,status=observed.si_status,pid=observed.si_pid)
    publish()
    # Covers success with leaked children, an early inner90s compiler failure,
    # and an outer timeout. Reaping the leader is deliberately last in all cases.
    for sig,grace in [(signal.SIGTERM,term_grace),(signal.SIGKILL,kill_grace)]:
        live=live_members()
        if not live:break
        os.killpg(anchor['pgid'],sig)
        result['signals'].append(dict(signal=int(sig),members=live));publish()
        until=time.monotonic()+grace
        while live_members() and time.monotonic()<until:time.sleep(0.05)
    remaining=live_members()
    result['remainingLiveMembers']=remaining
    result['noLiveOwnedMembers']=not remaining;publish()
    if remaining:
        # Never report success or signal a recycled group after losing anchor.
        raise RuntimeError('Owned compiler session still has live members after KILL')
    code=child.wait(timeout=5)
    result.update(actualWaitCompleted=True,exitCode=code,leaderReapedAfterGroupClosure=True)
    publish()
    return result

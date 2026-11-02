"""Linux-only real filesystem rejection regression; no ATS or media workload."""
from pathlib import Path
import argparse, json, os, select, subprocess, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import durable_peak_probe as probe
from buffer_probe import process_identity

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    assert os.name=='posix' and os.geteuid()!=0
    out=Path(args.out);out.mkdir(mode=0o700)
    child=subprocess.Popen([sys.executable,'-B','-c',
        "import sys; print('READY',flush=True); sys.stdin.readline()"],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    results=[]
    try:
        assert select.select([child.stdout],[],[],5)[0]
        assert child.stdout.readline()==b'READY\n'
        identity=process_identity(child)
        name='peak-'+str(child.pid)+'-'+str(identity['startTicks'])+'.jsonl'
        fifo=out/'fifo';fifo.mkdir(mode=0o700);os.mkfifo(fifo/name,0o600)
        start=time.monotonic()
        try:probe.capture_peak_journal(child,fifo,out/'fifo-capture',identity)
        except ValueError as error:
            assert 'private single-link' in str(error)
        else:raise AssertionError('FIFO accepted')
        elapsed=time.monotonic()-start;assert elapsed<2
        assert (out/'fifo-capture/durable-peaks.raw').read_bytes()==b''
        results.append(dict(scenario='real-fifo-no-writer',rejected=True,seconds=elapsed))
        for phase in ('before','during'):
            folder=out/phase;folder.mkdir(mode=0o700)
            path=folder/name;path.write_bytes(b'original\n');path.chmod(0o600)
            replacement=folder/'replacement';replacement.write_bytes(b'replacement\n');replacement.chmod(0o600)
            original_open=probe.os.open;original_fdopen=probe.os.fdopen
            def replaced_open(target,flags,*rest):
                fd=original_open(target,flags,*rest)
                if Path(target)==path and phase=='before':os.replace(replacement,path)
                return fd
            class ReplacedRead:
                def __init__(self,stream):self.stream=stream
                def __enter__(self):self.stream.__enter__();return self
                def __exit__(self,*args):return self.stream.__exit__(*args)
                def fileno(self):return self.stream.fileno()
                def read(self,count):
                    raw=self.stream.read(count);os.replace(replacement,path);return raw
            def replaced_fdopen(fd,*rest):return ReplacedRead(original_fdopen(fd,*rest))
            probe.os.open=replaced_open
            if phase=='during':probe.os.fdopen=replaced_fdopen
            try:
                try:probe.capture_peak_journal(child,folder,out/(phase+'-capture'),identity)
                except ValueError as error:
                    assert 'path replaced' in str(error) or 'private single-link' in str(error)
                else:raise AssertionError('replacement accepted')
            finally:probe.os.open=original_open;probe.os.fdopen=original_fdopen
            results.append(dict(scenario='actual-path-replacement-'+phase,rejected=True))
        child.stdin.write(b'EXIT\n');child.stdin.flush();child.stdin.close()
        assert child.wait(timeout=5)==0
        print(json.dumps(dict(scenarios=results,childPid=child.pid,exitCode=child.returncode,
                              waitCompleted=True,atsExecuted=False)),flush=True)
    finally:
        if child.poll() is None:child.kill();child.wait()

if __name__=='__main__':main()

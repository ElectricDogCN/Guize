"""Build the private live-buffer observer without starting any ATS process."""
import argparse,hashlib,json,os,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args();sdk=Path(args.include).resolve();out=Path(args.out).absolute()
    if os.name!='posix' or os.geteuid()==0 or out.exists() or out.is_symlink():
        raise ValueError('ordinary Linux user and a new private output directory required')
    compiler=shutil.which('g++');assert compiler
    here=Path(__file__).resolve().parent;source=here/'live_buffer_observer.cc';header=here/'live_buffer_accounting.h'
    headers={name:sha(sdk/'ts'/name) for name in ['ts.h','experimental.h','apidefs.h']}
    out.mkdir(mode=0o700);plugin=out/'live_buffer_observer.so'
    argv=[compiler,'-std=c++17','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror','-pthread',
          '-I'+str(sdk),'-DGUIZE_LIVE_HEADER_SHA256="'+sha(header)+'"',
          '-DGUIZE_LIVE_OBSERVER_SHA256="'+sha(source)+'"',str(source),'-ldl','-o',str(plugin)]
    started=datetime.now(timezone.utc).isoformat()
    with (out/'stdout.raw').open('xb') as stdout,(out/'stderr.raw').open('xb') as stderr:
        result=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=90)
    receipt=dict(kind='TASK_OWNED_LIVE_BUFFER_OBSERVER_BUILD',startedAt=started,finishedAt=datetime.now(timezone.utc).isoformat(),
                 argv=argv,compiler=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
                 sourceSha256=sha(source),ledgerHeaderSha256=sha(header),sdkHeaderSha256=headers,
                 exitCode=result.returncode,pluginSha256=sha(plugin) if plugin.exists() else None,
                 atsStarted=False,experimentApproved=False,fullMediaCoverageProven=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
    raise SystemExit(result.returncode)

if __name__=='__main__':main()

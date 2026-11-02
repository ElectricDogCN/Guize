"""Compile the task-owned observer against the pinned external ATS 9.2.3 SDK."""
import argparse,hashlib,json,os,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--include',required=True,help='Actual SDK usr/include directory')
    p.add_argument('--out',required=True,help='New private output directory')
    a=p.parse_args();sdk=Path(a.include).resolve();out=Path(a.out).absolute()
    if os.name!='posix' or os.geteuid()==0 or out.exists() or out.is_symlink():
        raise ValueError('ordinary Linux user and new private build output required')
    compiler=shutil.which('g++')
    if not compiler:raise ValueError('actual C++ compiler required')
    headers={name:sha(sdk/'ts'/name) for name in ['ts.h','experimental.h','apidefs.h']}
    source=Path(__file__).resolve().with_name('cache_export.cc')
    out.mkdir(mode=0o700);plugin=out/'cache_export.so'
    argv=[compiler,'-std=c++17','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror',
          '-pthread','-I'+str(sdk),str(source),'-o',str(plugin)]
    started=datetime.now(timezone.utc).isoformat()
    with (out/'stdout.raw').open('xb') as stdout,(out/'stderr.raw').open('xb') as stderr:
        result=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=90)
    version=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0]
    receipt=dict(kind='TASK_OWNED_CACHE_OBSERVER_BUILD',startedAt=started,
                 finishedAt=datetime.now(timezone.utc).isoformat(),argv=argv,
                 compiler=version,sourceSha256=sha(source),sdkHeaderSha256=headers,
                 exitCode=result.returncode,pluginSha256=sha(plugin) if plugin.exists() else None,
                 runtimeExecuted=False,experimentAccepted=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt));raise SystemExit(result.returncode)


if __name__=='__main__':main()

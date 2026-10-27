"""Run the complete frozen execution validator in an actual clean tracked context."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve(strict=True)
    out=args.output_dir.resolve()
    if out.is_relative_to(root):
        raise ValueError('Validation output must stay outside the immutable Git validation context')
    git=lambda *a:subprocess.check_output(['git','-c','core.longpaths=true','-c','core.autocrlf=false','-C',str(root),*a],text=True).strip()
    before=dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),status=git('status','--porcelain=v1','--untracked-files=all'))
    if before['status']:
        raise ValueError('Clean tracked validation context required')
    prefix='evidence/POC-005/profiles/local-v1/v1'
    execution_ref=prefix+'/attempt-010/execution-candidate.json'
    load=lambda ref:yaml.safe_load((root/ref).read_text(encoding='utf-8'))
    execution=load(execution_ref)
    tested=execution['environmentCaptured']['testedSource']
    subprocess.run(['git','-c','core.longpaths=true','-C',str(root),'merge-base','--is-ancestor',tested['commit'],before['head']],check=True)
    plan=load('specs/poc/plans/POC-005.yaml')
    task=yaml.safe_load((root/'specs/tasks/POC-005.md').read_text(encoding='utf-8').split('---',2)[1])
    resources={r['id']:r for r in load('specs/poc/resources.yaml')['resources']}
    checker_path=root/'specs/poc/check_program.py'
    spec=importlib.util.spec_from_file_location('actual_frozen_poc005_full_execution',checker_path)
    checker=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    definitions=load('specs/poc/program.schema.yaml')['$defs']
    out.mkdir()
    errors=[]
    raw_path=out/'full-execution-validation.raw'
    started=datetime.now(timezone.utc).isoformat()
    with raw_path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('Validation Context Commit: '+before['head']+'\nTested Runtime Commit: '+tested['commit']+'\nCommand: '+subprocess.list2cmdline([sys.executable,*sys.argv])+'\n')
        stream.flush()
        with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
            checker.validate_execution(root,plan,task['implementer'],execution,resources,
                load('specs/poc/execution-record.schema.yaml'),load('specs/poc/sample-approval.schema.yaml'),
                'pass',errors,load('specs/poc/compliance-review.schema.yaml'),prefix,definitions,task['reviewer'],{execution_ref})
        for error in errors: stream.write(str(error)+'\n')
        code=1 if errors else 0
        stream.write('Exit Code: '+str(code)+'\n')
    after=dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),status=git('status','--porcelain=v1','--untracked-files=all'))
    if before!=after:
        raise ValueError('Frozen validation mutated its Git context')
    raw=raw_path.read_bytes()
    result=dict(kind='actual_complete_frozen_execution_validation',sourceRuntime=tested,validationContext=before,
        sourceContextUnchanged=True,executionRef=execution_ref,checkerSha256=hashlib.sha256(checker_path.read_bytes()).hexdigest(),
        validator='validate_execution complete call chain, status=pass',startedAt=started,finishedAt=datetime.now(timezone.utc).isoformat(),
        exitCode=code,errors=errors,status='full_execution_validation_passed' if not errors else 'rejected',
        raw=raw_path.name,rawBytes=len(raw),rawSha256=hashlib.sha256(raw).hexdigest(),independentResultAccepted=False,
        profileTerminalIndexAccepted=False,scale1mAccepted=False,taskCompleted=False,v1Completed=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=result['status'],exitCode=code,errorCount=len(errors),firstErrors=errors[:5],sourceContextUnchanged=True,taskCompleted=False)))
    raise SystemExit(code)


if __name__=='__main__':
    main()

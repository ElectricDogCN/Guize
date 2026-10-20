"""Read-only ordinary GZ-021 Completion envelope; central history/lifecycle gates remain required.

Rules: task-template.md:181-205; check-program-plan-history.py:399-458;
check-program-lifecycle-guards.py:310-315. GZ-021 is in tasks, not foundationTasks.
"""
import argparse, copy, json, os, re, subprocess
from pathlib import Path
import yaml

TASK_ID='GZ-021'
PLAN='specs/coordination/program-plan.yaml'
ACTIVE='specs/coordination/active-work.yaml'
TASK='specs/tasks/GZ-021.md'
LEDGER='specs/coordination/task-completions.yaml'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','base','source','tree','parent','branch','reservation-ref','reservation-commit','implementation-ref','implementation-merge'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    assert all(re.fullmatch('[0-9a-f]{40}',value) for value in (args.base,args.source,args.tree,args.parent,args.reservation_commit,args.implementation_merge))
    assert args.parent==args.base and args.source!=args.base
    assert all(re.fullmatch('PR-[1-9][0-9]*',value) for value in (args.reservation_ref,args.implementation_ref)) and args.reservation_ref!=args.implementation_ref
    assert args.branch.startswith('chore/GZ-021-')
    root=Path(args.repo);assert root.is_absolute();root=root.resolve()
    def git(*values):
        return subprocess.check_output(['git','-C',str(root),*values],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    def text(*values):return git(*values).decode('utf8').strip()
    def raw(ref,path):return git('show',ref+':'+path)
    def doc(ref,path):return yaml.safe_load(raw(ref,path))
    git('check-ref-format','--branch',args.branch)
    assert text('rev-parse','HEAD')==args.source and text('rev-parse','HEAD^{tree}')==args.tree and text('branch','--show-current')==args.branch
    assert text('show','-s','--format=%P',args.source)==args.parent
    for commit in (args.base,args.reservation_commit,args.implementation_merge):assert text('rev-parse','--verify',commit+'^{commit}')==commit
    assert args.reservation_commit!=args.implementation_merge
    git('merge-base','--is-ancestor',args.reservation_commit,args.implementation_merge)
    git('merge-base','--is-ancestor',args.implementation_merge,args.base)
    changed=text('diff','--no-renames','--name-only',args.base,args.source).splitlines()
    allowed={PLAN,ACTIVE,TASK,LEDGER}
    assert allowed.issubset(changed) and all(path in allowed or path.startswith('evidence/GZ-021/') for path in changed)
    expected=doc(args.base,PLAN)
    assert not any(row.get('taskId')==TASK_ID for row in expected.get('foundationTasks',[]))
    own=[row for row in expected['tasks'] if row['taskId']==TASK_ID];assert len(own)==1 and own[0]['status'] in ('review','integration')
    prior_status=own[0]['status'];own[0]['status']='completed';assert doc(args.source,PLAN)==expected
    expected=doc(args.base,ACTIVE);own=[row for row in expected['tasks'] if row['taskId']==TASK_ID]
    assert len(own)==1 and own[0]['status']==prior_status and own[0]['agentRole']=={'review':'reviewer','integration':'integrator'}[prior_status]
    claims=copy.deepcopy(own[0]['exclusivePaths']);assert len(claims)==46
    expected['tasks']=[row for row in expected['tasks'] if row['taskId']!=TASK_ID];assert doc(args.source,ACTIVE)==expected
    before=raw(args.base,TASK).decode('utf8');after=raw(args.source,TASK).decode('utf8')
    assert before.startswith('---\n') and after.startswith('---\n')
    front=yaml.safe_load(before.split('---',2)[1]);assert front['id']==TASK_ID and front['status']==prior_status
    front.update(status='completed',baseSha=args.base,workBranch=args.branch,agentRole='integrator')
    assert yaml.safe_load(after.split('---',2)[1])==front
    expected=doc(args.base,LEDGER);assert not any(row['taskId']==TASK_ID for row in expected['records'])
    record=dict(taskId=TASK_ID,reservationRef=args.reservation_ref,reservationCommit=args.reservation_commit,completionRef=args.implementation_ref,
        mergeCommit=args.implementation_merge,taskSpec=TASK,evidencePath='evidence/GZ-021',handoffPath='evidence/GZ-021/handoff.md')
    expected['records'].append(record);assert doc(args.source,LEDGER)==expected
    assert raw(args.source,LEDGER).startswith(raw(args.base,LEDGER))
    for path in claims:
        if path not in allowed and not path.startswith('evidence/GZ-021/'):assert raw(args.base,path)==raw(args.source,path)
    for path in ('evidence/GZ-021/planning-revision.json','tests/governance/test_repository_boundary.py'):
        assert raw(args.base,path)==raw(args.source,path)
    print(json.dumps(dict(source=args.source,tree=args.tree,base=args.base,parent=args.parent,branch=args.branch,result='PASS',scopeStage='completion',
        ordinaryTask=True,ownCompletionMetadataOnly=True,ownLeaseRemovedOnly=True,oldLedgerPrefixUnchanged=True,appendedRecord=record,
        codeAndClaimsUnchanged=True,originalManifestAndPoliciesUnchanged=True,changedPaths=changed,centralHistoryAndLifecycleStillRequired=True,fullV1Complete=False)))
    return 0


if __name__=='__main__':raise SystemExit(main())

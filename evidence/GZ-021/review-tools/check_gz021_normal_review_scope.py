"""Only own legal review metadata plus exact raw evidence may differ."""
import subprocess,sys,json,yaml,copy
root,base,head=sys.argv[1:]
def git(*args):return subprocess.check_output(['git','-C',root,*args])
def raw(ref,path):return git('show',ref+':'+path)
def doc(ref,path):return yaml.safe_load(raw(ref,path))
changed=git('diff','--name-only',base,head).decode().splitlines()
allowed={'specs/coordination/program-plan.yaml','specs/coordination/active-work.yaml','specs/tasks/GZ-021.md'}
assert changed and all(p in allowed or p.startswith('evidence/GZ-021/') for p in changed)
plan='specs/coordination/program-plan.yaml';expected=doc(base,plan)
row=next(r for r in expected['tasks'] if r['taskId']=='GZ-021');assert row['status']=='in_progress';row['status']='review'
assert doc(head,plan)==expected
active='specs/coordination/active-work.yaml';expected=doc(base,active)
row=next(r for r in expected['tasks'] if r['taskId']=='GZ-021');assert row['status']=='in_progress' and row['agentRole']=='implementer'
claims=copy.deepcopy(row['exclusivePaths']);assert len(claims)==46
row.update(status='review',agentRole='reviewer',baseSha=base)
assert doc(head,active)==expected
for path in claims:
    if path!=plan:assert raw(base,path)==raw(head,path)
for path in ['evidence/GZ-021/planning-revision.json','specs/coordination/task-completions.yaml','tests/governance/test_repository_boundary.py']:
    assert raw(base,path)==raw(head,path)
print(json.dumps({'source':head,'base':base,'result':'PASS','ownReviewMetadataOnly':True,'codeAndClaimsUnchanged':True,'originalManifestLedgerAndPolicyUnchanged':True,'changedPaths':changed}))

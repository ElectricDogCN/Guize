"""Read-only input-shape inventory for future design; no validation/permission grant."""
from pathlib import Path
import json,subprocess
from datetime import datetime,timezone
T=Path(__file__).resolve().parent;c=json.loads((T/'ops021-reservation-v1-current-candidate.json').read_bytes());R=Path(c['author'])
def git(*args):return subprocess.check_output(['git','-c','core.longpaths=true','-C',str(R),*args]).decode('utf-8')
before=dict(head=git('rev-parse','HEAD'),refs=git('for-each-ref','--format=%(refname) %(objectname)'),status=git('status','--porcelain=v1','--untracked-files=all'))
assert before['head'].strip()==c['source'] and not before['status']
nodes=git('rev-list','--full-history','--reverse','251fac61809ed4b209c4fc7a71dee41ba4061db6..'+c['base'],'--','specs/tasks/OPS-020.md').splitlines()
rows=[]
for task,commits in [('OPS-020',nodes),('OPS-021',[c['source']])]:
    for commit in commits:
        path='specs/tasks/'+task+'.md';raw=git('show',commit+':'+path)
        front={}
        for line in raw.split('---',2)[1].splitlines():
            if ':' in line:
                key,value=line.split(':',1);front[key.strip()]=value.strip()
        paths=[path,'evidence/'+task+'/handoff.md','specs/coordination/program-plan.yaml','specs/coordination/active-work.yaml']
        modes={}
        for line in git('ls-tree',commit,'--',*paths).splitlines():
            meta,name=line.split('\t',1);modes[name]=meta.split()[0]
        row=dict(task=task,commit=commit,id=front.get('id'),evidencePath=front.get('evidencePath'),handoffPath=front.get('handoffPath'),modes=modes)
        row['canonicalRegularMetadataShape']=front.get('id')==task and front.get('evidencePath')=='evidence/'+task and front.get('handoffPath')=='evidence/'+task+'/handoff.md' and set(modes)==set(paths) and set(modes.values())=={'100644'}
        rows.append(row)
after=dict(head=git('rev-parse','HEAD'),refs=git('for-each-ref','--format=%(refname) %(objectname)'),status=git('status','--porcelain=v1','--untracked-files=all'))
assert before==after and rows and all(r['canonicalRegularMetadataShape'] for r in rows)
result=dict(kind='READONLY_HISTORICAL_INPUT_SHAPES_ONLY',source=c['source'],base=c['base'],observedAt=datetime.now(timezone.utc).isoformat(),rows=rows,contextUnchanged=True,productionChanged=False,testsRun=False,implementationAllowed=False,note='This inventory supports future bounded OPS020/OPS021 metadata materialization design. It neither validates arbitrary future snapshots nor replaces cold negative equivalence tests or normal registration acceptance. Unproven task IDs/shapes retain the original dense path.')
with (T/'ops021-historical-metadata-input-shapes-readonly.json').open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(historicalSnapshots=len(rows),canonicalRegularShapes=True,contextUnchanged=True,testsRun=False,implementationAllowed=False)))

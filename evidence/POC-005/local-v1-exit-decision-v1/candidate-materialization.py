"""Transcribe the actual independent local exit decision; do not approve or test it."""
from pathlib import Path
import hashlib
import json
import subprocess
import yaml
import jsonschema

ROOT=Path(__file__).resolve().parent
REPO=ROOT/'poc005-thaw-integration'
PARENT='77d99effc1a0e1524dcf1795d1c0aff359ab219c'
PREFIX='evidence/POC-005/profiles/local-v1/v1'
DECISION='evidence/POC-005/local-v1-exit-decision-v1'


def main():
    git=lambda *a:subprocess.check_output(['git','-c','core.longpaths=true','-C',str(REPO),*a]).decode().strip()
    assert git('rev-parse','HEAD')==PARENT and not git('diff','--name-only') and not git('diff','--cached','--name-only')
    approval_raw=(ROOT/'poc005-local-v1-scale-exit-independent-assessment.json').read_bytes()
    assert hashlib.sha256(approval_raw).hexdigest()=='7f39fc6a341a8ae4d4661a3d41ee27a98c7cc46e5d65cb8d6e7cfbaa06efc704'
    assessment=json.loads(approval_raw)
    assert assessment['localExitDecisionApproved'] and not assessment['mustFix']
    result=assessment['approvedResultRecordFields']
    assert result['approvedAt']=='2026-10-27T05:18:53Z' and result['reviewer']=='independent-review-agent'
    for k in ('report','databaseSnapshot','archive'):
        r=assessment[k];raw=(REPO/r['ref']).read_bytes()
        assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
    index={'schemaVersion':2,'pocId':'POC-05','pocTaskId':'POC-005','ownerTask':'POC-005',
           'acceptanceProfile':{'id':'local-v1','version':1,'bindingRevision':1,'scope':'LOCAL_FULL_V1'},
           'resultRef':PREFIX+'/result.json'}
    load=lambda p:yaml.safe_load((REPO/p).read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(load('specs/poc/result-record.schema.yaml')).validate(result)
    jsonschema.Draft202012Validator(load('specs/poc/program.schema.yaml')['$defs']['profileEvidenceIndex']).validate(index)
    decision_dir=REPO/DECISION;decision_dir.mkdir()
    (decision_dir/'.gitattributes').write_bytes(b'* -text whitespace=cr-at-eol\n')
    (decision_dir/'independent-assessment.json').write_bytes(approval_raw)
    for source,name in ((ROOT/'prepare_poc005_local_profile_exit_report_v1.py','report-preparation.py'),(Path(__file__),'candidate-materialization.py')):
        (decision_dir/name).write_bytes(source.read_bytes())
    for target,value in ((REPO/PREFIX/'result.json',result),(REPO/PREFIX/'index.yaml',index)):
        with target.open('x',encoding='utf-8',newline='\n') as out:
            out.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    summary='''## Current local-v1 exit decision; formal profile validation pending

The actual independent local exit decision is pass/approved at2026-10-27T05:18:53Z, retained byte-exact in local-v1-exit-decision-v1/independent-assessment.json. The source-labelled report local-v1-scale-exit-report.md covers the five frozen criteria and all13 observations, two full source traversals, complete population/fanout/depth/name distributions, deterministic changes, fault/quota/Range/ETag facts, limitations and actual cleanup/retention. Only actualed8/010 is the terminal primary execution. Original8f/00810k andc98/009100k remain supporting qualifications on their own sources/contexts.

The exacted8 source was independently accepted after Task15/CI868752. Actual010 supervisor/controller/scanner and complete frozen execution validator48531 ended0; independent2f608b79 accepts1m execution qualification. Actual11277-path context77d was ordinarily FF imported into this author;45 original qualification/source/CI/cleanup/analysis records are recoverable in qualified-local-1m-attempt010-v1/index.json. All4171 previous untracked paths,10 runtimeDBs and three controlled mutations remain; the private provider was actually forced-stopped with wait/exit3221225786 and native listener verification, not naturally exited or restored. Runtime databases logical3169824768B are separate from578041112B selected raw and scanner31.12109375MiB.

The formal index/result candidate transcribes that real independent opinion/time; the full --profile local-v1 --require-results --poc POC-05 command is NOT YET RUN on this new candidate. Source/schema/code/thresholds and prior approvals remain unchanged. This new metadata candidate needs its own final Task checks/CI/review, actual-main integration and normal Review/Completion. PR136 remains Draft/remoteed8 until an actual publication; noReady/merge/task/production/V1 completion is claimed. Next integrator freezes the exact candidate in a clean compatible tracked context and runs the mandatory full profile command, then final source workflow. Historical sections below retain their original source/status attribution.

'''
    for name in ('summary.md','handoff.md'):
        path=REPO/'evidence/POC-005'/name
        path.write_bytes(summary.encode()+path.read_bytes())
    task=REPO/'specs/tasks/POC-005.md';old=task.read_bytes();end=old.find(b'---',3)+3
    assert old.startswith(b'---') and end>3
    note='''

## Current local-v1 exit/report candidate

Independent local exit pass/approved at2026-10-27T05:18:53Z is preserved in evidence/POC-005/local-v1-exit-decision-v1/independent-assessment.json. The exacted8/0101m execution has full frozen execution qualification;008/009 retain their original source identities as report support. The source-labelled scale report includes all13 measurements, actual source traversal/directory/name/change/provider costs and cleanup drift. Formal single010 result/index files now transcribe that real decision; complete profile validation and this new candidate's Task15/CI/source review/integration remain pending. Current Task stays in_progress/implementer; frozen protocols, thresholds, registration/lease and all original results remain unchanged. No production/Ready/main/Task/V1 completion is supplied. See current Evidence summary/handoff before the historical progress notes below.
'''
    task.write_bytes(old[:end]+note.encode()+old[end:])
    commands=REPO/'evidence/POC-005/commands.txt'
    commands.write_bytes(('''Current candidate validation plan (not yet executed at this metadata source):
python specs/poc/check_program.py --profile local-v1 --require-results --poc POC-05
Freeze exact Git source/tree and run all15 existing required Task checks; obtain same-head CI and independent final-source/result review before ordinary integration and actual-main verification.
Runtimeed8/CI868 and original010 complete execution qualification retain their exact identities. The formal index/result candidate does not inherit those checks as a new metadata-source result.

Historical command preparation follows with its original source/status attribution:

''').encode()+commands.read_bytes())
    print(json.dumps({'profileIndex':index,'resultApprovedAt':result['approvedAt'],'independentDecisionTranscribed':True,
                      'schemaShapesValid':True,'formalProfileExecuted':False,'taskCompleted':False}))


if __name__=='__main__':main()

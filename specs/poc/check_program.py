#!/usr/bin/env python3
"""Fail-closed validator for POC-PROTOCOL-V1."""

from __future__ import annotations
import argparse, math, re, sys
from pathlib import Path
from typing import Any
import jsonschema, yaml

POCS={f"POC-{i:02d}" for i in range(1,11)}
TASKS={f"POC-{i:03d}" for i in range(1,11)}
TERMINAL={"pass","fail","inconclusive"}
NONTERMINAL={"not_started","running","blocked","cancelled"}
PLACEHOLDER={"","TBD","TBD_BEFORE_EXECUTION","UNKNOWN","PENDING"}
SAFE_KEYS={"credentials_stored","credentials_stored_in_repository"}
SENSITIVE={"password","passwd","token","secret","api_key","apikey","access_key","accesskey","private_key","privatekey","credential","credentials"}
SECRET_PATTERNS=[
    re.compile(r"glpat-[A-Za-z0-9_-]{8,}"),re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*\S+"),
]
SHA256=re.compile(r"^sha256:[0-9a-fA-F]{64}$")
IMMUTABLE_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{7,127}$")
REQUIRED_MEASUREMENTS={
"POC-01":{"gpu_passthrough_visible","driver_runtime_ready","vm_reboot_recovery","device_reset_recovery"},
"POC-02":{"av1_quality","encode_throughput","first_segment_latency","sustained_encode_stability","sustained_encode_duration","encode_provenance_complete"},
"POC-03":{"range_correctness","etag_semantics","if_range_semantics","cache_key_isolation","large_file_streaming"},
"POC-04":{"iscsi_transport_ready","sequential_throughput","io_latency","watermark_behavior","failure_recovery"},
"POC-05":{"file_count","directory_count","directory_depth_max","average_file_size","source_api_quota","enumeration_rate","incremental_scan_cost","memory_peak"},
"POC-09":{"quality_score","throughput","cost_estimate","license_privacy_pass","caller_permission_gate","asset_acl_gate","hard_budget_gate","request_quota_gate","concurrency_quota_gate"},
"POC-10":{"db_restore","secret_store_restore","secret_value_roundtrip","secret_unreadable_failure_detected","file_restore","rpo_observed","rto_observed"},
}
REQUIRED_ENV={"POC-09":{"model_identity","model_version","prompt_template_version","inference_parameters","input_sample_version"}}
REQUIRED_PROVENANCE={"POC-02":{"input_sha256","output_sha256","encoder_parameters"}}

def load(path:Path)->Any:
    with path.open("r",encoding="utf-8") as f:return yaml.safe_load(f)

def schema_check(schema:Any,label:str,errors:list[str])->None:
    try:
        cls=jsonschema.validators.validator_for(schema);cls.check_schema(schema)
    except Exception as e:errors.append(f"{label} invalid JSON Schema: {e}")

def validate_schema(value:Any,schema:Any,label:str,errors:list[str])->None:
    try:
        cls=jsonschema.validators.validator_for(schema);cls.check_schema(schema)
        for e in sorted(cls(schema).iter_errors(value),key=lambda x:list(x.absolute_path)):
            loc="/".join(map(str,e.absolute_path)) or "<root>"
            errors.append(f"{label} schema violation at {loc}: {e.message}")
    except Exception as e:errors.append(f"{label} schema validation failed: {e}")

def normalize_key(k:Any)->str:
    s=str(k).replace("-","_");s=re.sub(r"([a-z0-9])([A-Z])",r"\1_\2",s)
    return s.lower()

def secret_key(k:Any)->bool:
    n=normalize_key(k)
    if n in SAFE_KEYS:return False
    return any(re.search(rf"(?:^|_){re.escape(t)}(?:_|$)",n) for t in SENSITIVE)

def secret_scan(v:Any,path:str,errors:list[str])->None:
    if isinstance(v,dict):
        for k,x in v.items():
            if secret_key(k):errors.append(f"secret-like key forbidden at {path}/{k}")
            secret_scan(x,f"{path}/{k}",errors)
    elif isinstance(v,list):
        for i,x in enumerate(v):secret_scan(x,f"{path}/{i}",errors)
    elif isinstance(v,str) and any(p.search(v) for p in SECRET_PATTERNS):
        errors.append(f"secret-like value forbidden at {path}")

def maps(plan:dict[str,Any]):
    p={x["pocId"]:x for x in plan.get("pocs",[])}
    t={x["taskId"]:x for x in plan.get("tasks",[]) if str(x.get("taskId","")).startswith("POC-")}
    return p,t

def recorded(v:Any)->bool:
    if v is None:return False
    if isinstance(v,bool):return True
    if isinstance(v,(int,float)) and not isinstance(v,bool):return math.isfinite(float(v))
    if isinstance(v,str):
        s=v.strip();return bool(s) and s.upper() not in PLACEHOLDER
    if isinstance(v,list):return bool(v) and all(recorded(x) for x in v)
    if isinstance(v,dict):return bool(v) and all(str(k).strip() and recorded(x) for k,x in v.items())
    return False

def good_checksum(v:Any)->bool:return isinstance(v,str) and SHA256.fullmatch(v.strip()) is not None
def good_id(v:Any)->bool:
    return isinstance(v,str) and v.strip().upper() not in PLACEHOLDER and IMMUTABLE_ID.fullmatch(v.strip()) is not None
def good_actual(unit:Any,v:Any)->bool:
    if str(unit).lower()=="boolean":return isinstance(v,bool)
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v))

def lexical_ref(ref:Any,evidence:str)->bool:
    if not isinstance(ref,str):return False
    v=ref.strip()
    if not v or v.startswith("/") or "\\" in v:return False
    if any(p in {"",".",".."} for p in v.split("/")):return False
    return v.startswith(evidence+"/") and len(v)>len(evidence)+1

def existing_ref(root:Path,ref:Any,evidence:str)->Path|None:
    if not lexical_ref(ref,evidence):return None
    er=(root/evidence).resolve();p=(root/str(ref)).resolve()
    try:p.relative_to(er)
    except ValueError:return None
    return p if p.is_file() else None

def baseline_plan(plan:dict[str,Any],label:str,errors:list[str])->None:
    if plan.get("status")!="planned":errors.append(f"{label}: canonical plan status must remain planned")
    if plan.get("resultStatus")!="not_started":errors.append(f"{label}: canonical plan resultStatus must remain not_started")
    if (plan.get("environment") or {}).get("capturedValues") not in ({},None):errors.append(f"{label}: canonical plan capturedValues must remain empty")
    p=plan.get("protocol") or {}
    if p.get("commands") or p.get("rawOutputRefs"):errors.append(f"{label}: canonical plan must not contain execution commands/raw refs")
    if any(x.get("actual") is not None for x in p.get("measurements") or []):errors.append(f"{label}: canonical plan measurement actual must remain null")
    d=plan.get("decision") or {}
    if d.get("status")!="not_evaluated" or d.get("rationale") is not None or d.get("resultRef") is not None:errors.append(f"{label}: canonical plan decision must remain not_evaluated/null")
    r=plan.get("review") or {}
    if any(r.get(k) is not None for k in ("reviewer","approvedAt","approval")):errors.append(f"{label}: canonical plan review fields must remain null")

def validate_execution(root:Path,plan:dict[str,Any],task:dict[str,Any],x:dict[str,Any],schema:dict[str,Any],status:str,errors:list[str])->None:
    tid=plan["taskId"];pid=plan["pocId"];ev=plan["evidencePath"];label=f"execution record {tid}"
    validate_schema(x,schema,label,errors);secret_scan(x,label,errors)
    for k,w in (("pocId",pid),("taskId",tid),("evidencePath",ev),("executor",task.get("ownerRole"))):
        if x.get(k)!=w:errors.append(f"{label}: {k} must equal {w!r}")
    env=x.get("environmentCaptured") or {};req=set(plan["environment"]["captureBeforeExecution"])
    miss=req-set(env)
    if miss:errors.append(f"{label}: missing environment fields {sorted(miss)}")
    bad=[k for k in req if k in env and not recorded(env[k])]
    if bad:errors.append(f"{label}: empty/placeholder environment values {sorted(bad)}")
    cmds=x.get("commands") or []
    if not cmds or any(not isinstance(c,str) or not c.strip() for c in cmds):errors.append(f"{label}: commands must contain nonempty recorded commands")
    raw=x.get("rawOutputRefs") or []
    if not raw:errors.append(f"{label}: at least one raw output reference is required")
    for ref in raw:
        if existing_ref(root,ref,ev) is None:errors.append(f"{label}: raw evidence file must exist under {ev}: {ref!r}")
    samples=x.get("samples") or [];ids=[s.get("id") for s in samples]
    if len(ids)!=len(set(ids)):errors.append(f"{label}: execution sample IDs must be unique")
    if set(ids)!=set(plan.get("sampleIds") or []):errors.append(f"{label}: execution sample IDs must exactly match plan")
    for s in samples:
        sid=s.get("id")
        if s.get("approved") is not True:errors.append(f"{label}: sample {sid} must be explicitly approved")
        if not good_id(s.get("immutableId")):errors.append(f"{label}: sample {sid} immutableId is invalid/placeholder")
        if not good_checksum(s.get("checksum")):errors.append(f"{label}: sample {sid} checksum must be sha256:<64 hex>")
        if existing_ref(root,s.get("approvalRef"),ev) is None:errors.append(f"{label}: sample {sid} approvalRef must exist under {ev}")
    pm={m["id"]:m for m in plan["protocol"]["measurements"]};xm=x.get("measurements") or [];am={m.get("id"):m.get("actual") for m in xm}
    if len(am)!=len(xm):errors.append(f"{label}: measurement IDs must be unique")
    if set(am)!=set(pm):errors.append(f"{label}: measurement IDs must exactly match plan")
    bad=[i for i,m in pm.items() if i in am and not good_actual(m.get("unit"),am[i])]
    if bad:errors.append(f"{label}: invalid/placeholder measurement values {sorted(bad)}")
    false=[i for i,m in pm.items() if status=="pass" and str(m.get("unit")).lower()=="boolean" and am.get(i) is not True]
    if false:errors.append(f"{label}: PASS has false/non-true boolean gates {sorted(false)}")
    prov=x.get("provenance") or {};reqp=REQUIRED_PROVENANCE.get(pid,set());miss=reqp-set(prov)
    if miss:errors.append(f"{label}: missing required provenance fields {sorted(miss)}")
    for k in reqp & set(prov):
        if k in {"input_sha256","output_sha256"} and not good_checksum(prov[k]):errors.append(f"{label}: provenance {k} must be sha256:<64 hex>")
        elif k not in {"input_sha256","output_sha256"} and not recorded(prov[k]):errors.append(f"{label}: provenance {k} must be nonempty/non-placeholder")
    if not task.get("ownerRole") or not task.get("reviewerRole") or task.get("ownerRole")==task.get("reviewerRole"):
        errors.append(f"{label}: canonical task must define distinct ownerRole/reviewerRole")

def validate_terminal(root:Path,plan:dict[str,Any],task:dict[str,Any],entry:dict[str,Any],rs:dict[str,Any],xs:dict[str,Any],errors:list[str])->None:
    tid=plan["taskId"];ev=plan["evidencePath"];status=entry.get("status");label=f"results-index {tid}"
    rp=existing_ref(root,entry.get("resultRef"),ev)
    if rp is None:errors.append(f"{label}: terminal resultRef must point to an existing file under {ev}");return
    result=load(rp)
    if not isinstance(result,dict):errors.append(f"result record {tid}: must be a mapping");return
    validate_schema(result,rs,f"result record {tid}",errors);secret_scan(result,f"result record {tid}",errors)
    reviewer=task.get("reviewerRole");owner=task.get("ownerRole")
    if not reviewer or not owner or reviewer==owner:errors.append(f"{label}: canonical task must define distinct ownerRole/reviewerRole")
    for k,w in (("pocId",plan["pocId"]),("taskId",tid),("status",status),("evidencePath",ev),("decision",status),("reviewer",reviewer),("approvedAt",entry.get("approvedAt"))):
        if result.get(k)!=w:errors.append(f"result record {tid}: {k} must equal {w!r}")
    if entry.get("decision")!=status:errors.append(f"{label}: decision must equal terminal status")
    if entry.get("reviewer")!=reviewer or entry.get("reviewer")==owner:errors.append(f"{label}: reviewer must equal governed reviewerRole and differ from ownerRole")
    if not isinstance(entry.get("approvedAt"),str) or not entry["approvedAt"].strip():errors.append(f"{label}: approvedAt must be nonempty")
    if result.get("approval")!="approved":errors.append(f"result record {tid}: approval must be approved")
    if not isinstance(result.get("rationale"),str) or not result["rationale"].strip():errors.append(f"result record {tid}: rationale must be nonempty")
    xp=existing_ref(root,result.get("executionRef"),ev)
    if xp is None:errors.append(f"result record {tid}: executionRef must point to an existing file under {ev}");return
    execution=load(xp)
    if not isinstance(execution,dict):errors.append(f"execution record {tid}: must be a mapping");return
    if result.get("reviewer")==execution.get("executor"):errors.append(f"result record {tid}: reviewer must differ from execution executor")
    validate_execution(root,plan,task,execution,xs,status,errors)

def validate_repository(root:Path)->list[str]:
    errors=[];base=root/"specs"/"poc"
    try:
        program=load(base/"program.yaml");ps=load(base/"program.schema.yaml");plans=load(base/"plan.schema.yaml");protos=load(base/"protocol.schema.yaml")
        ris=load(base/"result-index.schema.yaml");xes=load(base/"execution-record.schema.yaml");rrs=load(base/"result-record.schema.yaml")
        resources=load(base/"resources.yaml");samples=load(base/"samples.yaml");results=load(base/"results-index.yaml");policy=load(base/"policy.yaml")
        pp=load(root/"specs"/"coordination"/"program-plan.yaml")
    except Exception as e:return [f"cannot load POC Program: {e}"]
    for n,s in (("program.schema.yaml",ps),("plan.schema.yaml",plans),("protocol.schema.yaml",protos),("result-index.schema.yaml",ris),("execution-record.schema.yaml",xes),("result-record.schema.yaml",rrs)):schema_check(s,n,errors)
    validate_schema(program,ps,"program.yaml",errors);validate_schema(results,ris,"results-index.yaml",errors)
    expected={"executionRecordSchema":"execution-record.schema.yaml","resultRecordSchema":"result-record.schema.yaml","executionRecordTemplate":"templates/execution-record.yaml","resultRecordTemplate":"templates/result-record.yaml"}
    for k,w in expected.items():
        if program.get(k)!=w:errors.append(f"program.yaml {k} must equal {w!r}")
    if program.get("executionEnabled") is not False:errors.append("GZ-010 program executionEnabled must be false")
    if policy.get("executionAllowedInGz010") is not False:errors.append("policy executionAllowedInGz010 must be false")
    for k in ("sampleExecutionRequiresApproval","canonicalPlansImmutable","cataloguesImmutableInPocTasks","terminalEvidenceMustExist","terminalReviewRoleBound","highCriticalIsolation","criticalStandalone"):
        if policy.get(k) is not True:errors.append(f"policy {k} must be true")
    if policy.get("maxConcurrentHighCritical")!=1:errors.append("policy maxConcurrentHighCritical must be 1")
    cp,ct=maps(pp)
    if set(cp)!=POCS:errors.append("canonical Program Plan POC IDs mismatch")
    if set(ct)!=TASKS:errors.append("canonical Program Plan POC task IDs mismatch")
    files=program.get("planFiles") or [];expected_files={f"plans/POC-{i:03d}.yaml" for i in range(1,11)}
    if set(files)!=expected_files:errors.append("program.yaml planFiles must contain exactly POC-001..POC-010")
    rm={x.get("id"):x for x in resources.get("resources",[])};sm={x.get("id"):x for x in samples.get("samples",[])}
    byp={};byt={};evs=set()
    for rel in files:
        path=base/rel
        if not path.is_file():errors.append(f"missing POC plan: {rel}");continue
        p=load(path);validate_schema(p,plans,rel,errors);validate_schema(p.get("protocol"),protos,rel+"/protocol",errors);secret_scan(p,rel,errors);baseline_plan(p,rel,errors)
        pid=p.get("pocId");tid=p.get("taskId");byp[pid]=p;byt[tid]=p;c=cp.get(pid);t=ct.get(tid)
        if not c:errors.append(f"{rel}: unknown canonical pocId {pid}")
        if not t:errors.append(f"{rel}: unknown canonical taskId {tid}")
        if c and c.get("taskId")!=tid:errors.append(f"{rel}: POC↔Task mismatch")
        if c and t:
            checks={"riskLevel":(p.get("riskLevel"),t.get("riskLevel")),"wave":(p.get("wave"),t.get("wave")),"requirementIds":(set(p.get("requirementIds") or []),set(t.get("requirementIds") or [])),"moduleIds":(set(p.get("moduleIds") or []),set(t.get("moduleIds") or [])),"evidencePath":(p.get("evidencePath"),c.get("evidencePath")),"dependsOn":(set(p.get("dependsOn") or []),set(t.get("dependsOn") or []))}
            for k,(a,w) in checks.items():
                if a!=w:errors.append(f"{rel}: {k} does not match Program Plan")
            ep=p.get("evidencePath");outs=set(t.get("outputPaths") or [])
            if not outs.intersection({ep,f"{ep}/**"}):errors.append(f"{rel}: downstream task must own its Evidence path {ep!r}")
            if "specs/poc/results-index.yaml" not in (t.get("sharedPaths") or []):errors.append(f"{rel}: downstream task must share specs/poc/results-index.yaml")
        ep=p.get("evidencePath")
        if ep in evs:errors.append(f"duplicate POC evidence path: {ep}")
        evs.add(ep)
        mids=[m.get("id") for m in (p.get("protocol") or {}).get("measurements",[])]
        miss=REQUIRED_MEASUREMENTS.get(pid,set())-set(mids)
        if miss:errors.append(f"{rel}: missing frozen required measurements {sorted(miss)}")
        cap=set((p.get("environment") or {}).get("captureBeforeExecution") or []);miss=REQUIRED_ENV.get(pid,set())-cap
        if miss:errors.append(f"{rel}: missing required environment provenance fields {sorted(miss)}")
        for rid in p.get("resourceIds") or []:
            if rid not in rm:errors.append(f"{rel}: unknown resource {rid}")
        for sid in p.get("sampleIds") or []:
            if sid not in sm:errors.append(f"{rel}: unknown sample {sid}")
            elif pid not in (sm[sid].get("allowedPocs") or []):errors.append(f"{rel}: sample {sid} does not allow {pid}")
    if set(byp)!=POCS:errors.append("plan POC IDs must be exactly POC-01..10")
    if set(byt)!=TASKS:errors.append("plan task IDs must be exactly POC-001..010")
    for sid,s in sm.items():
        if s.get("approvalState")!="pending_before_execution":errors.append(f"sample {sid}: approvalState must remain pending_before_execution")
        if s.get("immutableId")!="TBD_BEFORE_EXECUTION":errors.append(f"sample {sid}: immutableId must remain TBD_BEFORE_EXECUTION")
        if s.get("checksum")!="TBD_BEFORE_EXECUTION":errors.append(f"sample {sid}: checksum must remain TBD_BEFORE_EXECUTION")
    for rid,r in rm.items():
        if r.get("credentialsStored") is not False:errors.append(f"resource {rid}: credentialsStored must be false")
    entries=results.get("entries") or [];idx={x.get("taskId"):x for x in entries}
    if set(idx)!=TASKS or len(idx)!=len(entries):errors.append("results-index must contain exactly unique POC-001..POC-010")
    for tid,e in idx.items():
        p=byt.get(tid);t=ct.get(tid)
        if not p or not t:continue
        if e.get("pocId")!=p.get("pocId"):errors.append(f"results-index {tid}: pocId mismatch")
        if e.get("evidencePath")!=p.get("evidencePath"):errors.append(f"results-index {tid}: evidencePath mismatch")
        st=e.get("status")
        if st in NONTERMINAL:
            for k in ("resultRef","decision","reviewer","approvedAt"):
                if e.get(k) is not None:errors.append(f"results-index {tid}: nonterminal {st} {k} must be null")
        elif st in TERMINAL:validate_terminal(root,p,t,e,rrs,xes,errors)
        else:errors.append(f"results-index {tid}: unsupported status {st!r}")
    for n,v in (("resources.yaml",resources),("samples.yaml",samples),("results-index.yaml",results),("policy.yaml",policy)):secret_scan(v,n,errors)
    return errors

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--repo-root");a=ap.parse_args()
    root=Path(a.repo_root).resolve() if a.repo_root else Path(__file__).resolve().parents[2]
    errors=validate_repository(root)
    if errors:
        for e in errors:print("FAIL:",e)
        return 1
    print("PASS: POC-PROTOCOL-V1 immutable planning baseline and task-owned Evidence contracts are consistent with Program Plan")
    return 0

if __name__=="__main__":sys.exit(main())

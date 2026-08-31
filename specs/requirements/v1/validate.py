#!/usr/bin/env python3
"""Fail-closed cross-file validator for GZ-004."""

import argparse, copy, re, sys
from pathlib import Path
import yaml
from jsonschema import Draft202012Validator

R=Path(__file__).resolve().parents[3]
P=lambda s:R/s
FILES={
"req":"specs/requirements/v1/requirements.yaml",
"nfr":"specs/requirements/v1/nfr.yaml",
"trace":"specs/requirements/v1/traceability.yaml",
"acc":"specs/acceptance/requirements/acceptance.yaml",
"reqs":"specs/requirements/v1/requirements.schema.yaml",
"nfrs":"specs/requirements/v1/nfr.schema.yaml",
"traces":"specs/requirements/v1/traceability.schema.yaml",
"accs":"specs/acceptance/requirements/acceptance.schema.yaml",
"idx":"specs/requirements/requirements-index.yaml",
"mods":"specs/designs/module-ownership.yaml",
"prog":"specs/coordination/program-plan.yaml",
}
PRODUCT="specs/requirements/product-requirements.md"
INDEX="specs/requirements/requirements-index.yaml"
PROGRAM="specs/coordination/program-plan.yaml"
REQS={f"REQ-V1-{i:04d}" for i in range(1,11)}
CONTRACTS=["REQ-V1","NFR-V1","ACCEPTANCE-TRACE-V1"]
CATS={"security","privacy","performance","capacity","availability","recovery","observability","compatibility","maintainability","supply-chain"}
PROG_ACC={"REQ-V1-0003":{"验收V1-0005"}}
FROZEN={"NFR-V1-CAP-001":(700,"TB_APPROX"),"NFR-V1-CAP-002":(500,"GB_MIN"),"NFR-V1-COMP-001":("6.7","ESXI_VERSION")}

def y(path): return yaml.safe_load(P(path).read_text(encoding="utf-8"))
def S(v): return set(v or [])
def schema_errors(instance,schema,label):
    out=[]
    for e in Draft202012Validator(schema).iter_errors(instance):
        loc=".".join(map(str,e.absolute_path)) or "<root>"
        out.append(f"{label} schema {loc}: {e.message}")
    return out
def task_ids(p): return {x["taskId"] for x in p.get("tasks",[]) if x.get("taskId")}
def poc_ids(p): return {x["pocId"] for x in p.get("pocs",[]) if x.get("pocId")}
def ext_ids(p): return {x["id"] for x in p.get("externalBlockers",[]) if x.get("id")}
def mod_ids(m): return {x["id"] for x in m.get("modules",[]) if x.get("id")}
def prog_pocs(p):
    z={rid:set() for rid in REQS}
    for x in p.get("pocs",[]):
        for rid in x.get("requirementIds",[]) or []:
            if rid in z: z[rid].add(x["pocId"])
    return z
def fake_claims(v,path=""):
    out=[]
    if isinstance(v,dict):
        for k,x in v.items():
            q=f"{path}.{k}" if path else str(k)
            n=str(k).lower().replace("_","").replace("-","")
            if n in {"pocresult","pocresultstate","pocstatus","measuredresult","measurementresult"}: out.append(q)
            out+=fake_claims(x,q)
    elif isinstance(v,list):
        for i,x in enumerate(v): out+=fake_claims(x,f"{path}[{i}]")
    elif isinstance(v,str) and v.strip().upper() in {"PASS","PASSED","MEASURED"}: out.append(path)
    return out

def validate(b):
    req,nfr,tr,acc=b["req"],b["nfr"],b["trace"],b["acc"]
    idx,mods,prog=b["idx"],b["mods"],b["prog"]
    E=[]
    for k,sk in [("req","reqs"),("nfr","nfrs"),("trace","traces"),("acc","accs")]:
        E+=schema_errors(b[k],b[sk],FILES[k])
    rr=req.get("requirements",[]) or []; rb={x.get("id"):x for x in rr if x.get("id")}
    if len(rr)!=10 or set(rb)!=REQS:E.append("requirements must contain exactly REQ-V1-0001..0010")
    a=req.get("authority",{})
    if a.get("product")!=PRODUCT or a.get("index")!=INDEX:E.append("requirements authority drift")
    if not {PRODUCT,INDEX}<=S(req.get("derivedFrom")):E.append("requirements derivedFrom drift")
    seen={}
    for rid,x in rb.items():
        for alias in x.get("aliases",[]) or []:
            if alias in seen and seen[alias]!=rid:E.append(f"duplicate alias {alias}")
            seen[alias]=rid
    ib={x.get("id"):x for x in idx.get("requirements",[]) if x.get("id")}
    if set(ib)!=REQS:E.append("requirements-index does not expose exact V1 requirement set")
    for rid in REQS:
        x,c=rb.get(rid),ib.get(rid)
        if not x or not c:continue
        for f in ("aliases","moduleIds","workPackages","acceptanceIds","blockers","nextTasks"):
            if S(x.get(f))!=S(c.get(f)):E.append(f"{rid} {f} differs from requirements-index")
        if PRODUCT not in S(x.get("sourceRefs")):E.append(f"{rid} missing product sourceRef")
        bad=S(x.get("moduleIds"))-mod_ids(mods)
        if bad:E.append(f"{rid} unknown modules {sorted(bad)}")

    aa=acc.get("acceptances",[]) or []; ab={}
    for x in aa:
        aid=x.get("id")
        if aid in ab:E.append(f"duplicate acceptance {aid}")
        ab[aid]=x
        declared=S(x.get("requirementIds"))
        for sc in x.get("scenarios",[]) or []:
            if sc.get("requirementId") not in declared:E.append(f"{aid} scenario reverse-link mismatch")
    for rid,x in rb.items():
        for aid in x.get("acceptanceIds",[]) or []:
            z=ab.get(aid)
            if not z:E.append(f"{rid} missing acceptance {aid}")
            elif rid not in S(z.get("requirementIds")):E.append(f"{rid}/{aid} reverse-link mismatch")
            if z and z.get("provenance"):E.append(f"{rid}/{aid} index acceptance cannot be supplemental")
    tb={x.get("requirementId"):x for x in tr.get("requirements",[]) if x.get("requirementId")}
    if len(tb)!=10 or set(tb)!=REQS:E.append("traceability must contain exact V1 requirement set")
    for rid in REQS:
        exp=PROG_ACC.get(rid,set()); got=S(tb.get(rid,{}).get("programAcceptanceIds"))
        if got!=exp:E.append(f"{rid} programAcceptanceIds mismatch")
        for aid in got:
            z=ab.get(aid); pv=(z or {}).get("provenance") or {}
            if not z or rid not in S(z.get("requirementIds")):E.append(f"{rid}/{aid} supplemental reverse-link mismatch")
            if pv.get("type")!="PROGRAM_SUPPLEMENT" or pv.get("source")!=PROGRAM:E.append(f"{aid} supplemental provenance invalid")
    types={rid:set() for rid in REQS}
    for x in aa:
        for sc in x.get("scenarios",[]) or []:
            rid=sc.get("requirementId")
            if rid in types:types[rid].add(sc.get("type"))
    for rid,x in rb.items():
        if not {"success","failure"}<=types[rid]:E.append(f"{rid} missing success/failure coverage")
        miss=S(x.get("requiredScenarioTypes"))-types[rid]
        if miss:E.append(f"{rid} missing scenario types {sorted(miss)}")

    tids,pids,eids=task_ids(prog),poc_ids(prog),ext_ids(prog); pp=prog_pocs(prog)
    if tr.get("producedContracts")!=CONTRACTS:E.append("trace producedContracts drift")
    auth=tr.get("authority",{})
    if auth.get("programPlan")!=PROGRAM or auth.get("moduleOwnership")!="specs/designs/module-ownership.yaml":E.append("trace authority drift")
    for rid,x in rb.items():
        z=tb.get(rid)
        if not z:continue
        for f in ("moduleIds","workPackages","acceptanceIds"):
            if S(z.get(f))!=S(x.get(f)):E.append(f"{rid} trace {f} mismatch")
        bp={q for q in x.get("blockers",[]) or [] if re.fullmatch(r"POC-\d{2}",str(q))}
        ob=S(x.get("blockers"))-bp
        if S(z.get("pocIds"))!=bp:E.append(f"{rid} blocker pocIds mismatch")
        if S(z.get("programPocIds"))!=pp[rid]:E.append(f"{rid} Program POC mapping mismatch")
        if S(z.get("otherBlockers"))!=ob:E.append(f"{rid} otherBlockers mismatch")
        if S(z.get("downstreamTasks"))!=S(x.get("nextTasks")):E.append(f"{rid} downstreamTasks mismatch")
        if z.get("producedContracts")!=CONTRACTS:E.append(f"{rid} producedContracts mismatch")
        if (S(z.get("pocIds"))|S(z.get("programPocIds")))-pids:E.append(f"{rid} unknown POC")
        if S(z.get("downstreamTasks"))-tids:E.append(f"{rid} unknown downstream task")
        if {q for q in z.get("otherBlockers",[]) or [] if q not in tids and q not in eids}:E.append(f"{rid} unresolved blocker")

    if S(nfr.get("requiredCategories"))!=CATS:E.append("NFR required category set mismatch")
    if not CATS<={x.get("category") for x in nfr.get("items",[]) or []}:E.append("NFR category not represented")
    seen=set()
    for x in nfr.get("items",[]) or []:
        i=x.get("id"); m=x.get("measurement") or {}; st=m.get("state"); val=m.get("value"); unit=m.get("unit"); owners=m.get("verificationOwners") or []
        if i in seen:E.append(f"duplicate NFR {i}")
        seen.add(i)
        if st=="MEASUREMENT_REQUIRED" and (val is not None or unit is not None or not owners):E.append(f"{i} invalid MEASUREMENT_REQUIRED")
        if i in FROZEN and (st!="FROZEN_CONSTRAINT" or (val,unit)!=FROZEN[i]):E.append(f"{i} frozen value drift")
        elif st=="FROZEN_CONSTRAINT" and val is not None and i not in FROZEN:E.append(f"{i} unapproved frozen numeric/version value")
        for o in owners:
            if re.fullmatch(r"POC-\d{2}",str(o)) and o not in pids:E.append(f"{i} unknown verification POC {o}")
            elif re.fullmatch(r"GZ-\d{3}",str(o)) and o not in tids:E.append(f"{i} unknown verification task {o}")
            elif not re.fullmatch(r"(POC-\d{2}|GZ-\d{3})",str(o)):E.append(f"{i} invalid verification owner {o}")
    for k in ("req","nfr","trace","acc"):
        for q in fake_claims(b[k]):E.append(f"{k} unapproved POC/measurement result claim at {q}")
    return E

def load():
    return {k:y(v) for k,v in FILES.items()}

def negatives(b):
    tests=[]
    def run(name,fn):
        c={k:copy.deepcopy(b[k]) for k in ("req","nfr","trace","acc")}
        d=dict(b);d.update(c);fn(d);e=validate(d)
        ok=bool(e);print(f"[{'PASS' if ok else 'FAIL'}] {name}: {'rejected' if ok else 'accepted'}")
        return ok
    tests.append(run("duplicate-alias",lambda d:d["req"]["requirements"][1]["aliases"].append(d["req"]["requirements"][0]["aliases"][0])))
    tests.append(run("unknown-module",lambda d:d["req"]["requirements"][0]["moduleIds"].append("MOD-UNKNOWN")))
    tests.append(run("missing-requirement",lambda d:d["req"]["requirements"].pop()))
    tests.append(run("asymmetric-trace",lambda d:d["trace"]["requirements"][0]["acceptanceIds"].pop()))
    tests.append(run("measurement-required-with-value",lambda d:next(x for x in d["nfr"]["items"] if x["measurement"]["state"]=="MEASUREMENT_REQUIRED")["measurement"].update({"value":123,"unit":"ms"})))
    tests.append(run("fake-poc-pass",lambda d:d["trace"]["requirements"][0].update({"pocResultState":"PASS"})))
    print(f"GZ-004 negative fixtures: {'PASS' if all(tests) else 'FAIL'} ({sum(tests)}/{len(tests)} rejected)")
    return 0 if all(tests) else 1

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--negative-fixtures",action="store_true");a=ap.parse_args()
    try:b=load()
    except Exception as e:print(f"load failure: {e}",file=sys.stderr);return 1
    e=validate(b)
    if e:
        print(f"GZ-004 V1 requirements baseline: FAIL ({len(e)})",file=sys.stderr)
        for x in e:print(f"- {x}",file=sys.stderr)
        return 1
    if a.negative_fixtures:return negatives(b)
    print("GZ-004 V1 requirements baseline: PASS")
    print(f"- requirements: {len(b['req']['requirements'])}")
    print(f"- nfr items: {len(b['nfr']['items'])}")
    print(f"- acceptances: {len(b['acc']['acceptances'])}")
    print(f"- trace records: {len(b['trace']['requirements'])}")
    return 0
if __name__=="__main__":raise SystemExit(main())

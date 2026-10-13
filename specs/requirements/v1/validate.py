#!/usr/bin/env python3
"""Fail-closed cross-file validator for GZ-004."""

import argparse
import copy
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

R = Path(__file__).resolve().parents[3]
P = lambda s: R / s
FILES = {
    "req": "specs/requirements/v1/requirements.yaml",
    "nfr": "specs/requirements/v1/nfr.yaml",
    "trace": "specs/requirements/v1/traceability.yaml",
    "acc": "specs/acceptance/requirements/acceptance.yaml",
    "reqs": "specs/requirements/v1/requirements.schema.yaml",
    "nfrs": "specs/requirements/v1/nfr.schema.yaml",
    "traces": "specs/requirements/v1/traceability.schema.yaml",
    "accs": "specs/acceptance/requirements/acceptance.schema.yaml",
    "idx": "specs/requirements/requirements-index.yaml",
    "mods": "specs/designs/module-ownership.yaml",
    "prog": "specs/coordination/program-plan.yaml",
}
PRODUCT = "specs/requirements/product-requirements.md"
INDEX = "specs/requirements/requirements-index.yaml"
PROGRAM = "specs/coordination/program-plan.yaml"
REQS = {f"REQ-V1-{i:04d}" for i in range(1, 11)}
CANONICAL_ACCEPTANCES = {f"验收V1-{i:04d}" for i in range(1, 13)}
CONTRACTS = ["REQ-V1", "NFR-V1", "ACCEPTANCE-TRACE-V1"]
CATS = {
    "security",
    "privacy",
    "performance",
    "capacity",
    "availability",
    "recovery",
    "observability",
    "compatibility",
    "maintainability",
    "supply-chain",
}
FROZEN = {
    "NFR-V1-CAP-001": (700, "TB_APPROX"),
    "NFR-V1-CAP-002": (500, "GB_MIN"),
    "NFR-V1-COMP-001": ("6.7", "ESXI_VERSION"),
}
PROFILE_BINDINGS = {
    "local-v1": ("GZ-018", "LOCAL_FULL_V1", False),
    "production": ("GZ-020", "PRODUCTION_RELEASE", True),
}
PRODUCTION_ONLY_NFR = set(FROZEN) | {"NFR-V1-COMP-002"}
LOCAL_FLOOR_NFR = "NFR-V1-CAP-005"
HETEROGENEOUS_NFR = "NFR-V1-COMP-003"


def string_ids(value):
    return set(value) if isinstance(value, list) and all(isinstance(x, str) for x in value) else set()


def validate_profile_bindings(b, errors, selected_profile):
    """Validate declarations only; baseline validation never grants a measured result."""
    if selected_profile is not None and selected_profile not in PROFILE_BINDINGS:
        errors.append("unknown acceptance profile")
    if type(b["idx"].get("version")) is not int or b["idx"].get("version") != 2:
        errors.append("requirements index format must retain version 2")
    binding = b["nfr"].get("acceptanceProfileBinding")
    if not isinstance(binding, dict):
        errors.append("missing structured acceptance profile binding")
        return
    for key in ["req", "trace", "acc", "idx"]:
        if b[key].get("acceptanceProfileBinding") != binding:
            errors.append(f"{key} acceptance profile binding drift")
    if (binding.get("revision"), binding.get("authorityTask"), binding.get("decisionRef")) != (
        1, "GZ-021", "adr/0015-heterogeneous-av1-workers-and-local-storage-validation.md"
    ):
        errors.append("acceptance profile authority/version drift")
    profiles = binding.get("profiles")
    if not isinstance(profiles, list) or not all(isinstance(p, dict) for p in profiles):
        errors.append("acceptance profiles must be structured records")
        return
    ids = [p.get("id") for p in profiles]
    if len(ids) != 2 or any(not isinstance(x, str) for x in ids) or set(ids) != set(PROFILE_BINDINGS):
        errors.append("acceptance profile IDs must be exactly local-v1 and production")
    tasks = {t.get("taskId"): t for t in b["prog"].get("tasks", []) if isinstance(t, dict)}
    production = tasks.get("GZ-020", {})
    required_acceptances = CANONICAL_ACCEPTANCES
    known_acceptances = {a.get("id") for a in b["acc"].get("acceptances", [])}
    if string_ids(production.get("acceptanceIds")) != required_acceptances or not required_acceptances <= known_acceptances:
        errors.append("full V1 must retain twelve canonical acceptances")
    for profile in profiles:
        identity = profile.get("id")
        expected = PROFILE_BINDINGS.get(identity) if isinstance(identity, str) else None
        if expected is None:
            errors.append("unknown acceptance profile declaration")
            continue
        milestone, scope, can_satisfy_production = expected
        if profile.get("version") != 1 or profile.get("milestoneTask") != milestone or profile.get("scope") != scope:
            errors.append(f"{identity} profile version/milestone/scope mismatch")
        if profile.get("canSatisfyProductionGate") is not can_satisfy_production:
            errors.append(f"{identity} production gate boundary mismatch")
        task = tasks.get(milestone, {})
        if string_ids(profile.get("requirementIds")) != REQS or string_ids(task.get("requirementIds")) != REQS:
            errors.append(f"{identity} must cover all ten V1 requirements")
        if string_ids(profile.get("acceptanceIds")) != required_acceptances or string_ids(task.get("acceptanceIds")) != required_acceptances:
            errors.append(f"{identity} must cover all twelve V1 acceptances")
    nfrs = {n.get("id"): n for n in b["nfr"].get("items", [])}
    missing = (PRODUCTION_ONLY_NFR | {LOCAL_FLOOR_NFR, HETEROGENEOUS_NFR}) - set(nfrs)
    if missing:
        errors.append(f"missing protected production/local NFRs {sorted(missing)}")
    for identity, item in nfrs.items():
        expected = {"production"} if identity in PRODUCTION_ONLY_NFR else ({"local-v1"} if identity == LOCAL_FLOOR_NFR else set(PROFILE_BINDINGS))
        if string_ids(item.get("applicableProfiles")) != expected:
            errors.append(f"{identity} NFR profile applicability drift")
    floor = nfrs.get(LOCAL_FLOOR_NFR, {}).get("measurement", {})
    if floor and (floor.get("state") != "DESIGN_TARGET" or floor.get("value") is not None or floor.get("unit") is not None):
        errors.append("local floor must remain configured/measured per execution, never a fabricated baseline value")
    for identity in PROFILE_BINDINGS:
        categories = {item.get("category") for item in nfrs.values() if identity in string_ids(item.get("applicableProfiles"))}
        if not CATS <= categories:
            errors.append(f"{identity} missing mandatory NFR categories")


def y(path):
    return yaml.safe_load(P(path).read_text(encoding="utf-8"))


def S(v):
    return set(v or [])


def schema_errors(instance, schema, label):
    out = []
    for e in Draft202012Validator(schema).iter_errors(instance):
        loc = ".".join(map(str, e.absolute_path)) or "<root>"
        out.append(f"{label} schema {loc}: {e.message}")
    return out


def task_ids(p):
    return {x["taskId"] for x in p.get("tasks", []) if x.get("taskId")}


def task_requirement_map(p):
    return {
        x["taskId"]: S(x.get("requirementIds"))
        for x in p.get("tasks", [])
        if x.get("taskId")
    }


def poc_ids(p):
    return {x["pocId"] for x in p.get("pocs", []) if x.get("pocId")}


def ext_ids(p):
    return {x["id"] for x in p.get("externalBlockers", []) if x.get("id")}


def mod_ids(m):
    return {x["id"] for x in m.get("modules", []) if x.get("id")}


def prog_pocs(p):
    z = {rid: set() for rid in REQS}
    for x in p.get("pocs", []):
        for rid in x.get("requirementIds", []) or []:
            if rid in z:
                z[rid].add(x["pocId"])
    return z


def supplemental_acceptances(acc, prog, errors):
    """Resolve PROGRAM_SUPPLEMENT relationships from the canonical Program Plan."""
    tasks = [x for x in prog.get("tasks", []) if isinstance(x, dict)]
    out = {rid: set() for rid in REQS}
    for item in acc.get("acceptances", []) or []:
        aid = item.get("id")
        provenance = item.get("provenance")
        if not provenance:
            continue
        if (
            provenance.get("type") != "PROGRAM_SUPPLEMENT"
            or provenance.get("source") != PROGRAM
        ):
            errors.append(f"{aid} supplemental provenance invalid")
            continue
        for rid in S(item.get("requirementIds")):
            if rid not in REQS:
                continue
            matches = [
                task.get("taskId")
                for task in tasks
                if aid in S(task.get("acceptanceIds"))
                and rid in S(task.get("requirementIds"))
            ]
            if not matches:
                errors.append(
                    f"{rid}/{aid} supplement has no matching Program task acceptance/requirement source"
                )
            else:
                out[rid].add(aid)
    return out


def fake_claims(v, path=""):
    out = []
    if isinstance(v, dict):
        for k, x in v.items():
            q = f"{path}.{k}" if path else str(k)
            n = str(k).lower().replace("_", "").replace("-", "")
            if n in {
                "pocresult",
                "pocresultstate",
                "pocstatus",
                "measuredresult",
                "measurementresult",
            }:
                out.append(q)
            out += fake_claims(x, q)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            out += fake_claims(x, f"{path}[{i}]")
    elif isinstance(v, str) and v.strip().upper() in {"PASS", "PASSED", "MEASURED"}:
        out.append(path)
    return out


def validate(b, selected_profile=None):
    req, nfr, tr, acc = b["req"], b["nfr"], b["trace"], b["acc"]
    idx, mods, prog = b["idx"], b["mods"], b["prog"]
    E = []

    for k, sk in [
        ("req", "reqs"),
        ("nfr", "nfrs"),
        ("trace", "traces"),
        ("acc", "accs"),
    ]:
        E += schema_errors(b[k], b[sk], FILES[k])

    validate_profile_bindings(b, E, selected_profile)

    rr = req.get("requirements", []) or []
    rb = {x.get("id"): x for x in rr if x.get("id")}
    if len(rr) != 10 or set(rb) != REQS:
        E.append("requirements must contain exactly REQ-V1-0001..0010")

    authority = req.get("authority", {})
    if authority.get("product") != PRODUCT or authority.get("index") != INDEX:
        E.append("requirements authority drift")
    if not {PRODUCT, INDEX} <= S(req.get("derivedFrom")):
        E.append("requirements derivedFrom drift")

    aliases = {}
    for rid, item in rb.items():
        for alias in item.get("aliases", []) or []:
            if alias in aliases and aliases[alias] != rid:
                E.append(f"duplicate alias {alias}")
            aliases[alias] = rid

    ib = {
        x.get("id"): x
        for x in idx.get("requirements", [])
        if x.get("id")
    }
    if set(ib) != REQS:
        E.append("requirements-index does not expose exact V1 requirement set")

    known_modules = mod_ids(mods)
    for rid in REQS:
        item, canonical = rb.get(rid), ib.get(rid)
        if not item or not canonical:
            continue
        for field in (
            "aliases",
            "moduleIds",
            "workPackages",
            "acceptanceIds",
            "blockers",
            "nextTasks",
        ):
            if S(item.get(field)) != S(canonical.get(field)):
                E.append(f"{rid} {field} differs from requirements-index")
        if PRODUCT not in S(item.get("sourceRefs")):
            E.append(f"{rid} missing product sourceRef")
        unknown_modules = S(item.get("moduleIds")) - known_modules
        if unknown_modules:
            E.append(f"{rid} unknown modules {sorted(unknown_modules)}")

    aa = acc.get("acceptances", []) or []
    ab = {}
    for item in aa:
        aid = item.get("id")
        if aid in ab:
            E.append(f"duplicate acceptance {aid}")
        ab[aid] = item
        declared = S(item.get("requirementIds"))
        unknown_declared = declared - REQS
        if unknown_declared:
            E.append(
                f"{aid} declares unknown requirements {sorted(unknown_declared)}"
            )
        scenario_ids = set()
        for scenario in item.get("scenarios", []) or []:
            rid = scenario.get("requirementId")
            if rid not in REQS:
                E.append(f"{aid} scenario references unknown requirement {rid}")
            if rid not in declared:
                E.append(f"{aid} scenario reverse-link mismatch")
            if rid:
                scenario_ids.add(rid)
        if scenario_ids != declared:
            E.append(
                f"{aid} declared requirements do not exactly match scenario reverse links"
            )

    supplements = supplemental_acceptances(acc, prog, E)

    for rid, item in rb.items():
        for aid in item.get("acceptanceIds", []) or []:
            acceptance = ab.get(aid)
            if not acceptance:
                E.append(f"{rid} missing acceptance {aid}")
            elif rid not in S(acceptance.get("requirementIds")):
                E.append(f"{rid}/{aid} reverse-link mismatch")
            if acceptance and acceptance.get("provenance"):
                E.append(f"{rid}/{aid} index acceptance cannot be supplemental")

    tb = {
        x.get("requirementId"): x
        for x in tr.get("requirements", [])
        if x.get("requirementId")
    }
    if len(tb) != 10 or set(tb) != REQS:
        E.append("traceability must contain exact V1 requirement set")

    for rid in REQS:
        expected = supplements.get(rid, set())
        got = S(tb.get(rid, {}).get("programAcceptanceIds"))
        if got != expected:
            E.append(f"{rid} programAcceptanceIds mismatch")
        for aid in got:
            acceptance = ab.get(aid)
            if not acceptance or rid not in S(acceptance.get("requirementIds")):
                E.append(f"{rid}/{aid} supplemental reverse-link mismatch")

    scenario_types = {rid: set() for rid in REQS}
    for item in aa:
        for scenario in item.get("scenarios", []) or []:
            rid = scenario.get("requirementId")
            if rid in scenario_types:
                scenario_types[rid].add(scenario.get("type"))

    for rid, item in rb.items():
        if not {"success", "failure"} <= scenario_types[rid]:
            E.append(f"{rid} missing success/failure coverage")
        missing = S(item.get("requiredScenarioTypes")) - scenario_types[rid]
        if missing:
            E.append(f"{rid} missing scenario types {sorted(missing)}")

    tids, pids, eids = task_ids(prog), poc_ids(prog), ext_ids(prog)
    task_reqs = task_requirement_map(prog)
    program_pocs = prog_pocs(prog)

    if tr.get("producedContracts") != CONTRACTS:
        E.append("trace producedContracts drift")
    trace_authority = tr.get("authority", {})
    if (
        trace_authority.get("programPlan") != PROGRAM
        or trace_authority.get("moduleOwnership")
        != "specs/designs/module-ownership.yaml"
    ):
        E.append("trace authority drift")

    for rid, item in rb.items():
        trace = tb.get(rid)
        if not trace:
            continue
        for field in ("moduleIds", "workPackages", "acceptanceIds"):
            if S(trace.get(field)) != S(item.get(field)):
                E.append(f"{rid} trace {field} mismatch")

        blocker_pocs = {
            q
            for q in item.get("blockers", []) or []
            if re.fullmatch(r"POC-\d{2}", str(q))
        }
        other_blockers = S(item.get("blockers")) - blocker_pocs
        if S(trace.get("pocIds")) != blocker_pocs:
            E.append(f"{rid} blocker pocIds mismatch")
        if S(trace.get("programPocIds")) != program_pocs[rid]:
            E.append(f"{rid} Program POC mapping mismatch")
        if S(trace.get("otherBlockers")) != other_blockers:
            E.append(f"{rid} otherBlockers mismatch")
        if S(trace.get("downstreamTasks")) != S(item.get("nextTasks")):
            E.append(f"{rid} downstreamTasks mismatch")

        expected_conflicts = {
            task_id
            for task_id in S(item.get("nextTasks"))
            if task_id in task_reqs and rid not in task_reqs[task_id]
        }
        if S(trace.get("programTaskMappingConflicts")) != expected_conflicts:
            E.append(
                f"{rid} Program task mapping conflicts mismatch: "
                f"expected {sorted(expected_conflicts)}"
            )

        if trace.get("producedContracts") != CONTRACTS:
            E.append(f"{rid} producedContracts mismatch")
        if (S(trace.get("pocIds")) | S(trace.get("programPocIds"))) - pids:
            E.append(f"{rid} unknown POC")
        if S(trace.get("downstreamTasks")) - tids:
            E.append(f"{rid} unknown downstream task")
        unresolved = {
            q
            for q in trace.get("otherBlockers", []) or []
            if q not in tids and q not in eids
        }
        if unresolved:
            E.append(f"{rid} unresolved blocker")

    if S(nfr.get("requiredCategories")) != CATS:
        E.append("NFR required category set mismatch")
    if not CATS <= {
        x.get("category") for x in nfr.get("items", []) or []
    }:
        E.append("NFR category not represented")

    seen_nfr = set()
    for item in nfr.get("items", []) or []:
        nfr_id = item.get("id")
        measurement = item.get("measurement") or {}
        state = measurement.get("state")
        value = measurement.get("value")
        unit = measurement.get("unit")
        owners = measurement.get("verificationOwners") or []

        if nfr_id in seen_nfr:
            E.append(f"duplicate NFR {nfr_id}")
        seen_nfr.add(nfr_id)

        if state == "MEASUREMENT_REQUIRED" and (
            value is not None or unit is not None or not owners
        ):
            E.append(f"{nfr_id} invalid MEASUREMENT_REQUIRED")

        if nfr_id in FROZEN and (
            state != "FROZEN_CONSTRAINT"
            or (value, unit) != FROZEN[nfr_id]
        ):
            E.append(f"{nfr_id} frozen value drift")
        elif (
            state == "FROZEN_CONSTRAINT"
            and value is not None
            and nfr_id not in FROZEN
        ):
            E.append(f"{nfr_id} unapproved frozen numeric/version value")

        for owner in owners:
            if re.fullmatch(r"POC-\d{2}", str(owner)) and owner not in pids:
                E.append(f"{nfr_id} unknown verification POC {owner}")
            elif re.fullmatch(r"GZ-\d{3}", str(owner)) and owner not in tids:
                E.append(f"{nfr_id} unknown verification task {owner}")
            elif not re.fullmatch(r"(POC-\d{2}|GZ-\d{3})", str(owner)):
                E.append(f"{nfr_id} invalid verification owner {owner}")

    for key in ("req", "nfr", "trace", "acc"):
        for path in fake_claims(b[key]):
            E.append(
                f"{key} unapproved POC/measurement result claim at {path}"
            )

    return E


def load():
    return {k: y(v) for k, v in FILES.items()}


def negatives(b):
    tests = []

    def run(name, fn):
        copied = {
            k: copy.deepcopy(b[k])
            for k in ("req", "nfr", "trace", "acc", "prog", "idx")
        }
        data = dict(b)
        data.update(copied)
        fn(data)
        errors = validate(data)
        ok = bool(errors)
        print(
            f"[{'PASS' if ok else 'FAIL'}] {name}: "
            f"{'rejected' if ok else 'accepted'}"
        )
        return ok

    tests.append(
        run(
            "duplicate-alias",
            lambda d: d["req"]["requirements"][1]["aliases"].append(
                d["req"]["requirements"][0]["aliases"][0]
            ),
        )
    )
    tests.append(
        run(
            "unknown-module",
            lambda d: d["req"]["requirements"][0]["moduleIds"].append(
                "MOD-UNKNOWN"
            ),
        )
    )
    tests.append(
        run(
            "missing-requirement",
            lambda d: d["req"]["requirements"].pop(),
        )
    )
    tests.append(
        run(
            "asymmetric-trace",
            lambda d: d["trace"]["requirements"][0]["acceptanceIds"].pop(),
        )
    )
    tests.append(
        run(
            "unknown-acceptance-requirement",
            lambda d: d["acc"]["acceptances"][0]["requirementIds"].append(
                "REQ-V1-9999"
            ),
        )
    )
    tests.append(
        run(
            "supplement-without-program-source",
            lambda d: [
                task.update(
                    {
                        "acceptanceIds": [
                            aid
                            for aid in task.get("acceptanceIds", []) or []
                            if aid != "验收V1-0005"
                        ]
                    }
                )
                for task in d["prog"].get("tasks", [])
                if "验收V1-0005" in S(task.get("acceptanceIds"))
            ],
        )
    )
    tests.append(
        run(
            "unrecorded-program-task-conflict",
            lambda d: next(
                x
                for x in d["trace"]["requirements"]
                if x["requirementId"] == "REQ-V1-0003"
            ).update({"programTaskMappingConflicts": []}),
        )
    )
    tests.append(
        run(
            "measurement-required-with-value",
            lambda d: next(
                x
                for x in d["nfr"]["items"]
                if x["measurement"]["state"] == "MEASUREMENT_REQUIRED"
            )["measurement"].update({"value": 123, "unit": "ms"}),
        )
    )
    tests.append(
        run(
            "fake-poc-pass",
            lambda d: d["trace"]["requirements"][0].update(
                {"pocResultState": "PASS"}
            ),
        )
    )
    for key in ["req", "trace", "acc", "idx"]:
        tests.append(run("profile-binding-drift-" + key, lambda d, key=key: d[key]["acceptanceProfileBinding"].update(revision=2)))
    tests.append(run("unknown-profile-declaration", lambda d: d["nfr"]["acceptanceProfileBinding"]["profiles"][0].update(id="test-production")))
    tests.append(run("local-result-cannot-satisfy-production", lambda d: d["nfr"]["acceptanceProfileBinding"]["profiles"][0].update(canSatisfyProductionGate=True)))
    tests.append(run("local-milestone-cannot-be-production", lambda d: d["nfr"]["acceptanceProfileBinding"]["profiles"][0].update(milestoneTask="GZ-020")))
    tests.append(run("index-format-version-drift", lambda d: d["idx"].update(version=3)))
    tests.append(run("unknown-profile-version", lambda d: d["nfr"]["acceptanceProfileBinding"]["profiles"][0].update(version=99)))
    tests.append(run("missing-production-floor", lambda d: d["nfr"].update(items=[n for n in d["nfr"]["items"] if n["id"] != "NFR-V1-CAP-002"])))
    tests.append(run("production-floor-value-drift", lambda d: next(n for n in d["nfr"]["items"] if n["id"] == "NFR-V1-CAP-002")["measurement"].update(value=1)))
    tests.append(run("shared-permission-cannot-be-production-only", lambda d: next(n for n in d["nfr"]["items"] if n["id"] == "NFR-V1-SEC-001").update(applicableProfiles=["production"])))
    tests.append(run("incomplete-local-requirement-scope", lambda d: next(t for t in d["prog"]["tasks"] if t["taskId"] == "GZ-018")["requirementIds"].pop()))
    tests.append(run("incomplete-local-acceptance-scope", lambda d: next(t for t in d["prog"]["tasks"] if t["taskId"] == "GZ-018")["acceptanceIds"].pop()))
    tests.append(run("fabricated-local-floor-value", lambda d: next(n for n in d["nfr"]["items"] if n["id"] == LOCAL_FLOOR_NFR)["measurement"].update(value=0,unit="GB")))
    def all_bindings(data, mutate):
        for key in ["req", "nfr", "trace", "acc", "idx"]:
            mutate(data[key]["acceptanceProfileBinding"])
    tests.append(run("consistent-forged-local-production-claim", lambda d: all_bindings(d, lambda binding: binding["profiles"][0].update(canSatisfyProductionGate=True))))
    tests.append(run("consistent-missing-production-profile", lambda d: all_bindings(d, lambda binding: binding["profiles"].pop())))
    tests.append(run("consistent-duplicate-local-profile", lambda d: all_bindings(d, lambda binding: binding["profiles"].__setitem__(1, copy.deepcopy(binding["profiles"][0])))))
    def replace_canonical_acceptance(data):
        def replace(ids):
            return ["ACCEPT-SOURCE-SYNC" if identity == "验收V1-0001" else identity for identity in ids]
        for key in ["req", "nfr", "trace", "acc", "idx"]:
            for profile in data[key]["acceptanceProfileBinding"]["profiles"]:
                profile["acceptanceIds"] = replace(profile["acceptanceIds"])
        for task in data["prog"]["tasks"]:
            if task["taskId"] in ["GZ-018", "GZ-020"]:
                task["acceptanceIds"] = replace(task["acceptanceIds"])
    tests.append(run("consistent-canonical-acceptance-replacement", replace_canonical_acceptance))
    rejected = bool(validate(b, selected_profile="unknown"))
    print(f"[{'PASS' if rejected else 'FAIL'}] unknown-profile-selector: {'rejected' if rejected else 'accepted'}")
    tests.append(rejected)

    print(
        "GZ-004 negative fixtures: "
        f"{'PASS' if all(tests) else 'FAIL'} "
        f"({sum(tests)}/{len(tests)} rejected)"
    )
    return 0 if all(tests) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-fixtures", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILE_BINDINGS))
    args = parser.parse_args()

    try:
        data = load()
    except Exception as exc:
        print(f"load failure: {exc}", file=sys.stderr)
        return 1

    errors = validate(data, selected_profile=args.profile)
    if errors:
        print(
            f"GZ-004 V1 requirements baseline: FAIL ({len(errors)})",
            file=sys.stderr,
        )
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.negative_fixtures:
        return negatives(data)

    print("GZ-004 V1 requirements baseline: PASS")
    print(f"- requirements: {len(data['req']['requirements'])}")
    print(f"- nfr items: {len(data['nfr']['items'])}")
    print(f"- acceptances: {len(data['acc']['acceptances'])}")
    print(f"- trace records: {len(data['trace']['requirements'])}")
    print(f"- acceptance binding: revision 1; {args.profile or 'both declared profiles'}; no POC or release result granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

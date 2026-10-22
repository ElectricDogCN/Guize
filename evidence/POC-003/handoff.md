Task: POC-003
Issue: 131
Branch: chore/POC-003-ats-range
Base / actual reservation merge: 11c32830c0d1bb8ccdcc04aa278876065bce1f33
State: in_progress / implementer
Current implementation source/tests: PENDING; no inherited experimental PASS.

Reservation PR133 source 2fa51e8d0d8d83761dc324ce1bb5e0da4afcad3c / tree e4f9c0f4957778063cbf306a3f63f9ec6d9e05a0; original base 44e5200ed506d30c0abc83ca38f1d6912cbab1c1. Actual local15/CI807713/1463.80s, independent source content and all3 threads accepted; actual merge parents/tree and five main checks plus POC checker executed successfully. FullpushCI808 pending. Exact prior inventory/commands/logs and raw byte archive are retained in reservation-merge-11c3283/ and its source snapshot; current changed files must be regenerated from Git when implementation is committed.

Roles/claims/lease/order remain original: owner ElectricDogCN, coordinator program-coordinator-agent, implementer/executor task-owner-agent, independent reviewer independent-review-agent, integrator integration-agent; expires2026-10-29T12:47:06Z, poc-results/order2. Own poc/POC-03-ats-range/** and evidence/POC-003/**; shared adr/** and only own results-index row.

Next Implementer: review actual historical candidates, implement real bounded gateway/origin/ATS observations and direct revocation assertions; retain exact source/config/input identities. Before any formal experiment, obtain concrete independent sample/resource/domain approval binding current tested source and actual bytes/window. Next Reviewer: inspect actual implementation, raw facts, all15, separate revocation and original failures; no source or experimental acceptance until actual validations. Next Integrator: source exact-head gates, current review/threads/latestmain/order/lease, ordinary merge then actualmain checks. FullV1 remains incomplete.

Rollback: stop/clean only owned sandbox; preserve inputs/evidence/history, lawful cancellation or forward repair, no unrelated services or Docker/WSL restart.

Current code source SHA/tree/PR: pending first implementation commit, resolve exact Git HEAD/PR before validation. This is an intermediate implementation; per-stage native payload export, original15 typed result assembly and approved buffering interpretation remain incomplete. Real grant state and mandatory revocation script have been implemented but not run in a real sandbox. Eight prior offline boundary tests and the actual native observer compile exit0 are development-only, not current committed-source or experimental acceptance. Next action: commit actual draft, run current source15 and offline8, independently review actual code; approve concrete input/resource/source/window before any experiment.

Exact implementation draft inventory against actual reservation base (59 files):

- `evidence/POC-003/EVIDENCE-STRUCTURE.md`
- `evidence/POC-003/assumptions.md`
- `evidence/POC-003/changed-files.md`
- `evidence/POC-003/commands.txt`
- `evidence/POC-003/development-checks/manifest.json`
- `evidence/POC-003/development-checks/missing-sandbox-must-fail.txt`
- `evidence/POC-003/development-checks/offline8.txt`
- `evidence/POC-003/development-observer-build/receipt.json`
- `evidence/POC-003/development-observer-build/stderr.raw`
- `evidence/POC-003/development-observer-build/stdout.raw`
- `evidence/POC-003/follow-ups.md`
- `evidence/POC-003/handoff.md`
- `evidence/POC-003/implementation-input-provenance.json`
- `evidence/POC-003/reservation-merge-11c3283/index.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-adoption.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-checks__00.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-checks__01.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-checks__02.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-checks__03.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-checks__04.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-checks__results.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-protocol__protocol.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-11c3283-main-protocol__results.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-ci807.raw.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-ci807.snapshot.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-independent-review.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__00.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__01.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__02.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__03.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__04.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__05.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__06.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__07.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__08.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__09.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__10.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__11.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__12.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__13.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__14.txt.base64.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-results__results.json`
- `evidence/POC-003/reservation-merge-11c3283/poc003-reservation-2fa51e8-source-admission.json`
- `evidence/POC-003/risks.md`
- `evidence/POC-003/scope.md`
- `evidence/POC-003/summary.md`
- `evidence/POC-003/test-results/README.md`
- `poc/POC-03-ats-range/README.md`
- `poc/POC-03-ats-range/build_observer.py`
- `poc/POC-03-ats-range/cache_export.cc`
- `poc/POC-03-ats-range/collect.py`
- `poc/POC-03-ats-range/config.example.json`
- `poc/POC-03-ats-range/grants.py`
- `poc/POC-03-ats-range/lab.py`
- `poc/POC-03-ats-range/test_lab.py`
- `poc/POC-03-ats-range/test_warm_cache_revocation.py`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/POC-003.md`

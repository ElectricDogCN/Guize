# GZ-005 exact published implementation results

Actual tested source: 85bd46cfc39fc934c9d43623be09acbb557b6930; tree a9e33bc684f0ba500586064dc705445568537115; base 429a6566d81f128cb618c524ee8dc22faba1c0a4.
All17 actual source checks exit0. Full make527 tests773.46s and contract116 tests71.36s; both nonempty JUnits have zero failures/errors/skips. Standard parser and contract checker pass93 operations/136 schemas/33 errors/920 examples/93 HTTP pairs. Authoring and native verification roots stayed clean at the identical immutable source/tree.
Same-head PR CI630 run38025689889/job114135937984 succeeded,527 tests604.87s with skip audit0; all applicable1–25 and cleanup steps succeed. Its synthetic checkout61eb423d730f03f37cc6295941ff48403b5c307e has [base429,actual85] parents and the same source tree; it is not the actual main merge.
Raw commands, exits, source identity, JUnits, worktree binding and saved CI log are in test-results/published-source-85bd46c/. Extra saved transport newline is disclosed. API checks were local additions; existing governance CI did not execute those new API checks.
Current archive changes only Own Evidence. Actual archive-head gates, latest CI and independent final integration review remain required. Prior failed and unstable exploratory runs are retained as unaccepted. No runtime browser/signature, POC, consumer or full V1 success is asserted.

## Prior current implementation handoff and historical records
# GZ-005 current contract implementation

Task: GZ-005 / Issue68
Base: 429a6566d81f128cb618c524ee8dc22faba1c0a4
Branch: chore/GZ-005-openapi-baseline
Status: in_progress / implementer; implementation candidate, not accepted

Actual prerequisite main429 was accepted after OPS-004 Completion: local full make verify 527 tests (1150.51s), zero failures/errors/skips; push CI629 run38021268746/job114122569280 succeeded with 527 tests (850.07s). Root main remained clean at the same source/tree. This prerequisite does not certify the new API.

The existing pure Reservation PR70 and valid original lease permit own reserved -> in_progress plus registered contract implementation in one candidate. No additional pure activation merge is required. Lease remains 2026-10-09T11:52:29Z to 2026-10-16T11:52:29Z without renewal. Other Task/Program/Registry identities, ordinary Ledger, permanent policy, requirements, governance scripts/tests/workflows and POC plans are unchanged.

Implemented candidate: modular OpenAPI3.1.1, stable bilingual errors and93 serialized synthetic HTTP pairs; complete approval request intent with RFC8785/SHA256 reference vectors; full safety-extension compatibility comparison; fail-closed assertion reference siblings; typed WebAuthn creation/authentication options and canonical Base64url. Validation dependency hashes lock the separate Linux x86_64/CPython3.12 tool environment.

Examples establish contract consistency, not runtime authorization, valid signatures, browser execution, real POCs or V1 completion. Independent content review and actual published-source 17 checks (including one full make and three API checks), latest same-head CI, post-main validation and separate Completion remain required.

Prior failed346c9b6 activation and d0d93f4 implementation exploratory results remain preserved under test-results/prior-failed-*; their failure is not counted as current PASS. Original archived reservation facts are historical only.

Rollback: closing the unmerged implementation PR leaves main unchanged. A legal blocked state retains lease and capacity; release only after governed cancellation or Completion.

## Current reviewer and integrator actions

Reviewer: use specs/tasks/GZ-005.md current required-test section and the current
evidence/GZ-005/changed-files.md inventory. Review the final published Git source
and tree, all17 actual source checks and raw logs, full make527 nonempty JUnit
with zero failures/errors/skips, and the three additional API checks/contract JUnit.
Review authorization, complete approval snapshot binding, idempotency, compatibility,
reference constraints, typed WebAuthn and all synthetic/runtime limitations.
Historical reservation commands and failed drafts are provenance, not current proof.

Integrator: verify GZ-004 dependency, original lease and exact latest main baseline;
obtain independent review of the final source and applicable evidence archive.
Require latest same-head CI success, resolve every review thread after checking its
disposition, then merge with the expected reviewed head. Verify actual merged main
with its real source/parents/tree, local full make and actual main CI. Record the
actual code integration identity and perform separate legal Completion only after
post-main acceptance; never release a blocked lease or invent completed identities.

Current parser: python -m openapi_spec_validator contracts/openapi/common/openapi.yaml
Current API check: python specs/contracts/openapi/check_contract.py --base-ref 429a6566d81f128cb618c524ee8dc22faba1c0a4 --initial-baseline
Current contract tests: python -m pytest specs/contracts/openapi/test_contract.py -q
Current full gate: make verify TASK=GZ-005 BASE=429a6566d81f128cb618c524ee8dc22faba1c0a4 HEAD_REF=HEAD BRANCH=chore/GZ-005-openapi-baseline

Contract versions: OPENAPI-V1/API1.0.0/OAS3.1.1 and ERROR-CATALOG-V1/1.0.0.
Published source/actual outcomes are pending and must come from the real execution
records and PR; this handoff makes no current acceptance or V1 completion claim.

## Historical reservation records (unchanged)
# GZ-005 reservation handoff

Task GZ-005 / Issue #68 / WP-M0-03B / W2 / integration order 1.
Target base: 788e6f257d9052db81a8df793bf8b448a05011a1.
Reservation PR branch: chore/GZ-005-openapi-reservation.
Implementation claim: chore/GZ-005-openapi-baseline.
Actual tested source: 731ee84e52431864eeaf8f52680319ca1090a3fa.
Owner ElectricDogCN delegates routine decisions and merges to the coordinator.
Coordinator program-coordinator-agent; implementer openapi-contract-agent;
independent reviewer independent-openapi-review-agent; integrator integration-agent.
Lease: 2026-10-09T11:52:29Z through 2026-10-16T11:52:29Z, no automatic renewal.

Only own Task, Program status, Registry registration and evidence changed. Other
inherited statuses retain their original resolved values; old completed identities,
Ledger, POCs, application/governance code and contract bytes are unchanged.
All 15 source checks exit 0, full verify PASS, JUnit 328 zero failures/errors/skips.
Commands/exit codes and prior failures are in commands.txt and test-results/reservation-20261009/.
No API version has been implemented or frozen by this metadata reservation.
No shared paths. Exclusive contract paths: contracts/openapi/** and specs/contracts/openapi/**.

Reviewer must read the final committed archive and exact source logs. Integrator must
verify latest remote head CI, no unresolved threads, expected-head merge and post-main.
Then branch from the actual merged main, activate only GZ-005 and implement OPENAPI-V1 /
ERROR-CATALOG-V1 with HTTP examples and real validators. GZ-012 integrates contract CI.
Before merge, close this reservation PR to leave main unchanged; afterward cancel/block
own task using the governed lifecycle and release only its lease. Never rewrite old
completed tasks or the append-only Ledger. Real API correctness and POCs remain pending.

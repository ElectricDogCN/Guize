# GZ-003 Test Results

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Result: COMPLETED
Maintenance: OPS-003 / PR #44 validation in progress

## Original completion

GZ-003 remains completed. This maintenance does not reopen its Program/Foundation state, create a new Completion Ledger record, or rewrite the original completion identity.

## Reproduction — GZ-010 Reservation Gate #374

PR #42 exact Reservation HEAD: `f66f10d81ad44a52a2b9ffbcab338741d7783708`
Run: `33479774222`

Observed result:

- Task validation: PASS
- Project Readiness: PASS
- Program integrity/history/transitions/finalization/lifecycle: PASS
- Agent Coordination: PASS
- direct Schema validation: PASS, including `OK PROGRAM ACTIVATION: GZ-010 <- W1`
- Evidence / Scope / Secret / Spec Sync / static checks: PASS
- Governance tests: **258 PASS / 1 FAIL**

Sole failure:

`TestCheckSchemas.test_regular_program_task_activation_passes`

The copied fixture retained Program GZ-010=`reserved`, but `_activate_gz004()` replaced copied Active Work with only synthetic GZ-004, deleting the legitimate GZ-010 Lease and manufacturing a missing-Lease error.

PR #42 was closed unmerged because this failure would also have existed on post-merge main.

## OPS-003 repair candidate — Gate #375

PR #44 code/evidence candidate before canonical Completion Evidence refresh: `fbffb61b5ac1bdd630a53e71d19deca93b99d7de`
Run: `33480225903`

Functional change: preserve existing non-GZ-004 Active Work while keeping synthetic GZ-004 at list index 0.

Observed results:

- Governance tests: **259/259 PASS**
- `test_regular_program_task_activation_passes`: PASS
- Agent Coordination: PASS
- Markdown / Schema / Secret / Evidence / Evidence integrity / linkage / Scope / Spec Sync / parent-dir / CI static: PASS
- Program execution integrity: PASS
- Program history: PASS
- Program transitions: PASS
- Program Finalization: FAIL only because this completed-GZ-003 maintenance had not refreshed the four canonical Completion Evidence files

The fixture repair therefore fixes the actual regression without weakening the existing negative schema/coordination assertions.

## Current canonical Evidence refresh

`summary.md`, `commands.txt`, `handoff.md` and this test-results file now record OPS-003 while preserving original GZ-003 Completion merge `9e3a821ada292ac3ef69b7c059384d17f6530b48`.

A new exact-head Gate is required. The expected acceptable boundary is:

- Program Finalization PASS after canonical Evidence refresh;
- 259/259 governance tests PASS;
- every non-self-hosting check PASS;
- if the completed-GZ-003 lifecycle/scope guard rejects `tests/governance/test_check_schemas.py`, that single self-hosting rejection may be considered for explicitly documented Human/Integrator break-glass only after fresh exact-head review.

No latest-head Gate, review, merge or post-merge success is pre-claimed.

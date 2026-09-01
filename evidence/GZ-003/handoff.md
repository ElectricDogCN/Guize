# GZ-003 Handoff

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Status: COMPLETED
Maintenance: OPS-003 / PR #44 validation in progress

## Identity

- Original Task: GZ-003
- Original Issue: #10
- Original Completion PR: #11
- Original Completion merge: `9e3a821ada292ac3ef69b7c059384d17f6530b48`
- Current maintenance tracking: OPS-003 #43
- Current maintenance PR: #44
- Maintenance branch: `fix/GZ-003-schema-fixture-active-work`
- Maintenance base: `main@7c78c15097046d02ce04959b56c485ef76943c49`
- GZ-003 Program/Foundation state remains `completed`
- Shared paths: NONE

## Trigger

GZ-010 Reservation PR #42 correctly introduced a real GZ-010 `reserved` Program/Registry state, but Gate #374 exposed a stale schema-test fixture. The helper `_activate_gz004()` replaced all copied Active Work with synthetic GZ-004, deleting the legitimate copied GZ-010 Lease while leaving Program GZ-010 reserved. This manufactured the only failing test and would have made post-merge `main` red, so PR #42 was closed unmerged.

## Current maintenance files

Expected PR #44 diff after canonical Evidence refresh:

1. `tests/governance/test_check_schemas.py`;
2. `evidence/GZ-003/schema-fixture-active-work-repair.md`;
3. `evidence/GZ-003/summary.md`;
4. `evidence/GZ-003/commands.txt`;
5. `evidence/GZ-003/handoff.md`;
6. `evidence/GZ-003/test-results/README.md`.

No Program Plan, Active Work, Completion Ledger, Task Spec, production checker, Schema, workflow, Makefile, product/POC contract, business code, deployment, Secret, permission or production data is changed.

## Functional repair

`_activate_gz004()` now sets:

```python
active["tasks"] = [registry] + [
    item for item in active.get("tasks", []) if item.get("taskId") != "GZ-004"
]
```

This preserves synthetic GZ-004 at index 0, so all existing tests that intentionally mutate `active["tasks"][0]` keep their semantics. It also preserves every existing non-GZ-004 Active Work entry, eliminating fixture-created missing-Lease failures. Duplicate GZ-004 entries are excluded by task ID.

## Verification facts

- GZ-010 Reservation PR #42 / Gate #374: production lifecycle, Agent Coordination, direct Schema, Evidence, Scope and static checks passed; governance tests were 258 PASS / 1 fixture-generated FAIL.
- PR #44 Gate #375 before canonical Evidence refresh: **259/259 governance tests PASS**, including `test_regular_program_task_activation_passes`.
- Gate #375 Program integrity/history/transitions passed; Finalization failed only because this completed-GZ-003 maintenance had not refreshed the four canonical Completion Evidence files.
- This update refreshes those files while preserving original Completion identity `9e3a821...`.

Exact command and run identities are recorded in `evidence/GZ-003/commands.txt`; test details are in `evidence/GZ-003/test-results/README.md`.

## Remaining self-hosting boundary

After this Evidence refresh, a new exact-head Gate is mandatory. If Program Finalization becomes green but the completed-task lifecycle/scope guard rejects `tests/governance/test_check_schemas.py`, that is the same structural self-hosting boundary previously encountered for completed GZ-003 governance-test maintenance: the completed task cannot machine-authorize edits to the test surface needed to keep the Harness compatible.

Do not add a reusable checker bypass. A one-time Human Owner / Integrator break-glass may be considered only if:

- actual diff remains exactly the six maintenance files above;
- 259/259 governance tests pass;
- all production checkers and every Gate except the single completed-GZ-003 test-scope rejection pass;
- fresh exact-head review has no content/design blocker;
- unresolved threads are zero;
- exact HEAD is re-audited before merge;
- post-merge `main` Gate is fully green.

## Rollback

Before merge, close PR #44. After merge, if post-main Gate is red, use a dedicated Revert PR for the fixture line and maintenance Evidence; never rewrite `main`, modify Program/Ledger history, or weaken a guard.

## Next exact action

1. run a new exact-head Gate after this canonical Evidence refresh;
2. obtain fresh review of the same HEAD;
3. fix any new blocker;
4. if only the documented completed-task self-hosting scope red remains, perform exact-head Human/Integrator decision;
5. require post-merge `main` Gate success;
6. close OPS-003 #43;
7. rebuild GZ-010 Reservation from that new green main—do not reuse PR #42/base SHA.

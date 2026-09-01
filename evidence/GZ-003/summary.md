# GZ-003 Evidence Summary

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Status: COMPLETED
Maintenance status: OPS-003 IMPLEMENTED / MERGE VALIDATION PENDING

## Original delivery

GZ-003 was completed by PR #11 and merged as `9e3a821ada292ac3ef69b7c059384d17f6530b48`. Its Program/Foundation state remains `completed`; this maintenance does not reopen GZ-003, create a new Completion Ledger entry, or alter Program/Registry/Task state.

## Prior bootstrap maintenance

PR #35 previously removed stale governance-test assumptions discovered by the first GZ-004 Reservation attempt. That repair deliberately left no persistent lifecycle-checker bypass and was validated by a green post-merge `main` Gate before GZ-004 was rebuilt.

## OPS-003 trigger

After GZ-004 completed, GZ-010 Reservation PR #42 was created from green `main@7c78c15097046d02ce04959b56c485ef76943c49`.

Gate #374 / run `33479774222` proved the GZ-010 Reservation metadata itself was valid:

- Task / Project Readiness: PASS;
- Program integrity/history/transitions/finalization/lifecycle: PASS;
- Agent Coordination: PASS;
- direct Schema validation: PASS, including `OK PROGRAM ACTIVATION: GZ-010 <- W1`;
- Evidence / Scope / Secret / Spec Sync / static checks: PASS;
- governance tests: 258 PASS / 1 FAIL.

The sole failing test was `TestCheckSchemas.test_regular_program_task_activation_passes`. Its fixture copied the current Program/Registry snapshot, then `_activate_gz004()` replaced the copied Active Work with only synthetic GZ-004. With real GZ-010 reserved, this manufactured an inconsistent fixture: Program still said GZ-010 was reserved while its Lease had been deleted.

PR #42 was closed unmerged rather than overriding a failure that would also make post-merge `main` red. OPS-003 Issue #43 tracks the prerequisite repair.

## Current minimal repair — PR #44

Branch: `fix/GZ-003-schema-fixture-active-work`
Base: `main@7c78c15097046d02ce04959b56c485ef76943c49`

Functional change:

```python
active["tasks"] = [registry] + [
    item for item in active.get("tasks", []) if item.get("taskId") != "GZ-004"
]
```

This keeps synthetic GZ-004 at index 0 so existing mutation tests retain their semantics while preserving every real non-GZ-004 Active Work entry copied from the repository.

No production checker, Program Plan, Active Work, Completion Ledger, Task Spec, Schema, workflow, product/POC contract, business code, deployment, Secret, permission or production data is modified.

## Gate #375 facts

Exact code candidate before this canonical Evidence refresh: `fbffb61b5ac1bdd630a53e71d19deca93b99d7de`.

Gate #375 / run `33480225903` observed:

- governance tests: **259/259 PASS**;
- specifically, `test_regular_program_task_activation_passes`: PASS;
- Agent Coordination, Schema, Evidence, Evidence integrity, Scope, Secret, Spec Sync and CI static checks: PASS;
- Program Integrity composite: FAIL only because `check-program-plan-finalization.py` requires the four canonical GZ-003 completion Evidence files to be refreshed when a completed GZ-003 maintenance PR changes repository content.

This refresh satisfies that completion-Evidence maintenance requirement while preserving the original GZ-003 Completion identity `9e3a821ada292ac3ef69b7c059384d17f6530b48`.

## Remaining merge boundary

After this Evidence refresh, a new exact-head Gate must be run. If Finalization becomes green and the only remaining red condition is the known completed-GZ-003 self-hosting scope rejection for `tests/governance/test_check_schemas.py`, a one-time Human Owner / Integrator break-glass may be considered only after exact-head review. No machine exception may be added.

The post-merge `main` Governance Gate must be fully green before OPS-003 is closed and before GZ-010 Reservation is rebuilt.

No PR #44 merge or post-merge success is pre-claimed.

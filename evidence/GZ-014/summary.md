# GZ-014 Evidence Summary

## Identity

- Task: GZ-014
- Issue: #17
- Current PR: #27
- Branch: `chore/GZ-014-foundation-lifecycle-states`
- Base: `main@ef1048344aa082c678e5ef948dc7f62e5aa84510`
- Implementation merge: PR #26 / `ef1048344aa082c678e5ef948dc7f62e5aa84510`
- Post-merge main Gate: run #267, success
- Last validated repair HEAD before this Evidence refresh: `656c7b9c20cd18de2850caa46c734f46a0fc6c90`
- Governance Gate run #268 on that HEAD: success
- Current phase: `FOUNDATION_LIFECYCLE_MODEL_REPAIR`
- External blocker OPS-001 #20 remains open and gates only GZ-020.

## Problem

GZ-014 could not legally reach completion:

- the Program Plan Schema allowed Foundation states only `in_progress / blocked / completed`;
- the lifecycle guard permits completion only when the target-base state is `review` or `integration`.

Directly changing GZ-014 from `in_progress` to `completed` would therefore fail the accepted lifecycle gate. This was treated as a governance-state-machine defect, not bypassed.

## Repair

- Foundation Schema now allows `review` and `integration` in addition to the existing controlled states;
- unknown Foundation states remain rejected;
- ordinary Program Task state definitions are unchanged;
- a new regression test validates the current complete Program Plan with GZ-014 in `review` and `integration`;
- a history-aware temporary Git repository verifies Foundation `integration -> completed` with structured task-bound Evidence.

## Scope

PR #27 changes only:

- `specs/coordination/program-plan.schema.yaml`;
- `tests/governance/test_foundation_lifecycle_states.py`;
- `specs/tasks/GZ-014.md`;
- `specs/coordination/active-work.yaml`;
- `evidence/GZ-014/**`.

It does not change the current Program Plan state, lifecycle checker, transition checker, Workflow, Makefile, product requirements, business contracts/code, deployment, Secrets, permissions or production data. GZ-014 remains `in_progress` and its Lease remains active.

## Validation

Governance Gate run #268 succeeded on `656c7b9c20cd18de2850caa46c734f46a0fc6c90`, including Task, Readiness, Program integrity/history/transitions/finalization/lifecycle, Coordination, governance tests, Schema, Scope, Evidence and Spec Sync.

This Evidence update creates a later HEAD. The latest PR #27 Governance Gate and fresh Review remain the integration authority; run #268 cannot approve a later failed commit.

## Next sequence

1. latest PR #27 Gate succeeds and fresh Review has no blocker;
2. merge with `expected_head_sha` and verify post-merge `main` Gate;
3. transition GZ-014 `in_progress -> review` in a metadata-only PR;
4. transition `review -> integration` in a second metadata-only PR;
5. close Issue #17 as completed at the required completion-Gate stage;
6. transition `integration -> completed`, record PR #26 merge provenance, refresh structured Evidence and remove only the GZ-014 Lease;
7. verify post-completion `main` Gate before reserving GZ-004 or GZ-010.

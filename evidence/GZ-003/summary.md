# GZ-003 Evidence Summary

Task: GZ-003
Merge: 9e3a821ada292ac3ef69b7c059384d17f6530b48
Status: PASS

## Original delivery

GZ-003 was completed by PR #11 and merged as `9e3a821ada292ac3ef69b7c059384d17f6530b48`. Its Program/Foundation state remains `completed` and is not reopened by this maintenance.

## Bootstrap maintenance — PR #35

GZ-004 Reservation PR #34 exposed two stale governance-test assumptions:

1. copied schema fixtures assumed only GZ-014 needed a Task Spec and did not copy arbitrary current Active Work Task Specs;
2. the repository lifecycle smoke test hard-coded historical GZ-014 task/branch context whenever HEAD differed from `origin/main`.

GZ-004 explicitly forbids `tests/**`, so #34 was closed instead of widening a requirements task into governance maintenance.

## Final repair design

The final PR #35 design deliberately leaves **no persistent migration exception** in production governance code:

- `scripts/check-program-lifecycle-guards.py` is byte-for-byte restored to the target `main` version;
- `tests/governance/test_check_schemas.py` copies the exact/unique-suffixed Task Spec for GZ-014 plus every current Active Work task and clears the fixture Registry before the missing-Lease negative test;
- `tests/governance/test_program_lifecycle_guards.py` keeps all existing guard tests and changes only the repository smoke test so the wrapper derives affected tasks from the real Program/Registry/Task diff instead of injecting historical GZ-014 context;
- GZ-003 canonical Evidence is refreshed because completed-task finalization requires maintenance Evidence.

No Program Plan, Active Work, Completion Ledger, Task Spec, Schema, Workflow, Makefile, product requirement, business contract/code, deployment, Secret, permission, production data or downstream task activation is changed.

## Break-glass boundary

The normal PR lifecycle guard cannot authorize a completed GZ-003 task to edit `tests/governance/**`; that is the exact self-hosting defect being repaired. Therefore PR #35 is a one-time **human/Integrator break-glass merge candidate**, not a new machine exception.

Required conditions before any override merge:

- actual diff contains only the two governance tests plus the four GZ-003 canonical Evidence files;
- governance regression tests pass;
- every Gate other than the expected completed-task metadata-scope rejection passes;
- fresh Codex Review on the same exact HEAD reports no code/design blocker beyond that known bootstrap scope deadlock;
- exact-head human/Integrator re-review approves the diff;
- merge uses `expected_head_sha`;
- post-merge `main` Governance Gate must be fully green before GZ-004 is rebuilt.

Any additional failure, unexpected file, persistent checker exception, or new review finding blocks merge.

# GZ-003 Handoff

Task: GZ-003
Merge: 9e3a821ada292ac3ef69b7c059384d17f6530b48
Status: COMPLETED

## Identity

- Task：GZ-003
- Issue：#10
- Original PR：#11
- Original merge：`9e3a821ada292ac3ef69b7c059384d17f6530b48`
- Bootstrap maintenance PR：#35
- Branch：`chore/GZ-003-multi-agent-readiness`
- Target base：`main@3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`
- Status：GZ-003 remains `completed`

## Trigger

GZ-004 Reservation PR #34 exposed governance tests coupled to historical GZ-014 active state. GZ-004 forbids `tests/**`; #34 was closed and the compatibility defect was isolated to GZ-003 bootstrap maintenance.

## Exact seven-file maintenance scope

1. `scripts/check-program-lifecycle-guards.py`
2. `tests/governance/test_check_schemas.py`
3. `tests/governance/test_program_lifecycle_guards.py`
4. `evidence/GZ-003/summary.md`
5. `evidence/GZ-003/commands.txt`
6. `evidence/GZ-003/handoff.md`
7. `evidence/GZ-003/test-results/README.md`

No Program Plan、Active Work、Completion Ledger、Task Spec、Schema、Workflow、Makefile、GZ-004 metadata、requirement、business contract/code、deployment、Secret、permission or production data is modified.

## Validation history

- Gate #303：failed because completed-task finalization required refreshed GZ-003 Evidence.
- Gate #306：failed with `251 passed, 10 failed` because the maintenance branch contained stale whole-file test overwrites and incomplete Evidence refresh.
- Gate #312 on `d6253b00a5dfb22aa0aa5a85af69ba3499a801e1`：governance suite `259 passed, 0 failed, 0 skipped`; all reported gates passed except normal completed-task lifecycle scope.
- Gate #318 on `4562805eeac43ad8997c48f3ff4e3f95ed02a6eb`：all Governance Gate steps passed; fresh review then found mutable-base and empty-affected smoke-test design blockers.
- Gate #324 on `08cab050f9ed336d11f992ff0b6794e0a3bc9ae1`：governance suite `265 passed`; every reported Gate area except Program finalization passed. Finalization correctly required this Handoff to expose the original implementation merge in machine-readable form.

## Current repair

The one-time migration authorization is not a mutable base constant. The guard derives the authorization base from Git first-parent history: the first commit where GZ-014 is completed in Program and Task and absent from Active Work. Later `main` commits do not alter that first-completion history fact.

The migration additionally requires:

- exact Task `GZ-003`;
- `completed -> completed`;
- Program/Registry/Ledger/GZ-003 Task Spec unchanged;
- exact seven-file changed set.

The repository smoke test explicitly passes `--task GZ-003` and asserts `affectedTaskIds` contains GZ-003, so the migration predicate is exercised.

## Reviewer exact action

1. Review the latest PR #35 HEAD only.
2. Verify actual changed-file inventory is exactly the seven audited paths.
3. Verify history-derived authorization base remains the first GZ-014 completed/released snapshot after `main` advances.
4. Verify Program/Registry/Ledger/Task Spec equality and exact path equality remain mandatory.
5. Verify all old negative tests remain and the repository smoke test exercises GZ-003.
6. Require latest exact-head Governance Gate success and zero unresolved blockers.

## Integrator exact action

1. Re-fetch exact HEAD, seven-file inventory, Gate and fresh review.
2. Re-review exact HEAD before approval.
3. Merge with `expected_head_sha` only if all blockers are resolved.
4. Verify post-merge `main` Gate.
5. Close Issue #10 again.
6. Rebuild GZ-004 Reservation from the new green main; do not reuse PR #34.

## Rollback

Before merge, close #35. After merge, use a dedicated Revert PR; never directly rewrite `main`.

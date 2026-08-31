# GZ-003 Handoff

## Identity

- Task：GZ-003
- Issue：#10
- Original PR：#11
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

- #303：finalization Evidence failure.
- #306：stale overwrite; governance suite `251 passed, 10 failed`.
- #312：governance suite `259 passed, 0 failed, 0 skipped`; only normal completed-task lifecycle scope rejected test changes.
- #318 on `4562805eeac43ad8997c48f3ff4e3f95ed02a6eb`：all Governance Gate steps passed; fresh Review then found two current design blockers.

## Current repair

The one-time migration authorization is no longer a mutable base constant. The guard derives the authorization base from immutable Git first-parent history: the first commit where GZ-014 is completed in Program and Task and absent from Active Work. This history fact remains unchanged after `main` advances.

The migration additionally requires:

- exact Task `GZ-003`;
- `completed -> completed`;
- Program/Registry/Ledger/GZ-003 Task Spec unchanged;
- exact seven-file changed set.

The repository smoke test now explicitly passes `--task GZ-003` and asserts `affectedTaskIds` contains GZ-003, so the migration predicate is actually exercised instead of succeeding on an empty affected set.

## Reviewer exact action

1. Review latest #35 HEAD only.
2. Verify Git-history-derived authorization base cannot move when `main` advances.
3. Verify exact seven-file equality and unchanged Program/Registry/Ledger/Task Spec.
4. Verify repository smoke test exercises GZ-003 migration path.
5. Verify all old negative tests remain.
6. Require exact-head Gate success and zero unresolved blockers.

## Integrator exact action

1. Re-fetch exact HEAD, seven-file inventory, Gate and fresh review.
2. Re-review exact HEAD before approval.
3. Merge with `expected_head_sha` only if all blockers resolved.
4. Verify post-merge `main` Gate.
5. Close Issue #10 again.
6. Rebuild GZ-004 Reservation from the new green main; do not reuse PR #34.

## Rollback

Before merge, close #35. After merge, use a dedicated Revert PR; never directly rewrite `main`.

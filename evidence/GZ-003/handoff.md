# GZ-003 Handoff

## Identity and baseline

- Task：GZ-003
- Issue：#10
- Original implementation PR：#11
- Maintenance PR：#35
- Branch：`chore/GZ-003-multi-agent-readiness`
- Maintenance target base：`main@3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`
- Work Package：`WP-M0-05`
- Risk：high
- Coordination mode：bootstrap
- Integration strategy：merge

## Roles

- Coordinator/Implementer：current Agent operating under ElectricDogCN authorization
- Independent Reviewer：Codex/GitHub review
- Integrator：ElectricDogCN-authorized exact-head integration after all gates and findings

GZ-003 was merged by PR #11 as `9e3a821ada292ac3ef69b7c059384d17f6530b48` and remains completed.

## Post-completion bootstrap maintenance — PR #35

### Trigger

GZ-004 Reservation PR #34 exposed governance-test compatibility defects when the first ordinary Program Task became active. GZ-004 forbids `tests/**`, so #34 was closed rather than widening the requirements task scope.

### Validation history

- Gate #303：failed because completed-task finalization required refreshed GZ-003 Evidence.
- Gate #306：failed with `251 passed, 10 failed` because the maintenance branch contained stale whole-file test overwrites and incomplete Evidence refresh.
- Gate #312 on `d6253b00a5dfb22aa0aa5a85af69ba3499a801e1`：governance suite `259 passed, 0 failed, 0 skipped`; all reported gates passed except lifecycle scope, which correctly rejected a normal completed GZ-003 from changing governance tests.

### Exact current maintenance scope

Seven files only:

1. `scripts/check-program-lifecycle-guards.py`
2. `tests/governance/test_check_schemas.py`
3. `tests/governance/test_program_lifecycle_guards.py`
4. `evidence/GZ-003/summary.md`
5. `evidence/GZ-003/commands.txt`
6. `evidence/GZ-003/handoff.md`
7. `evidence/GZ-003/test-results/README.md`

No Program Plan state, Active Work lease, Completion Ledger, Task Spec, Schema, Workflow, Makefile, GZ-004 metadata, requirement, business contract/code, deployment, Secret, permission or production data is modified.

### Functional change

`tests/governance/test_check_schemas.py` is rebuilt from current `main`, preserves explicit Foundation fixtures and all negative assertions, copies Task Specs for current Active Work tasks, and isolates the missing-Lease negative case by clearing copied Registry entries first.

`tests/governance/test_program_lifecycle_guards.py` is rebuilt from current `main`; the repository smoke test lets `run-program-lifecycle-gate.py` derive affected tasks from the actual diff. All current completion, identity, Foundation and negative tests remain.

`check-program-lifecycle-guards.py` adds no general completed-task maintenance mode. It adds one fixed-base GZ-003 self-hosting exception that succeeds only when Program Plan, Active Work, Completion Ledger and GZ-003 Task Spec are unchanged and the changed-file set is exactly the seven files above. The fixed base is `3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`, so the exception automatically becomes unusable after this migration advances `main`.

Focused tests prove the exception rejects a wrong base, extra paths, Program/Registry/Ledger drift and Task Spec drift.

## Reviewer exact action

1. Review the latest PR #35 HEAD, not #303/#306/#312 historical heads.
2. Confirm actual changed-file inventory is exactly the seven audited paths.
3. Confirm the one-time exception requires the exact fixed base, completed→completed GZ-003, unchanged Program/Registry/Ledger/Task Spec and exact path equality.
4. Confirm it cannot apply after `main` advances and cannot apply to any other Task.
5. Confirm both governance test files preserve all current negative assertions.
6. Require latest exact-head Governance Gate success and zero unresolved blockers.

## Integrator exact action

1. Re-fetch latest HEAD, seven-file inventory, Gate and fresh review.
2. Re-review the exact HEAD before approval.
3. Merge with `expected_head_sha` only if all blockers are resolved.
4. Verify the immediate post-merge `main` Governance Gate; the migration exception must no longer be reusable on later bases.
5. Close Issue #10 again and rebuild GZ-004 Reservation from that exact green `main`.

## Rollback

Before merge, close PR #35 and retain its branch/history. After merge, create an independent revert branch and PR. Because the migration exception is fixed to the pre-merge base, any rollback must itself be reviewed as a new governance action; never directly rewrite `main`.

# GZ-004 Completion Rollback Verification

Status: COMPLETED-STATE ROLLBACK CONTRACT

Task: GZ-004
Completion merge: `2ab9bc5faab8397bb8b02549d0e8a489a3ef1024`
Pre-completion review-state base: `846b140c9115959708fe1cdf214f643d8d55f75e`
Implementation merge: `1ff9fe355f6a4ca9d36d0d82bafd416c56d91b96`
Original review lease expiry: `2026-09-07T06:30:00Z`

## 1. Do not use the reservation rollback procedure

The old reservation rollback (`completed/planned` confusion, deleting Task/Evidence artifacts, removing the lease) is invalid after GZ-004 Completion. Git/PR/Evidence history and the ordinary Completion Ledger are permanent audit records and must not be deleted or rewritten.

## 2. Normal post-completion correction path

For defects discovered after Completion, prefer a new correction/repair task or a task-bound post-completion Evidence repair. Preserve:

- GZ-004 Program status `completed`;
- the immutable GZ-004 Completion Ledger record;
- Reservation PR #36, Implementation PR #37, Review PR #38 and Completion PR #39 history;
- all existing Evidence history.

This is the path used for the late PR #39 P2 Evidence findings.

## 3. Exceptional lifecycle rollback to review

A direct `completed -> review` regression is not currently an ordinary allowed transition: repository Program history and Completion Ledger guards intentionally fail closed on completed-task regression. Therefore **do not blindly `git revert` PR #39** and do not remove or rewrite the Completion Ledger.

If a true lifecycle rollback to `review` is required, first create a separate governance-approved repair that explicitly authorizes and tests that rollback transition. Only after that control-plane change is reviewed and merged may the task metadata be restored to review.

The restored review state must use:

- Program status: `review`;
- Task Spec status: `review`;
- Active Work status: `review`;
- `agentRole: reviewer`;
- branch: `chore/GZ-004-requirements-baseline` or a separately approved repair branch;
- baseSha anchored to the implementation merge or other explicitly approved review base;
- the original GZ-004 Requirement/Module/path claims and `integrationOrder: 1`;
- no shared paths.

## 4. Lease safety

Never restore an expired historical lease.

The pre-completion lease was:

- acquiredAt: `2026-08-31T06:30:00Z`
- expiresAt: `2026-09-07T06:30:00Z`

If an exceptional rollback is executed before that expiry and the governance-approved rollback mechanism explicitly permits reuse, verify the lease is still non-expired at execution time.

If rollback occurs at or after the expiry, acquire a **fresh** review lease:

- `acquiredAt`: actual rollback reservation time;
- `expiresAt`: no more than 168 hours after `acquiredAt`;
- preserve high-risk role separation and all original path claims.

A rollback PR that would reintroduce an expired lease must fail and must not be merged.

## 5. Downstream dependency safety

Before any lifecycle rollback, inspect Program Plan and Active Work for tasks that consume GZ-004. If any downstream task has already been reserved, activated or completed, do not regress GZ-004 underneath it. Stop or cancel affected active downstream work using its own lifecycle rules, or use a forward correction task instead.

At the time this Completion Evidence repair started, GZ-010 remained `planned`, GZ-005 remained `planned`, and Active Work was empty.

## 6. Issue state

Issue #14 was closed with `state_reason=completed` before successful Completion Gate #369, as required by the lifecycle guard.

- If PR #39 had been aborted before merge, Issue #14 had to be reopened immediately.
- Because PR #39 merged and post-completion Gate #370 passed, Issue #14 correctly remains closed during Evidence-only repair.
- Only an explicitly approved lifecycle rollback that makes GZ-004 incomplete again may reopen Issue #14.

## 7. Verification commands

Replay current completed-state integrity:

```bash
git show --no-patch --format='%H %s' 2ab9bc5faab8397bb8b02549d0e8a489a3ef1024
python scripts/check-project-readiness.py
python scripts/check-program-plan-integrity.py --base-ref 846b140c9115959708fe1cdf214f643d8d55f75e
python -m pytest tests/governance/ -q
git diff --name-only 846b140c9115959708fe1cdf214f643d8d55f75e 2ab9bc5faab8397bb8b02549d0e8a489a3ef1024
```

Expected result for the completed baseline: all repository governance checks pass, Active Work is empty, and the GZ-004 Completion Ledger record remains present and immutable.

## 8. Human approval boundary

Any disaster/lifecycle rollback remains a human-approved operation. Never push directly to `main`, rewrite history, delete Completion Evidence, or weaken guards to force a rollback through.

# GZ-014 Foundation Review Handoff

## Identity

- Task: GZ-014
- Issue: #17
- Branch: `chore/GZ-014-foundation-review`
- Base: `main@44b66f699e333af9781779dc18665bad0850d9c4`
- Phase: `review`
- Program Wave: FOUNDATION
- Risk: high
- Integration Order: 1
- Lease expires: `2026-09-07T00:00:00Z`

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`
- Current role: Reviewer

## Transition scope

- Program Foundation GZ-014: `in_progress -> review`;
- Task Spec: `in_progress -> review`;
- Active Work: `in_progress -> review`;
- agentRole: `implementer -> reviewer`;
- branch/base: current review branch and `44b66f699e333af9781779dc18665bad0850d9c4`.

No implementation file, lifecycle rule, Program task definition, completion provenance, Issue state, Lease or downstream task is changed.

## Reviewer exact action

1. Read the actual latest diff and exact-head Governance Gate.
2. Verify only GZ-014 Foundation status changed in Program Plan.
3. Verify Task/Registry status, branch, baseSha, role, Lease, dependencies, paths and contract sets are consistent.
4. Re-check PR #21/#22/#26/#27 history, failure Evidence and post-merge Gates.
5. Verify Foundation completion is not yet claimed and Issue #17 remains open.
6. Submit a review conclusion only for the latest HEAD.

## Integrator exact action

1. Require latest Gate success and zero unresolved blocker threads.
2. Re-read actual changed-file inventory.
3. Record authorized re-review against exact HEAD.
4. Merge using `expected_head_sha`.
5. Verify post-merge `main` Governance Gate.
6. Create a separate `review -> integration` branch from that merge.

## Completion boundary

GZ-014 cannot complete from this PR. Completion remains blocked until review enters green `main`, integration enters green `main`, Issue #17 is closed with `state_reason=completed` at the required stage, structured Evidence is refreshed, PR #26 merge provenance is recorded and only the GZ-014 Lease is removed.

## Rollback

Before merge, close the PR and retain Evidence. After merge, revert the metadata transition through a dedicated PR; do not directly update or rewrite `main`.

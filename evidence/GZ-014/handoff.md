# GZ-014 Test-Repair Branch Reservation Handoff

## Identity

- Task: GZ-014
- Issue: #17
- Current phase: `ACTIVE_BRANCH_RESERVATION`
- Authoritative work branch: `chore/GZ-014-test-repair-reservation-v2`
- Reservation base: `main@903754295e4a0393638c82aa851c3ada8cd507fb`
- Risk: high
- Program Wave: `FOUNDATION`
- Integration Order: 1
- Lease expires: `2026-09-05T01:59:00Z`

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Historical chain

- Reservation PR #18 merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.
- Program Plan PR #21 merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.
- Lifecycle hardening PR #22 merged as `903754295e4a0393638c82aa851c3ada8cd507fb`.
- Main Gate #237 passed production lifecycle/control checks but failed one repository integration test because the test treated `origin/main == HEAD` as the audit base.
- PR #23 was closed without merge after Review found no prior branch reservation, stale Handoff identity, and a fixed GZ-014 test attribution.

## Reservation output

This PR may only:

1. move the existing GZ-014 Task/Registry branch and base to `chore/GZ-014-test-repair-reservation-v2@903754295e4a0393638c82aa851c3ada8cd507fb`;
2. preserve Foundation/Task/Registry status `in_progress`;
3. preserve role separation, Lease and governance path claims;
4. refresh this Handoff and task-bound Reservation Evidence.

No Program Plan change is required. It must not modify `tests/**`, `scripts/**`, product requirements, business contracts, business code, deployment, Secrets, permissions or data.

## Implementation exact action

After this Reservation PR merges:

1. fast-forward the same branch to the Reservation merge commit so it contains updated `main`;
2. append only the test implementation and task-bound Evidence commits;
3. change the repository integration test to invoke the same no-Task lifecycle wrapper semantics as Governance Gate:
   - PR checkout validates `origin/main...HEAD` and derives affected tasks from the diff;
   - main push validates the complete push/merge range and derives affected tasks from that diff;
   - no future unrelated main push is hardcoded to GZ-014;
4. keep production Foundation `baseSha`, path ownership and fail-closed guards unchanged;
5. open a separate Implementation PR and obtain exact-head Gate, Review, expected-head merge and post-merge main Gate.

## Reviewer exact action

Reservation Review:

1. verify the diff contains only Task Spec, Active Work, this Handoff and task-bound Reservation Evidence;
2. verify no Program Plan, test, script or business path changed;
3. verify Foundation/Task/Registry remain `in_progress`;
4. verify branch, baseSha, roles, paths, Lease and Handoff are identical across Task and Registry;
5. verify no implementation is included.

Implementation Review:

1. verify the test calls the wrapper without fixed Task ID;
2. verify production guards are unchanged;
3. verify PR and post-merge main Gates pass on exact SHAs;
4. verify Handoff and Evidence are refreshed to the implementation merge.

## Integrator exact action

1. merge this Reservation only after exact-head Gate and no-finding Review;
2. record the Reservation merge SHA;
3. fast-forward this same branch to that merge commit before implementation;
4. do not create Foundation Completion until implementation and post-merge main Gates succeed;
5. Foundation Completion remains a separate narrow PR, releases only GZ-014 and leaves the ordinary completion ledger unchanged.

## Known blocker

OPS-001 #20 remains open and only gates final GZ-020 release.

## Rollback

Before merge, close the PR. After merge, revert the Task/Registry/Handoff reservation in a dedicated PR; never reset or directly push `main`.
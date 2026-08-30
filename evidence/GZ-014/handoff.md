# GZ-014 Test-Repair Reservation Handoff

## Identity

- Task: GZ-014
- Issue: #17
- Current phase: `BLOCKED_RESERVATION`
- Reservation branch: `chore/GZ-014-test-repair-reservation-v2`
- Registered implementation branch: `chore/GZ-014-post-merge-test-repair-v2`
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

- GZ-014 Reservation PR #18 merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.
- Program Plan implementation PR #21 merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.
- Lifecycle hardening PR #22 merged as `903754295e4a0393638c82aa851c3ada8cd507fb`.
- Main Gate #237 passed every production lifecycle/control step but failed one repository integration test because the test used `origin/main == HEAD` as its audit base.
- PR #23 attempted the test repair but was closed without merge after independent Review found no prior Reservation, stale Handoff identity, and a test that fixed the task ID to GZ-014 on every future main push.

## Reservation output

This phase may only:

1. change the GZ-014 Foundation/Task/Registry status to `blocked`;
2. register `chore/GZ-014-post-merge-test-repair-v2` and base `903754295e4a0393638c82aa851c3ada8cd507fb`;
3. preserve the existing role separation, Lease and governance path claims;
4. refresh this Handoff and add task-bound Reservation Evidence.

It must not change test code, production lifecycle scripts, product requirements, business contracts, business code, deployment, Secrets, permissions or data.

## Implementation exact action

After the Reservation PR merges:

1. move the registered implementation branch to the Reservation merge commit so the branch contains the updated `main` baseline;
2. change only GZ-014 Foundation/Task/Registry from `blocked` to `in_progress` and `agentRole` to `implementer`;
3. replace the fixed-task integration test with an environment-independent wrapper invocation:
   - PR checkout uses `origin/main` and derives affected tasks from the exact PR diff;
   - main push uses the merge first parent / push-before range and derives affected tasks from the complete diff;
   - no test hardcodes GZ-014 for future unrelated main pushes;
4. keep production `validate_foundation_claims`, exact `baseSha`, path ownership and fail-closed behavior unchanged;
5. update `evidence/GZ-014/post-merge-test-repair.md` with real commands and results;
6. open a separate implementation PR, run the exact HEAD Gate, obtain independent Review, merge with expected HEAD, and verify the push-to-main Gate.

## Reviewer exact action

For the Reservation PR:

1. verify the diff contains only Program Plan, Task Spec, Active Work, this Handoff and task-bound Evidence;
2. verify no `tests/**`, `scripts/**` or business path changed;
3. verify Program Foundation, Task and Registry are all `blocked`;
4. verify branch, baseSha, roles, paths, Lease and Handoff are identical across Task/Registry;
5. verify the implementation branch did not exist with implementation commits before Reservation merge.

For the later implementation PR:

1. verify the integration test calls the same lifecycle wrapper semantics as Governance Gate and does not force GZ-014;
2. verify production guards were not weakened;
3. verify PR and post-merge main Gates both pass;
4. verify the exact reviewed SHA is the merged SHA.

## Integrator exact action

1. merge the Reservation only after exact-head Gate success and no-finding Review;
2. record the actual Reservation merge SHA;
3. update/move the registered implementation branch to that merge commit before implementation;
4. do not begin Foundation Completion until the implementation PR and its post-merge main Gate both succeed;
5. Foundation Completion must be a separate PR that updates only GZ-014 completion metadata and fresh Evidence, releases only the GZ-014 Lease, and leaves the ordinary completion ledger unchanged.

## Known blocker

OPS-001 #20 remains open. It blocks final GZ-020 release, not this repository-only repair.

## Rollback

Before Reservation merge, close the PR and retain history. After merge, use a dedicated Revert PR to restore the prior GZ-014 Task/Registry/Foundation state; never directly push or reset `main`.
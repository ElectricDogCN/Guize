# GZ-014 Evidence Summary

## Identity

- Issue: #17
- Original Reservation PR: #18 / merge `d731ce09fbf2535948bc1864490539d06ce1f139`
- Program Plan implementation PR: #21 / merge `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`
- Lifecycle hardening PR: #22 / merge `903754295e4a0393638c82aa851c3ada8cd507fb`
- Failed post-merge main Gate: run #237
- Closed unreserved repair attempt: PR #23, not merged
- Current clean Reservation: PR #24
- Current authoritative branch: `chore/GZ-014-test-repair-reservation-v2`
- Current Reservation base: `main@903754295e4a0393638c82aa851c3ada8cd507fb`
- Last fully successful PR #24 HEAD before P1 remediation: `8efc71cf21ca0a6c9543722b89d8cad37cc71018`
- Governance Gate run #245 on that HEAD: `success`
- External release blocker: OPS-001 #20 remains open
- Current phase: `ACTIVE_BRANCH_RESERVATION_REVIEW`

## Objective

Keep GZ-014’s Program lifecycle, Task Spec, Active Work Lease, Git history and Evidence consistent while repairing the single repository-integration test failure exposed after PR #22 merged. The repair must not weaken production lifecycle checks, fabricate a Foundation completion, or start downstream work before the active GZ-014 lease is correctly re-reserved and completed.

## Delivered control plane retained

- canonical Program Plan and Requirement/Module/Public Contract ownership;
- GZ-004～GZ-020 and POC-001～POC-010 DAG;
- Reservation, Active Work Lease, Wave/risk/path control and role separation;
- Program Integrity, History, Transitions, Finalization and Lifecycle Guard gates;
- ordinary-task Completion Ledger and separate Foundation completion model;
- exact push-range validation and no-task main-push task derivation;
- task-bound cancellation/completion Evidence;
- dependency completion ordering and reservation-base ancestry;
- live GitHub Ruleset verification for the final release blocker.

No accepted control has been removed or made advisory.

## Current incident and recovery

PR #22 merged as `903754...`. Its post-merge `main` run #237 passed the production lifecycle, Program, Coordination, Schema, Scope, Evidence and Spec Sync steps, but failed the governance-test step. The failed test invoked a GZ-014-specific lifecycle audit while `origin/main == HEAD`, which is not the same context as the no-task main-push wrapper used by Governance Gate.

PR #23 attempted to repair the test, but was closed without merge because it combined a new branch/Lease migration with implementation, left the canonical Handoff stale and still hard-coded GZ-014 for future unrelated main pushes.

PR #24 is the clean Reservation-only recovery. It keeps Program Foundation, Task and Registry status `in_progress`, moves Task/Registry to branch `chore/GZ-014-test-repair-reservation-v2` at base `903754...`, refreshes canonical Handoff/Evidence and contains no test or script implementation.

## Current validation and review state

- PR #24 Governance Gate run #245 succeeded on exact HEAD `8efc71cf21ca0a6c9543722b89d8cad37cc71018`.
- Fresh Codex Review identified five P1 documentation/control-plane consistency findings:
  1. ensure Program/Task/Registry state is synchronized;
  2. restore a resumable canonical Handoff;
  3. require Task/Registry `baseSha` to advance to the actual Reservation merge before implementation;
  4. limit the test-repair prohibition to PR #24 rather than the lifetime task;
  5. refresh canonical Summary, Commands, Changed Files and Test Results.
- Task-boundary remediation commit `06eaad8a3ecf2d4af5d667dc19fd53b8354bf689` and subsequent Evidence commits address those findings.
- The resulting latest HEAD requires a new Governance Gate and fresh exact-HEAD Review. No previous Gate or Review is reused as approval.

## Exact next sequence

1. Finish PR #24 with latest-head Gate success, fresh no-finding Review, zero unresolved threads and expected-head merge.
2. Record the actual PR #24 merge SHA.
3. Before any test commit, fast-forward the authoritative branch to that merge and update **both** Task and Registry `baseSha` to the merge SHA.
4. Submit a separate Implementation PR containing only the minimal `tests/governance/**` repair and fresh task-bound Evidence.
5. Require exact-head Implementation Gate, Review, expected-head merge and a successful post-merge `main` Gate.
6. Submit a separate narrow Foundation Completion PR that records the actual repair merge, marks GZ-014 completed and removes only its Lease.
7. Only after GZ-014 completion may the canonical first-stage Program tasks be reserved.

## Remaining boundaries

- PR #24 is not approved until its latest HEAD is green and independently re-reviewed.
- `main` remains red at run #237 until the independent test-repair Implementation is merged and revalidated.
- GZ-014 remains `in_progress`; no Completion or Lease release is allowed in PR #24.
- GZ-004, GZ-010 and all downstream tasks remain blocked.
- OPS-001 #20 remains open and gates only final GZ-020 production release.
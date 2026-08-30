# GZ-014 Foundation Completion Handoff

## Identity

- Task: `GZ-014`
- Issue: #17, closed with `state_reason=completed`
- Branch: `chore/GZ-014-foundation-completion-v3`
- Completion base: `main@8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`
- Phase: `completed` candidate
- Program Wave: `FOUNDATION`
- Risk: `high`
- Integration Order: `1`
- Foundation completion identity: `PR-32` / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`
- Integration history: PR #29 / `c26fc712e050dba4e83c9af022fd25b8f7e84d6d`
- Earlier implementation/repair history: PR #26 / `ef1048344aa082c678e5ef948dc7f62e5aa84510`
- PR #32 post-merge Governance Gate: run #293 = `PASS`

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Completion scope

- Program Foundation GZ-014: `integration -> completed`;
- Task Spec GZ-014: `integration -> completed`;
- Foundation provenance: `completionRef: PR-32`, `mergeCommit: 8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`;
- Active Work: remove only GZ-014 Lease while preserving policy;
- Issue #17: preserve closed/completed state;
- Evidence: refresh Summary, Commands, Changed Files, Test Results and this Handoff.

PR #29 / `c26fc712...` is retained only as integration history. PR #26 / `ef104834...` is retained only as earlier implementation/repair history. The ordinary Program Task completion ledger is unchanged because GZ-014 is a Foundation task.

## Verified predecessor history

1. PR #28 moved GZ-014 into review; its post-merge main Gate passed.
2. PR #29 moved GZ-014 into integration and merged as `c26fc712e050dba4e83c9af022fd25b8f7e84d6d`.
3. PR #32 repaired completion-readiness regression tests without completing the Foundation.
4. PR #32 exact HEAD `9adf9a135fabe4581285a945b4b434d9302e9a80` passed Governance Gate run #292.
5. PR #32 merged as `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
6. PR #32 post-merge main Governance Gate run #293 completed with `PASS`.
7. `8221fd0f...` strictly descends from the prior GZ-014 integration base and its commit message identifies GZ-014 / PR #32.

## Reviewer exact action

1. Read PR #33 latest diff and latest Governance Gate.
2. Confirm the target base has GZ-014 Foundation, Task and Registry in `integration`.
3. Verify only the GZ-014 Foundation status/provenance, GZ-014 Task, GZ-014 Lease and five task-bound Evidence files changed.
4. Verify `completionRef: PR-32` and `mergeCommit: 8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
5. Verify PR #29/c26 and PR #26/ef are history only.
6. Verify Issue #17 is closed/completed.
7. Verify Active Work policy and ordinary `task-completions.yaml` are unchanged.
8. Verify Evidence contains GZ-014, PR #32, full 8221 SHA, Foundation completion semantics, real commands, exit status and PASS/COMPLETED.
9. Submit a conclusion only for the latest exact HEAD.

## Integrator exact action

1. Require latest Gate success and zero unresolved blocker threads.
2. Re-fetch actual changed-file inventory and exact PR HEAD.
3. Confirm fresh approval targets the same HEAD.
4. Merge with `expected_head_sha`.
5. Verify post-merge `main` Governance Gate succeeds.
6. Re-read Program Plan, Active Work, Task Spec and Issue #17 from `main`.
7. Only after those checks may GZ-004 and GZ-010 Reservation PRs begin.

## Rollback

Before merge, close PR #33. After merge, revert through a dedicated PR that restores GZ-014 to `integration` and restores only its previous Lease; do not directly update or rewrite `main`. Preserve Issue/PR/Evidence history.

Handoff result: `COMPLETED CANDIDATE`; final completion remains conditional on PR #33 exact-head and post-merge `PASS` results.

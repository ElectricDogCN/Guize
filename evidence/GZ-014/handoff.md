# GZ-014 Foundation Integration Handoff

## Identity

- Task: GZ-014
- Issue: #17
- Branch: `chore/GZ-014-foundation-integration`
- Base: `main@b15ed0dd907c59a69f1fd178907f648fef2b880a`
- Phase: `integration`
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
- Current role: Integrator

## Transition scope

- Program Foundation GZ-014: `review -> integration`;
- Task Spec: `review -> integration`;
- Active Work: `review -> integration`;
- agentRole: `reviewer -> integrator`;
- branch/base: integration branch and `b15ed0dd907c59a69f1fd178907f648fef2b880a`.

No implementation, lifecycle rule, completion provenance, Issue state, Lease or downstream task changes.

## Integrator exact action

1. Read actual latest diff and exact-head Governance Gate.
2. Verify only GZ-014 Foundation status changed in Program Plan.
3. Verify Task/Registry status, branch, baseSha, role, Lease, dependencies, paths and contract sets.
4. Re-check PR #26 implementation merge and all later post-merge Gates.
5. Confirm Issue #17 remains open and completion is not claimed.
6. Record approval only for latest HEAD, merge with expected SHA, then verify post-merge main Gate.

## Completion exact inputs

After integration enters green main, the Completion PR must:

- start from that exact main commit;
- close Issue #17 with `state_reason=completed` when required by lifecycle Gate;
- change Foundation and Task to `completed`;
- set `completionRef: PR-26` and `mergeCommit: ef1048344aa082c678e5ef948dc7f62e5aa84510`;
- remove only the GZ-014 Active Work entry, preserving policy;
- leave ordinary `task-completions.yaml` unchanged for this Foundation;
- refresh structured Summary, Commands, Test Results and Handoff containing Task ID, implementation merge SHA, executed commands, exit code 0 and explicit PASS/COMPLETED.

## Rollback

Before merge, close the PR and retain Evidence. After merge, revert the integration metadata through a dedicated PR; do not directly update or rewrite `main`.

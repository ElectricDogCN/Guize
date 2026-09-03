# OPS-006 Registration Handoff

## Current phase

Clean Registration candidate construction from a verified green main. OPS-006 is not reserved, not activated and not implemented. No Active Work Lease exists.

## Identity

- Task: OPS-006
- Issue: #52
- Contract: PROGRAM-TASK-REGISTRATION-V1
- Exact target base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
- Base validation: Governance Gate #446 / run `33736578549` = SUCCESS
- Branch: `chore/OPS-006-task-registration-r2`
- Superseded PR: #53, closed without merge
- Current candidate PR / HEAD / run: pending creation
- Wave / Integration Order: W1 / 3
- Risk: medium
- Depends On: GZ-014 completed
- Requirement: REQ-V1-0010
- Module: MOD-GOV
- Shared paths: NONE

## Roles

- Human Owner: `ElectricDogCN`
- Coordinator: `program-coordinator-agent`
- Implementer: `governance-lifecycle-agent`
- Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`

## Scope boundary

The Registration commit may contain only the canonical Program Plan, `specs/tasks/OPS-006.md` and `evidence/OPS-006/**`. It must introduce exactly one planned task and one append-only GZ-020 dependency. Active Work, Completion Ledger, Checker, test and Workflow implementations must remain unchanged.

OPS-007 already repaired terminal Wave occupancy. Project Readiness must now pass on the real Registration tree; a repeated W1 capacity failure is no longer an acceptable classification.

## Exact next action

1. create one commit from the exact target base;
2. verify one commit ahead, zero behind and exactly thirteen changed files;
3. open a Draft PR and observe its exact-head Governance Gate;
4. refresh canonical Evidence with actual exit codes, test count, source SHA, generated merge SHA and run/job IDs;
5. request independent exact-head review;
6. do not merge until every unexpected failure and review blocker is resolved and the Human Owner / Integrator decision is recorded against the final HEAD.

## Forbidden next action

- do not create Active Work before Registration merges;
- do not start implementation;
- do not reuse or force-push the closed PR #53 branch;
- do not modify PR #51 or #48 content;
- do not increase capacity or add a reusable bypass;
- do not claim pending commands or future phases as successful.

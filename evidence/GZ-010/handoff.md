# GZ-010 Implementation Handoff

Task: GZ-010
Status: IN_PROGRESS

## Identity

- Issue: #15
- Program task: GZ-010
- Wave / order: W1 / 2
- Work Package: WP-M0-04
- Risk: medium
- Implementation base: `main@74ab9d53f29834fda37dcbd726fd58f997f8f21a`
- Reservation PR: #45
- Implementation branch: `chore/GZ-010-poc-program-baseline`
- Lease: `2026-09-01T08:27:00Z` → `2026-09-08T08:27:00Z`
- Produced contract: `POC-PROTOCOL-V1`

## Roles

- Human Owner: `ElectricDogCN`
- Coordinator: `program-coordinator-agent`
- Implementer: `poc-program-agent`
- Reviewer: `independent-poc-program-review-agent`
- Integrator: `integration-agent`

## Verified predecessor

- Reservation v2 exact HEAD `88d0a0d84cce83eaa183b547225ab7ff71074208` passed Gate #381 and fresh Codex review.
- PR #45 merged as `74ab9d53f29834fda37dcbd726fd58f997f8f21a`.
- Post-Reservation main Gate #382 / run `33492832222`: PASS.

## Implemented scope

- canonical `specs/poc/program.yaml` manifest;
- strict Program/Plan/Protocol/Result Index schemas;
- policy, resource catalogue and sample catalogue;
- result index with ten `not_started` entries;
- POC-001～POC-010 plans mapped exactly to Program Plan;
- plan/result/execution templates;
- fail-closed `check_program.py`;
- `test_program.py` with 19 baseline/negative tests;
- human `poc/README.md`.

All plans remain `planned/not_started`; commands/raw outputs/actual measurements/results/decisions/reviewers remain empty. GZ-010 creates no `evidence/POC-*` result.

## Validation already executed

- POC Program validator: exit code 0 / PASS.
- POC Program tests: 19/19 PASS.
- Program patch is expected to contain only GZ-010 `reserved -> in_progress`.
- Repository exact-head Gate/Review are still required and override isolated pre-push validation if they find a problem.

## Reviewer exact action

1. Review only PR #46 latest HEAD.
2. Verify lifecycle metadata all say GZ-010 `in_progress`, base `74ab9d53...`, agentRole `implementer`.
3. Verify Program Plan has no unrelated hunk.
4. Verify every POC plan mirrors Program Plan POC/Task/Requirement/Module/Wave/Risk/Evidence/Dependency facts.
5. Verify all ten plans/results remain unexecuted and contain no result claim.
6. Review Validator for bypasses in unknown references, result prefill, sample approval, secret detection and high/critical scheduling.
7. Verify no forbidden path, `evidence/POC-*`, business contract/code, deployment or Secret change exists.
8. Treat any exact-head Gate failure or new Finding as blocker.

## Integrator exact action

1. Require latest exact-head Governance Gate result and zero unresolved blocker threads.
2. Require fresh exact-head independent Review.
3. Re-fetch actual changed files, Program patch, Registry and Task Spec.
4. Merge only with `expected_head_sha` after re-audit.
5. Require post-merge main Gate success.
6. Only then move GZ-010 to review/completion lifecycle; do not activate POC Tasks or W2 Tasks in the same PR.

## Rollback

Before merge, close PR #46 and preserve branch/Evidence. After merge but before Completion, use a dedicated governed revert/correction PR to restore a valid lifecycle state and remove only GZ-010 implementation outputs as required. Never rewrite `main`, delete immutable Completion history, or fabricate POC results.

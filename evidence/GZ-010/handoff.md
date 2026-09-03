# GZ-010 Implementation Activation Handoff

Task: GZ-010
Status: IN_PROGRESS activation candidate

## Identity

- Issue: #15
- Program task: GZ-010
- Wave / order: W1 / 2
- Work Package: WP-M0-04
- Risk: medium
- Activation base: `main@74ab9d53f29834fda37dcbd726fd58f997f8f21a`
- Registered branch: `chore/GZ-010-poc-program-baseline`
- Reservation PR: #45
- Reservation merge: `74ab9d53f29834fda37dcbd726fd58f997f8f21a`
- Reservation post-main Governance Gate: #382 / run `33492832222` = PASS
- Lease: `2026-09-01T08:27:00Z` → `2026-09-08T08:27:00Z`
- Produced contract: `POC-PROTOCOL-V1` (implementation output; not produced by this Activation)

## Roles after Activation

- Human Owner: `ElectricDogCN`
- Coordinator: `program-coordinator-agent`
- Implementer: `poc-program-agent`
- Reviewer: `independent-poc-program-review-agent`
- Integrator: `integration-agent`
- Active role: `implementer`

## Activation scope

This PR performs only the lifecycle transition required before implementation:

- Program GZ-010: `reserved -> in_progress`;
- Active Work GZ-010: `reserved -> in_progress`;
- Registry `baseSha` becomes the Reservation merge SHA;
- Registry/Task `agentRole` becomes `implementer`;
- Task Spec front matter mirrors those fields;
- `activation.md` and this registered Handoff describe the transition.

It does **not** create or modify:

- `specs/poc/**`;
- `poc/README.md`;
- `evidence/POC-001/**` ～ `evidence/POC-010/**`;
- experiment commands, measurements, results or decisions;
- business contracts/code, deployment, Secrets, permissions or production data.

Historical PR #46 is closed/unmerged and is not current PASS/merge evidence.

## Implementer exact action after Activation merge

1. Confirm the Activation merge commit is present on `main` and its post-merge Governance Gate is fully SUCCESS.
2. Rebuild/reset `chore/GZ-010-poc-program-baseline` from that exact green `main` commit.
3. Implement only the reserved paths:
   - `specs/poc/**`
   - `poc/README.md`
   - `evidence/GZ-010/**`
4. Establish the POC Program Schema/index/Validator before any plan execution semantics.
5. Keep every POC plan and result index in `planned/not_started`; do not create `evidence/POC-*` results.
6. Run and record the task-specific Validator/tests and the repository governance commands.
7. Hand off the final exact implementation candidate to `independent-poc-program-review-agent`.

## Reviewer exact action for this Activation

1. Review the current Activation HEAD only.
2. Verify the PR contains exactly the five metadata/Evidence files declared by the PR body.
3. Verify Program Plan changes only GZ-010 `reserved -> in_progress`.
4. Verify Active Work changes only status/baseSha/agentRole.
5. Verify Task Spec body is unchanged from Reservation v2 and only its front matter status/baseSha/agentRole changed.
6. Verify this Handoff no longer contains stale Reservation instructions.
7. Verify no POC implementation or experiment result is present.
8. Inspect the exact-head Governance Gate and all current review threads.

## Integrator exact action

1. Re-fetch exact HEAD, five-file list, Program/Registry/Task patches, Gate, review and threads.
2. Merge only the reviewed expected HEAD under the explicitly documented metadata-only exception if the sole machine failure remains the known Agent Coordination Program Plan-path self-hosting mismatch.
3. Verify post-merge `main` Governance Gate is fully SUCCESS.
4. Do not rebuild or merge implementation work until that post-main Gate is green.

## Rollback

Before Activation merge: close the PR and leave GZ-010 reserved on main. After Activation merge but before implementation: use a dedicated correction/revert PR to restore the valid prior GZ-010 lifecycle state and lease metadata. Never rewrite `main` or delete governance/Evidence history.

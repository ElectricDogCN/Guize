# GZ-014 Clean Test-Repair Branch Reservation V2

## Trigger

- Lifecycle hardening merge: PR #22 / `903754295e4a0393638c82aa851c3ada8cd507fb`
- Failed post-merge `main` Governance Gate: run #237
- Closed first repair attempt: PR #23, not merged
- Current clean Reservation: PR #24

## Reservation objective

Move the existing active GZ-014 Foundation Lease from the ended repair branch to one authoritative work branch and verified base before any new test implementation is committed. This is a lifecycle-metadata Reservation, not the test implementation.

## Declared context

- Branch: `chore/GZ-014-test-repair-reservation-v2`
- Reservation base: `903754295e4a0393638c82aa851c3ada8cd507fb`
- Program Foundation status: `in_progress`
- Task Spec status: `in_progress`
- Active Work status: `in_progress`
- Implementer: `governance-hardening-agent`
- Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Lease expiry: `2026-09-05T01:59:00Z`

Because all three statuses remain `in_progress`, PR #24 does not modify `specs/coordination/program-plan.yaml`.

## Reservation-only scope

The canonical declared PR #24 file set is:

- `specs/coordination/active-work.yaml`;
- `specs/tasks/GZ-014.md`;
- `evidence/GZ-014/handoff.md`;
- `evidence/GZ-014/test-repair-reservation-v2.md`;
- `evidence/GZ-014/summary.md`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/changed-files.md`;
- `evidence/GZ-014/test-results/README.md`.

This Reservation PR must not modify `tests/**`, `scripts/**`, product requirements, business contracts/code, deployment, Secrets, permissions or data.

The prohibition is phase-specific. After Reservation merge and base synchronization, the separate Implementation PR may use the already registered lifetime scope `tests/governance/**` for the minimal repository integration-test repair.

## Post-merge base rule

After PR #24 merges and before any test implementation commit:

1. record the actual Reservation merge SHA;
2. fast-forward the authoritative branch to that merge;
3. update both `specs/tasks/GZ-014.md` and `specs/coordination/active-work.yaml` `baseSha` to the actual merge SHA;
4. preserve the same branch, roles, risk, path claims, Lease, Handoff and integration order;
5. append the minimal test repair and fresh Evidence only after those changes are present.

A later Implementation PR that still uses `903754...` as its Task/Registry `baseSha` must fail review.

## Validation history

- PR #24 Gate #245 succeeded on `8efc71cf21ca0a6c9543722b89d8cad37cc71018`.
- Fresh Review then found five P1 canonical state/Evidence issues.
- The latest remediated HEAD is newer than Gate #245 and must receive a new Gate and fresh Review.

## Evidence authority

This file is a Reservation-specific supplement. The canonical current status is maintained in:

- `evidence/GZ-014/summary.md`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/changed-files.md`;
- `evidence/GZ-014/test-results/README.md`;
- `evidence/GZ-014/handoff.md`.

No success is inferred from this note alone.
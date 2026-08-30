# GZ-014 Clean Test-Repair Reservation V2

## Trigger

- Lifecycle hardening merge: PR #22 / `903754295e4a0393638c82aa851c3ada8cd507fb`
- Post-merge main Gate: run #237
- Failed first repair attempt: PR #23, closed without merge

## Reservation objective

Pause GZ-014 as `blocked`, establish one authoritative implementation branch and base SHA, and refresh Handoff before any test implementation is committed.

## Declared implementation context

- Branch: `chore/GZ-014-post-merge-test-repair-v2`
- Base: `903754295e4a0393638c82aa851c3ada8cd507fb`
- Implementer: `governance-hardening-agent`
- Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Lease expiry: `2026-09-05T01:59:00Z`

## Reservation-only scope

Expected changed paths:

- `specs/coordination/program-plan.yaml` — only GZ-014 Foundation status `in_progress -> blocked`;
- `specs/coordination/active-work.yaml` — only the GZ-014 entry status/branch/base/agentRole;
- `specs/tasks/GZ-014.md` — only current lifecycle context and Reservation specification;
- `evidence/GZ-014/handoff.md`;
- `evidence/GZ-014/test-repair-reservation-v2.md`.

No `tests/**`, `scripts/**`, product requirement, business contract, business code, deployment, Secret, permission or data change is permitted.

## Evidence status

This file records intent and observed history only. It does not claim the Reservation Gate, Review or merge has succeeded. Those results must be obtained from the exact latest PR HEAD.
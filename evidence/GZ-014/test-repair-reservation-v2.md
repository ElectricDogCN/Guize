# GZ-014 Clean Test-Repair Branch Reservation V2

## Trigger

- Lifecycle hardening merge: PR #22 / `903754295e4a0393638c82aa851c3ada8cd507fb`
- Post-merge main Gate: run #237
- Failed first repair attempt: PR #23, closed without merge

## Reservation objective

Move the existing active GZ-014 Foundation Lease from the ended repair branch to one authoritative work branch and verified base before any new test implementation is committed.

## Declared context

- Branch: `chore/GZ-014-test-repair-reservation-v2`
- Base: `903754295e4a0393638c82aa851c3ada8cd507fb`
- Status: `in_progress`
- Implementer: `governance-hardening-agent`
- Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Lease expiry: `2026-09-05T01:59:00Z`

## Reservation-only scope

Expected changed paths:

- `specs/coordination/active-work.yaml` — only the GZ-014 branch/baseSha;
- `specs/tasks/GZ-014.md` — current branch/base and Reservation specification;
- `evidence/GZ-014/handoff.md`;
- `evidence/GZ-014/test-repair-reservation-v2.md`.

The Program Plan remains byte-for-byte unchanged with GZ-014 Foundation `in_progress`.

No `tests/**`, `scripts/**`, product requirement, business contract, business code, deployment, Secret, permission or data change is permitted.

## Post-merge branch rule

After this Reservation merges, the same branch must be fast-forwarded to the Reservation merge commit before any implementation commit. The later Implementation PR must contain the test repair and fresh Evidence only after that updated-main baseline is present.

## Evidence status

This file records intent and observed history only. It does not claim the Reservation Gate, Review or merge has succeeded. Those results must be obtained from the exact latest PR HEAD.
# GZ-014 Changed Files

## Current PR

- PR: #24
- Phase: clean active-branch Reservation V2
- Base: `main@903754295e4a0393638c82aa851c3ada8cd507fb`
- Branch: `chore/GZ-014-test-repair-reservation-v2`

## Declared latest file set

The remediated PR #24 is expected to contain only:

- `specs/coordination/active-work.yaml` — move only the GZ-014 active branch/base while preserving status, roles, paths, Lease and integration order;
- `specs/tasks/GZ-014.md` — align current branch/base, Reservation-only boundary and required post-merge base update;
- `evidence/GZ-014/handoff.md` — current resumable Handoff with historical validation chain;
- `evidence/GZ-014/test-repair-reservation-v2.md` — Reservation-specific supplemental record;
- `evidence/GZ-014/summary.md` — canonical current phase and boundaries;
- `evidence/GZ-014/commands.txt` — actual operations, results and pending checks;
- `evidence/GZ-014/changed-files.md` — this inventory;
- `evidence/GZ-014/test-results/README.md` — Gate/review history and current validation state.

## Explicitly unchanged

- `specs/coordination/program-plan.yaml` remains byte-for-byte unchanged with GZ-014 Foundation `in_progress`;
- no `tests/**` file changes in this Reservation PR;
- no `scripts/**` file changes in this Reservation PR;
- no business requirement, contract, code, deployment, Secret, permission or production-data change;
- no Foundation completion and no Active Work lease release.

## Verification rule

The Integrator must obtain the actual latest changed-file list from GitHub immediately before approval. The PR is merge-blocked if any path differs from the eight declared paths above. A later Implementation PR may use the already registered `tests/governance/**` lifetime scope only after the Reservation merge is present and Task/Registry `baseSha` is updated to that actual merge commit.
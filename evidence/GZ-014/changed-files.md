# GZ-014 Changed Files

## Current PR

- PR: #25
- Phase: lifecycle wrapper repair implementation
- Base: `main@bb22b4cd8662e6c1ed7d3b63255098d8a74237c1`
- Branch: `chore/GZ-014-test-repair-reservation-v2`
- Last validated implementation HEAD: `8914773e6f4c10558ece8cc4f668ced25d0d54c2`
- Gate: run #260, success

## Declared file set

PR #25 is expected to contain only:

- `scripts/run-program-lifecycle-gate.py` — preserve original task-derivation function and map external blockers by explicit ID;
- `tests/governance/test_program_lifecycle_guards.py` — repository integration and no-recursion regression tests;
- `specs/tasks/GZ-014.md` — implementation scope/root-cause/validation update and normalized `./Makefile` path expression;
- `specs/coordination/active-work.yaml` — implementation branch/base synchronization retained from the clean Reservation;
- `evidence/GZ-014/summary.md`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/changed-files.md`;
- `evidence/GZ-014/test-results/README.md`;
- `evidence/GZ-014/handoff.md`.

## Explicitly unchanged

- `scripts/check-program-lifecycle-guards.py` remains unchanged;
- `.github/workflows/governance-gate.yml` remains unchanged;
- `Makefile` remains unchanged;
- `specs/coordination/program-plan.yaml` remains unchanged with GZ-014 Foundation `in_progress`;
- product requirements, business machine contracts, business code, deployment, Secrets, permissions and production data remain unchanged;
- no Foundation completion and no Active Work Lease release occur in PR #25.

## Verification rule

The Integrator must obtain GitHub’s actual latest changed-file list immediately before approval. The PR is blocked if any path is outside the nine paths above or if the latest exact-head Gate fails. Evidence-only changes after run #260 require a new Gate and fresh Review.
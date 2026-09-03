# OPS-006 Registration Rollback Verification

## Before merge

Close the PR; no `main` rollback is required.

```bash
git fetch origin main
git diff --exit-code origin/main -- specs/coordination/active-work.yaml specs/coordination/task-completions.yaml
git diff --name-only origin/main...HEAD
```

Expected OPS-006 pre-merge result: Registry and Completion Ledger have no diff, and every changed path is Program Plan, `specs/tasks/OPS-006.md`, or `evidence/OPS-006/**`.

## After an explicitly approved Registration merge, before Reservation

Use a separate Revert PR. Verify that it removes exactly the OPS-006 Program entry, the final GZ-020 dependency tail entry, the OPS-006 Task Spec and OPS-006 Evidence while preserving all other Program data.

```bash
git revert <OPS-006-registration-merge-sha>
python scripts/check-schemas.py
python scripts/check-program-plan-integrity.py --base-ref origin/main
make verify TASK=OPS-006 BASE=origin/main HEAD_REF=HEAD BRANCH=revert/OPS-006-registration
```

No force push, history rewrite, direct `main` edit or deletion of unrelated Evidence is an acceptable OPS-006 rollback.
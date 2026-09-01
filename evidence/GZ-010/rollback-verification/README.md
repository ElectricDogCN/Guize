# GZ-010 Reservation Rollback Verification

Task: GZ-010
Status: RESERVATION ROLLBACK CONTRACT

Reservation base: `7c78c15097046d02ce04959b56c485ef76943c49`

## Before Reservation merge

Close the Reservation PR without merging and retain the branch/history for audit. No Program or `main` rollback is required.

## After Reservation merge, before implementation output

Use a dedicated Revert/cleanup PR that changes only GZ-010 lifecycle artifacts:

1. `specs/coordination/program-plan.yaml`: GZ-010 `reserved -> planned`;
2. `specs/coordination/active-work.yaml`: remove only GZ-010;
3. remove `specs/tasks/GZ-010.md` if the repository lifecycle checker permits Task removal for a reverted reservation;
4. remove only GZ-010 Reservation Evidence if required by the same audited revert;
5. preserve all GZ-004 Completion history/Ledger, all Foundation state and every other Program/POC task.

Do not execute this rollback after `specs/poc/**` or `poc/README.md` implementation output has been merged. Once implementation exists, use the task's normal lifecycle/correction process instead of pretending the task was never started.

## Verification commands

Before approving a reservation rollback PR:

```bash
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python scripts/run-program-lifecycle-gate.py --base-ref origin/main --head-ref HEAD --task GZ-010 --branch-name chore/GZ-010-reservation
python scripts/run-agent-coordination-gate.py --task GZ-010 --base-ref origin/main --head-ref HEAD --branch-name chore/GZ-010-reservation
python -m pytest tests/governance/ -q
```

Expected rollback state: GZ-010 `planned`, no GZ-010 Active Work lease, no implementation output, and all unrelated Program/Ledger history unchanged.

Never push directly to `main`, rewrite history, modify another task, or weaken a guard to force rollback.

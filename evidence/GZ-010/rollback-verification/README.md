# GZ-010 Reservation v2 Rollback Verification

Task: GZ-010

## Before merge

Close the Reservation PR and do not merge it. `main` remains unchanged and GZ-010 remains `planned`.

## After merge but before implementation

Use a dedicated revert/correction PR. Do not rewrite `main` and do not delete unrelated history.

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git checkout -b revert/GZ-010-reservation-v2
# Revert only the Reservation v2 merge commit through normal Git review.
# Verify GZ-010 returns to planned, its Active Work entry is removed,
# and only GZ-010 Reservation Task/Evidence files are reverted.
make verify
```

If any `specs/poc/**` implementation has already started, do not use this Reservation-only rollback procedure; open a separately scoped lifecycle correction task instead.

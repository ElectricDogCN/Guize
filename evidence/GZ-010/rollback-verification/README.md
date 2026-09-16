# GZ-010 Completion Rollback Verification

Task: GZ-010
Completion PR: #63
Base: `3a11c5f639717993f51a26c5b5970701570fe367`
Validation status: NOT_EXECUTED; executable rehearsal below, no fabricated result.

## Before merge

Closing PR #63 without merging leaves main unchanged: GZ-010 remains in review, its existing Active Work entry remains, and no GZ-010 completion record is added. The already merged POC planning implementation is retained. Do not use the historical Reservation rollback, which returned the task to planned and assumed implementation had not begun.

## Isolated restoration rehearsal

Run from the clean candidate repository. This modifies only a newly created detached temporary worktree; it does not commit, push, reset the working branch, contact production or rewrite history. The assertion proves that restoring the exact completion-only paths recovers the complete target-base tree while leaving the POC implementation intact.

```bash
set -euo pipefail
BASE=3a11c5f639717993f51a26c5b5970701570fe367
CANDIDATE=$(git rev-parse HEAD)
git merge-base --is-ancestor "$BASE" "$CANDIDATE"
git diff --exit-code "$BASE" "$CANDIDATE" -- specs/poc poc/README.md .github/workflows
TMP=$(mktemp -d)
rmdir "$TMP"
git worktree add --detach "$TMP" "$CANDIDATE"
trap 'git worktree remove --force "$TMP"' EXIT
git -C "$TMP" restore --source="$BASE" --staged --worktree -- \
  specs/coordination/program-plan.yaml \
  specs/coordination/active-work.yaml \
  specs/coordination/task-completions.yaml \
  specs/tasks/GZ-010.md \
  evidence/GZ-010
RESTORED=$(git -C "$TMP" write-tree)
EXPECTED=$(git rev-parse "$BASE^{tree}")
test "$RESTORED" = "$EXPECTED"
printf 'completion_restoration=PASS candidate=%s restored_tree=%s\n' "$CANDIDATE" "$RESTORED"
```

Record real stdout, exit code and candidate SHA after execution. This is a mechanical restoration test, not a claim that a post-completion ledger deletion is policy-approved.

## After an authorized merge

Freeze downstream activation if the post-main Gate fails. The Integrator must identify the actual PR #63 merge, retain it and its parents, and prepare a dedicated reviewed correction or Revert PR. A mechanical preview uses `git revert --no-commit -m 1 "$COMPLETION_MERGE"` only on a fresh recovery branch after verifying that the SHA is the actual two-parent completion merge; the variable is deliberately not assigned an invented future SHA here.

Run the current lifecycle, ledger, scope and full verification on that proposed recovery. If append-only completion rules reject reopening/removal, do not waive the guard or force the revert: preserve historical records and obtain the Human Owner's approved forward-correction decision. No automatic rollback, production migration, deletion of experiments or direct main update is authorized by this document.

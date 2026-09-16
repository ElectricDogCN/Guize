# GZ-010 Nonterminal Review Repair — Recovery Boundary

Task: GZ-010
PR: #63
Result: NEEDS_REVIEW
Target: `3a11c5f639717993f51a26c5b5970701570fe367`
Worktree rehearsal: NOT_EXECUTED in the current local environment

## Withdraw the unsafe terminal proposal, not a completed main task

The candidate keeps GZ-010 at review and uses the target's identical Program, Active Work and Completion Ledger objects. It does not append a completion record or remove a lease. Only Task/Evidence differ from main. This removes the proposed irreversible completion transition from this PR; it does not repair or bypass the general completed-task recovery limitation.

The prior Git Data equality result on b1ca is retained in Git at `035e786022f7995724e0c3b99a86a9356c51e1cf`. It proved byte restoration only. Applying that old tree after a completion merge would remove an immutable record and regress completed; it is not an approved or validated recovery procedure. Do not run that old completion-revert instruction on main.

## Before merge

Abandoning or closing this PR leaves main unchanged in review with its original lease. No revert, reset, Issue-state change or ledger write is needed. No such close action is claimed here.

## Isolated rehearsal for this nonterminal documentation proposal

This script is restricted to the unchanged target and a clean exact candidate. It refuses any coordination or implementation difference, restores only Task/Evidence in a newly created detached worktree, and compares the entire tree to the target. It does not push, move a branch or remove completion records. The clone attempt failed before checkout, so this shell execution is NOT claimed.

```bash
set -euo pipefail
BASE=3a11c5f639717993f51a26c5b5970701570fe367
CANDIDATE=$(git rev-parse HEAD)
test -z "$(git status --porcelain)"
git merge-base --is-ancestor "$BASE" "$CANDIDATE"
git diff --exit-code "$BASE" "$CANDIDATE" -- \
  specs/coordination specs/poc poc/README.md .github scripts tests
TMP=$(mktemp -d)
rmdir "$TMP"
git worktree add --detach "$TMP" "$CANDIDATE"
trap 'git worktree remove --force "$TMP"' EXIT
git -C "$TMP" restore --source="$BASE" --staged --worktree -- \
  specs/tasks/GZ-010.md evidence/GZ-010
RESTORED=$(git -C "$TMP" write-tree)
EXPECTED=$(git rev-parse "$BASE^{tree}")
test "$RESTORED" = "$EXPECTED"
git -C "$TMP" diff --cached --exit-code "$CANDIDATE" -- specs/coordination
printf 'review_document_restoration=PASS candidate=%s restored_tree=%s\n' \
  "$CANDIDATE" "$RESTORED"
```

A tree match alone is not a full governance rehearsal. For a complete rehearsal, create an explicitly simulation-only local commit in the detached worktree and run the Task Spec validation against the candidate base, recording real output and exit codes. Never push that simulation commit or present it as a main merge. Pending completion acceptance is not fulfilled by this nonterminal test.

## After a documentation-only merge

Only after a real authorized PR #63 documentation merge exists, resolve its actual two parents and verify that its coordination files equal the first parent. On a separate local recovery branch, preview reverting only that documentation merge (`git revert --no-commit -m 1 "$DOCUMENTATION_MERGE"`). Check that the resulting diff contains only Task/Evidence and all coordination files remain unchanged, then use the existing independent review and validation process before any recovery merge.

This recipe must stop if main has moved into a later lifecycle state, a lease has expired, a conflict exists, or other tasks/coordination metadata would change. It is not an automatic production rollback. No future merge hash or successful execution is invented.

## Future completion remains blocked

Before GZ-010 may become completed, a concrete forward recovery that preserves immutable completion records and prevents improper downstream execution must be documented and actually tested against existing guards. That result does not exist in this checkpoint. No new status, policy exception, workflow or controller is introduced here; the safe current disposition is review, not a claimed reversible completion.

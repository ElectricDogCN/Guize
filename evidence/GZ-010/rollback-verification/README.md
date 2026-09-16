# GZ-010 Completion Rollback Verification

Task: GZ-010
Completion PR: #63
Base: `3a11c5f639717993f51a26c5b5970701570fe367`
Object-restoration result: PASS for exact candidate `b1ca9864759c325f12addf2b06b0ab22a81f9d9c`
Local worktree rehearsal: NOT_EXECUTED; pending acceptance item retained

## Executed isolated Git-object restoration

Using the authorized GitHub Git Data API, a tree was constructed on candidate root `0313cb874843a839519435cea81a1a6773892afb`. Only these exact entries from the target base were restored:

- `specs/coordination/program-plan.yaml`, mode `100644`, blob `27edc2750e1567b6764581e43d0d49de8de54970`.
- `specs/coordination/active-work.yaml`, mode `100644`, blob `2e9859fc504800f64ad6284933cb0b59ae411f39`.
- `specs/coordination/task-completions.yaml`, mode `100644`, blob `0607130b53d58c5bbb177725b991dae2dac45115`.
- `specs/tasks/GZ-010.md`, mode `100644`, blob `a523bfeb7e2579c5f4df1cceb590da7a7d6219a2`.
- `evidence/GZ-010`, mode `040000`, tree `c4c2b070d728826ee2036d62de4ea5ae45484e23`.

Observed API result:

```text
returned_tree=5725e4f352fa420dbac260247947dca5cf482c4f
expected_base_tree=5725e4f352fa420dbac260247947dca5cf482c4f
equality=PASS
```

These object identities were read from the real candidate commit and the complete target tree. The operation returned the exact full target root, demonstrating content restoration and preservation of all unrelated implementation content. No restoration commit was created and no branch/ref moved. This does not claim execution of shell commands, worktree creation/cleanup, a production recovery, or permission to erase completion history after merge.

## Before merge

Closing PR #63 leaves main unchanged: GZ-010 remains review, its existing lease remains, and its completion record has not been added. The merged POC planning implementation stays intact. The old Reservation rollback that assumed no implementation exists is not applicable.

## Local worktree rehearsal still to execute

The existing script remains a pending Task Spec acceptance item. The separate object-equality check above is additional evidence, not a fabricated PASS for this shell script. The general Codex execution request did not start because a repository environment is missing; see response `5694080113` on PR #63.

Run on the clean final candidate. It only changes a newly created detached temporary worktree, does not push or reset any branch, and verifies the exact restored tree:

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

Record actual stdout, exit and tested SHA after execution. Do not change the pending status based on a different operation.

## After an authorized merge

If post-main validation fails, freeze downstream activation. Identify the actual two-parent PR #63 merge and retain it and its parents. Prepare a separate reviewed correction/revert on a recovery branch; a mechanical preview can use `git revert --no-commit -m 1 "$COMPLETION_MERGE"` only after resolving the real merge SHA. No future merge SHA is fabricated here.

Run current lifecycle, ledger, scope and full verification on the proposed recovery. If append-only completion rules reject reopening/removal, do not force a revert or waive the guard: preserve records and obtain the Human Owner's approved forward-correction decision. No direct main update, production migration, history deletion or automatic rollback is authorized by this document.

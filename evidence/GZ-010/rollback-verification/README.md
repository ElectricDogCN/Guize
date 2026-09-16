# GZ-010 Nonterminal Review Repair — Recovery Rehearsal

Task: GZ-010
PR: #63
Result: NEEDS_REVIEW
Target: `3a11c5f639717993f51a26c5b5970701570fe367`
Execution status: procedure supplied; a successful full-rehearsal result is not yet claimed

## State and Issue recovery

This PR keeps GZ-010 at review. Program, Active Work and Completion Ledger are identical to the target; no completion record is appended or lease removed. Only Task/Evidence documents differ.

Issue #15 was reopened through the authorized GitHub connection at `2026-09-16T15:52:58Z`; returned state was `open`, reason `reopened`, and `closed_at` was null. Issue comment `5700433671` records the correction. This follows the abort/reopen precedent in `evidence/GZ-004/rollback-verification/README.md`. If this nonterminal PR is abandoned, closed or merged, keep Issue #15 open until an actually validated completion is authorized. Do not leave an external completed signal after withdrawing completion.

Abandoning this PR before merge needs no Git revert: main is unchanged. The old completed-candidate tree restoration, retained at `035e786022f7995724e0c3b99a86a9356c51e1cf`, is not a permitted post-completion ledger rollback.

## Full local rehearsal of this documentation recovery

Run the entire block from the clean, fully fetched candidate after installing the existing `requirements-governance.txt`. It creates one isolated detached worktree, restores only Task/Evidence, commits that restoration locally as an explicitly labelled simulation, and runs the actual lifecycle, history, coordination, scope, named `make verify`, planning tests and skip audit against the **candidate commit**, not the old main base. It leaves the original checkout and all remote refs untouched.

Commands and stdout/stderr go to individually named logs outside the checkout. The EXIT trap removes only the created worktree and verifies cleanup; logs and the JUnit report remain in the printed directory even on failure. A failed step terminates the rehearsal with its nonzero exit. A simulation commit is not a real PR or merge and must never be pushed.

```bash
set -euo pipefail
BASE=3a11c5f639717993f51a26c5b5970701570fe367
BRANCH=chore/GZ-010-poc-program-baseline
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
CANDIDATE=$(git rev-parse HEAD)
test -z "$(git status --porcelain)"
git merge-base --is-ancestor "$BASE" "$CANDIDATE"
git diff --exit-code "$BASE" "$CANDIDATE" -- \
  specs/coordination specs/poc poc/README.md .github scripts tests
OUT=$(mktemp -d "${TMPDIR:-/tmp}/gz010-review-recovery.XXXXXX")
WT="$OUT/worktree"
printf 'candidate=%s\nbase=%s\nlogs=%s\n' "$CANDIDATE" "$BASE" "$OUT"
printf 'candidate=%s\nbase=%s\n' "$CANDIDATE" "$BASE" > "$OUT/identity.txt"
git worktree list --porcelain > "$OUT/worktrees-before.txt"
cleanup() {
  rc=$?
  trap - EXIT
  cd "$ROOT"
  if git worktree list --porcelain | grep -Fxq "worktree $WT"; then
    if ! git worktree remove --force "$WT" > "$OUT/cleanup.log" 2>&1; then
      rc=1
    fi
  fi
  git worktree list --porcelain > "$OUT/worktrees-after.txt"
  if ! cmp -s "$OUT/worktrees-before.txt" "$OUT/worktrees-after.txt"; then
    printf 'Worktree cleanup differs; inspect %s\n' "$OUT" >&2
    rc=1
  fi
  if [ "$(git rev-parse HEAD)" != "$CANDIDATE" ] ||
     [ -n "$(git status --porcelain)" ]; then
    printf 'Original checkout changed; inspect it before continuing.\n' >&2
    rc=1
  fi
  printf 'exit code: %s\nlogs: %s\n' "$rc" "$OUT" | tee "$OUT/result.txt"
  exit "$rc"
}
trap cleanup EXIT
step() {
  name=$1
  shift
  printf 'command:' > "$OUT/$name.log"
  printf ' %q' "$@" >> "$OUT/$name.log"
  printf '\n' >> "$OUT/$name.log"
  if "$@" >> "$OUT/$name.log" 2>&1; then rc=0; else rc=$?; fi
  printf '\nexit code: %s\n' "$rc" >> "$OUT/$name.log"
  cat "$OUT/$name.log"
  return "$rc"
}
step dependencies python -c 'import yaml, jsonschema, pytest; print("dependencies=PASS")'
step add-worktree git worktree add --detach "$WT" "$CANDIDATE"
step restore git -C "$WT" restore --source="$BASE" --staged --worktree -- \
  specs/tasks/GZ-010.md evidence/GZ-010
RESTORED=$(git -C "$WT" write-tree)
EXPECTED=$(git rev-parse "$BASE^{tree}")
test "$RESTORED" = "$EXPECTED"
step unchanged-coordination git -C "$WT" diff --cached --exit-code "$CANDIDATE" -- specs/coordination
step simulation-commit git -C "$WT" \
  -c user.name='Guize LOCAL-ONLY recovery rehearsal' \
  -c user.email='guize-rehearsal@example.invalid' \
  commit -m 'test(GZ-010): LOCAL-ONLY review-document recovery simulation; never push'
SIMULATION=$(git -C "$WT" rev-parse HEAD)
test "$(git -C "$WT" rev-parse HEAD^1)" = "$CANDIDATE"
test "$(git -C "$WT" rev-parse HEAD^{tree})" = "$EXPECTED"
printf 'simulation=%s\nrestored_tree=%s\n' "$SIMULATION" "$RESTORED" >> "$OUT/identity.txt"
cd "$WT"
export GITHUB_REPOSITORY=ElectricDogCN/Guize
export PYTHONDONTWRITEBYTECODE=1
unset GUIZE_GITHUB_API_URL
step task python scripts/check-task-file.py --task GZ-010
step lifecycle python scripts/run-program-lifecycle-gate.py \
  --base-ref "$CANDIDATE" --head-ref HEAD --task GZ-010 --branch-name "$BRANCH"
step history python scripts/check-program-plan-history.py \
  --base-ref "$CANDIDATE" --head-ref HEAD --task GZ-010 --branch-name "$BRANCH"
step coordination python scripts/run-agent-coordination-gate.py \
  --base-ref "$CANDIDATE" --head-ref HEAD --task GZ-010 --branch-name "$BRANCH"
step scope python scripts/run-task-scope-gate.py --task GZ-010 --base "$CANDIDATE"
step verify make verify TASK=GZ-010 BASE="$CANDIDATE" HEAD_REF=HEAD BRANCH="$BRANCH"
step planning-check python specs/poc/check_program.py
step planning-tests python specs/poc/test_program.py
step junit python -m pytest tests/governance/ -q -ra --junitxml="$OUT/governance.xml"
step skips python scripts/check-pytest-skips.py "$OUT/governance.xml" tests/governance/allowed-skips.txt
test -z "$(git status --porcelain)"
printf 'review_recovery=PASS candidate=%s simulation=%s restored_tree=%s\n' \
  "$CANDIDATE" "$SIMULATION" "$RESTORED" | tee "$OUT/verification.txt"
```

Retain `identity.txt`, each command log, `governance.xml`, `verification.txt` if produced, the before/after worktree lists and `result.txt`. A successful tree equality with a failed later check is an incomplete rehearsal, not overall PASS. The final successful marker and exit 0 must both exist. The simulation SHA identifies a local-only test subject; do not list it as a reachable remote production commit.

## After an authorized documentation-only merge

Resolve the actual PR #63 merge and its first parent. On a separate recovery branch preview `git revert --no-commit -m 1 "$DOCUMENTATION_MERGE"` only after verifying that the merge changed Task/Evidence alone and did not alter coordination files. Run the same lifecycle/history/coordination/scope and named make checks using the real pre-recovery main commit as base. Preserve review and main-merge approval. Stop on conflicts, changed lifecycle, expired lease or any unrelated change; this script is not an automatic rollback authorization.

## Future completion

No main merge or full local rehearsal is claimed by supplying these instructions. Before proposing completed again, the separate completion prerequisites remain: successful final-candidate checks and an actually tested forward recovery preserving immutable completion records. The nonterminal rehearsal above does not certify a post-completion status regression or ledger deletion.

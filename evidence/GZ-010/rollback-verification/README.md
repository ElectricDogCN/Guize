# GZ-010 Nonterminal Review Repair — Recovery Rehearsal

Task: GZ-010
PR: #63
Result: NEEDS_REVIEW
Target: `3a11c5f639717993f51a26c5b5970701570fe367`
Execution status: full nonterminal rehearsal passed on c91265bf1430c3e7df6b0f1321705b4a00a66b25; original checkout and worktree list were preserved. Actual logs: test-results/resumption-20261009/recovery/

## State and Issue recovery

This PR keeps GZ-010 at review. Program and Completion Ledger are identical to the target; Active Work differs only in the existing GZ-010 lease timestamps. No completion record is appended or lease removed. Coordinator proposes a 168-hour renewal, 2026-10-09T08:57:38Z to 2026-10-16T08:57:38Z; all other Registry fields remain exact.

Issue #15 was reopened through the authorized GitHub connection at `2026-09-16T15:52:58Z`; returned state was `open`, reason `reopened`, and `closed_at` was null. Issue comment `5700433671` records the correction. This follows the abort/reopen precedent in `evidence/GZ-004/rollback-verification/README.md`. If this nonterminal PR is abandoned, closed or merged, keep Issue #15 open until an actually validated completion is authorized. Do not leave an external completed signal after withdrawing completion.

Abandoning this PR before merge needs no Git revert: main is unchanged. The old completed-candidate tree restoration, retained at `035e786022f7995724e0c3b99a86a9356c51e1cf`, is not a permitted post-completion ledger rollback.

## Full local rehearsal of this documentation recovery

Run the entire block from the clean, fully fetched candidate after installing the existing `requirements-governance.txt`. It creates one isolated detached worktree, restores the target Task/Evidence while preserving the candidate renewal and synchronizing only the restored Task lease, commits that restoration locally as an explicitly labelled simulation, and runs the actual lifecycle, history, coordination, scope, named `make verify`, planning tests and skip audit against the **candidate commit**, not the old main base. It leaves the original checkout and all remote refs untouched.

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
  specs/coordination/program-plan.yaml specs/coordination/task-completions.yaml \
  specs/poc poc/README.md .github scripts tests
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
# Fail closed: the candidate Registry differs from target only in one lease.
# Preserve that renewal during recovery; restoring September expiry would
# deliberately create an invalid October Task/Registry pair.
step renewal-overlay python - "$WT" "$BASE" "$CANDIDATE" "$OUT" <<'PY'
import copy, json, os, re, subprocess, sys
from pathlib import Path
import yaml
wt, base, candidate, out = sys.argv[1:]
active_path = 'specs/coordination/active-work.yaml'
task_path = 'specs/tasks/GZ-010.md'
def git(*args, env=None):
    return subprocess.check_output(['git', '-C', wt, *args], env=env, text=True).strip()
before = yaml.safe_load(git('show', f'{base}:{active_path}'))
after = yaml.safe_load(git('show', f'{candidate}:{active_path}'))
old = [t for t in before['tasks'] if t['taskId'] == 'GZ-010']
new = [t for t in after['tasks'] if t['taskId'] == 'GZ-010']
assert len(old) == len(new) == 1
assert new[0]['status'] == old[0]['status'] == 'review'
masked = copy.deepcopy(after)
next(t for t in masked['tasks'] if t['taskId'] == 'GZ-010')['lease'] = old[0]['lease']
assert masked == before, 'Unrelated Registry drift'
lease = new[0]['lease']
assert lease == {'acquiredAt': '2026-10-09T08:57:38Z', 'expiresAt': '2026-10-16T08:57:38Z'}
restored = Path(wt, task_path)
text = restored.read_text(encoding='utf-8')
text, count = re.subn(r'^leaseExpiresAt: .+$', 'leaseExpiresAt: ' + lease['expiresAt'], text, count=1, flags=re.M)
assert count == 1
text = text.replace('2026-09-14T06:00:00Z', lease['acquiredAt']).replace('2026-09-21T06:00:00Z', lease['expiresAt'])
restored.write_text(text, encoding='utf-8', newline='\n')
git('add', task_path)
# Independently build the target tree plus exactly two renewal overlay blobs.
env = dict(os.environ, GIT_INDEX_FILE=str(Path(out, 'expected-index')))
git('read-tree', base, env=env)
task_blob = git('hash-object', '-w', task_path)
active_blob = git('rev-parse', f'{candidate}:{active_path}')
git('update-index', '--add', '--cacheinfo', f'100644,{task_blob},{task_path}', env=env)
git('update-index', '--add', '--cacheinfo', f'100644,{active_blob},{active_path}', env=env)
expected = git('write-tree', env=env)
assert git('write-tree') == expected
Path(out, 'expected-tree.txt').write_text(expected + '\n', encoding='utf-8')
print(json.dumps({'renewal_preserved': True, 'expected_tree': expected}))
PY
RESTORED=$(git -C "$WT" write-tree)
EXPECTED=$(cat "$OUT/expected-tree.txt")
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

Resolve the actual PR #63 merge and its first parent. First capture the actual pre-recovery HEAD and Registry, verify its lease is still valid, and verify the exact original merge diff. On a separate recovery branch preview `git revert --no-commit -m 1 "$DOCUMENTATION_MERGE"` only after verifying the merge changed Task/Evidence plus the exact GZ-010 lease renewal. The intermediate reverted tree is not a recovery candidate: do not validate, commit or push it. Restore active-work.yaml from the captured pre-recovery HEAD, then synchronize the restored Task leaseExpiresAt and body timestamps to that Registry before any checks. Preserve the current valid lease; stop on expiry before starting, conflicts, any other Registry/lifecycle drift or unrelated changes. Run the same lifecycle/history/coordination/scope and named make checks using the real pre-recovery main commit as base. Preserve review and main-merge approval. Stop on conflicts, changed lifecycle, expired lease or any unrelated change; this script is not an automatic rollback authorization.

## Future completion

No main merge or terminal recovery is claimed. The nonterminal rehearsal actually passed on the source identified above; raw transcripts distinguish it from future Completion requirements. Before proposing completed again, this lease-preserving rehearsal covers nonterminal documentation recovery only. The separate completion prerequisites remain: successful final-candidate checks and an actually tested forward recovery preserving immutable completion records. The nonterminal rehearsal above does not certify a post-completion status regression or ledger deletion.

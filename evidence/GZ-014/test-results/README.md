# GZ-014 Test Results

## Verified predecessor lifecycle

- PR #32 exact HEAD: `9adf9a135fabe4581285a945b4b434d9302e9a80`.
- PR #32 Governance Gate run #292: `PASS`.
- PR #32 expected-head merge: `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- PR #32 post-merge main Governance Gate run #293: `PASS`.
- Ancestry: prior GZ-014 integration base `c26fc712e050dba4e83c9af022fd25b8f7e84d6d` is a strict ancestor of `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- Commit identity: `8221fd0f...` identifies GZ-014 and PR #32.

## Completion commands

PR #33 latest HEAD must execute:

```bash
python scripts/check-task-file.py --task GZ-014
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python scripts/run-program-lifecycle-gate.py \
  --base-ref origin/main \
  --head-ref HEAD \
  --task GZ-014 \
  --branch-name chore/GZ-014-foundation-completion-v3
python scripts/run-agent-coordination-gate.py \
  --task GZ-014 \
  --base-ref origin/main \
  --head-ref HEAD \
  --branch-name chore/GZ-014-foundation-completion-v3
python scripts/run-task-scope-gate.py --task GZ-014 --base origin/main
python scripts/check-evidence.py --task GZ-014
make verify \
  TASK=GZ-014 \
  BASE=origin/main \
  HEAD_REF=HEAD \
  BRANCH=chore/GZ-014-foundation-completion-v3
```

## Expected fail-closed assertions

- GZ-014 exists in `foundationTasks` and moves only `integration -> completed`;
- `completionRef` is exactly `PR-32`;
- `mergeCommit` is exactly `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`;
- Issue #17 is closed/completed;
- GZ-014 Lease is absent after completion, while Registry policy is unchanged;
- ordinary Task Completion Ledger is unchanged;
- Task `exitGate` is unchanged;
- exact diff is limited to the declared eight files;
- Evidence contains the required identity, commands, exit status and explicit PASS/COMPLETED tokens;
- no W1 task is activated in the same change.

Current result: `PENDING PR-33 EXACT-HEAD VALIDATION`.

No PR #33 Gate, Review, merge, or post-merge main result is pre-claimed. Completion becomes final only after all four are observed with `PASS`.

# OPS-008 / GZ-014 rollback verification

Task: GZ-014  
Tracking issue: #57

The repair is governance-only. Before integration, verify that reverting the candidate restores the exact target-base behavior and does not alter Program, Active Work, Completion Ledger, product data, Secrets, or deployment state.

```bash
set -euo pipefail
BASE=3acc6e4ee582f4fdee8ba90c630bf99eb870b252
HEAD=HEAD

git diff --exit-code "$BASE" "$HEAD" -- \
  specs/coordination/program-plan.yaml \
  specs/coordination/active-work.yaml \
  specs/coordination/task-completions.yaml \
  specs/tasks/GZ-014.md

# Candidate rollback rehearsal in an isolated branch/worktree.
git switch --detach "$HEAD"
git revert --no-commit "$BASE..$HEAD"
python -m compileall -q scripts tests
python -m pytest tests/governance/ -q
make verify TASK=GZ-014 BASE="$BASE" HEAD_REF=HEAD \
  BRANCH=fix/GZ-014-program-registration-bootstrap
git reset --hard "$HEAD"
```

Expected results:

- the four immutable coordination/Task files have no diff;
- the revert applies without touching product or deployment paths;
- governance tests and `make verify` return exit code `0` on the reviewed final candidate;
- no rollback command is executed against `main` directly.

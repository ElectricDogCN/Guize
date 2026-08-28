# GZ-001 R5 Clean Recovery Report

## Decision

Status: **READY_FOR_REMOTE_CI**.

PR #5 is an ancestor snapshot of PR #4, not an independent change set. The clean recovery branch
starts from PR #4 HEAD and preserves its entire history. PR #4 and PR #5 are to be closed as
superseded only after this replacement PR is created.

## Verified lineage

- `main`: verified separately as the replacement PR base; its tip is on the sibling main history
- PR #5 HEAD: `b6878d66aeb241e7ad3fe1a4c0ac30e217ed453a`
- PR #4 HEAD / recovery base: `4176767e7f82f92a66f4fa873fd469d6280bf60a`
- Governance repair: `545a11f099acc4f64b44444ac6700123eb0d2246`
- Scope base repair: `2b006cc`

Git comparison established that PR #5 is behind PR #4 by two commits with no unique commits or
files. No force push, history rewrite, or deletion of the old branches is required.

## Repaired integrity gaps

1. Evidence containing a real but unreachable commit now fails validation.
2. Pull-request branches outside `<type>/<TASK-ID>-<short-name>` fail closed instead of skipping
   task, Evidence, and scope checks.
3. Scope validation fails closed when Git cannot determine the changed-file set.
4. Markdown validation checks both trailing whitespace and internal `.md` targets.
5. Secret scanning uses the tested scanner and excludes intentional test fixtures.
6. Parent-reference scanning no longer treats its own test literals as production violations.
7. The CI static test now fails when strict shell mode is absent.
8. The Makefile invokes pytest through the active Python interpreter.
9. The documented manual `.github` rollback command now creates and targets the correct directory.
10. Scope validation rejects a missing base ref instead of mistaking a clean worktree for zero changes.

## Local verification

- `python -m compileall -q scripts tests`: exit 0
- `python -m pytest tests/governance/ -q`: exit 0, 68 passed
- `make verify TASK=GZ-001 BASE=origin/main BRANCH=chore/GZ-001-clean-recovery`: exit 0
- Markdown validation: 94 files, no issues
- Schema validation: all discovered contract YAML/JSON files parsed
- High-risk secret scan: no findings

## Remaining gate

The replacement PR's GitHub Actions Governance Gate must complete successfully. Until that remote
run exists, this report does not claim that GitHub Actions passed and does not authorize merge.

## Rollback

Before merge, close the replacement PR and retain its branch. After merge, revert the replacement
PR's merge commit; do not rewrite `main` or delete the historical PR branches as part of rollback.

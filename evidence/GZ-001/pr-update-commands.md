# GZ-001-R3: PR Update Commands

## Summary

This document provides commands for manually updating PR #3 after completing GZ-001-R3.

## Push Branch

**Command**:

```bash
git push origin chore/GZ-001-repository-baseline
```

**Notes**:
- Do NOT use `--force` or `--force-with-lease`
- Only use standard push for Fast-forward updates
- Verify remote branch status after push

## Update PR Title

**Command** (using GitHub CLI):

```bash
gh pr edit 3 --title "GZ-001: establish repository governance and agent execution harness"
```

**Alternative** (manual):
- Go to https://github.com/ElectricDogCN/Guize/pull/3
- Edit the PR title field
- Save changes

## Update PR Body

**Command** (using GitHub CLI):

```bash
gh pr edit 3 --body-file evidence/GZ-001/pull-request-draft.md
```

**Alternative** (manual):
- Go to https://github.com/ElectricDogCN/Guize/pull/3
- Edit the PR description
- Paste content from `evidence/GZ-001/pull-request-draft.md`
- Save changes

## Verify PR Status

**Command**:

```bash
gh pr status
gh pr view 3
```

**Expected Output**:
- PR shows as ready for review
- Branch is up-to-date with remote
- All checks are pending (GitHub Actions not yet run)

## Monitor GitHub Actions

After pushing the branch, monitor Actions at:

https://github.com/ElectricDogCN/Guize/actions

## Do NOT Execute

The following commands are **NOT** to be executed automatically:

- `git push --force`
- `git push --force-with-lease`
- `gh pr merge`
- `gh pr close`
- Any command that modifies remote branches or PR state

## Manual Verification Checklist

Before merging the PR:

- [ ] Branch pushed successfully
- [ ] PR title updated
- [ ] PR body updated with draft content
- [ ] GitHub Actions workflow triggered
- [ ] All Actions checks pass
- [ ] Governance report generated
- [ ] Code review completed
- [ ] No unresolved conflicts

## Notes

All commands must be executed manually by a human operator. No automatic push, merge, or PR modification is allowed.

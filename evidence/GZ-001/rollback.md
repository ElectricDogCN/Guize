# GZ-001-R3: Rollback Instructions

## Summary

This document provides detailed rollback instructions for the GZ-001-R3 repository root normalization.

## Rollback Options

### Option 1: Delete Unpushed Branch (Recommended for PR Not Yet Merged)

If the branch has not been pushed to remote or the PR has not been merged:

```bash
git checkout main
git branch -D chore/GZ-001-repository-baseline
```

**Conditions**:
- Branch has not been pushed to remote
- No other commits depend on this branch
- Working directory is clean

**Advantages**:
- Quick and safe
- No risk of losing other work
- Preserves main branch history

---

### Option 2: Revert Migration Commits

If the branch has been pushed but not merged:

```bash
# Identify migration commits
git log --oneline chore/GZ-001-repository-baseline..HEAD

# Revert individual commits (in reverse order)
git revert <commit-hash-4>
git revert <commit-hash-3>
git revert <commit-hash-2>
git revert <commit-hash-1>

# Push revert commits
git push origin chore/GZ-001-repository-baseline
```

**Conditions**:
- Branch has been pushed to remote
- No merge conflicts expected
- Want to preserve commit history

**Advantages**:
- Preserves audit trail
- No force push required
- Safe for shared branches

---

### Option 3: Revert Merge Commit Through a Review Branch (For Merged PR)

If the PR has already been merged into `main`, never create the revert directly on `main`. Create an independent rollback branch, push it, run the Governance Gate, and merge the revert only after review.

```bash
git checkout main
git pull --ff-only origin main

# Find the merge commit that introduced GZ-001
git log --oneline --merges -10

# Create a dedicated rollback task branch
git checkout -b fix/GZ-001-revert-governance-baseline

# Revert the selected merge commit on the rollback branch
git revert -m 1 <merge-commit-hash>

# Publish only the rollback branch
git push -u origin fix/GZ-001-revert-governance-baseline
```

Then:

1. Create a PR from `fix/GZ-001-revert-governance-baseline` to `main`.
2. Record the rollback reason and affected release/commit in Evidence.
3. Run the Governance Gate and any affected integration checks.
4. Review conflicts and confirm later `main` changes are preserved.
5. Merge the rollback PR only after the required human approval.
6. Verify repository structure and governance commands after merge.

**Conditions**:
- The GZ-001 change has already been merged.
- The target merge commit is known and its revert has been reviewed for conflicts with later work.

**Advantages**:
- Preserves full history.
- Does not bypass branch protection or review.
- Keeps later commits on `main` unless the revert explicitly conflicts with them.
- Produces an auditable rollback PR and Evidence trail.

---

### Option 4: Manual Restoration (Last Resort)

If all other options fail, manually restore the `guize-solution/` directory on a dedicated rollback branch, never directly on `main`:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b fix/GZ-001-manual-wrapper-restore

# Create wrapper directory
mkdir guize-solution

# Move files back
mv AGENTS.md MANIFEST.md Makefile README.md requirements-governance.txt guize-solution/
mv .github/ guize-solution/
mv .agent/ guize-solution/
mv .trae/ guize-solution/
mv adr/ contracts/ deployment/ docs/ evidence/ prompts/ rules/ scripts/ specs/ tests/ guize-solution/

# Update path references
# WARNING: This requires manual updates to all files
# See "Path Reference Updates" below

# Verify before publishing
cd guize-solution
git status --short
python -m pytest tests/governance/ -v
```

After verification, commit and push the rollback branch, then submit a PR to `main`; do not push restored content directly to `main`.

**Conditions**:
- Git revert paths cannot safely restore the required repository state.
- Other rollback options failed.
- A reviewed manual restoration is explicitly required.

**Disadvantages**:
- Complex and error-prone.
- Requires extensive path updates and regression verification.
- Must not bypass the normal branch/PR governance flow.

---

## Path Reference Updates for Manual Rollback

If performing a manual rollback, the following files need path updates:

### Workflow

```yaml
# .github/workflows/governance-gate.yml
defaults:
  run:
    working-directory: guize-solution

on:
  push:
    paths:
      - 'guize-solution/AGENTS.md'
      - 'guize-solution/rules/**'
      # ... other paths with guize-solution/ prefix
```

### Makefile

```makefile
# Update all paths to use guize-solution/ prefix
```

### Scripts

```python
# scripts/check-task-scope.py
# Update default paths to include guize-solution/
```

### Tests

```python
# tests/governance/test_repository_boundary.py
# Restore original assertions for working-directory
```

### Prompts

```markdown
# prompts/*.md
# Update path references to use guize-solution/
```

---

## Rollback Verification

After rollback, verify:

1. The intended repository structure matches the rollback target.
2. The rollback PR preserved unrelated later `main` changes.
3. Expected governance entry points exist at the rollback target paths.
4. Workflow working-directory/path filters match the restored structure.
5. Governance tests pass from the intended repository root.
6. `make verify` or the rollback task's declared validation command passes.
7. The rollback PR, merge commit, commands, exit codes, and post-merge verification are recorded in Evidence.

---

## Warning

**Hard Reset Warning**: The following command is destructive and should only be used on a private, unpushed task branch as a last resort:

```bash
git reset --hard <base-commit>
```

Never use a hard reset to rewrite shared `main` history. Only use this on a local/unpushed task branch when:
- There are no uncommitted changes that must be preserved.
- No other work depends on the branch history.
- The result will still enter `main` through the normal PR/review process if it must be published.

---

## Rollback Checklist

- [ ] Identify rollback option based on current state
- [ ] Verify working directory is clean
- [ ] Backup any uncommitted changes
- [ ] Create or confirm the dedicated rollback branch
- [ ] Execute rollback commands on that branch
- [ ] Run required tests and verification
- [ ] Push the rollback branch, not `main`
- [ ] Create and review the rollback PR
- [ ] Verify post-merge repository state
- [ ] Record rollback evidence and final result

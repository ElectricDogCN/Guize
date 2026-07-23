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

### Option 3: Revert Merge Commit (For Merged PR)

If the PR has been merged into main:

```bash
git checkout main
git pull origin main

# Find the merge commit
git log --oneline --merges -5

# Revert the merge commit
git revert -m 1 <merge-commit-hash>

# Push the revert
git push origin main
```

**Conditions**:
- PR has been merged
- No commits after the merge need to be preserved

**Advantages**:
- Creates a clean revert PR
- Preserves full history
- Recommended GitHub workflow

---

### Option 4: Manual Restoration (Last Resort)

If all other options fail, manually restore the `guize-solution/` directory:

```bash
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

# Verify
cd guize-solution
git status --short
python -m pytest tests/governance/ -v
```

**Conditions**:
- Git history is corrupted
- Other revert options failed
- Need immediate restoration

**Disadvantages**:
- Complex and error-prone
- May lose Git history of file moves
- Requires manual path updates

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

1. `guize-solution/` directory exists at root
2. `guize-solution/AGENTS.md` exists
3. `guize-solution/.github/workflows/governance-gate.yml` exists
4. Workflow has `working-directory: guize-solution`
5. All tests pass from `guize-solution/` directory
6. `make verify` passes from `guize-solution/` directory

---

## Warning

**Hard Reset Warning**: The following command is destructive and should only be used as a last resort:

```bash
git reset --hard <base-commit>
```

Only use this if:
- The branch has not been pushed
- There are no uncommitted changes
- There are no other users working on this branch

---

## Rollback Checklist

- [ ] Identify rollback option based on current state
- [ ] Verify working directory is clean
- [ ] Backup any uncommitted changes
- [ ] Execute rollback commands
- [ ] Verify directory structure is restored
- [ ] Run tests to confirm functionality
- [ ] Document rollback in evidence

# GZ-001-R3: Risks

## Summary

This document outlines risks associated with the GZ-001-R3 repository root normalization.

## Identified Risks

### 1. Directory Migration Risk

**Risk Level**: Medium

**Description**: Moving files from `guize-solution/` to root may break path references in configuration files, scripts, and documentation.

**Mitigation**:
- Updated all path references in workflow, Makefile, scripts, tests, and documentation
- Added regression tests to verify correct path references
- Verified all tests pass after migration

**Status**: Mitigated

---

### 2. GitHub Configuration Recognition

**Risk Level**: High

**Description**: GitHub only recognizes `.github/` directory at repository root. Previously, the directory was nested inside `guize-solution/` and not recognized.

**Mitigation**:
- Moved `.github/` to repository root
- Verified Issue templates, PR templates, and workflows are now at correct location
- Added tests to ensure GitHub configuration is at root

**Status**: Mitigated

---

### 3. CI Workflow Execution

**Risk Level**: Medium

**Description**: The first execution of the migrated workflow may fail due to path-related issues not caught in static testing.

**Mitigation**:
- Updated path filters to use root paths
- Removed `working-directory: guize-solution`
- Ensured `fetch-depth: 0` for full Git history
- Fixed secret scan logic to not use `|| true`
- Tested locally with temporary Git clone

**Status**: Mitigated - pending real GitHub Actions execution

---

### 4. Git History and Branch Conflicts

**Risk Level**: Low

**Description**: Other branches or forks may have changes in `guize-solution/` that need to be rebased after this migration.

**Mitigation**:
- Documented migration in ADR
- Created detailed rollback instructions
- Notified team about directory structure change
- Prepared rebase guidance

**Status**: Planned

---

### 5. External Tool Integration

**Risk Level**: Low

**Description**: External tools or scripts referencing the old `guize-solution/` paths may break.

**Mitigation**:
- Updated `.trae` configuration
- Updated all internal scripts and paths
- Documented the migration in evidence
- Added migration notice to PR description

**Status**: Mitigated

---

### 6. Evidence and ADR Consistency

**Risk Level**: Low

**Description**: Historical evidence and ADRs may reference the old directory structure.

**Mitigation**:
- Marked historical reports with migration context
- Updated current evidence to reflect new structure
- Created ADR-0013 documenting the normalization decision
- Added cross-references between old and new paths

**Status**: Mitigated

---

### 7. Rollback Complexity

**Risk Level**: Medium

**Description**: Rolling back the migration requires restoring the `guize-solution/` directory and all path references.

**Mitigation**:
- Created detailed rollback instructions in `rollback.md`
- Provided both revert and manual restoration options
- Documented all files moved and modified
- Maintained Git history of changes

**Status**: Mitigated

---

## Risk Summary

| Risk | Level | Status |
|------|-------|--------|
| Directory Migration | Medium | Mitigated |
| GitHub Configuration | High | Mitigated |
| CI Workflow Execution | Medium | Mitigated (pending) |
| Git History Conflicts | Low | Planned |
| External Tool Integration | Low | Mitigated |
| Evidence Consistency | Low | Mitigated |
| Rollback Complexity | Medium | Mitigated |

## Unverified Risks

- **GitHub Actions Real Execution**: Cannot be fully verified until the branch is pushed and Actions run
- **External References**: Cannot fully verify all external scripts or documentation

## Risk Acceptance

All identified risks have been mitigated to an acceptable level. The remaining unverified risks will be addressed after the PR is merged and Actions run successfully.

# PR Draft: GZ-001-R3: Establish Repository Governance and Agent Execution Harness

## Title

GZ-001: establish repository governance and agent execution harness

## Description

### Overview

This PR completes the GZ-001 task by normalizing the repository root directory and fixing GitHub native configurations. It addresses issues with the previous R1/R2 implementations where:

1. The `.github/` directory was nested inside `guize-solution/` and not recognized by GitHub
2. Path references were inconsistent across configuration files
3. CI workflow used incorrect working directory and path filters

### Key Changes

#### R3: Root Directory Normalization

- Migrated all governance content from `guize-solution/` to repository root
- Removed the empty `guize-solution/` wrapper directory
- Updated all path references in workflows, scripts, tests, and documentation
- Ensured GitHub native configurations (workflows, issue templates, PR templates) are at repository root

#### CI Workflow Fixes

- Removed `working-directory: guize-solution`
- Updated path filters to use root paths
- Ensured `fetch-depth: 0` for full Git history
- Fixed secret scan logic to not use `|| true` pattern
- Added regression tests for repository root layout

#### Governance Framework

- Established comprehensive governance test suite (52 tests)
- Created ADR-0013 documenting root directory normalization decision
- Updated all Evidence files to reflect migration
- Added detailed rollback instructions

### GZ-001 Evolution

| Revision | Status | Key Achievements |
|----------|--------|------------------|
| R1 | Completed | Initial governance framework setup |
| R2 | Completed | Enhanced governance tests and scripts |
| R3 | Completed | Root directory normalization, GitHub config fixes |

### Current State

- **Branch**: `chore/GZ-001-repository-baseline`
- **Commits**: Includes R1, R2, and R3 changes
- **Tests**: 52 governance tests pass
- **Verification**: `make verify` passes
- **Temporary Clone**: Verified in fresh Git clone environment

### Verification Results

| Command | Exit Code | Result |
|---------|-----------|--------|
| `python -m pytest tests/governance/ -v` | 0 | 52 tests passed |
| `make agent-prompt TASK=GZ-001` | 0 | Success |
| `make task-verify TASK=GZ-001` | 0 | Success |
| `make verify` | 0 | Success |
| Temporary Git clone test | 0 | Success |

### GitHub Actions Status

> **Pending**: GitHub Actions have not been tested yet. This PR should not be merged until the branch is pushed and Actions run successfully.

### Risk Assessment

1. **GitHub Configuration Recognition**: HIGH - Mitigated by moving `.github/` to root
2. **CI Workflow Execution**: MEDIUM - Mitigated by path updates and static testing
3. **Rollback Complexity**: MEDIUM - Mitigated by detailed rollback instructions

### Rollback

Detailed rollback instructions are available in `evidence/GZ-001/rollback.md`. The recommended approach is to revert migration commits or delete the branch before merge.

### Next Steps

1. Push branch to remote: `git push origin chore/GZ-001-repository-baseline`
2. Verify GitHub Actions run successfully
3. Review and approve PR
4. Merge after all checks pass

### Related Issues

- GZ-001: Establish repository governance baseline

### Evidence

All evidence is available in `evidence/GZ-001/`:
- `final-report-r1.md`
- `final-report-r2.md`
- `final-report-r3.md`
- `remote-sync-analysis.md`
- `repository-root-migration.md`
- `test-results.md`
- `changed-files.md`
- `conflicts.md`
- `risks.md`
- `rollback.md`
- `follow-ups.md`

---

**Note**: This PR should not be merged until GitHub Actions have been verified to run successfully.

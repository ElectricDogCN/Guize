# GZ-001-R3: Changed Files

## Summary

This document lists all files changed during GZ-001-R3 repository root normalization.

## New Files

| File | Description |
|------|-------------|
| `adr/0013-normalize-governance-repository-root.md` | ADR documenting root directory normalization decision |
| `tests/governance/test_repository_root_layout.py` | Repository root layout regression tests |
| `evidence/GZ-001/remote-sync-analysis.md` | Remote sync analysis report |
| `evidence/GZ-001/repository-root-migration.md` | Root directory migration record |
| `evidence/GZ-001/final-report-r3.md` | R3 final report |
| `evidence/GZ-001/pr-update-commands.md` | PR update commands |

## Moved Files (from guize-solution/ to root)

| Old Path | New Path |
|----------|----------|
| `guize-solution/AGENTS.md` | `AGENTS.md` |
| `guize-solution/MANIFEST.md` | `MANIFEST.md` |
| `guize-solution/Makefile` | `Makefile` |
| `guize-solution/README.md` | `README.md` |
| `guize-solution/requirements-governance.txt` | `requirements-governance.txt` |
| `guize-solution/.github/` | `.github/` |
| `guize-solution/.agent/` | `.agent/` |
| `guize-solution/.trae/` | `.trae/` |
| `guize-solution/adr/` | `adr/` |
| `guize-solution/contracts/` | `contracts/` |
| `guize-solution/deployment/` | `deployment/` |
| `guize-solution/docs/` | `docs/` |
| `guize-solution/evidence/` | `evidence/` |
| `guize-solution/prompts/` | `prompts/` |
| `guize-solution/rules/` | `rules/` |
| `guize-solution/scripts/` | `scripts/` |
| `guize-solution/specs/` | `specs/` |
| `guize-solution/tests/` | `tests/` |

## Modified Files (path reference updates)

| File | Changes |
|------|---------|
| `.github/workflows/governance-gate.yml` | Removed `working-directory: guize-solution`, updated path filters, fixed secret scan logic |
| `Makefile` | Removed `guize-solution/` prefix from paths |
| `scripts/check-task-scope.py` | Updated default paths |
| `scripts/check-evidence.py` | Updated default paths |
| `scripts/check-spec-sync.py` | Updated paths |
| `tests/governance/test_repository_boundary.py` | Updated assertions for new directory structure |
| `prompts/agent-prompt-base.md` | Updated path references |
| `prompts/evidence-collection.md` | Updated path references |
| `specs/tasks/GZ-001-repository-baseline.md` | Updated acceptance criteria and rollback instructions |
| `evidence/GZ-001/final-report-r2.md` | Added migration context |

## Deleted Files/Directories

| Path | Reason |
|------|--------|
| `guize-solution/` | Empty wrapper directory after migration |
| `README.md` (original placeholder) | Replaced by complete project README |

## Total Changes

- New: 6 files
- Moved: 18 items (files/directories)
- Modified: 11 files
- Deleted: 2 items

## Verification

All changes have been verified by:
1. Running `git status --short`
2. Running `python -m pytest tests/governance/ -v` (52 tests passed)
3. Running `make verify`
4. Temporary Git clone verification

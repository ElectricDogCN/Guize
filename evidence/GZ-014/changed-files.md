# GZ-014 Changed Files

## Current PR

- PR: #27
- Phase: Foundation lifecycle-state model repair
- Base: `main@ef1048344aa082c678e5ef948dc7f62e5aa84510`
- Branch: `chore/GZ-014-foundation-lifecycle-states`
- Last validated pre-Evidence HEAD: `656c7b9c20cd18de2850caa46c734f46a0fc6c90`
- Gate: run #268, success

## Declared files

- `specs/coordination/program-plan.schema.yaml`
- `tests/governance/test_foundation_lifecycle_states.py`
- `specs/tasks/GZ-014.md`
- `specs/coordination/active-work.yaml`
- `evidence/GZ-014/summary.md`
- `evidence/GZ-014/commands.txt`
- `evidence/GZ-014/changed-files.md`
- `evidence/GZ-014/test-results/README.md`
- `evidence/GZ-014/handoff.md`

## Explicitly unchanged

- `specs/coordination/program-plan.yaml` remains unchanged with GZ-014 `in_progress`;
- `scripts/check-program-lifecycle-guards.py` and `scripts/check-program-plan-transitions.py` remain unchanged;
- Workflow and Makefile remain unchanged;
- no product requirement, business contract/code, deployment, Secret, permission or production-data change;
- no Lease release and no Foundation completion.

## Verification rule

Integrator must obtain the actual GitHub changed-file list immediately before approval. Any path outside the declared nine files, a failed latest Gate, stale base, or unresolved blocker prevents merge.

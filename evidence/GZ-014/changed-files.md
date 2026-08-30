# GZ-014 Changed Files

## Current phase

- Task: GZ-014
- Phase: `FOUNDATION_COMPLETION`
- Branch: `chore/GZ-014-foundation-completion`
- Base: `main@c26fc712e050dba4e83c9af022fd25b8f7e84d6d`

## Declared files

- `specs/coordination/program-plan.yaml`
- `specs/coordination/active-work.yaml`
- `specs/tasks/GZ-014.md`
- `evidence/GZ-014/summary.md`
- `evidence/GZ-014/commands.txt`
- `evidence/GZ-014/changed-files.md`
- `evidence/GZ-014/test-results/README.md`
- `evidence/GZ-014/handoff.md`

## Exact semantic change

- GZ-014 Foundation status changes from `integration` to `completed`;
- Foundation provenance becomes `completionRef: PR-26` and `mergeCommit: ef1048344aa082c678e5ef948dc7f62e5aa84510`;
- GZ-014 Task Spec becomes `completed` on the completion branch/base;
- only the GZ-014 Active Work Lease is removed;
- task-bound completion Evidence is refreshed.

## Explicitly unchanged

- ordinary `specs/coordination/task-completions.yaml`;
- all other Foundations, Program tasks, POCs, waves, blockers and release policy;
- Active Work policy and any other task entry;
- lifecycle code, schemas, tests, Workflow and Makefile;
- requirements, business contracts/code, deployment, Secrets, permissions and production data;
- OPS-001 #20 remains open and gates only GZ-020.

The Integrator must compare GitHub's actual latest file list with these eight paths before approval. Any unexpected path, failed latest Gate, stale base, incorrect Issue state, provenance mismatch or unresolved blocker prevents merge.

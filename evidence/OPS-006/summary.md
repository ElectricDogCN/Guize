# OPS-006 Registration Evidence Summary

## Evidence phase

This Evidence covers only the clean, metadata-only Registration bootstrap for OPS-006. It does not claim that `PROGRAM-TASK-REGISTRATION-V1` is implemented, that OPS-006 owns an Active Work Lease, or that the current Harness accepts `planned`.

## Exact baseline

- Repository: `ElectricDogCN/Guize`
- Target: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
- Target verification: Governance Gate #446 / run `33736578549` = SUCCESS
- Registration branch: `chore/OPS-006-task-registration-r2`
- Issue: #52
- Superseded diagnostic PR: #53, closed without merge
- Prerequisite repair: OPS-007 #54 / PR #55, completed
- Candidate commit and PR: pending creation by this Evidence commit

## Registration-only change

The intended cumulative diff is exactly thirteen files:

1. `specs/coordination/program-plan.yaml`:
   - add exactly one ordinary Program Task, OPS-006, with `status: planned`;
   - append OPS-006 to the tail of planned GZ-020 `dependsOn` without changing prior order;
2. `specs/tasks/OPS-006.md`;
3. eleven files under `evidence/OPS-006/**`.

`specs/coordination/active-work.yaml` and `specs/coordination/task-completions.yaml` remain unchanged. No Checker, test, Workflow, POC, GZ-010, OPS-005, business, deployment, Secret or production-data file is included.

## Corrected bootstrap baseline

The obsolete PR #53 correctly diagnosed the missing Registration lifecycle, but it was based on `main@219d709...` and also observed a W1 capacity failure. OPS-007 removed that independent blocker and post-merge main is green. The rebuilt Registration candidate must therefore show Project Readiness PASS; carrying the former W1 failure forward would be stale or false Evidence.

The remaining expected bootstrap classifications are limited to current Harness surfaces that do not yet support `planned` Registration:

- Registry Task checker rejects `status: planned`;
- Agent Coordination dispatcher rejects `planned`;
- Task Scope dispatcher rejects `planned`;
- lifecycle guard treats the append-only GZ-020 dependency attachment as an ordinary affected-task mutation and requires a current GZ-020 Task Spec;
- repository-state tests may mirror only those exact conditions.

Any other failure is a blocker.

## Decision boundary

The first candidate HEAD must be checked by GitHub Actions and independently reviewed. No Registration merge is authorized by this pre-run Evidence. After exact results are known, canonical Evidence must be refreshed before any integration decision.

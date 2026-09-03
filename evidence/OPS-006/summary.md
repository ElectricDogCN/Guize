# OPS-006 Registration Evidence Summary

## Evidence phase

This Evidence covers only the one-time metadata-only Registration bootstrap for OPS-006. It does not claim that `PROGRAM-TASK-REGISTRATION-V1` is implemented, that OPS-006 has an Active Work Lease, or that the existing Harness accepts `planned`.

## Exact baseline

- Repository: `ElectricDogCN/Guize`
- Target branch: `main`
- Target SHA audited before branch creation: `219d7096756ad75717a46d85baf7d2b216e2472b`
- Registration branch: `chore/OPS-006-task-registration`
- Issue: #52
- Triggering blocked work: Issue #50 / PR #51

## Registration-only change

The intended PR diff is confined to:

1. `specs/coordination/program-plan.yaml`
   - add exactly one `planned` Program Task: OPS-006;
   - append OPS-006 to the end of planned final task GZ-020 `dependsOn`, preserving the existing dependency order and final release closure;
2. `specs/tasks/OPS-006.md`;
3. `evidence/OPS-006/**`.

`specs/coordination/active-work.yaml` and `specs/coordination/task-completions.yaml` remain unchanged. No checker, test, Workflow, POC, GZ-010, business, deployment or production file is included.

## Expected legacy-Harness result

The current baseline has no Registration mode. Therefore this bootstrap must not be represented as a green ordinary lifecycle PR. The exact PR run is expected to expose only failures caused by the pre-existing lifecycle gap, including rejection of Task Spec status `planned`, planned-state dispatch, and treatment of the GZ-020 append as an ordinary affected-task mutation.

Any unrelated schema, integrity, secret, evidence, content-scope or syntax failure is a blocker and requires correction before review.

## Decision boundary

OPS-006 Registration requires:

- exact-HEAD changed-file audit;
- exact-HEAD CI failure classification;
- independent human review of the metadata-only bootstrap;
- explicit user approval in a separate step before merge.

No merge approval is recorded in this Evidence.
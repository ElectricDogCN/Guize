# OPS-006 Registration Evidence Summary

## Evidence phase

This Evidence covers only the one-time metadata-only Registration bootstrap for OPS-006. It does not claim that `PROGRAM-TASK-REGISTRATION-V1` is implemented, that OPS-006 has an Active Work Lease, or that the existing Harness accepts `planned`.

## Exact baseline

- Repository: `ElectricDogCN/Guize`
- Target branch: `main`
- Target SHA audited before branch creation: `219d7096756ad75717a46d85baf7d2b216e2472b`
- Registration branch: `chore/OPS-006-task-registration`
- Initial Registration HEAD classified by CI: `b216f84368b54e631dce0b57b46b14cf5424e068`
- Initial Governance Gate run: `33720823036` / job `100539417786`
- Issue: #52
- Draft PR: #53
- Triggering blocked work: Issue #50 / PR #51

## Registration-only change

The intended PR diff is confined to:

1. `specs/coordination/program-plan.yaml`
   - add exactly one `planned` Program Task: OPS-006;
   - append OPS-006 to the end of planned final task GZ-020 `dependsOn`, preserving the existing dependency order and final release closure;
   - register the complete future OPS-006 implementation paths, including Project Readiness and its contract test;
2. `specs/tasks/OPS-006.md`;
3. `evidence/OPS-006/**`.

`specs/coordination/active-work.yaml` and `specs/coordination/task-completions.yaml` remain unchanged. No checker, test, Workflow, POC, GZ-010, business, deployment or production file is included.

## Exact initial CI classification

At source HEAD `b216f84368b54e631dce0b57b46b14cf5424e068`, the workflow completed with these successful controls:

- checkout, dependency installation, Python import and compile checks;
- pytest collection;
- task-context, skip-audit, Markdown, YAML/Schema and secret checks;
- Program Plan schema and integrity;
- Program Plan history and transition checks;
- Evidence structure and Evidence integrity;
- task/branch linkage, spec sync, parent-directory and CI static checks;
- 257 of 259 governance tests.

The failures were classified as the pre-existing missing Registration contract:

1. Task checker rejects Registry Task status `planned`;
2. Agent Coordination dispatcher rejects `planned`;
3. Task Scope dispatcher rejects `planned`;
4. lifecycle guard treats the append-only GZ-020 dependency as an ordinary affected-task mutation and requires a GZ-020 Task Spec;
5. Project Readiness counts terminal completed GZ-004 against W1 `maxConcurrent`, causing the registered planned task to appear over capacity;
6. the two repository-state governance tests mirror items 4 and 5.

No unrelated schema, Program Integrity, Evidence, secret, syntax, collection or additional governance-test failure was observed in run `33720823036`.

## Narrow capacity contract added after run 441

OPS-006 future implementation scope now includes `scripts/check-project-readiness.py` and `tests/governance/test_check_project_readiness.py`. Only `completed` and `cancelled` Program Tasks may release a Wave occupancy slot. Every other state remains counted. No global/Wave concurrency or high-risk limit is increased, and Reservation/Active Work enforcement remains mandatory.

## Decision boundary

OPS-006 Registration requires:

- exact-final-HEAD changed-file audit;
- exact-final-HEAD CI failure classification;
- independent human review of the metadata-only bootstrap;
- explicit user approval in a separate step before merge.

No merge approval is recorded in this Evidence.
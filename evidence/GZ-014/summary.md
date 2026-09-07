# GZ-014 Program Registration Self-Hosting Maintenance

Status: READY_FOR_INDEPENDENT_REVIEW

## Immutable Foundation identity

- Foundation task: `GZ-014` remains `completed`.
- Original completion identity remains PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- The Program Foundation status, Active Work Registry and ordinary Completion Ledger are not reopened or changed by this maintenance.

## Maintenance identity

- Tracking: OPS-008 / Issue #57.
- Draft PR: #58.
- Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.
- Branch: `fix/GZ-014-program-registration-bootstrap`.
- Risk: high.
- Validated implementation source HEAD: `a0c31ffd409e93ae648c061758600c2aa1addc53`.
- Validated synthetic PR merge ref: `571336786c60579f42bdccd02b2b780ac1145855`.
- Governance Gate: run #495 / `34141330075`, job `101803750766`, conclusion `success`.

The subsequent Evidence-only commits do not change implementation, protocol, ownership, tests, Program Plan, Active Work or Completion Ledger. Their own exact HEAD must receive a fresh green Gate before review; no file embeds its own future commit SHA.

## Delivered contract

The candidate establishes a general fail-closed Program Task Registration contract before Reservation:

- exactly one ordinary task may move from absent to `planned`;
- one matching schemaVersion 2 Task Spec uses `coordinationMode: registration` and `agentRole: coordinator`;
- Active Work and Completion Ledger remain byte-identical;
- no Lease, implementation scope, execution result, review, integration or completion authority is granted;
- only task-bound metadata and validated downstream planned dependency tail appends are allowed;
- Program Transition, Lifecycle, Agent Coordination and Task Scope use the same history-aware validator;
- task-aware and push/no-task modes require authoritative base and branch provenance;
- copy/rename/symlink/path traversal, duplicate task IDs, broad root globs, incomplete Task Specs and incomplete Evidence fail closed;
- ordinary non-Registration lifecycle behavior delegates to the preserved exact core implementations;
- positive and negative behavioral fixtures execute against temporary Git repositories.

## Exact validation result

On Gate #495 for source HEAD `a0c31ffd409e93ae648c061758600c2aa1addc53`:

- dependency install and import verification: success;
- Python compile: success;
- governance collection: 327 tests;
- full governance suite: 327 passed, 0 failed, 0 skipped, 46.77 seconds;
- Project Readiness: success with truthful external-readiness warnings;
- Program integrity/history/transitions/finalization/completed-Foundation maintenance: success;
- Agent Coordination and Task Scope: success;
- Markdown, schema, secret, Evidence, Evidence-integrity, branch linkage, spec-sync, repository-boundary and CI-static checks: success.

The workflow did not execute a separately named `make verify` command. It executed the mandatory underlying Gate components directly, and this record does not claim an unobserved local command.

## Explicitly unchanged

- `specs/coordination/program-plan.yaml`;
- `specs/coordination/active-work.yaml`;
- `specs/coordination/task-completions.yaml`;
- `specs/tasks/OPS-006.md` and `evidence/OPS-006/**`;
- GZ-010, OPS-005, POC, business, deployment, Secret, permission and production-data content;
- configured concurrency and high-risk limits;
- OPS-007 terminal Wave occupancy semantics.

## Remaining boundary

- PR #58 remains Draft and unmerged.
- A fresh independent review must target the final Evidence-refresh HEAD.
- Every non-outdated review thread must be resolved against that HEAD.
- Normal merge and post-main Gate remain separate Integrator actions and are not claimed here.

# GZ-014 Program Registration Self-Hosting Maintenance

Status: IN_PROGRESS

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

## Candidate scope

The candidate introduces a general fail-closed Program Task Registration contract before Reservation:

- exactly one ordinary task may move from absent to `planned`;
- one matching schemaVersion 2 Task Spec uses `coordinationMode: registration` and `agentRole: coordinator`;
- Active Work and Completion Ledger remain byte-identical;
- no Lease, implementation scope, execution result or completion authority is granted;
- only task-bound metadata and validated downstream planned dependency tail appends are allowed;
- Program Transition, Lifecycle, Agent Coordination and Task Scope use the same history-aware validator;
- positive and negative behavioral fixtures execute against temporary Git repositories.

## Explicitly unchanged

- `specs/coordination/program-plan.yaml`;
- `specs/coordination/active-work.yaml`;
- `specs/coordination/task-completions.yaml`;
- `specs/tasks/OPS-006.md` and `evidence/OPS-006/**`;
- GZ-010, OPS-005, POC, business, deployment, Secret, permission and production-data content;
- configured concurrency and high-risk limits;
- OPS-007 terminal Wave occupancy semantics.

## Current result boundary

Implementation bytes are being assembled on Draft PR #58. No exact-head test, independent Review, merge or post-main Gate success is claimed by this record. Those facts must be appended only after GitHub returns authoritative results for the immutable candidate HEAD.

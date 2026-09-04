# GZ-014 Program Registration Bootstrap Plan

## Maintenance identity

- Tracking issue: OPS-008 / #57
- Foundation owner: completed GZ-014
- Original GZ-014 completion identity: PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`
- Exact maintenance base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
- Base validation: Governance Gate #446 / run `33736578549` = SUCCESS
- Branch: `fix/GZ-014-program-registration-bootstrap`
- Risk: high
- Shared paths: none

GZ-014 remains completed. This maintenance does not reopen its Foundation state, create an Active Work lease, alter Program Plan or Completion Ledger, or replace the original completion identity.

## Trigger

OPS-006 diagnostic Registration PRs #53 and #56 proved that a task cannot enter the canonical Program Plan through a green absent-to-planned path. Independent review of #56 rejected using bounded red Gate results as integration authority and identified six P1 requirements now captured in OPS-008 #57.

## Implementation contract

Use one dedicated validator, `scripts/check-program-task-registration.py`, as the source of truth for history-aware Registration validation. Integrate it into:

- Task Spec validation for the planned metadata state;
- Program transition validation in task-aware and no-task/push modes;
- Program lifecycle companion-task handling;
- Agent Coordination metadata dispatch;
- Task Scope metadata dispatch.

The validator must fail closed unless the exact target-base diff proves one high/critical absent-to-planned task, one matching schemaVersion 2 planned Task Spec, no Active Work or Completion Ledger drift, no implementation files, only tail-appended dependencies on later planned tasks, valid DAG/final-task closure, exact branch/base identity when available, and complete Program/Task scope parity.

Also add exact MOD-GOV ownership for `docs/25-multi-agent-collaboration-protocol.md` and update AGENTS/protocol documentation to define Registration before Reservation.

## Allowed scope

Only the files listed in OPS-008 #57 are allowed. No Program Plan, Active Work, Completion Ledger, Workflow, OPS-006, OPS-005, GZ-010, POC, business, deployment, Secret, permission or production-data file may change.

## Verification contract

The implementation must add behavioral positive and negative tests, not text-only assertions. Required properties include:

- valid task-aware and no-task Registration;
- valid one/multiple companion tail appends;
- no Lease or ordinary implementation dispatch;
- exact Program/Task identity parity;
- rejection of multiple tasks, non-high risk, existing-task masquerade, missing/mismatched Task Spec, Active/Ledger drift, unrelated files, dependency mutation/reorder/duplicate, invalid Wave/target state, cycles and missing final closure.

Run the full governance suite with zero skipped tests. Record actual commands, exit codes, tested SHA, changed-file inventory, limitations, rollback and independent review in canonical `evidence/GZ-014/**` before integration.

## Self-hosting boundary

Do not add an exception to suppress completed-GZ-014 lifecycle scope. The exact-head Gate may remain red only for the existing completed-task classification of the functional maintenance files. Every production behavior and test must otherwise be green. Merge requires independent exact-head review, explicit Human Owner / Integrator decision and a fully green post-merge main Gate.

No future success or merge is claimed by this planning record.

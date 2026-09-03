# OPS-006 Registration Scope

## Included in this bootstrap

- `specs/coordination/program-plan.yaml`: exactly one planned OPS-006 entry, exactly one append-only dependency reference on planned GZ-020, and registration of the complete future OPS-006 implementation paths.
- `specs/tasks/OPS-006.md`: planned Task identity, future implementation contract, exact first-run failure classification and the narrow terminal-Wave-occupancy rule.
- `evidence/OPS-006/**`: task-bound scope, commands, observed CI results, risk, rollback and handoff records.

## Future implementation paths registered, not modified here

The future OPS-006 implementation includes the Task/coordination/scope/lifecycle checkers plus `scripts/check-project-readiness.py` and their exact governance tests. The Readiness change may only exclude `completed/cancelled` from Wave occupancy. It may not ignore any non-terminal Task, increase capacity or weaken Active Work enforcement.

## Explicitly excluded

OPS-006 Registration excludes Active Work, Completion Ledger, checker implementation, test implementation, Workflows, GZ-003, GZ-010, OPS-005, POC Program content, business code, deployment, production data and Secrets.

The wider output paths in the Program entry are future OPS-006 implementation scope only. They are not authorized until a separate Registration merge, Reservation, Activation and Implementation PR sequence completes.
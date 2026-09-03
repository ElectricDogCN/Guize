# OPS-006 Registration Scope

## Included in this bootstrap

- `specs/coordination/program-plan.yaml`: introduce exactly one planned OPS-006 entry and append OPS-006 to the tail of planned GZ-020 `dependsOn`.
- `specs/tasks/OPS-006.md`: bind the planned Task identity, exact green base, future implementation contract, role separation, validation commands, rollback and handoff.
- `evidence/OPS-006/**`: record current scope, assumptions, risks, commands, actual CI classification and subsequent phase boundaries.

## Future implementation paths registered, not modified here

The Program entry reserves the future Registration-lifecycle implementation surfaces under governance, including the Task checker, coordination and scope dispatchers, transition/lifecycle checkers, protocol documentation, Task template and focused tests.

`check-project-readiness.py` and its focused test remain listed only as compatibility/regression surfaces because OPS-007 already landed the terminal-occupancy rule. OPS-006 may not rewrite that behavior without a separately evidenced regression need.

## Explicitly excluded

Registration excludes:

- `specs/coordination/active-work.yaml`;
- `specs/coordination/task-completions.yaml`;
- every Checker, test and Workflow implementation;
- GZ-003, GZ-010 and OPS-005 Evidence or lifecycle state;
- `specs/poc/**`, `poc/**` and all POC results;
- business code, deployment, production data, permissions and Secrets.

The wider output paths recorded in the Program entry are future OPS-006 implementation authority only. They do not authorize writes until Registration is merged, Reservation is green and merged, and OPS-006 is activated through a separate PR.

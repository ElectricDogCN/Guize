# GZ-004 Reservation Changed Files

Expected Reservation diff:

- `specs/coordination/program-plan.yaml` — only GZ-004 `planned -> reserved`;
- `specs/coordination/active-work.yaml` — exactly one GZ-004 lease;
- `specs/tasks/GZ-004.md` — schemaVersion 2 Reservation Task Spec;
- `evidence/GZ-004/**` — Reservation-only Evidence.

The Reservation PR must not create or modify:

- `specs/requirements/v1/**`;
- `specs/acceptance/requirements/**`;
- `docs/requirements/**`;
- business contracts/code, deployment, Secrets, permissions or production data.
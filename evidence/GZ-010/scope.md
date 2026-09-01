# GZ-010 Reservation Scope

Task: GZ-010

Reservation phase may change only:

- `specs/coordination/program-plan.yaml` — only GZ-010 `planned -> reserved`;
- `specs/coordination/active-work.yaml` — exactly one GZ-010 lease;
- `specs/tasks/GZ-010.md` — schemaVersion 2 Reservation Task Spec;
- `evidence/GZ-010/**` — Reservation-only Evidence.

Reservation must not create or modify:

- `specs/poc/**`;
- `poc/README.md`;
- `evidence/POC-001/**` through `evidence/POC-010/**`;
- any POC command, measurement, result, decision or reviewer conclusion;
- product requirements, acceptance, business contracts/code, deployment, Secrets, permissions or production data.

The output paths `specs/poc/**`, `poc/README.md` and `evidence/GZ-010/**` are reserved for the later registered implementation branch; Reservation itself contains no POC Program implementation output.

# GZ-010 Reservation v2 Scope

Task: GZ-010

## Reservation metadata scope

- `specs/coordination/program-plan.yaml`: only GZ-010 `planned -> reserved`.
- `specs/coordination/active-work.yaml`: exactly one GZ-010 lease.
- `specs/tasks/GZ-010.md`.
- `evidence/GZ-010/**`.

## Reserved implementation scope

- `specs/poc/**`
- `poc/README.md`
- `evidence/GZ-010/**`

## Explicitly excluded

- `evidence/POC-001/**` through `evidence/POC-010/**`;
- `contracts/**`, business code, deployment, tests/scripts changes;
- requirements/acceptance baseline changes;
- secrets, permissions, migrations, production data;
- any POC execution result.

PR #42 is historical only and remains closed/unmerged.

# GZ-004 Implementation Changed Files

Implementation diff is restricted to the existing GZ-004 Task scope.

## Lifecycle metadata

- `specs/coordination/program-plan.yaml` — GZ-004 only: `reserved -> in_progress`;
- `specs/coordination/active-work.yaml` — GZ-004 status/role/base updated to `in_progress` / `implementer` / Reservation merge SHA while preserving lease and registered scope;
- `specs/tasks/GZ-004.md` — same lifecycle identity and implementation-base synchronization.

## Derived contracts and documentation

- `specs/requirements/v1/requirements.yaml`
- `specs/requirements/v1/requirements.schema.yaml`
- `specs/requirements/v1/nfr.yaml`
- `specs/requirements/v1/nfr.schema.yaml`
- `specs/requirements/v1/traceability.yaml`
- `specs/requirements/v1/traceability.schema.yaml`
- `specs/requirements/v1/validate.py`
- `specs/acceptance/requirements/acceptance.yaml`
- `specs/acceptance/requirements/acceptance.schema.yaml`
- `docs/requirements/README.md`
- `evidence/GZ-004/**`

## Explicitly unchanged/read-only

- `specs/requirements/product-requirements.md`
- `specs/requirements/requirements-index.yaml`
- `specs/designs/module-ownership.yaml`
- `.github/**`, `scripts/**`, `tests/**`, `contracts/**`, `data/**`, business/runtime code, deployment, Secrets, permissions and production data.

The final exact diff must be re-checked after the repair commit; any unexpected path is a blocker.

# GZ-004 Implementation Changed Files

Status: IN_PROGRESS

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

## Review-hardening changes inside the same scope

- asset source-deletion no-cascade is bound to `REQ-V1-0002` / `验收V1-0001`;
- Acceptance Requirement declarations and scenario reverse links are fail-closed against the exact V1 Requirement set;
- Program supplemental Acceptance relationships are verified against actual Program task mappings;
- Trace includes exact `programTaskMappingConflicts`, including `REQ-V1-0003 -> GZ-006`;
- Validator negative fixtures expanded to cover those cross-file failure modes.

## Explicitly unchanged/read-only

- `specs/requirements/product-requirements.md`
- `specs/requirements/requirements-index.yaml`
- `specs/designs/module-ownership.yaml`
- `.github/**`, `scripts/**`, `tests/**`, `contracts/**`, `data/**`, business/runtime code, deployment, Secrets, permissions and production data.

The final implementation PR file set remains 19 paths. Task Scope on the latest tested code candidate reported all 19 allowed, 0 forbidden and 0 out-of-scope; the Evidence-only refresh does not add a new path.

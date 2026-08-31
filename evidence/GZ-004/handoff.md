# GZ-004 Reservation Handoff

Status: RESERVATION

## Identity

- Task: `GZ-004`
- Issue: #14
- Reservation branch: `chore/GZ-004-reservation-v3`
- Registered implementation branch: `chore/GZ-004-requirements-baseline`
- Base SHA: `86637ee15aa4d7d57093e96091a61ac671bb31aa`
- Wave / Order: `W1 / 1`
- Risk: `high`
- Lease: `2026-08-31T06:30:00Z` → `2026-09-07T06:30:00Z`

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `requirements-baseline-agent`
- Independent Reviewer: `independent-requirements-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Reserved output paths

- `specs/requirements/v1/**`
- `specs/acceptance/requirements/**`
- `docs/requirements/**`
- `evidence/GZ-004/**`

## Next exact action

Only after this Reservation PR is merged and the resulting `main` Governance Gate succeeds:

1. create/reset `chore/GZ-004-requirements-baseline` from that exact merge commit;
2. update Program/Task/Registry from `reserved` to `in_progress` with the new implementation base SHA;
3. implement only the four reserved output path groups;
4. preserve the approved product authority `specs/requirements/product-requirements.md` unchanged;
5. mark unmeasured numeric targets `MEASUREMENT_REQUIRED` rather than inventing production thresholds.

No downstream consumer task may activate before GZ-004 is completed on `main`.
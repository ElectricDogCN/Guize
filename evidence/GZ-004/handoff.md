# GZ-004 Implementation Handoff

Status: IN_PROGRESS

## Identity

- Task: `GZ-004`
- Issue: #14
- Reservation PR: #36
- Implementation branch: `chore/GZ-004-requirements-baseline`
- Implementation base: `56d6bfacba45d36e82376ebb5a5cea7394c88f0d`
- Wave / Order: `W1 / 1`
- Risk: `high`
- Lease: `2026-08-31T06:30:00Z` → `2026-09-07T06:30:00Z`

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `requirements-baseline-agent`
- Independent Reviewer: `independent-requirements-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Implemented output paths

- `specs/requirements/v1/**`
- `specs/acceptance/requirements/**`
- `docs/requirements/**`
- `evidence/GZ-004/**`
- lifecycle metadata only in `specs/coordination/program-plan.yaml`, `specs/coordination/active-work.yaml`, `specs/tasks/GZ-004.md`

## Authority and reconciliation

`specs/requirements/product-requirements.md` remains the APPROVED/FROZEN product authority; `requirements-index.yaml` and `module-ownership.yaml` remain read-only inputs. The derived Requirement records preserve the exact Requirement Index relation sets.

The Program Plan already references `验收V1-0005`, although the read-only Requirement Index for REQ-V1-0003 does not. The derived baseline records this as an explicit `PROGRAM_SUPPLEMENT`, sourced from the Program Plan, and leaves the Requirement Index-derived `acceptanceIds` untouched. Program POC relationships missing from Requirement Index blockers are similarly carried as `programPocIds` with Program authority rather than silently changing blocker sets.

## Previous exact-head evidence

- Reservation #36 merge: `56d6bfacba45d36e82376ebb5a5cea7394c88f0d`;
- post-Reservation main Gate #333: PASS;
- implementation Gate #343 on `0ffca4bdf1dfe6e3eeec402b18ef1dea048ae783`: FAIL only because GZ-004 was still `reserved`; governance tests 259/259 and all other Gate steps passed.

## Candidate preflight

The repaired candidate passed `validate.py` and all six negative fixtures in a locally materialized exact candidate. GitHub exact-head CI and fresh independent Review are still required and are not pre-claimed.

## Next exact action

1. push the atomic repair commit with Program/Task/Registry `in_progress`;
2. verify actual diff remains inside GZ-004 authorized scope and Program Plan changes only the GZ-004 lifecycle state;
3. require exact-head Governance Gate success;
4. request a fresh high-risk independent review and resolve every blocker;
5. only then advance through review/integration/completion according to the repository lifecycle; do not activate downstream tasks before GZ-004 completion on main.

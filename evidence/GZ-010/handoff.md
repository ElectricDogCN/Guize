# GZ-010 Reservation Handoff

Status: RESERVATION

## Identity

- Task: `GZ-010`
- Issue: #15
- Reservation base: `7c78c15097046d02ce04959b56c485ef76943c49`
- Reservation branch: `chore/GZ-010-reservation`
- Registered implementation branch: `chore/GZ-010-poc-program-baseline`
- Wave / Integration Order: `W1 / 2`
- Work Package: `WP-M0-04`
- Risk: `medium`
- Lease: `2026-09-01T06:45:00Z` → `2026-09-08T06:45:00Z`

## Roles

- Human Owner: `ElectricDogCN`
- Coordinator: `program-coordinator-agent`
- Implementer: `poc-program-agent`
- Independent Reviewer: `independent-poc-program-review-agent`
- Integrator: `integration-agent`

## Program identity

- Depends On: `GZ-014` completed
- Requirements: `REQ-V1-0001～REQ-V1-0010`
- Modules: `MOD-GOV`, `MOD-DEPLOY`, `MOD-DATA`, `MOD-EDGE`, `MOD-MEDIA`, `MOD-AI`, `MOD-SEARCH`, `MOD-SOURCE`, `MOD-CONNECTOR`
- Produces: `POC-PROTOCOL-V1`
- Consumes: none
- Coordination Group: `poc-program`
- Shared paths: `NONE`

## Reserved implementation paths

- `specs/poc/**`
- `poc/README.md`
- `evidence/GZ-010/**`

## Reservation actual/expected files

The final Reservation PR is allowed to contain only:

- `specs/coordination/program-plan.yaml` — GZ-010 `planned -> reserved` only;
- `specs/coordination/active-work.yaml` — one GZ-010 lease;
- `specs/tasks/GZ-010.md`;
- `evidence/GZ-010/**`.

No `specs/poc/**`, `poc/README.md` or `evidence/POC-*` implementation/result file may exist in Reservation.

## Verified predecessor

- GZ-004 completed and Completion Ledger present;
- GZ-004 late Review Evidence repair PR #40 merged as `7c78c15097046d02ce04959b56c485ef76943c49`;
- post-repair `main` Governance Gate #373 / run `33478734549`: PASS;
- PR #39 late P2 threads were resolved after the repaired Evidence entered green `main`;
- Active Work was empty before GZ-010 Reservation.

## Limitations

- No POC has been executed.
- No experiment command, environment fingerprint, measurement, raw result, decision, PASS/FAIL or reviewer conclusion exists yet.
- `specs/poc/**` Schema/Validator is not present until Implementation.
- OPS-001 #20 remains a release-only blocker for GZ-020.
- OPS-002 #41 tracks a Harness Evidence-repair mode and does not change GZ-010 behavior.

## Evidence references

- Summary: `evidence/GZ-010/summary.md`
- Commands: `evidence/GZ-010/commands.txt`
- Test results: `evidence/GZ-010/test-results/README.md`
- Scope: `evidence/GZ-010/scope.md`
- Changed files: `evidence/GZ-010/changed-files.md`
- Assumptions/Risks/Follow-ups: sibling files in `evidence/GZ-010/`
- Security: `evidence/GZ-010/security/README.md`
- Rollback: `evidence/GZ-010/rollback-verification/README.md`

## Rollback

Before Reservation merge, close the PR and retain branch/history. After Reservation merge but before any implementation output, use a dedicated Revert PR to restore only GZ-010 to `planned`, remove only its Active Work lease, and remove its Reservation Task/Evidence artifacts. Never change GZ-004 Completion Ledger or any other Program task, and never push directly to `main`.

## Next exact action

1. Complete Program GZ-010 `planned -> reserved` and canonical Reservation Evidence.
2. Verify GitHub compare contains only Reservation metadata/Evidence.
3. Open Reservation PR, require exact-head Gate and fresh review, and resolve all blocker threads.
4. Merge only exact reviewed HEAD; require post-merge main Gate success.
5. Create/reset `chore/GZ-010-poc-program-baseline` from that merge SHA.
6. Implementation starts with POC Program Schema/policy/indexes; all POC execution/result fields remain unstarted.

# GZ-010 Reservation v2 Handoff

Task: GZ-010
Status: RESERVED candidate

## Identity

- Issue: #15
- Program task: GZ-010
- Wave / order: W1 / 2
- Work Package: WP-M0-04
- Risk: medium
- Base: `main@d23543f97facff00d02f79aab1693a37788765c9`
- Reservation branch: `chore/GZ-010-reservation-v2`
- Implementation branch: `chore/GZ-010-poc-program-baseline`
- Lease: `2026-09-01T08:27:00Z` → `2026-09-08T08:27:00Z`
- Produced contract: `POC-PROTOCOL-V1` (implementation output; not yet produced)

## Roles

- Human Owner: `ElectricDogCN`
- Coordinator: `program-coordinator-agent`
- Implementer: `poc-program-agent`
- Reviewer: `independent-poc-program-review-agent`
- Integrator: `integration-agent`

## Predecessor evidence

- OPS-003 repair merge: PR #44 → `d23543f97facff00d02f79aab1693a37788765c9`.
- Post-repair main Governance Gate #380 / run `33480807557`: SUCCESS.
- Historical GZ-010 PR #42: CLOSED / UNMERGED.
- Historical Gate #374: 258 PASS / 1 FAIL due to schema fixture; not current PASS evidence.

## Reservation scope

Program Plan only marks GZ-010 `reserved`; Registry contains exactly one GZ-010 lease; Task Spec and `evidence/GZ-010/**` are added. No implementation output, POC result, business contract, test/script change, deployment, secret or production data is included.

Exclusive implementation paths reserved after merge:

- `specs/poc/**`
- `poc/README.md`
- `evidence/GZ-010/**`

Shared paths: NONE.

## Reviewer exact action

1. Review the final Reservation v2 HEAD only.
2. Verify compare against `main@d23543f9...` contains exactly the 18 expected Reservation files.
3. Verify Program Plan patch contains only GZ-010 `status: reserved`.
4. Verify Active Work and Task Spec base SHA, roles, branch, scope and lease match exactly.
5. Verify no `specs/poc/**`, `poc/README.md` or `evidence/POC-*` implementation/result file appears.
6. Inspect exact-head Governance Gate and report any failure as blocker.
7. Ensure unresolved blocker thread count is zero.

## Integrator exact action

1. Re-fetch exact HEAD, file list, Program patch, Gate, review and threads.
2. Merge only the reviewed expected HEAD.
3. Verify post-merge `main` Governance Gate SUCCESS.
4. Only after that, create/reset `chore/GZ-010-poc-program-baseline` from the Reservation merge commit.
5. Start implementation with POC Program Schema/index first; do not populate experiment results.

## Rollback

Before merge: close the Reservation PR. After merge but before implementation: use a dedicated revert/correction PR limited to GZ-010 Reservation state. Never rewrite `main` or delete unrelated history.

# GZ-004 Implementation Handoff

Status: IN_PROGRESS

## Identity

- Task: `GZ-004`; Issue #14
- Reservation PR: #36
- Implementation base: `56d6bfacba45d36e82376ebb5a5cea7394c88f0d`
- Branch: `chore/GZ-004-requirements-baseline`
- Wave / Order: `W1 / 1`; Risk: `high`
- Lease: `2026-08-31T06:30:00Z` → `2026-09-07T06:30:00Z`

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `requirements-baseline-agent`
- Reviewer: `independent-requirements-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Authority

`specs/requirements/product-requirements.md` remains the APPROVED/FROZEN product authority. Requirement Index and Module Ownership remain read-only. `验收V1-0005` and Program-only POC relationships are explicit Program supplements and do not mutate index-derived acceptance/blocker sets. Requirement Index / Program task asymmetries are explicitly surfaced by Trace and Validator.

## Completed implementation scope

- exact `REQ-V1-0001..0010` derived requirements baseline;
- NFR baseline with frozen/design/measurement-required separation;
- requirement-level Acceptance with high-risk permission/data-integrity/recovery/production gates;
- Requirement -> Module -> WP -> Acceptance -> POC/Blocker -> Task -> produced-contract trace;
- strict schemas and fail-closed cross-file validator;
- Program supplement and Requirement Index / Program conflict semantics;
- human-readable requirements documentation and canonical Evidence.

## Exact verification facts

- Reservation #36 merge `56d6bfac...`: PASS; post-main Gate #333: PASS.
- Gate #343 on `0ffca4b...`: failed only because lifecycle state was still `reserved`; 259 governance tests and all other checks passed.
- Historical Validator preflight: positive PASS and 6/6 negative fixtures PASS before later review hardening.
- Gate #344 on `0767cc9f...`: all checks PASS except Agent Coordination; 259/259 governance PASS; Task Scope 19/19 PASS.
- Gate #345 on `523a97b...`: same single Agent Coordination failure; all other checks PASS.
- Fresh independent Review on `523a97b...`: four blockers found and all fixed/resolved.
- Gate #349 on `17256dc...`: all checks PASS except the same Agent Coordination activation self-hosting failure.
- Hardened Validator now has 9 negative fixtures, but no final 9/9 runtime PASS is claimed because this chat runtime cannot materialize the exact GitHub worktree; direct GitHub host resolution is unavailable here.

## Fresh-review fixes after 523a97b

1. `REQ-V1-0002` / `验收V1-0001` explicitly requires SourceObject deletion to preserve the logical Asset and remaining references.
2. Acceptance declarations/scenarios must reference only exact known V1 Requirement IDs and must be set-symmetric.
3. `PROGRAM_SUPPLEMENT` Acceptance is validated against actual Program Plan task acceptance+requirement co-occurrence; a stale hard-coded supplement cannot pass.
4. Trace requires exact `programTaskMappingConflicts`; `REQ-V1-0003` records `[GZ-006]` because Requirement Index lists GZ-006 while canonical Program GZ-006 does not consume REQ-V1-0003.

## Self-hosting boundary

The collaboration protocol requires Task/Registry to become `in_progress` on the implementation branch. Program integrity requires the Program status to match that active Registry state. The coordination dispatcher classifies `in_progress` as ordinary implementation and therefore rejects Program Plan because it is deliberately not an implementation-owned path. Expanding task scope or weakening the checker is prohibited.

A one-time Human Owner / Integrator merge override is permissible only if the final exact HEAD has a completed independent Review with zero unresolved blocker and its latest Gate has no failure other than this exact known Agent Coordination self-hosting error. The post-merge `main` Gate must be fully green; otherwise stop and repair/revert before any further lifecycle transition.

## Next role exact action

1. freeze the final implementation HEAD after this Evidence refresh;
2. require exact-head Governance Gate and fresh independent Review;
3. fix any new blocker and repeat until unresolved blocker count is zero;
4. if the only Gate failure is the known activation self-hosting contradiction, Human Owner / Integrator may perform expected-head merge;
5. require post-merge `main` full green;
6. fast-forward the registered branch to that merge and advance GZ-004 through a separate `in_progress -> review` metadata PR;
7. after review-state main is green, use a separate completion PR to set `completed`, remove Active Work, add the completion ledger with the true implementation merge SHA, refresh structured completion Evidence, and close Issue #14 only after post-completion main is green.

Downstream GZ-005+ remains blocked until GZ-004 Completion is present on `main`.

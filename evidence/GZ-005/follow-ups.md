# GZ-005 current contract implementation

Task: GZ-005 / Issue68
Base: 429a6566d81f128cb618c524ee8dc22faba1c0a4
Branch: chore/GZ-005-openapi-baseline
Status: in_progress / implementer; implementation candidate, not accepted

Actual prerequisite main429 was accepted after OPS-004 Completion: local full make verify 527 tests (1150.51s), zero failures/errors/skips; push CI629 run38021268746/job114122569280 succeeded with 527 tests (850.07s). Root main remained clean at the same source/tree. This prerequisite does not certify the new API.

The existing pure Reservation PR70 and valid original lease permit own reserved -> in_progress plus registered contract implementation in one candidate. No additional pure activation merge is required. Lease remains 2026-10-09T11:52:29Z to 2026-10-16T11:52:29Z without renewal. Other Task/Program/Registry identities, ordinary Ledger, permanent policy, requirements, governance scripts/tests/workflows and POC plans are unchanged.

Implemented candidate: modular OpenAPI3.1.1, stable bilingual errors and93 serialized synthetic HTTP pairs; complete approval request intent with RFC8785/SHA256 reference vectors; full safety-extension compatibility comparison; fail-closed assertion reference siblings; typed WebAuthn creation/authentication options and canonical Base64url. Validation dependency hashes lock the separate Linux x86_64/CPython3.12 tool environment.

Examples establish contract consistency, not runtime authorization, valid signatures, browser execution, real POCs or V1 completion. Independent content review and actual published-source 17 checks (including one full make and three API checks), latest same-head CI, post-main validation and separate Completion remain required.

Prior failed346c9b6 activation and d0d93f4 implementation exploratory results remain preserved under test-results/prior-failed-*; their failure is not counted as current PASS. Original archived reservation facts are historical only.

Rollback: closing the unmerged implementation PR leaves main unchanged. A legal blocked state retains lease and capacity; release only after governed cancellation or Completion.

## Historical reservation records (unchanged)
# GZ-005 follow-ups

1. Validate this exact reservation source, archive actual results, obtain independent
   review, pass latest CI and merge with expected head before activation.
2. Implement V1 OpenAPI, stable errors and schema-valid HTTP examples within own paths.
3. Exercise schema/ref resolution, write idempotency, permissions, trace IDs, coverage
   and compatibility with meaningful negative cases; independently review content.
4. GZ-012 incorporates these contract checks into language CI before application builds.
5. Complete GZ-005 separately after the reviewed implementation merges and main passes.

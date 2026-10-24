# OPS-013 implementation design

Status: design candidate; governance code not implemented or accepted. The
reservation actually merged as 3eb9bb69b4fb1df85a359750b73356b953429540.
Five actual-main gates and the unchanged POC checker passed and were independently
accepted. Push CI832 remains pending. This design does not admit OPS-014 yet.

## Result and exact authority

Implement one bounded admission proof for the future independently registered
repair, rather than a general foreign-path allowance. Its authority is the actual
OPS-013 original reservation on the audited main first-parent chain and the
unchanged Git bytes of contract-repair-authorization.json (SHA256
4f344a74a47a56ff1c3b0e27c368767e0cb779ebc61e721b263f102b39a83401).
The declaration identifies the real GZ-021 producer/defect and fixes OPS-014,
its two exact paths and original Git-blob lengths/hashes. A matching Task ID
alone is never evidence of authority.

## Proof and integration

1. Add scripts/poc-contract-repair-admission.py as a read-only proof module.
   Read committed snapshots through Git, not candidate-local JSON or mutable
   worktree evidence. Find the original OPS-013 reserved introduction on the
   supplied integration base's complete first-parent history; check its real
   parent, metadata-only scope, independent roles, exact six governance claims,
   intent bytes, referenced defect bytes and declaration's original two blobs.
   Reject duplicate/reintroduced or late-added authority.
2. Require OPS-013's normal reservation, nonempty implementation, independent
   Review and Completion in canonical history, with released active lease/high
   slot. Reuse existing completed-producer/history primitives only where they
   actually cover Foundation records; retain the normal history gates. Side
   branches, unreachable implementation, direct reserved-to-completed records
   or a candidate-local Completion cannot grant permission.
3. Bind future OPS-014 to its own metadata-only original reservation after that
   completion. Its original base must retain both original approved Git blobs.
   Validate exact two exclusive paths/no shared paths, high/MOD-GOV/Foundation,
   assigned independent roles, live lease, capacity/conflicts, real base and
   immutable original identity. Later Review/Completion audits use this original
   reservation base for the old-blob proof, allowing the intended repair to
   change those files without pretending the new bytes are the old baseline.
4. Integrate the same proof into lifecycle, transition and history ownership
   checks, including frozen recovery admission. Ordinary governance subsets
   and the pre-existing audited legacy path remain unchanged. Only these exact
   authenticated repair claims can supplement ownership; errors fail closed.
   Callers without actual repository/base context cannot obtain this exception.
   Check both rename sides and every candidate commit's registered scope through
   the existing history/lifecycle chain; do not inspect only the final diff.
5. Keep AGENTS17.8 recovery mandatory: before completed GZ-021 contract edits,
   the separately registered repair must establish its actual frozen event,
   bind GZ-021/source/verification, preserve ordinary tasks and follow the
   existing repair verification and separate independently accepted thaw flow.
   Permission to claim two paths is not permission to omit recovery.
6. Update AGENTS17.8 to describe this exact provenance-based supplement to
   MOD-GOV ownership. Do not alter ownership, schemas, ordinary plan membership,
   completed tasks, old ledgers, tests/thresholds or the POC contract itself.

## Verification

Use isolated real Git histories with the existing governance test fixtures.
Cover authentic completed authority and separately reserved successor, then
reject: only an ID, absent/uncompleted authority, sibling history, forged
parents/Completion, late or altered intent, altered defect/raw bytes, changed
original blobs, extra/renamed paths, another successor, appended claims,
invalid roles/lease/capacity, missing original registration and contract edits
without the real frozen recovery. Preserve ordinary Foundation/legacy/normal
task and completed-Evidence semantics. Execute the exact new source's required
checks, full governance/JUnit, make verify, same-head CI and independent review.
Do not change a failed assertion, skip or the existing timeout to get acceptance.

## Handoff and limitations

Implementation remains within the six reserved governance paths and Own
Task/Evidence/necessary lifecycle metadata. Preserve parent480 failures,
cae exact-source terminal proof and actual registration-main proof in Own
Evidence. This task must itself normally enter Review/Completion and release
capacity before OPS-014 is registered. OPS-014 separately decides the minimal
416 diagnostic-body rule and verifies the original 33-byte response; this
design does not change its contract, run a source experiment, qualify either
POC or accept V1. Rollback is a reviewed forward governance change; no history
rewrite or original-evidence deletion.

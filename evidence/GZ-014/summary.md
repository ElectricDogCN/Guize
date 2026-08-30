# GZ-014 Evidence Summary

## Identity

- Issue: #17
- Reservation PR: #18
- Reservation merge: `d731ce09fbf2535948bc1864490539d06ce1f139`
- Program Plan implementation PR: #21
- Implementation merge: `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`
- Post-merge review-repair PR: #22
- Repair branch: `chore/GZ-014-post-merge-review-repair`
- External GitHub enforcement blocker: OPS-001 #20
- Current phase: `POST_MERGE_REVIEW_REPAIR`

## Objective

Reconcile Guize V1 requirements, architecture, machine-contract preparation, ten blocking POCs, engineering scaffolds and M1–M6 delivery into one canonical Program Plan. Ensure multiple Agents can reserve, implement, review, integrate and complete tasks without fabricating dependencies, ownership, completion provenance, Evidence freshness or platform protection.

## Delivered control plane

- canonical Program Plan, Schema, Requirement Index and Module/Public Contract ownership;
- GZ-004～GZ-020 and POC-001～POC-010 DAG with W1～W17 risk/capacity ordering;
- Active Work reservation/lease control;
- permanent ordinary-task Completion Ledger and separate Foundation completion model;
- Program snapshot integrity, target-branch history and finalization checks;
- Task Spec ↔ Active Work ↔ Program Plan lifecycle and identity validation;
- dependency completion ordering and reservation-base ancestry;
- Reservation snapshot proof from the recorded commit;
- narrow ordinary/Foundation Completion PR transition rules;
- completion Evidence freshness and target-base merge verification;
- final GZ-020 transitive release closure;
- live GitHub API verification of Ruleset include/exclude, Required Check, approval, CODEOWNERS, thread resolution, stale-review dismissal, independent approval after the latest push, latest-target-branch testing, deletion protection and non-fast-forward protection;
- mandatory Governance Gate and Makefile wiring for Integrity, History, Finalization, Coordination Dispatcher and Scope Dispatcher.

## Real failures retained as evidence

1. Initial Reservation Gate rejected four asymmetric Requirement/Module mappings and an ambiguous empty shared-scope sentence.
2. Implementation Gate #111 rejected unquoted YAML lease timestamps; values were quoted without weakening the Schema.
3. PR #21 was merged before the manually requested latest-HEAD Codex review completed. The completed review identified additional completion, dependency and provenance blockers, so GZ-014 remained `in_progress` and PR #22 was created.
4. Repair Gate #156 rejected the initial empty-ledger migration, extensionless root `Makefile` path, a test helper that shadowed `unittest.TestCase.run`, and a stale Workflow Contract assertion.
5. Later exact-HEAD reviews identified completion-aware Scope dispatch, schema-versioned Foundation status protection, fresh completion Evidence, target-base merge existence, Ruleset exclude handling, Program/Registry executing-state mapping and completion/finalization provenance gaps.
6. Repair Gate #191 proved the new Finalization control and 223 governance tests passed, but Agent Coordination rejected the Task/Registry path set because the Task expressed the extensionless root `Makefile` as a bare token.
7. Gate #196 succeeded on `da2e1cbf9ca15881fc7cf271b531ffe7353eb067`, including Program Integrity/History/Finalization, completion-aware Coordination/Scope and 200 governance tests after the test suite was consolidated.
8. Mandatory pre-approval review then found that the live Ruleset verifier did not require `strict_required_status_checks_policy=true`; a stale-target-base check could satisfy OPS-001. The verifier and regression suite were corrected.
9. Continued exact-head review found a second independent-review gap: `require_last_push_approval` was not mandatory. The verifier now rejects a Ruleset unless the latest reviewable push must be approved by someone other than its pusher.

No accepted rule was removed or converted to advisory-only behavior.

## Current validation state

The latest code and Evidence commits are newer than all previously successful Gates. Their GitHub Governance Gate and fresh Codex review are authoritative; no prior Gate or review is reused as approval for the changed HEAD.

## Remaining boundary

- PR #22 requires a successful latest-HEAD Governance Gate and a fresh Codex review of the same SHA with no findings.
- All current review threads must remain resolved against current code and tests.
- Merge must use the exact reviewed HEAD; the resulting `main` Gate must succeed.
- A separate Foundation Completion PR must record the actual PR #22 merge SHA, mark GZ-014 completed, remove only its Active Work lease and refresh completion Evidence.
- OPS-001 #20 remains open. GitHub Branch Protection/Ruleset is not considered enabled until live API verification succeeds, including `strict_required_status_checks_policy=true` and `require_last_push_approval=true`.
- Business OpenAPI/Event/DDL/Runtime contracts, POCs, scaffolds and product implementation remain future Program Plan work.

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
- live GitHub API verification of Ruleset include/exclude and required protections;
- mandatory Governance Gate and Makefile wiring for Integrity, History, Finalization, Coordination Dispatcher and Scope Dispatcher.

## Real failures retained as evidence

1. Initial Reservation Gate rejected four asymmetric Requirement/Module mappings and an ambiguous empty shared-scope sentence.
2. Implementation Gate #111 rejected unquoted YAML lease timestamps; values were quoted without weakening the Schema.
3. PR #21 was merged before the manually requested latest-HEAD Codex review completed. The completed review identified additional completion, dependency and provenance blockers, so GZ-014 remained `in_progress` and PR #22 was created.
4. Repair Gate #156 rejected the initial empty-ledger migration, extensionless root `Makefile` path, a test helper that shadowed `unittest.TestCase.run`, and a stale Workflow Contract assertion.
5. A later exact-HEAD review identified six further gaps: completion-aware Scope dispatch, schema-versioned Foundation status protection, fresh completion Evidence, target-base merge existence, Ruleset exclude handling, and Program/Registry executing-state one-to-one mapping.
6. Repair Gate #191 proved the new Finalization control and 223 governance tests passed, but Agent Coordination rejected the Task/Registry path set because the Task expressed the extensionless root `Makefile` as a bare token.
7. The Task now expresses that root file as `./Makefile`; normalization yields the same Registry path without changing scope.

No accepted rule was removed or converted to advisory-only behavior.

## Verified repair state

Governance Gate #192 succeeded on exact HEAD:

`2c8f08ea136fc509bf2d40819fb5eddcaf8f8b4b`

All mandatory workflow steps succeeded, including:

- Task Spec and Project Readiness;
- Program Integrity, History and Finalization;
- completion-aware Agent Coordination;
- governance regression tests and skip audit;
- Markdown and all Schema instances;
- Secret scan;
- Evidence and Evidence integrity;
- PR/Task linkage;
- completion-aware Scope and Spec Sync;
- repository-boundary and Workflow static validation.

This Evidence refresh creates a later HEAD. The Gate and fresh independent review attached to that final HEAD remain authoritative; Gate #192 is not reused as approval for changed Evidence.

## Remaining boundary

- PR #22 requires a successful final Evidence HEAD Gate and a fresh Codex review of the same SHA with no findings.
- All current review threads must be resolved against current code and tests.
- Merge must use the exact reviewed HEAD; the resulting `main` Gate must succeed.
- A separate Foundation Completion PR must record the actual PR #22 merge SHA, mark GZ-014 completed, remove only its Active Work lease and refresh completion Evidence.
- OPS-001 #20 remains open. GitHub Branch Protection/Ruleset is not considered enabled until live API verification succeeds.
- Business OpenAPI/Event/DDL/Runtime contracts, POCs, scaffolds and product implementation remain future Program Plan work.

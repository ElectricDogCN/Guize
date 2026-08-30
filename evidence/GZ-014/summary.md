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

Reconcile Guize V1 requirements, architecture, machine-contract preparation, ten blocking POCs, engineering scaffolds and M1–M6 delivery into one canonical Program Plan. Ensure multiple Agents can reserve, implement, review, integrate and complete tasks without fabricating dependencies, ownership, completion provenance or platform protection.

## Delivered control plane

- canonical `specs/coordination/program-plan.yaml` and Schema;
- GZ-004～GZ-020 and POC-001～POC-010 dependency DAG;
- W1～W17 Wave, capacity, risk and integration ordering;
- requirement index v2;
- 21 modules and 37 public Contract Namespaces with unique owner/consumer/shared-writer rules;
- `active-work.yaml` reservation/lease control;
- permanent ordinary-task completion ledger;
- Program Plan snapshot integrity and target-branch history-transition checks;
- Task Spec ↔ Active Work ↔ Program Plan linkage;
- dependency completion ordering and reservation-base ancestry;
- Foundation-specific completion model;
- final GZ-020 release dependency closure;
- live GitHub API verification before Branch Protection may be marked resolved;
- mandatory local and GitHub Governance Gate integration.

## Real failures retained as evidence

1. Initial reservation Gate rejected four asymmetric Requirement/Module mappings and an ambiguous empty shared-scope sentence.
2. Implementation Gate #111 rejected unquoted YAML lease timestamps; values were quoted without weakening the Schema.
3. PR #21 was merged before the manually requested latest-HEAD Codex review completed. The later review identified additional P1/P2 completion, dependency and provenance gaps, so GZ-014 remained `in_progress` and PR #22 was created.
4. Repair Gate #156 rejected:
   - the first migration because `origin/main` did not yet contain `task-completions.yaml`;
   - the root `Makefile` path because the Task path parser ignored an extensionless root file;
   - a governance test helper named `run`, which shadowed `unittest.TestCase.run`;
   - an outdated Workflow Contract assertion.
5. These defects were corrected by a fail-closed empty-ledger migration rule, machine-readable `./Makefile` path, renamed test helper and updated mandatory workflow assertions.

## Verified repair state

Governance Gate #160 succeeded on exact HEAD:

`fcc4e028822594c3dd8d758dda626977a74f42dc`

Successful mandatory areas included:

- Task Spec;
- Project Readiness;
- Program Plan integrity and history transitions;
- Agent Coordination;
- governance regression tests and skip audit;
- Markdown and Schema validation;
- Secret scan;
- Evidence and Evidence integrity;
- PR/Task linkage;
- Scope and Spec Sync;
- repository-boundary and Workflow static validation.

This Evidence update creates a later HEAD. Its own latest Governance Gate and latest-HEAD independent review remain authoritative; Gate #160 is not reused as approval for a changed commit.

## Remaining boundary

- PR #22 must receive a successful latest-HEAD Gate, fresh Codex review and resolved blocker threads before merge.
- The repair merge must be followed by a successful `main` Gate.
- A separate Foundation Completion PR must record the real repair merge SHA, mark GZ-014 completed, remove only the GZ-014 Active Work lease and finalize Evidence.
- OPS-001 #20 remains open. GitHub Branch Protection/Ruleset is not considered enabled until live API verification succeeds.
- Business OpenAPI/Event/DDL/Runtime contracts, POCs, scaffolds and product implementation remain future Program Plan tasks.

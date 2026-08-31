# GZ-004 Implementation Summary

Status: IN_PROGRESS

- Task: `GZ-004`
- Issue: #14
- Program Wave / Order: `W1 / 1`
- Risk: `high`
- Reservation PR: #36
- Implementation base: `main@56d6bfacba45d36e82376ebb5a5cea7394c88f0d`
- Branch: `chore/GZ-004-requirements-baseline`
- Produces: `REQ-V1`, `NFR-V1`, `ACCEPTANCE-TRACE-V1`

The derived implementation baseline preserves the APPROVED/FROZEN product authority and the exact Requirement Index relationship sets. Program-only Acceptance/POC relationships are carried with explicit Program provenance rather than rewriting the read-only index. Requirement Index vs Program Plan task asymmetries are represented explicitly rather than silently normalized.

The requirement/acceptance/NFR contracts now cover the high-risk invariants raised by independent review: recall-before-ACL plus final ACL recheck, source deletion without logical Asset cascade, source-specific ACL/tag/path/Retention preservation, AI derivative ACL/confidence/generated markers, commercial Provider data-policy and hard-budget gates, cache eviction without Asset mutation, FFmpeg protocol/path/resource boundaries, Temporal pause/resume, and administrator step-up confirmation.

Fresh Review of `523a97be615e2f1a76b231990b894669dc69db4d` found four additional cross-file blockers. Those were fixed by binding source deletion directly to `REQ-V1-0002` / `验收V1-0001`, rejecting unknown Acceptance Requirement IDs and asymmetric declaration/scenario sets, validating `PROGRAM_SUPPLEMENT` against actual Program Plan task mappings, and recording the `REQ-V1-0003 -> GZ-006` Requirement Index / Program Plan conflict via `programTaskMappingConflicts: [GZ-006]` with fail-closed validation.

Gate #343 exposed the missing lifecycle activation. After activation, Gates #344, #345 and #349 all passed Program integrity/history/transitions/finalization/lifecycle, governance regression, Task Scope and every other repository check; their only red step was Agent Coordination rejecting `specs/coordination/program-plan.yaml` as outside ordinary `in_progress` implementation path claims. This is the known first-activation self-hosting contradiction. No checker bypass or scope expansion was introduced.

The validator historically passed its positive path and 6/6 negative fixtures before the latest review hardening. It now contains 9 negative fixtures, including the new Acceptance/Program conflict cases. This chat runtime cannot materialize the exact GitHub worktree for a new direct execution, so a final 9/9 runtime PASS is not claimed; exact-head independent Review and repository/post-merge Gates remain authoritative.

No merge, post-merge or completion success is pre-claimed. Final exact-head independent Review must have zero unresolved blocker before any Human/Integrator override decision, and post-merge `main` must be fully green before lifecycle progression continues.

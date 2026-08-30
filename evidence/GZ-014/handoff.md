# GZ-014 Lifecycle Wrapper Repair Handoff

## Identity

- Task: `GZ-014`
- Issue: #17
- Current phase: `IMPLEMENTATION_FINAL_VALIDATION`
- Clean Reservation PR: #24
- Implementation PR: #25
- Authoritative branch: `chore/GZ-014-test-repair-reservation-v2`
- Implementation base: `main@bb22b4cd8662e6c1ed7d3b63255098d8a74237c1`
- Last validated implementation HEAD before this Handoff refresh: `8914773e6f4c10558ece8cc4f668ced25d0d54c2`
- Governance Gate: run #260, `success`
- Risk: `high`
- Program Wave: `FOUNDATION`
- Integration Order: `1`
- Lease expires: `2026-09-05T01:59:00Z`

The latest GitHub PR HEAD and its corresponding Gate remain authoritative. This Handoff update creates a later HEAD and does not pre-claim its result.

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Explicit path and contract state

- Shared paths: `[]`.
- Produced contracts: `[]`.
- Consumed contracts: `[]`.
- Coordination group: `program-plan-reconciliation`.
- GZ-014 Program Foundation status: `in_progress`.
- Task Spec status: `in_progress`.
- Active Work status: `in_progress`.
- Active Work Lease remains present.

## Historical chain

1. PR #18 established the original Foundation Reservation and merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.
2. PR #21 established the canonical Program Plan and merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.
3. PR #22 hardened lifecycle controls and merged as `903754295e4a0393638c82aa851c3ada8cd507fb`.
4. Post-merge `main` run #237 failed only governance integration tests; production Program/Lifecycle, Coordination, Schema, Scope, Evidence and Spec Sync checks passed.
5. PR #23 was rejected and closed because implementation began without an independent Reservation and canonical Handoff remained stale.
6. PR #24 independently reserved the repair branch/base and merged as `bb22b4cd8662e6c1ed7d3b63255098d8a74237c1`.
7. Before implementation, Task and Registry `baseSha` were both advanced to that merge.
8. PR #25 run #256 found Task/Registry path mismatch and production wrapper recursion.
9. Run #259 showed the recursion fix worked but exposed an unsupported `mapping(key=...)` assumption.
10. Run #260 succeeded on `8914773e6f4c10558ece8cc4f668ced25d0d54c2` with 256 governance tests and every mandatory Gate step passing.

No failure, Review finding or incomplete external control has been deleted from Evidence.

## Implemented repair

### Production wrapper

`run-program-lifecycle-gate.py` now:

- captures the original base `task_ids_from_diff` before monkey-patching;
- uses that immutable function from the extended wrapper;
- keeps exact rename/copy diff semantics;
- keeps POC task derivation;
- maps external blockers locally by explicit `id`;
- keeps completion Issue verification.

The base `check-program-lifecycle-guards.py` was not modified.

### Governance tests

`test_program_lifecycle_guards.py` now:

- executes repository current-state validation through the wrapper;
- uses no Task context when `HEAD == origin/main`;
- keeps explicit GZ-014 context for PR branches;
- monkey-patches the wrapper exactly as runtime does and verifies task derivation does not recurse.

### Task scope

Task prose uses `./Makefile` so the path parser recognizes it and normalizes it to the Registry value `Makefile`. The actual PR does not modify Makefile.

## Actual PR #25 scope

Expected latest files:

- `scripts/run-program-lifecycle-gate.py`;
- `tests/governance/test_program_lifecycle_guards.py`;
- `specs/tasks/GZ-014.md`;
- `specs/coordination/active-work.yaml`;
- `evidence/GZ-014/summary.md`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/changed-files.md`;
- `evidence/GZ-014/test-results/README.md`;
- `evidence/GZ-014/handoff.md`.

Explicitly unchanged:

- base lifecycle guard;
- Governance Workflow;
- Makefile;
- Program Plan;
- product requirements;
- business contracts/code;
- deployment, Secrets, permissions and production data.

## Reviewer exact action

1. Read PR #25 latest diff and latest exact-head Governance Gate.
2. Confirm the wrapper calls `ORIGINAL_TASK_IDS_FROM_DIFF`, not the monkey-patched mutable attribute.
3. Confirm external blockers are mapped by `id` without changing base guard API.
4. Confirm the regression test actually applies the runtime monkey-patch.
5. Confirm Task and Registry paths, branch, base, roles, Lease and empty contract/shared sets remain consistent.
6. Confirm actual changed-file list equals the declared nine paths.
7. Confirm GZ-014 remains `in_progress` and Program Plan is unchanged.
8. Submit fresh Review only for the latest HEAD.

## Integrator exact action

1. Require latest Gate `success` and zero unresolved blocker threads.
2. Re-read GitHub’s current file inventory and commit SHA.
3. Record approval/review decision against that exact HEAD.
4. Merge PR #25 using `expected_head_sha`.
5. Verify the post-merge `main` Governance Gate.
6. Only after that Gate succeeds, create a separate Foundation Completion branch/PR.

## Foundation Completion boundary

The Completion PR must be narrow and auditable:

- mark GZ-014 Foundation and Task Spec `completed`;
- record the actual PR #25 merge commit and completion PR identity;
- remove only the GZ-014 Active Work Lease;
- leave the ordinary Program Task completion ledger unchanged if the accepted Foundation model requires separate provenance;
- update only GZ-014 task-bound Evidence and canonical coordination metadata;
- close Issue #17 using `state_reason=completed` at the stage required by the lifecycle guard;
- pass exact-head Gate, fresh Review, expected-head merge and post-merge `main` Gate.

## Known blockers

- This Evidence refresh requires a new final Gate and Review.
- GZ-004, GZ-010 and all downstream tasks remain blocked until Foundation Completion.
- OPS-001 #20 remains open and gates only GZ-020 production release.

## Rollback

Before merge, close PR #25 and retain its branch/Evidence. After merge, revert only the wrapper/test repair through a dedicated PR; do not reset, force-push or directly modify `main`.
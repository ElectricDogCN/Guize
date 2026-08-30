# GZ-014 Evidence Summary

## Identity

- Task: GZ-014
- Issue: #17
- Original Reservation PR: #18 / merge `d731ce09fbf2535948bc1864490539d06ce1f139`
- Program Plan implementation PR: #21 / merge `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`
- Lifecycle hardening PR: #22 / merge `903754295e4a0393638c82aa851c3ada8cd507fb`
- Failed post-merge `main` Gate: run #237
- Closed unreserved repair attempt: PR #23, not merged
- Clean repair Reservation: PR #24 / merge `bb22b4cd8662e6c1ed7d3b63255098d8a74237c1`
- Current Implementation PR: #25
- Current branch: `chore/GZ-014-test-repair-reservation-v2`
- Implementation base: `main@bb22b4cd8662e6c1ed7d3b63255098d8a74237c1`
- Last validated implementation HEAD before this Evidence refresh: `8914773e6f4c10558ece8cc4f668ced25d0d54c2`
- Governance Gate run #260 on that HEAD: `success`
- External release blocker: OPS-001 #20 remains open
- Current phase: `IMPLEMENTATION_FINAL_VALIDATION`

## Objective

Repair the repository-wide/no-task lifecycle wrapper used by `main` pushes, preserve all accepted Program/Completion/Reservation controls, and restore a green post-merge `main` Gate before completing the GZ-014 Foundation task.

## Root cause and repair

PR #25 run #256 exposed two independent defects:

1. the Task body listed bare `Makefile`, which the scope parser did not recognize as a path even though Registry contained `Makefile`; the Task now uses `./Makefile`, which normalizes to the same Registry value;
2. `run-program-lifecycle-gate.py` replaced `GUARD.task_ids_from_diff` with its extended wrapper, while that wrapper called the same mutable attribute, causing infinite recursion in no-task mode.

The production wrapper now captures the original base implementation once as `ORIGINAL_TASK_IDS_FROM_DIFF` and calls that immutable reference. A regression test monkey-patches the guard exactly as runtime does and verifies task derivation returns without recursion.

Run #259 then exposed a separate API assumption: the base guard's `mapping()` accepts only task-style lists and has no `key=` parameter. External blockers are now mapped locally by explicit `id`; the base guard remains unchanged.

## Verified implementation state

Governance Gate run #260 succeeded on exact HEAD `8914773e6f4c10558ece8cc4f668ced25d0d54c2`:

- Task validation: PASS;
- Project Readiness: PASS;
- Program Integrity/History/Transitions/Finalization/Lifecycle: PASS;
- Agent Coordination: PASS;
- 256 governance tests: PASS;
- skip audit: PASS;
- Markdown/Schema/Secret/Evidence/Scope/Spec Sync/CI static checks: PASS.

This Evidence refresh creates a later HEAD. The Governance Gate attached to the latest PR #25 HEAD is authoritative; run #260 cannot approve a later failed commit.

## Scope boundary

PR #25 is limited to:

- `scripts/run-program-lifecycle-gate.py`;
- `tests/governance/test_program_lifecycle_guards.py`;
- `specs/tasks/GZ-014.md`;
- `specs/coordination/active-work.yaml`;
- `evidence/GZ-014/**`.

The base lifecycle guard, Workflow, Makefile, Program Plan, product requirements, business contracts/code, deployment, Secrets, permissions and production data remain unchanged. GZ-014 remains `in_progress`; its Lease is not released in this Implementation PR.

## Required next sequence

1. latest PR #25 HEAD Governance Gate succeeds;
2. fresh independent Review targets that same HEAD and reports no blocker;
3. all current Review threads are resolved;
4. Integrator rechecks actual GitHub file list and merges with `expected_head_sha`;
5. post-merge `main` Governance Gate succeeds;
6. a separate Foundation Completion PR records the real repair merge, marks GZ-014 completed, removes only its Lease, finalizes task-bound Evidence and closes Issue #17;
7. only then may Wave W1 tasks GZ-004 and GZ-010 be reserved.

## Remaining boundaries

- This Evidence commit requires its own final Gate and Review.
- OPS-001 #20 remains open and gates only GZ-020 production release.
- GZ-004, GZ-010 and all downstream tasks remain blocked until GZ-014 Foundation completion.
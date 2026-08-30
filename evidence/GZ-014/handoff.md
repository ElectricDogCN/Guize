# GZ-014 Foundation Lifecycle-State Repair Handoff

## Identity

- Task: GZ-014
- Issue: #17
- PR: #27
- Branch: `chore/GZ-014-foundation-lifecycle-states`
- Base: `main@ef1048344aa082c678e5ef948dc7f62e5aa84510`
- Last validated pre-Evidence HEAD: `656c7b9c20cd18de2850caa46c734f46a0fc6c90`
- Governance Gate run #268: success
- Program Wave: FOUNDATION
- Risk: high
- Integration Order: 1
- Lease expires: `2026-09-07T00:00:00Z`

The latest PR HEAD and its corresponding Gate are authoritative. This Handoff refresh creates a later HEAD and does not pre-claim its result.

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Defect

The accepted model was contradictory: Foundation Schema excluded `review/integration`, while completion required one of those target-base states. Direct completion was therefore impossible without bypassing a mandatory gate.

## Change

- Foundation state enum now includes `review` and `integration` only;
- current Program Plan remains unchanged and GZ-014 remains `in_progress`;
- ordinary Program Task state enum and transition code remain unchanged;
- new tests validate Schema states, unknown-state rejection and history-aware `integration -> completed` with structured Evidence.

## Actual scope

Expected PR #27 files after Evidence refresh:

- `specs/coordination/program-plan.schema.yaml`;
- `tests/governance/test_foundation_lifecycle_states.py`;
- `specs/tasks/GZ-014.md`;
- `specs/coordination/active-work.yaml`;
- `evidence/GZ-014/summary.md`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/changed-files.md`;
- `evidence/GZ-014/test-results/README.md`;
- `evidence/GZ-014/handoff.md`.

Explicitly unchanged: Program Plan status, lifecycle/transition checker, Workflow, Makefile, product requirements, business contracts/code, deployment, Secrets, permissions and production data.

## Reviewer exact action

1. Read PR #27 latest diff and latest exact-head Gate.
2. Verify Foundation enum adds only `review` and `integration`.
3. Verify ordinary task state definitions and lifecycle code are unchanged.
4. Verify the integration-to-completed test uses actual Git history and structured Evidence.
5. Verify Task/Registry branch, baseSha, roles, Lease and path claims are consistent.
6. Verify GZ-014 remains in_progress and Program Plan is unchanged.
7. Submit Review only for the latest HEAD.

## Integrator exact action

1. Require latest Gate success and zero unresolved blocker threads.
2. Re-read GitHub's actual changed-file inventory.
3. Record authorized re-review against exact HEAD.
4. Merge using `expected_head_sha`.
5. Verify post-merge main Gate.
6. Then create independent review and integration state-transition PRs before Foundation Completion.

## Completion boundary

After this repair enters a green `main`, execute:

```text
in_progress -> review
review -> integration
integration -> completed
```

The final completion must identify PR #26 merge `ef1048344aa082c678e5ef948dc7f62e5aa84510`, refresh structured task-bound Evidence, remove only the GZ-014 Lease, close Issue #17 as completed at the required Gate stage, and leave the ordinary task completion ledger unchanged.

## Rollback

Before merge, close PR #27 and retain branch/Evidence. After merge, revert Schema and test through a dedicated PR; do not reset, force-push or directly modify `main`.

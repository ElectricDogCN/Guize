# GZ-014 Program Registration Bootstrap Plan

## Maintenance identity

- Tracking issue: OPS-008 / #57
- Foundation owner: completed GZ-014
- Original GZ-014 completion identity: PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`
- Exact maintenance base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
- Base validation: Governance Gate #446 / run `33736578549` = SUCCESS
- Branch: `fix/GZ-014-program-registration-bootstrap`
- Risk: high
- Maintenance manifest: `evidence/GZ-014/foundation-maintenance.yaml`
- Shared paths: none

GZ-014 remains completed. This maintenance does not reopen its Foundation state, create an Active Work Lease, alter Program Plan or Completion Ledger, rewrite the completed GZ-014 Task Spec, or replace the original completion identity.

## Trigger

OPS-006 diagnostic Registration PRs #53 and #56 proved that an ordinary task could not enter the canonical Program Plan through a green absent-to-planned path. Independent review of #56 rejected a bounded-red bootstrap as integration authority and identified the missing machine rules now owned by OPS-008 / #57.

## Implementation contract

Use one dedicated validator, `scripts/check-program-task-registration.py`, as the source of truth for history-aware Registration validation. Integrate it into:

- Task Spec validation for the `planned` metadata state;
- Program transition validation in task-aware and push/no-task modes;
- Program lifecycle validation and downstream dependency attachment handling;
- Agent Coordination metadata dispatch;
- Task Scope metadata dispatch.

The validator must fail closed unless the exact target-base diff proves all of the following:

- exactly one high/critical ordinary Program task is absent in base and `planned` in the candidate;
- exactly one matching schemaVersion 2 Registration Task Spec exists;
- Program and Task Spec identities, scope, contracts, roles, Issue, branch pattern and exit gate are equal;
- actual target base and source branch provenance are authoritative in every mode;
- a task-aware PR proves its exact branch, or its two-parent PR merge ref proves the exact target-base first parent and source-branch second parent;
- a push/no-task validation proves a two-parent merge, exact first parent, exact source commit, retained source branch ref and matching merge tree;
- Active Work and Completion Ledger are byte-identical and no Lease or execution authority exists;
- Registration Diff is limited to Program Plan, the new Task Spec and canonical task Evidence;
- only valid tail appends to still-planned same/later-Wave downstream tasks are accepted;
- dependency existence, order, Wave direction, DAG and final-task closure remain valid;
- copy, rename, symlink, path traversal, duplicate IDs, duplicate explicit YAML keys and repository-wide glob claims fail closed;
- task-aware and push/no-task paths enforce the same Task Spec and Evidence contract.

Legitimate YAML `<<` merge inheritance and explicit overrides remain supported; duplicate explicit keys are rejected.

## Startup lifecycle

The authoritative ordinary-task sequence is:

```text
Registration → Reservation → Activation → Implementation
```

Every transition uses a separate PR. Registration is metadata-only and has no Lease. Reservation creates one valid Active Work Lease. Activation changes only `reserved → in_progress`. Implementation begins only after Activation merge and a successful post-main Gate.

## Completed-Foundation maintenance rule

The bootstrap is carried by a machine-enforced completed-Foundation maintenance mode rather than a red-Gate exception. The manifest binds:

- task and tracking Issue;
- exact base SHA and source branch;
- high risk and independent Review;
- post-main Gate requirement;
- an explicit, finite allowed-path list.

The lifecycle guard additionally requires GZ-014 Foundation metadata, completed Task Spec, Program Plan, Active Work and Completion Ledger to remain byte-identical. All changed paths must be owned by MOD-GOV or task-bound Evidence, and temporary files, probes, broad patterns, symlinks and rename/copy escapes are rejected.

The accidental controller probe and temporary `.tmp` files created during connector capability testing have been deleted from the final cumulative Diff. Their historical commits remain visible and are not treated as implementation Evidence.

## Allowed scope

Only files authorized by OPS-008 / #57 and the maintenance manifest may change. Program Plan, Active Work, Completion Ledger, GZ-014 Task Spec, OPS-006 Task/Evidence, workflows, OPS-005, GZ-010, POC, business, deployment, Secret, permission, configured-limit and production-data files remain forbidden.

## Verification contract

Behavioral positive and negative tests must use real temporary Git repositories. Every negative test first proves a valid baseline, applies one mutation, and checks the intended fail-closed result.

Required coverage includes:

- task-aware Registration and two-parent push/no-task Registration;
- branch/base/source-ref provenance and direct-push rejection;
- merge-key support and duplicate explicit key rejection;
- duplicate Program Task ID rejection;
- full Task Spec sections and Handoff validation;
- canonical Evidence, command/exit-code and executable rollback validation;
- non-overridable production Registration dispatch;
- copy, rename, symlink and broad-path rejection;
- downstream tail append, DAG, Wave and final closure;
- non-Registration delegation to unchanged Transition/Lifecycle cores;
- MOD-GOV protocol ownership and the four-stage protocol;
- preserved OPS-007 terminal/non-terminal Wave semantics.

Run pinned dependencies, compile checks, focused suites, full governance JUnit, zero-skip audit, `make verify`, exact-head Governance Gate and independent exact-head Review. Record actual commands, exit codes, tested SHA, changed-file inventory, limitations and rollback in canonical `evidence/GZ-014/**`.

## Merge boundary

A red exact-head Gate is never merge authority. PR #58 may be integrated only when:

1. the exact immutable HEAD Governance Gate is successful;
2. all functional and governance tests pass with zero unexpected skips;
3. independent Review targets the same HEAD and reports no blocker;
4. every non-outdated review thread is resolved;
5. the Human Owner/Integrator decision binds that exact HEAD;
6. merge uses a normal merge commit;
7. the resulting main SHA receives a successful push-triggered Governance Gate.

No future Review, merge or post-main success is claimed by this planning record.

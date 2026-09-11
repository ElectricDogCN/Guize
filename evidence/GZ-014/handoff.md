# GZ-014 OPS-008 Self-Hosting Handoff

Status: READY_FOR_INDEPENDENT_REVIEW

## Identity

- Foundation Task: `GZ-014`, still `completed`.
- Original Foundation completion: PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- Maintenance Issue: #57 (`OPS-008`).
- Draft PR: #58.
- Branch: `fix/GZ-014-program-registration-bootstrap`.
- Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.
- Validated functional source HEAD: `644c34927f945439f02beae4bbfa41a4d52297fe`.
- Validated test merge ref: `c556503aa4a815a98d2fbd824e4e36eedf29a145`.
- Governance Gate: #527 / run `34563651207`, job `103151281804`, success.
- Risk: `high`.
- Shared paths: none.
- Lease: none; no Active Work entry or implementation authority is granted.

Evidence-only commits follow the validated functional source. The final review must bind the actual PR HEAD after this Handoff is committed and after that exact HEAD receives a green Gate. No document pre-writes its own future commit SHA.

## Roles

- Human Owner: `ElectricDogCN`.
- Coordinator: `program-coordinator-agent`.
- Implementer: repository implementation controller.
- Required Independent Reviewer: `chatgpt-codex-connector`, distinct and read-only for the exact final HEAD.
- Integrator: separate integration action plus Human Owner authorization.

## Cumulative changed-file inventory

1. `AGENTS.md`
2. `docs/25-multi-agent-collaboration-protocol.md`
3. `evidence/GZ-014/commands.txt`
4. `evidence/GZ-014/foundation-maintenance.yaml`
5. `evidence/GZ-014/handoff.md`
6. `evidence/GZ-014/program-registration-bootstrap-plan.md`
7. `evidence/GZ-014/rollback-verification/ops-008-program-registration.md`
8. `evidence/GZ-014/summary.md`
9. `evidence/GZ-014/test-results/README.md`
10. `scripts/check-program-lifecycle-guards-core.py`
11. `scripts/check-program-lifecycle-guards.py`
12. `scripts/check-program-plan-transitions-core.py`
13. `scripts/check-program-plan-transitions.py`
14. `scripts/check-program-task-registration.py`
15. `scripts/check-task-file.py`
16. `scripts/run-agent-coordination-gate.py`
17. `scripts/run-task-scope-gate.py`
18. `specs/coordination/README.md`
19. `specs/designs/module-ownership.yaml`
20. `specs/tasks/task-template.md`
21. `tests/governance/test_program_lifecycle_guards.py`
22. `tests/governance/test_program_registration_dispatch.py`
23. `tests/governance/test_program_task_registration.py`

No probe, marker, placeholder, temporary file, Program Plan, Active Work, Completion Ledger, completed GZ-014 Task Spec, OPS-006 Task/Evidence, workflow or later-task file remains in the cumulative diff.

## Completed scope

- Implemented the general, fail-closed `absent → planned` Program Registration mechanism.
- Kept GZ-014 completion identity and lifecycle state immutable.
- Added one one-time completed-Foundation maintenance manifest.
- Added only one ownership delta: a tail append of the protocol path to `MOD-GOV.ownedPaths`.
- Added behavioral temporary-Git regression coverage for valid and invalid Registration, maintenance, dispatcher and post-main push paths.
- Did not perform Reservation, Activation, product implementation, merge or post-main work.

## Delivered contract

The shared validator, lifecycle dispatcher and coordination/scope dispatchers prove:

1. one and only one absent-to-planned high/critical ordinary Program task;
2. one unambiguous schemaVersion 2 Registration Task Spec and complete Program/Task identity equality;
3. exact target-base identity and exact merge-base ancestry for task-aware source branches;
4. local or remote branch-ref provenance only, with tags and other Git DWIM objects rejected;
5. byte-identical Active Work and Completion Ledger and no Lease;
6. Registration-only file scope and fail-closed rename, copy, symlink and path handling;
7. fresh, non-empty, task-bound canonical Evidence with candidate-tree Git-mode inspection;
8. a complete Handoff with identity, roles, base, candidate commit, changed files, contracts, command/exit evidence, limitations, shared paths, security, migration, rollback and next action;
9. executable rollback, revert or restore evidence, with empty/prose-only/N/A rollback rejected;
10. legal later-planned dependency tail append, dependency existence, DAG, Wave, same-Wave integration order and final-task closure;
11. no ordinary coordination, implementation scope, result, review, integration or completion authority at Registration;
12. separate Registration, Reservation and Activation PRs before Implementation;
13. no task-specific allowlist, production validator override, reusable bypass, skip, limit increase or expected-red suppression;
14. completed-Foundation maintenance is one-time and authorized from target-base ownership rather than candidate self-authorization;
15. task-aware completed-Foundation Agent Coordination reruns the canonical lifecycle proof and propagates any nonzero result;
16. post-main push/no-task Agent Coordination derives exactly one maintenance Task from the exact base-to-head diff, reruns the same lifecycle proof and propagates failure;
17. multiple maintenance manifests in one push fail closed;
18. ordinary global active-lease coordination is not used as a substitute for maintenance validation;
19. generalized probe, marker, temporary and placeholder residue fails closed;
20. unchanged ordinary lifecycle behavior and OPS-007 terminal/non-terminal Wave semantics;
21. exact preserved Transition core blob `89a0e302904b12e1f3c33fbc180af1ba3b81090e`;
22. exact preserved Lifecycle core blob `cd1242fbdd8959376635d25e4f4cb4aefa0fa11a`.

## Produced and consumed contracts

- Produced: `PROGRAM-TASK-REGISTRATION-V1` behavior encoded by the shared validator and protocol.
- Consumed: Program Plan, Task Spec, Active Work, Completion Ledger, module ownership and Evidence contracts already present in the repository.
- No product API, event, database, migration or deployment contract was changed.

## Commands and exit codes

- Command: dependency installation/import checks. Exit code: `0`.
- Command: `python -m compileall -q scripts tests`. Exit code: `0`.
- Command: governance collection. Exit code: `0`; 348 tests collected in 0.27 seconds.
- Command: Program integrity/history/transitions/finalization/lifecycle group. Exit code: `0`.
- Command: task-aware Agent Coordination. Exit code: `0`; canonical lifecycle maintenance proof reran.
- Command: push/no-task maintenance dispatcher fixtures. Exit code: `0`; success, failure propagation and multiple-manifest rejection were verified.
- Command: full governance pytest with JUnit. Exit code: `0`; 348 passed, 0 failed, 0 skipped in 62.97 seconds.
- Command: zero-skip audit. Exit code: `0`.
- Command: Markdown, schema, secret, Evidence, branch linkage, Task Scope, spec sync, parent-directory and CI-static checks. Exit code: `0`.
- Command: separately named local `make verify`. Exit code: not executed and not claimed.

## Security and migration

- Security: provenance, path, copy, rename, symlink, stale Evidence, broad scope and candidate self-authorization cases fail closed.
- Post-main safety: maintenance detection is based on the exact push diff and rejects ambiguity before global coordination can run.
- Migration: not applicable; no data or schema migration is performed.
- Secrets and permissions: unchanged; hosted secret scan passed.

## Known limitations and external blockers

- PR #58 remains Draft and unmerged.
- A fresh Gate must succeed on the final Evidence-refresh HEAD.
- A fresh independent exact-head review is mandatory.
- Existing non-outdated review findings must be replied to and resolved only after their fixes are verified on the final HEAD.
- GitHub branch protection/Ruleset remains an external repository setting and is not claimed as enabled.
- Product contracts and implementation remain intentionally incomplete; Project Readiness reports them as non-blocking warnings.
- No OPS-006 Registration, Reservation, Activation, implementation or later-task work is authorized before this maintenance merge and a green post-main Gate.

## Rollback

- Before merge: close PR #58 and preserve its branch and commits for audit.
- After a separately authorized normal merge: create a dedicated Revert PR for the exact maintenance merge.
- Run the executable rollback rehearsal in `evidence/GZ-014/rollback-verification/ops-008-program-registration.md` in an isolated branch or worktree.
- Keep Program Plan, Active Work, Completion Ledger and the completed GZ-014 Task Spec unchanged.
- Never force-push, rewrite history or edit `main` directly.

## Next exact action

1. Require a green Governance Gate on the final Evidence-refresh HEAD.
2. Re-evaluate all review threads against that exact HEAD.
3. Request a fresh independent exact-head review.
4. Repair any new finding without merging.
5. Leave normal merge and post-main validation to a separate Integrator action.

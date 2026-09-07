# GZ-014 OPS-008 Self-Hosting Handoff

Status: READY_FOR_INDEPENDENT_REVIEW

## Identity

- Foundation Task: `GZ-014`, still `completed`.
- Original Foundation completion: PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- Maintenance Issue: #57 (`OPS-008`).
- Draft PR: #58.
- Branch: `fix/GZ-014-program-registration-bootstrap`.
- Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.
- Validated implementation source HEAD: `a0c31ffd409e93ae648c061758600c2aa1addc53`.
- Validated test merge ref: `571336786c60579f42bdccd02b2b780ac1145855`.
- Governance Gate: #495 / run `34141330075`, job `101803750766`, success.
- Risk: `high`.
- Shared paths: none.

Evidence-only commits follow the validated implementation source. The final review must bind the actual PR HEAD returned by GitHub after this Handoff is committed; no document pre-writes its own future commit SHA.

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
7. `evidence/GZ-014/summary.md`
8. `evidence/GZ-014/test-results/README.md`
9. `scripts/check-program-lifecycle-guards-core.py`
10. `scripts/check-program-lifecycle-guards.py`
11. `scripts/check-program-plan-transitions-core.py`
12. `scripts/check-program-plan-transitions.py`
13. `scripts/check-program-task-registration.py`
14. `scripts/check-task-file.py`
15. `scripts/run-agent-coordination-gate.py`
16. `scripts/run-task-scope-gate.py`
17. `specs/coordination/README.md`
18. `specs/designs/module-ownership.yaml`
19. `specs/tasks/task-template.md`
20. `tests/governance/test_program-lifecycle-guards.py`
21. `tests/governance/test_program-registration-dispatch.py`
22. `tests/governance/test-program-task-registration.py`

Authoritative GitHub paths use underscores in the three test filenames:

- `tests/governance/test_program_lifecycle_guards.py`
- `tests/governance/test_program_registration_dispatch.py`
- `tests/governance/test_program_task_registration.py`

No probe, marker, placeholder, temporary file, Program Plan, Active Work, Completion Ledger, OPS-006 Task/Evidence, workflow or later-task file remains in the cumulative diff.

## Delivered contract

The shared validator and dispatchers prove:

1. one and only one absent-to-planned high/critical ordinary Program task;
2. one unambiguous schemaVersion 2 Registration Task Spec and complete Program/Task identity equality;
3. exact base and authoritative source-branch provenance in PR and push/no-task modes;
4. byte-identical Active Work and Completion Ledger;
5. Registration-only file scope and fail-closed rename/copy/symlink/path handling;
6. legal later-planned dependency tail append, valid dependency existence, DAG, Wave and final-task closure;
7. canonical Evidence, Handoff, scope, acceptance and executable validation sections;
8. no Lease, ordinary coordination, implementation scope, result, review, integration or completion authority;
9. separate Registration, Reservation and Activation PRs before Implementation;
10. no task-specific allowlist, production validator override, reusable bypass, skip, limit increase or expected-red suppression;
11. unchanged ordinary lifecycle behavior and OPS-007 terminal/non-terminal Wave semantics;
12. exact MOD-GOV ownership and authoritative collaboration protocol alignment.

## Validation

Gate #495 produced:

- 327 tests collected;
- 327 tests passed;
- 0 failed;
- 0 skipped;
- full governance duration 46.77 seconds;
- Program integrity/history/transitions/finalization/completed-Foundation maintenance success;
- Agent Coordination, Task Scope, Markdown, Schema, Secret, Evidence, branch-linkage, spec-sync, repository-boundary and CI-static success.

The hosted workflow ran each mandatory component directly. It did not expose a separately named `make verify` invocation, so no unobserved local command is claimed.

## Known limitations and external blockers

- PR #58 remains Draft and unmerged.
- A fresh Gate must succeed on the final Evidence-refresh HEAD.
- A fresh independent exact-head review is mandatory.
- Historical review threads that remain non-outdated must be replied to and resolved only after their fixes are verified on the final HEAD.
- GitHub branch protection/Ruleset remains an external repository setting and is not claimed as enabled.
- No OPS-006 Registration, Reservation, Activation, implementation or later-task work is authorized before this maintenance merge and green post-main Gate.

## Rollback

Before merge, close PR #58 and preserve its branch and commits. After a separately authorized normal merge, roll back only through a dedicated Revert PR for the exact maintenance merge. The Revert PR must restore the prior governance files, keep Program Plan/Active Work/Completion Ledger unchanged, and run the full Governance Gate plus representative valid and invalid Registration fixtures. Never force-push, rewrite history or edit `main` directly.

## Next exact action

1. Wait for the Governance Gate on the final Evidence-refresh HEAD to reach a terminal success state.
2. Request a fresh independent exact-head review.
3. Repair any new finding without merging.
4. Resolve only verified review threads.
5. Leave normal merge and post-main validation to a separate Integrator action.

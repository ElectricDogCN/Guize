# GZ-014 OPS-008 Self-Hosting Handoff

Status: IN_PROGRESS

## Identity

- Foundation Task: `GZ-014`, still `completed`.
- Original Foundation completion: PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- Maintenance Issue: #57 (`OPS-008`).
- Draft PR: #58.
- Branch: `fix/GZ-014-program-registration-bootstrap`.
- Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.
- Risk: `high`.
- Shared paths: none.

## Roles

- Human Owner: `ElectricDogCN`.
- Coordinator: `program-coordinator-agent`.
- Implementer: current repository implementation agent.
- Required Independent Reviewer: a distinct reviewer on the immutable final HEAD.
- Integrator: `integration-agent` plus Human Owner authorization.

## Intended files

- `scripts/check-program-task-registration.py`;
- Program transition/lifecycle entry and preserved core files;
- Agent Coordination and Task Scope dispatchers;
- focused behavioral tests under `tests/governance/**`;
- `AGENTS.md`;
- `docs/25-multi-agent-collaboration-protocol.md`;
- `specs/coordination/README.md`;
- `specs/tasks/task-template.md`;
- `specs/designs/module-ownership.yaml`;
- task-bound `evidence/GZ-014/**`.

The exact cumulative GitHub changed-file inventory must be copied into this handoff after the candidate HEAD is stable. No file outside Issue #57's allowed scope is authorized.

## Contract

The shared validator must prove:

1. one and only one absent-to-planned high/critical ordinary Program task;
2. complete Program/Task identity equality;
3. exact base and branch identity;
4. byte-identical Active Work and Completion Ledger;
5. Registration-only file scope and safe rename/copy/symlink behavior;
6. legal later-planned dependency tail append, valid DAG/Wave and final-task closure;
7. no Lease, ordinary coordination, implementation scope, result or completion authority;
8. a separate existing `planned -> reserved` lifecycle after Registration;
9. no task-specific allowlist, reusable bypass, skip, limit increase or expected-red suppression;
10. unchanged OPS-007 terminal/non-terminal Wave semantics.

## Commands and results

The final Handoff must record, with actual exit codes and counts:

```bash
python -m pip install -r requirements-governance.txt
python -m compileall -q scripts tests
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python -m pytest tests/governance/ -v -ra
make verify TASK=GZ-014 BASE=origin/main HEAD_REF=HEAD BRANCH=fix/GZ-014-program-registration-bootstrap
```

Current status: not yet accepted as exact-head remote Evidence. GitHub CI and local reruns must be read back before changing this status.

## Limitations and blockers

- PR #58 remains Draft.
- The existing completed-GZ-014 self-hosting lifecycle scope classification may remain the sole PR-level red condition; it must not be suppressed.
- Independent exact-head review is mandatory and currently not recorded.
- No OPS-006 Registration, Reservation, Activation, implementation or later-task work is authorized yet.

## Rollback

Before merge, close PR #58 and preserve its branch/commits as evidence. After a separately authorized merge, roll back only through a dedicated Revert PR for the exact maintenance merge. Validate the restored Program/Registry/Ledger snapshots, full Governance Gate, and both valid and invalid synthetic Registration fixtures. Never force-push, rewrite history or edit `main` directly.

## Next exact action

Stabilize the implementation HEAD, run all commands and CI, populate exact files/test counts/exit codes, request an independent exact-head review, and stop before merge.

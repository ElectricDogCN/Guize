# GZ-014 Program Registration Self-Hosting Maintenance

Status: READY_FOR_INDEPENDENT_REVIEW

## Immutable Foundation identity

- Foundation task: `GZ-014` remains `completed`.
- Original completion identity remains PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- Program Plan, Active Work Registry, Completion Ledger and the completed GZ-014 Task Spec remain byte-identical to the target base.

## Maintenance identity

- Tracking: OPS-008 / Issue #57.
- Draft PR: #58.
- Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.
- Branch: `fix/GZ-014-program-registration-bootstrap`.
- Risk: high.
- Validated functional source HEAD: `644c34927f945439f02beae4bbfa41a4d52297fe`.
- Validated synthetic PR merge ref: `c556503aa4a815a98d2fbd824e4e36eedf29a145`.
- Governance Gate: run #527 / `34563651207`, job `103151281804`, conclusion `success`.

The Evidence refresh follows the validated functional source. Its final exact HEAD must receive a fresh green Governance Gate before review. No Evidence file attempts to pre-record its own future commit SHA.

## Delivered contract

The candidate establishes a general fail-closed Program Task Registration contract before Reservation:

- exactly one ordinary task may move from absent to `planned`;
- one matching schemaVersion 2 Task Spec must use `coordinationMode: registration`, `agentRole: coordinator` and high/critical risk;
- Active Work and Completion Ledger remain byte-identical and no Lease or execution authority is created;
- Program Transition, Lifecycle, Agent Coordination and Task Scope use the same history-aware validator;
- task-aware source-branch validation requires the target base to be the exact merge base;
- provenance accepts only fully qualified local or remote branch namespaces, never tags or other Git DWIM objects;
- every mandatory Registration Evidence artifact is fresh, non-empty and task-bound, and every candidate Evidence-tree entry is checked for unsafe modes and symlinks;
- Handoff is structured and resumable, with identity, roles, base, candidate commit, changed files, contracts, commands/exits, limitations, rollback and next action;
- copy, rename, path traversal, repository-wide globs, duplicate rows or YAML keys, incomplete Task Specs, stale Evidence and invalid rollback fail closed;
- same-Wave dependencies must precede the new task by integration order, while same-Wave downstream attachment targets must follow it;
- completed-Foundation maintenance is one-time, manifest-bound and authorized from immutable target-base ownership;
- the only ownership change is one tail append of `docs/25-multi-agent-collaboration-protocol.md` to `MOD-GOV.ownedPaths`;
- completed-Foundation Agent Coordination reruns the canonical lifecycle proof in both task-aware PR and push/no-task modes;
- the push/no-task dispatcher derives the maintenance Task only from the exact base-to-head diff, rejects multiple maintenance manifests and propagates any lifecycle failure unchanged;
- ordinary global coordination is not used as a substitute for the maintenance lifecycle proof;
- ordinary non-Registration behavior delegates to the preserved exact core implementations;
- positive and negative behavioral fixtures execute against temporary Git repositories and prove their valid baseline before mutation.

## Exact validation result

On Gate #527 for functional source HEAD `644c34927f945439f02beae4bbfa41a4d52297fe`:

- dependency installation and import verification: success;
- Python compilation: success;
- governance collection: 348 tests in 0.27 seconds;
- full governance suite: 348 passed, 0 failed, 0 skipped in 62.97 seconds;
- Project Readiness: success with truthful non-blocking warnings for the external Ruleset and unfinished product contracts/implementation;
- Program integrity, history, transitions, finalization and one-time completed-Foundation maintenance: success;
- maintenance scope: 23 changed paths, 17 authorized path claims, zero errors;
- task-aware and push/no-task Agent Coordination: success;
- Task Scope: success;
- Markdown: 189 files checked, success;
- schema, secret, Evidence, branch linkage, spec sync, repository boundary and CI-static validation: success.

The workflow executed the mandatory validators and full suite directly. It did not execute a separately named `make verify` command, and this record does not claim an unobserved local command.

## Explicitly unchanged

- `specs/coordination/program-plan.yaml`;
- `specs/coordination/active-work.yaml`;
- `specs/coordination/task-completions.yaml`;
- `specs/tasks/GZ-014.md`;
- `specs/tasks/OPS-006.md` and `evidence/OPS-006/**`;
- GZ-010 state and Lease data;
- OPS-005, POC, business, deployment, Secret, permission and production-data content;
- configured concurrency and high-risk limits;
- OPS-007 terminal/non-terminal Wave occupancy semantics;
- `.github/workflows/**`.

## Remaining boundary

- PR #58 remains Draft and unmerged.
- A fresh independent review must target the final Evidence-refresh HEAD after its Gate succeeds.
- All non-outdated review threads must be resolved against that exact HEAD.
- Normal merge and post-main Gate remain separate Integrator actions and are not claimed here.

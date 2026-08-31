# GZ-003 Handoff

Task: GZ-003
Merge: 9e3a821ada292ac3ef69b7c059384d17f6530b48
Status: PASS

## Identity

- Original Task: GZ-003
- Issue: #10
- Original PR: #11
- Original merge: `9e3a821ada292ac3ef69b7c059384d17f6530b48`
- Maintenance PR: #35
- Branch: `chore/GZ-003-multi-agent-readiness`
- Target base: `main@3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`
- GZ-003 state remains `completed`

## Trigger

GZ-004 Reservation PR #34 exposed governance tests coupled to historical GZ-014 active state. GZ-004 forbids `tests/**`; #34 was closed and the defect was isolated to governance maintenance.

## Final maintenance scope

The final candidate contains only:

1. `tests/governance/test_check_schemas.py`;
2. `tests/governance/test_program_lifecycle_guards.py`;
3. `evidence/GZ-003/summary.md`;
4. `evidence/GZ-003/commands.txt`;
5. `evidence/GZ-003/handoff.md`;
6. `evidence/GZ-003/test-results/README.md`.

`scripts/check-program-lifecycle-guards.py` has been restored exactly to the target-main blob and must not appear in the final PR diff.

No Program Plan, Active Work, Completion Ledger, Task Spec, Schema, Workflow, Makefile, product requirement, business contract/code, deployment, Secret, permission, production data or downstream activation is modified.

## Functional repair

- Schema copied-fixture setup now includes Task Specs for all currently active Registry tasks using the same exact-or-unique-suffix resolution supported by production validation.
- The missing-Lease negative fixture explicitly clears Active Work before reserving GZ-004 in Program data.
- The repository lifecycle smoke test no longer injects GZ-014 whenever HEAD differs from `origin/main`; it invokes the wrapper generically, while dedicated unit tests continue to prove that Program/Registry/Task changes derive GZ-004 and other task IDs.
- No negative guard or fail-closed production checker is removed or weakened.

## Break-glass rationale

The current production lifecycle guard intentionally treats a completed GZ-003 task as metadata-only, so the pull-request Gate cannot authorize the very `tests/governance/**` edits required to remove its stale self-hosting assumptions. Adding a machine exception to that same checker was reviewed and rejected because it would leave a reusable bypass.

Accordingly, the only acceptable path is a one-time Human Owner / Integrator override on a test-only PR after exact-head review. The override is valid only if the known metadata-scope failure is the sole remaining Gate failure and the final repository state contains no bootstrap exception.

## Reviewer exact action

1. Review the latest PR #35 HEAD only.
2. Verify actual changed files equal the six paths listed above.
3. Verify `scripts/check-program-lifecycle-guards.py` is identical to `main` and absent from the diff.
4. Verify both test changes are state-agnostic and retain all existing negative assertions.
5. Inspect latest Governance Gate: governance tests and every non-bootstrap-scope check must pass; only the completed-GZ-003 test-scope lifecycle rejection may remain.
6. Report any additional failure or design flaw as a blocker.

## Integrator exact action

1. Re-fetch exact HEAD, six-file diff, Gate, reviews and unresolved threads.
2. Re-review the exact HEAD before approval.
3. If and only if the sole red check is the documented self-hosting scope deadlock, record explicit break-glass approval and merge with `expected_head_sha`.
4. Verify the post-merge `main` Governance Gate is fully successful with no exception code in the tree.
5. Re-close Issue #10.
6. Rebuild GZ-004 Reservation from that new green main; do not reuse PR #34.

## Rollback

Before merge, close PR #35. After merge, use a dedicated Revert PR for the two test files and Evidence; never rewrite `main` directly.

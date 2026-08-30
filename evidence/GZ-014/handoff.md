# GZ-014 Post-Merge Review-Repair Handoff

## Identity

- Task: GZ-014
- Issue: #17
- Reservation PR: #18
- Program Plan implementation PR: #21
- Implementation merge/base for repair: `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`
- Repair PR: #22
- Repair branch: `chore/GZ-014-post-merge-review-repair`
- Risk: high
- Program Wave: `FOUNDATION`
- Integration Order: 1

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`
- Lease expires: `2026-09-05T01:59:00Z`

## Completed repair scope

1. Added mandatory Program Plan snapshot-integrity and target-branch history-transition checks.
2. Added permanent ordinary-task completion ledger and Schema.
3. Bound completed ordinary tasks to Task Spec, Evidence, Handoff, Reservation PR/commit and implementation PR/merge commit.
4. Added Reservation commit snapshot validation against `active-work.yaml`, Task Spec, base SHA, roles and path claims.
5. Added append-only/immutable completion-record checks.
6. Added separate Foundation completion semantics without ordinary ledger use.
7. Prevented completed Foundation provenance regression.
8. Prevented completing a dependency and activating its downstream task in the same change.
9. Required dependency merge identity to be contained in downstream Reservation `baseSha`.
10. Required GZ-020 to transitively depend on all non-release Program tasks.
11. Required live GitHub API verification before Branch Protection may be marked resolved.
12. Added mandatory Governance Gate and Makefile integration.
13. Added positive and negative regression tests for completion, Foundation, dependencies, external blockers and release closure.

## Real validation history

- Reservation initial Gate: failed on mapping and shared-scope defects, then #109 succeeded.
- Program implementation Gate #111: failed on YAML timestamp typing, then repaired.
- PR #21 merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`; latest-HEAD review completed afterward and produced additional blockers.
- Repair Gate #156 on `8ff0fc026a79511382c774ddb5aab40a5d7b6a88`: failed on initial ledger migration, root `Makefile` path parsing, a test-runner naming collision and stale workflow assertions.
- Repair Gate #160 on `fcc4e028822594c3dd8d758dda626977a74f42dc`: all mandatory steps succeeded.

Evidence updates after #160 create a later HEAD. Reviewer and Integrator must use the Gate attached to the final HEAD, not reuse #160 as approval.

## Remaining blockers before repair merge

1. Latest PR #22 Governance Gate must be successful.
2. Fresh Codex review must target the exact latest HEAD.
3. Every non-outdated blocker thread must be resolved only after confirming the fix.
4. Integrator must compare actual changed files against GZ-014 scope.
5. Merge must use `expected_head_sha`.

## Reviewer exact action

1. Read the latest PR #22 diff and current Task/Registry/Evidence, not this Handoff alone.
2. Verify all earlier P1/P2 review findings against current code and negative tests.
3. Verify `check-program-plan-integrity.py` and `check-program-plan-history.py` are mandatory workflow and local gates.
4. Verify ordinary Completion PR and Foundation Completion PR cannot change unrelated Program, Registry, ledger, code or governance files.
5. Verify Reservation snapshot, exact PR/Task token, append-only ledger, dependency timing, final release closure and live Ruleset verification are fail-closed.
6. Confirm no business contract, business implementation, POC result, Secret, deployment runtime or production change entered PR #22.

## Integrator exact action

1. Confirm latest-HEAD Gate success and latest-HEAD review without blocker.
2. Confirm all review threads are resolved.
3. Compare PR #22 against `main@3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.
4. Merge with `expected_head_sha` and record the actual repair merge SHA.
5. Verify the resulting `main` Governance Gate succeeds.
6. Create a separate GZ-014 Foundation Completion PR that:
   - changes only GZ-014 Foundation completion identity in Program Plan;
   - removes only the GZ-014 Active Work entry;
   - updates GZ-014 Task Spec and Evidence;
   - does not add an ordinary completion-ledger record;
   - passes the new history and coordination gates.

## Known external blocker

OPS-001 #20 remains open. Repository files and CI do not prove GitHub Branch Protection/Ruleset is configured. GZ-020 release remains blocked until the live API verifier succeeds.

## Rollback

Before merge, close PR #22 and retain its branch and Evidence. After merge, create a dedicated revert branch and PR; do not reset or directly push `main`. Re-run Task, Readiness, Program Integrity/History, Coordination, Governance tests, Evidence, Scope and Spec Sync after rollback.

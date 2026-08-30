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

1. Program Plan snapshot integrity and target-branch history validation.
2. Program Finalization validation for Program/Registry state mapping, Foundation Task Spec lifecycle, completion Evidence freshness, target-base merge ancestry and live Ruleset behavior.
3. Permanent ordinary-task Completion Ledger and separate Foundation completion model.
4. Reservation commit snapshot validation against the recorded `active-work.yaml`, Task Spec, base SHA, roles, dependencies and paths.
5. Append-only completion records and immutable completed Foundation provenance.
6. Dependency completion must pre-exist in the target branch and be contained in downstream Reservation `baseSha`.
7. Completion PR changed-file restrictions for the current task only.
8. Completion Evidence must refresh Handoff, Summary, Commands and Test Results and record the full implementation merge SHA.
9. Final GZ-020 release transitive closure and external-blocker enforcement.
10. Mandatory Governance Gate and Makefile wiring for Integrity, History, Finalization, completion-aware Coordination and completion-aware Scope.
11. Live Ruleset validation covers include/exclude conditions, Required Governance Check, at least one approval, CODEOWNERS, stale-review dismissal, thread resolution, latest-target-branch testing, independent approval after the latest push, deletion protection and non-fast-forward protection.
12. Positive/negative governance tests cover all above conditions.

## Real validation history

- Initial Reservation Gate failed on mapping and shared-scope defects; #109 then succeeded.
- Program implementation Gate #111 failed on YAML timestamp typing; the accepted Schema was preserved.
- PR #21 merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`; a review completed afterward and produced additional blockers.
- Repair Gate #156 failed on initial ledger migration, root `Makefile` parsing, a test helper naming collision and stale workflow assertions.
- Subsequent reviews added completion/finalization blockers covering Scope/Coordination dispatch, Foundation lifecycle, Evidence freshness, target-base merge existence, Ruleset excludes, Program/Registry state mapping, ledger/history and dependency ordering.
- Repair Gate #191 on `771daf58415f1001085d19c4781176acf99afcb0` passed Integrity/History/Finalization and 223 tests but failed Agent Coordination because `Makefile` was expressed as a bare extensionless token.
- The Task uses `./Makefile`, normalized to the same Registry path.
- Repair Gate #196 on `da2e1cbf9ca15881fc7cf271b531ffe7353eb067` succeeded across every mandatory step and 200 governance tests.
- Mandatory manual review after #196 found missing `strict_required_status_checks_policy=true`; the verifier and regression suite were updated.
- Gate #202 on `7e38d391e3c1e997f5e90081d747dd0fe99a4dc0` succeeded on that repair.
- Continued exact-head review found missing `require_last_push_approval=true`; the verifier and regression suite were updated before approval.

The latest code and Evidence commits create a later HEAD. Reviewer and Integrator must use the Gate and review attached to that exact final HEAD; no earlier Gate is approval for a changed SHA.

## Remaining blockers before repair merge

1. Latest Evidence HEAD Governance Gate must succeed.
2. A fresh Codex review must target that same exact HEAD and report no findings.
3. All review threads must remain resolved after the latest code change.
4. Integrator must compare all actual changed files against GZ-014 scope and confirm no business/deployment/Secret/data change.
5. Approval and merge must be anchored to the exact reviewed HEAD.

## Reviewer exact action

1. Read the final PR #22 diff, Task, Registry, Program Plan, Ledger and Evidence.
2. Verify Completion Scope uses `run-task-scope-gate.py` in both CI and Makefile.
3. Verify schema-versioned completed Foundations cannot use `approved`; true pre-schema legacy Foundations remain compatible.
4. Verify Completion Evidence freshness and target-base implementation merge ancestry.
5. Verify Ruleset includes/excludes, `strict_required_status_checks_policy=true` and `require_last_push_approval=true` are enforced by the live API verifier.
6. Verify Program executing states and Active Work entries are one-to-one with matching status.
7. Recheck completion ledger immutability, dependency ordering, release closure and Reservation snapshot controls.
8. Confirm no product requirement, business contract, business implementation, POC result, production deployment, Secret or formal data operation entered PR #22.

## Integrator exact action

1. Confirm final exact-head Gate success and exact-head no-finding review.
2. Confirm all review threads are resolved.
3. Confirm PR #22 remains mergeable against its revalidated `main` base.
4. Merge with `expected_head_sha` and record the actual repair merge SHA.
5. Verify the resulting `main` Governance Gate succeeds.
6. Create a separate GZ-014 Foundation Completion PR that:
   - records the real repair merge SHA and PR identity;
   - updates only GZ-014 Foundation completion fields;
   - removes only the GZ-014 Active Work entry;
   - leaves the ordinary Completion Ledger unchanged;
   - updates GZ-014 Task Spec and refreshes the four required completion Evidence files;
   - passes Integrity, History, Finalization, Coordination, Scope, Evidence and review.

## Known external blocker

OPS-001 #20 remains open. Repository files and CI do not prove GitHub Branch Protection/Ruleset is configured. GZ-020 remains blocked until the live API verifier succeeds, including latest-target-branch testing and independent approval of the latest reviewable push.

## Rollback

Before merge, close PR #22 and retain its branch and Evidence. After merge, create a dedicated revert branch and PR; do not reset or directly push `main`. Re-run Task, Readiness, Integrity, History, Finalization, Coordination, Governance tests, Evidence, Scope and Spec Sync after rollback.

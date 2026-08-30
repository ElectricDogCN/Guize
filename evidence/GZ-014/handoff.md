# GZ-014 Test-Repair Reservation V2 Handoff

## Identity

- Task: `GZ-014`
- Issue: #17
- Current phase: `ACTIVE_BRANCH_RESERVATION_REVIEW`
- Reservation PR: #24
- Authoritative branch: `chore/GZ-014-test-repair-reservation-v2`
- Reservation target base: `main@903754295e4a0393638c82aa851c3ada8cd507fb`
- Last fully successful Reservation HEAD before P1 remediation: `8efc71cf21ca0a6c9543722b89d8cad37cc71018`
- P1-remediated validation HEAD: `3ac73f887c1c52b17d9a3d09636fe0406d746737`
- Governance Gate: run #252, `success` on `3ac73f887c1c52b17d9a3d09636fe0406d746737`
- Risk: `high`
- Program Wave: `FOUNDATION`
- Integration Order: `1`
- Lease expires: `2026-09-05T01:59:00Z`

The canonical latest PR HEAD and its GitHub Actions run remain authoritative. This Handoff records exact observed revisions but does not pre-claim that this later Handoff-only commit has passed.

## Roles

- Coordinator: `program-coordinator-agent`
- Implementer: `governance-hardening-agent`
- Independent Reviewer: `independent-governance-review-agent`
- Integrator: `integration-agent`
- Human Owner: `ElectricDogCN`

## Explicit path and contract state

These values are intentionally explicit so a replacement Agent does not need to infer whether data was omitted:

- Exclusive paths: the exact ordered set declared identically in `specs/tasks/GZ-014.md` and `specs/coordination/active-work.yaml`; PR #24 may modify only the eight Reservation metadata/Evidence paths listed below.
- Shared paths: `[]` — none; GZ-014 has no shared write path in this Reservation or active Lease.
- Produced contracts: `[]` — none; no produced contract version exists for this Reservation.
- Consumed contracts: `[]` — none; no consumed contract version exists for this Reservation.
- Coordination group: `program-plan-reconciliation`; it does not grant shared-path access because `sharedPaths` is empty.

## Historical chain retained

1. PR #18 established the original GZ-014 Reservation and merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.
2. PR #21 established the canonical Program Plan and merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.
3. PR #22 hardened Program lifecycle controls and merged as `903754295e4a0393638c82aa851c3ada8cd507fb`.
4. Post-merge `main` Governance Gate run #237:
   - Program Integrity/Lifecycle: PASS;
   - Agent Coordination: PASS;
   - Schema/Scope/Evidence/Spec Sync: PASS;
   - Governance tests: FAIL;
   - overall conclusion: FAIL.
5. PR #23 attempted the test repair in the same change that moved the Lease. It was closed without merge after Review found:
   - the new branch had no prior merged Reservation;
   - the registered Handoff remained stale;
   - the test hard-coded GZ-014 for every future `main` push.
6. PR #24 was created as a clean Reservation-only recovery from `main@903754...`.
7. PR #24 Governance Gate run #245 succeeded on HEAD `8efc71cf21ca0a6c9543722b89d8cad37cc71018`.
8. Fresh Codex Review then raised five P1 findings for canonical state/Evidence consistency.
9. Those five findings were remediated; Governance Gate run #252 succeeded on `3ac73f887c1c52b17d9a3d09636fe0406d746737`.
10. Fresh exact-HEAD Review found one remaining P1: this Handoff did not explicitly state empty shared-path and contract sets. This commit adds those audited values without changing Task, Registry, Program, tests or scripts.

No prior failure, review finding, or incomplete platform control has been removed from this record.

## Current canonical state

The following facts must all remain true in PR #24:

- Program Plan Foundation GZ-014 status: `in_progress`;
- Task Spec status: `in_progress`;
- Active Work status: `in_progress`;
- Task/Registry branch: `chore/GZ-014-test-repair-reservation-v2`;
- Task/Registry base SHA: `903754295e4a0393638c82aa851c3ada8cd507fb`;
- Task/Registry roles, exclusive paths, empty shared paths, empty contract sets, Lease, Handoff and integration order: identical;
- Program Plan: unchanged by this Reservation PR;
- no `tests/**`, `scripts/**`, business contract/code, deployment, Secret, permission or data modification.

## PR #24 changed-file inventory

The intended and reviewable changed paths for the remediated Reservation are:

- `specs/coordination/active-work.yaml`;
- `specs/tasks/GZ-014.md`;
- `evidence/GZ-014/handoff.md`;
- `evidence/GZ-014/test-repair-reservation-v2.md`;
- `evidence/GZ-014/summary.md`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/changed-files.md`;
- `evidence/GZ-014/test-results/README.md`.

The Integrator must re-read GitHub’s actual latest file list before merge and reject any unexpected path.

## Executed operations and observed results

| Operation | Exit/result | Observed outcome |
|---|---:|---|
| Read `main` ref after PR #22 | HTTP 200 / success | `main=903754295e4a0393638c82aa851c3ada8cd507fb` |
| Read `main` run #237 | HTTP 200 / failure conclusion | governance tests failed; other mandatory control-plane checks passed |
| Review PR #23 | success | PR closed, not merged; branch/history retained |
| Create PR #24 Reservation | success | clean Reservation-only PR opened against `main@903754...` |
| Governance Gate run #245 | exit 0 / success | exact HEAD `8efc71cf21ca0a6c9543722b89d8cad37cc71018` passed |
| First fresh Codex Review of PR #24 | review completed / 5 P1 | canonical state, Handoff, implementation base, reservation-only prohibition and canonical Evidence required remediation |
| Remediate Task/Handoff/canonical Evidence | success | exact HEAD `3ac73f887c1c52b17d9a3d09636fe0406d746737` contains the eight declared paths only |
| Governance Gate run #252 | exit 0 / success | exact HEAD `3ac73f887c1c52b17d9a3d09636fe0406d746737` passed all mandatory steps |
| Second fresh Codex Review | review completed / 1 P1 | requested explicit `sharedPaths: []`, `producesContracts: []`, and `consumesContracts: []` in canonical Handoff |
| Update explicit path/contract state | success | this Handoff-only commit; latest Gate and Review are pending |

## P1 remediation matrix

1. **Canonical state synchronization** — Program/Task/Registry all remain `in_progress`; Task and Registry use the same new branch/base. No Program transition exists, so Program Plan remains unchanged.
2. **Resumable Handoff** — this file preserves historical merges, failures, exact revisions, file inventory, commands/results and pending work.
3. **Post-merge base** — before any implementation commit, both Task and Registry `baseSha` must become the actual PR #24 Reservation merge SHA.
4. **Reservation-only prohibition** — `tests/**` and `scripts/**` are forbidden only in PR #24; the later Implementation PR may use the already registered `tests/governance/**` scope for the minimal test repair.
5. **Canonical Evidence** — Summary, Commands, Changed Files and Test Results are refreshed in the same PR; the supplemental note is not treated as the canonical status source.
6. **Explicit handoff state** — `sharedPaths: []`, `producesContracts: []`, and `consumesContracts: []` are recorded above; no empty set is inferred from omission.

## Exact action after Reservation merge

The Integrator must record the actual PR #24 merge commit. Before any test implementation commit:

1. fast-forward `chore/GZ-014-test-repair-reservation-v2` to the PR #24 merge commit;
2. update **both** `specs/tasks/GZ-014.md` and `specs/coordination/active-work.yaml` `baseSha` to that merge commit;
3. preserve the same branch, roles, risk, exclusive paths, empty shared paths, empty contract sets, Lease, Handoff and integration order;
4. append only the minimal repository integration-test repair under `tests/governance/**` and fresh task-bound Evidence;
5. create a separate Implementation PR;
6. do not modify production Program/Lifecycle guard behavior unless a new reviewed Reservation amendment explicitly authorizes it.

## Reviewer exact action

### Reservation review

- verify the actual Diff contains only the eight declared metadata/Evidence paths;
- verify Program Plan remains unchanged and all three GZ-014 statuses are `in_progress`;
- verify Task/Registry branch, baseSha, roles, exclusive paths, `sharedPaths: []`, `producesContracts: []`, `consumesContracts: []`, Lease and Handoff match;
- verify canonical Evidence describes PR #24 rather than PR #21/#22 as the current phase;
- verify no test or script implementation is present;
- review only the exact latest HEAD and its corresponding Gate.

### Implementation review

- verify implementation begins from the PR #24 merge commit and Task/Registry `baseSha` equals it;
- verify the test derives affected tasks through the lifecycle wrapper and does not hard-code GZ-014 for unrelated future main pushes;
- verify production lifecycle guards are unchanged;
- verify exact-head PR Gate and post-merge `main` Gate both succeed;
- verify Handoff and canonical Evidence are refreshed to the implementation merge.

## Integrator exact action

1. Do not approve PR #24 until the latest HEAD Gate succeeds and fresh Review has no blocker.
2. Resolve a Review thread only after the corresponding latest-HEAD files and verification demonstrate the fix.
3. Merge PR #24 with `expected_head_sha`.
4. Record the actual merge SHA and perform the base/branch synchronization described above.
5. Do not create Foundation Completion until the test Implementation PR and its post-merge `main` Gate succeed.
6. Foundation Completion remains a separate narrow PR, releases only GZ-014 and leaves the ordinary completion ledger unchanged.

## Known blockers and boundaries

- This Handoff-only commit requires a new exact-head Gate and fresh Review.
- `main` Gate #237 remains red until the independent test-repair Implementation is merged and the subsequent `main` Gate succeeds.
- GZ-014 remains `in_progress`; its Lease must not be released in PR #24.
- GZ-004, GZ-010 and all downstream tasks remain blocked.
- OPS-001 #20 remains open and only gates the final GZ-020 release.

## Rollback

Before merge, close PR #24 and retain the branch/Evidence. After merge, revert only the Task/Registry/Handoff/Evidence Reservation through a dedicated PR; never reset, force-push or directly modify `main`.
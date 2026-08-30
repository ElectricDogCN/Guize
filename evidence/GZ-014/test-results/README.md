# GZ-014 Test Results

## Historical validation retained

### Original Reservation

- Initial Reservation Gate: failed on four asymmetric Requirement/Module mappings and an ambiguous empty shared-scope sentence.
- Accepted repair: mappings and scope prose corrected without weakening checks.
- Governance Gate #109: success.
- PR #18 merge: `d731ce09fbf2535948bc1864490539d06ce1f139`.

### Program Plan implementation

- Governance Gate #111: failed because unquoted ISO lease timestamps became YAML datetime objects.
- Accepted repair: quote timestamps; keep Schema string-only.
- PR #21 merge: `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.

### Post-merge lifecycle hardening

Multiple exact-HEAD Gates and Reviews found and repaired:

- Completion-aware Scope/Coordination dispatch;
- Foundation status/provenance separation;
- immutable ordinary Completion Ledger;
- Reservation snapshot proof;
- dependency completion ordering and reservation-base ancestry;
- completion Evidence freshness and target-base merge existence;
- exact push-range lifecycle validation;
- no-task main-push affected-task derivation;
- final GZ-020 transitive closure;
- live Ruleset include/exclude, latest-target-branch and independent-last-push approval requirements.

Representative retained results:

- Gate #156: failed on first-ledger migration, extensionless `Makefile`, test helper naming and stale workflow assertion.
- Gate #191: Program controls and 223 tests passed; Agent Coordination rejected bare root `Makefile` scope.
- Gate #196: success on `da2e1cbf9ca15881fc7cf271b531ffe7353eb067`.
- Gate #236: success on the final PR #22 repair HEAD, including 255 governance tests and all mandatory lifecycle checks.
- PR #22 merge: `903754295e4a0393638c82aa851c3ada8cd507fb`.

No accepted control was removed or converted to advisory behavior.

## Post-merge main incident

### Main Governance Gate run #237

Validated commit: `903754295e4a0393638c82aa851c3ada8cd507fb`

Result: `failure`.

Observed step outcome:

- Task/Project Readiness: PASS;
- Program Integrity/History/Transitions/Finalization/Lifecycle: PASS;
- Agent Coordination: PASS;
- Markdown/Schema/Secret/Evidence/Scope/Spec Sync/CI static checks: PASS;
- Governance tests: FAIL.

The failure was isolated to a repository integration test that treated `origin/main == HEAD` as a GZ-014-specific audit base rather than exercising the no-task main-push lifecycle wrapper semantics used by the workflow.

## Closed failed repair attempt

### PR #23

Result: closed without merge.

Review found:

1. the new test-repair branch had no independently merged Reservation;
2. canonical Handoff still pointed to the previous branch/base;
3. the test forced every future unrelated main push through `--task GZ-014`.

The branch, commits and Review history were preserved as failure Evidence.

## Current clean Reservation V2

### PR #24 Gate #245

Validated HEAD: `8efc71cf21ca0a6c9543722b89d8cad37cc71018`

Result: `success`.

The exact Reservation-only file set at that revision passed all mandatory Governance Gate steps.

### PR #24 fresh Review

Result: approval withheld; five P1 findings.

Required remediation:

- keep Program/Task/Registry state synchronized;
- restore a complete resumable Handoff;
- update Task and Registry `baseSha` to the actual Reservation merge before implementation;
- limit the no-test-change rule to this Reservation PR;
- refresh canonical Summary, Commands, Changed Files and Test Results.

### Remediation revisions

- `06eaad8a3ecf2d4af5d667dc19fd53b8354bf689` — Task boundary and post-merge base instructions;
- `fa8822693a02194da4ece85b737d124180c1c627` — resumable Handoff;
- `90976514769759ded1a5d883dccb043b7f4d43c0` — canonical Summary;
- subsequent commits — canonical Commands, Changed Files and this Test Results update.

## Latest-head integration condition

The Evidence updates are newer than Gate #245. PR #24 remains blocked until the **exact latest HEAD** has all of the following:

1. Governance Gate `success`;
2. fresh independent Review with no blocker;
3. zero unresolved Review threads;
4. actual changed-file list exactly matching the eight declared metadata/Evidence paths;
5. final manual Program/Task/Registry/Handoff/Evidence consistency check;
6. expected-head merge.

After PR #24 merges, Task and Active Work `baseSha` must be updated to the actual Reservation merge SHA before any test implementation commit. The later Implementation PR must then pass its exact-head Gate and Review, and the resulting post-merge `main` Gate must succeed before Foundation Completion.
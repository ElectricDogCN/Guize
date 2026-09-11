# GZ-014 OPS-008 Test Results

Status: READY_FOR_INDEPENDENT_REVIEW

## Immutable history

- GZ-014 remains completed.
- Original completion identity remains PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- OPS-008 maintenance is tracked by Issue #57 and Draft PR #58 from `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.

## Validated functional source

- Functional source HEAD: `644c34927f945439f02beae4bbfa41a4d52297fe`.
- Pull-request test merge ref: `c556503aa4a815a98d2fbd824e4e36eedf29a145`.
- Governance Gate: run #527 / ID `34563651207`.
- Governance Checks job: `103151281804`.
- Conclusion: `success`.
- Runner: Ubuntu 24.04, Python 3.11.16, pytest 8.4.2.

The Evidence refresh is intentionally committed after the validated functional source. The final Evidence-refresh HEAD must be revalidated; this document does not attempt to contain its own commit SHA.

## Results

| Validation | Result |
|---|---|
| dependency installation/import | PASS |
| Python compilation | PASS |
| test collection | 348 collected in 0.27 seconds |
| full governance suite | 348 passed, 0 failed in 62.97 seconds |
| skip audit | 0 skipped, PASS |
| Project Readiness | PASS with truthful non-blocking readiness warnings |
| Program integrity/history/transitions/finalization | PASS |
| one-time completed-Foundation maintenance | PASS; 23 changed paths, 17 authorized claims |
| exact target-base ownership authorization | PASS |
| exact MOD-GOV protocol tail append | PASS |
| task-aware maintenance coordination | PASS through canonical lifecycle revalidation |
| push/no-task maintenance coordination | PASS through exact-diff manifest detection and canonical lifecycle revalidation |
| push lifecycle failure propagation | PASS |
| multiple maintenance manifests | correctly rejected |
| ordinary global coordination substitution | not invoked for maintenance |
| Task Scope | PASS |
| Markdown | PASS; 189 files checked |
| YAML/JSON Schema | PASS |
| Secret scan | PASS |
| Evidence and Evidence integrity | PASS |
| Branch linkage | PASS with the documented immutable GZ-014 historical branch warning |
| Spec sync and repository boundary | PASS |
| CI workflow static validation | PASS |

## Registration-specific behavioral coverage

The passing suite includes real temporary-Git fixtures for:

- valid task-aware Registration and valid two-parent push/no-task Registration provenance;
- exact merge-base enforcement and rejection of stale source branches;
- branch-namespace-only provenance and rejection of a same-named tag;
- exactly one new high/critical planned task, duplicate rows and duplicate explicit YAML keys;
- exact schemaVersion 2 Task Spec sections and Program/Task identity parity;
- fresh canonical Evidence, mandatory non-N/A artifacts and complete structured Handoff;
- candidate-tree Evidence mode/symlink inspection, including pre-existing Evidence rejection;
- executable rollback/revert/restore requirements and rejection of empty or prose-only rollback;
- unchanged Active Work and Completion Ledger and no Lease;
- canonical validator dispatch without production override;
- legal downstream planned tail append, dependency existence, DAG, Wave, final closure and same-Wave integration order;
- rename, copy, symlink, path traversal, unrelated-source copy and repository-wide glob rejection;
- one-time completed-Foundation maintenance and rejection of repeat use;
- immutable target-base ownership authorization and rejection of candidate self-authorization;
- generalized probe, marker, temporary and placeholder residue rejection;
- task-aware completed-Foundation coordination delegation to the canonical lifecycle proof;
- post-main push/no-task maintenance detection from the exact base-to-head diff;
- exact lifecycle exit-code propagation in PR and push modes;
- fail-closed rejection of multiple maintenance manifests;
- proof that ordinary global active-lease coordination is not a substitute for the maintenance lifecycle proof;
- preserved exact transition/lifecycle core blobs;
- ordinary Reservation, Activation, Review, Integration and Completion behavior;
- OPS-007 terminal/non-terminal Wave semantics;
- MOD-GOV ownership and the four-stage protocol sequence;
- a valid individual baseline before each negative mutation or negative invocation.

## Command boundary

The hosted workflow executes the mandatory validators and full governance suite directly. A separately named local `make verify` invocation was not observed and is not claimed.

## Remaining release controls

- A fresh Governance Gate must succeed on the final Evidence-refresh HEAD.
- Independent exact-head review is pending.
- Existing non-outdated review threads must be re-evaluated and resolved against the final HEAD.
- Merge and post-main validation are not authorized or claimed.

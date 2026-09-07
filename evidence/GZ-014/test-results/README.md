# GZ-014 OPS-008 Test Results

Status: READY_FOR_INDEPENDENT_REVIEW

## Immutable history

- GZ-014 remains completed.
- Original completion identity remains PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- OPS-008 maintenance is tracked by Issue #57 and Draft PR #58 from `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.

## Validated source

- Implementation source HEAD: `a0c31ffd409e93ae648c061758600c2aa1addc53`.
- Pull-request test merge ref: `571336786c60579f42bdccd02b2b780ac1145855`.
- Governance Gate: run #495 / ID `34141330075`.
- Governance Checks job: `101803750766`.
- Conclusion: `success`.
- Runner: Ubuntu 24.04, Python 3.11.16, pytest 8.4.2.

The Evidence refresh is intentionally committed after the validated implementation source. Its final HEAD must be revalidated; this document does not attempt to contain its own commit SHA.

## Results

| Validation | Result |
|---|---|
| dependency installation/import | PASS |
| Python compilation | PASS |
| test collection | 327 collected |
| full governance suite | 327 passed, 0 failed |
| skip audit | 0 skipped, PASS |
| Project Readiness | PASS with truthful non-blocking readiness warnings |
| Program integrity/history/transitions/finalization | PASS |
| completed-Foundation maintenance mode | PASS |
| Agent Coordination | PASS |
| Task Scope | PASS |
| Markdown | PASS; 188 files checked |
| YAML/JSON Schema | PASS |
| Secret scan | PASS |
| Evidence and Evidence integrity | PASS |
| Branch linkage | PASS with the documented immutable GZ-014 historical branch warning |
| Spec sync and repository boundary | PASS |
| CI workflow static validation | PASS |

Full governance duration: 46.77 seconds.

## Registration-specific behavioral coverage

The passing suite includes real temporary-Git fixtures for:

- valid task-aware Registration and valid push/no-task merge provenance;
- authoritative branch/base equality and rejection of direct push or missing source branch;
- exactly one new high/critical planned task and duplicate-row rejection;
- YAML merge anchors with explicit overrides and duplicate explicit-key rejection;
- exact schemaVersion 2 Task Spec sections, Handoff and canonical Evidence requirements;
- unchanged Active Work and Completion Ledger and no Lease;
- canonical validator dispatch without production override;
- legal downstream planned tail append, dependency existence, DAG, Wave and final closure;
- rename, copy, symlink, path traversal and unrelated-source copy rejection;
- repository-wide glob rejection;
- preserved exact transition/lifecycle core blobs;
- ordinary Reservation/Activation/Completion behavior and OPS-007 terminal Wave semantics;
- MOD-GOV ownership and the four-stage protocol sequence.

## Command boundary

The hosted workflow executes the mandatory validators and full governance suite directly. A separately named local `make verify` invocation was not observed and is not claimed. This limitation is explicit rather than represented as success.

## Remaining release controls

- A fresh Governance Gate must succeed on the final Evidence-refresh HEAD.
- Independent exact-head review is pending.
- Existing non-outdated review threads must be re-evaluated and resolved against the final HEAD.
- Merge and post-main validation are not authorized or claimed.

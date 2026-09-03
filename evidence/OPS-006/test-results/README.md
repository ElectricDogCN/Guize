# OPS-006 Registration Test Results

## Phase

Metadata-only bootstrap Registration. No implementation test is reported as PASS in this file.

## Pre-commit state

- Exact target base audited: `main@219d7096756ad75717a46d85baf7d2b216e2472b`.
- Program, Task, Registry, Ledger and lifecycle checkers were read from that SHA.
- Local repository execution was unavailable; no local exit code is fabricated.
- GitHub Actions results will be classified from the exact PR HEAD after the Registration commit is pushed.

## Expected legacy-Harness failures

The existing baseline is expected to reject OPS-006 because it has no Registration mode:

1. `check-task-file.py` excludes `planned` from Registry Task statuses;
2. `run-agent-coordination-gate.py` rejects `planned`;
3. `run-task-scope-gate.py` rejects `planned`;
4. `check-program-lifecycle-guards.py` has no rule for the narrowly appended GZ-020 dependency.

These are diagnosed gaps, not passing evidence. Any schema failure, missing reference, Program Integrity failure, Evidence failure, secret finding, unexpected changed file or unrelated test regression is a blocker.
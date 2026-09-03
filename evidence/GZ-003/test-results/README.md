# GZ-003 Test Results

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Result: COMPLETED
Maintenance: OPS-005 #50 / exact-head validation pending

## Harness gap being tested

The existing Governance Gate does not execute the POC Program's mandatory validator/regression commands. OPS-005 adds a separate repeatable `POC Program Gate` and workflow-contract regression tests without changing POC or product semantics.

## New workflow-contract coverage

`tests/governance/test_poc_program_workflow_contract.py` defines six checks:

1. pull requests and all main pushes trigger the gate;
2. GitHub Actions are immutable-SHA pinned and checkout credentials are not persisted;
3. the validation step requires and executes both POC commands and cannot continue on error;
4. only the state where **both** POC validation files are absent is allowed to skip contract execution;
5. the job summary exposes `poc_program_validation` outcome;
6. stale runs are cancelled.

## Expected integration behavior

On this maintenance branch, the POC Program files are absent because GZ-010 PR #48 is not merged; the new workflow must therefore report the no-contract case successfully while governance tests exercise the workflow contract.

After OPS-005 is merged to main and PR #48 is synchronized with that main, the same workflow must see both POC validation files in the PR merge checkout and execute:

```bash
python specs/poc/check_program.py
python specs/poc/test_program.py
```

A missing one-of-two file, validator failure, or regression-test failure must make `POC Program Gate` red.

## Current validation state

No exact-head Governance Gate, POC Program Gate, fresh Review, merge, post-main Gate, or GZ-010 test result is claimed in this Evidence yet. Those values must be taken from GitHub after the maintenance PR is created.

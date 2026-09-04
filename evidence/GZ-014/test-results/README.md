# GZ-014 OPS-008 Test Results

Status: PENDING_EXACT_HEAD_VALIDATION

## Immutable history

- GZ-014 remains completed.
- Original completion identity remains PR #32 / `8221fd0f6c2c8923e4eea10316eac33a9d7e1d87`.
- OPS-008 maintenance is tracked by Issue #57 and Draft PR #58 from `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.

## Required focused coverage

The exact candidate must prove:

- valid task-aware and no-task/push Registration;
- exactly one new high/critical planned task;
- matching schemaVersion 2 Registration Task Spec;
- unchanged Active Work and Completion Ledger;
- no Lease or ordinary execution/scope dispatch;
- complete Program/Task identity mapping;
- legal later-planned dependency tail append;
- valid Wave direction, DAG and final-task closure;
- fail-closed multiple-task, existing-task, status, identity, branch, base, Lease, ledger, unrelated-path, dependency, cycle, rename/copy, symlink and combined-phase mutations;
- preservation of all non-Registration transition/lifecycle behavior and OPS-007 Wave semantics.

## Required exact-head commands

```bash
python -m compileall -q scripts tests
python -m pytest \
  tests/governance/test_program_task_registration.py \
  tests/governance/test_program_registration_dispatch.py \
  tests/governance/test_program_plan_transitions.py \
  tests/governance/test_program_lifecycle_guards.py \
  -v -ra
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python -m pytest tests/governance/ -v -ra
make verify TASK=GZ-014 BASE=origin/main HEAD_REF=HEAD BRANCH=fix/GZ-014-program-registration-bootstrap
```

## Current results

- Focused tests: `PENDING`.
- Full governance tests: `PENDING`.
- Skipped tests: `PENDING`; required value is zero.
- PR #58 Governance Gate: `PENDING`.
- Independent exact-head Review: `PENDING`.
- Merge/post-main Gate: not authorized and not claimed.

This file must be updated with actual commands, exit codes, collected/passed/failed/skipped counts and the immutable candidate HEAD before independent review.

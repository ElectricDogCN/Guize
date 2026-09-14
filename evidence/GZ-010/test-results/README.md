# GZ-010 Test Results

Task: `GZ-010`  
Implementation commit under test: `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`  
GitHub Actions run: `34873071797`  
Job: `104073491558`

## Environment

- GitHub-hosted runner: Ubuntu 24.04
- Runner image: `ubuntu-24.04`
- Governance dependencies: installed from `requirements-governance.txt`
- Validation window: 2026-09-14T17:10:04Z through 2026-09-14T17:10:56Z

## Results

### Python compilation

```text
python -m py_compile specs/poc/check_program.py specs/poc/test_program.py
exit 0
```

### POC Program validator

```text
python specs/poc/check_program.py
PASS: POC-PROTOCOL-V1 immutable planning baseline and task-owned Evidence contracts are consistent with Program Plan
exit 0
```

### POC Program regression suite

```text
python specs/poc/test_program.py
Ran 85 tests in 49.148s
OK
exit 0
```

All 85 discovered tests completed successfully. Unexpected skips: `0`.

The suite includes positive baseline and terminal fixtures plus fail-closed cases covering immutable plans, plan/index mapping, duplicate YAML keys with merge-key compatibility, task-owned paths, concrete identities, Active Work role synchronization, secret-like keys and values, path and symlink escape, structured commands, expected/actual exit codes, raw outputs, exact planned resources, configuration/booking Evidence, approvals, compliance references, provenance, measurement domains, concurrency, row ownership, timestamps, and template integrity.

### Diff hygiene

```text
git diff --check
exit 0
```

## Formal gate status

Run `34873182514` on bot-authored commit `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3` was `action_required` and started zero jobs because the preceding commit was pushed with `GITHUB_TOKEN`. It is not treated as success or as a code/test failure.

The Evidence-bearing PR head must complete a normal user-triggered `pull_request/synchronize` Governance Gate, including repository governance tests and `make verify`, before review completion or merge.

## Non-execution statement

These are contract, validator, and regression results. No POC-001 through POC-010 experiment was executed. No hardware, provider, network, storage, recovery, AI, media, or performance result is represented by this file.

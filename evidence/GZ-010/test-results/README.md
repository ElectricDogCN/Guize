# GZ-010 Test Results

Task: `GZ-010`
Implementation commit under direct POC test: `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`
Plan-completeness commit under exact repository Gate: `056b17fb730e334ed8b45bc887870b0918cfaa8f`

## Direct POC validation

GitHub Actions run `34873071797`, job `104073491558`, Ubuntu 24.04:

```text
python -m py_compile specs/poc/check_program.py specs/poc/test_program.py
exit 0

python specs/poc/check_program.py
PASS: POC-PROTOCOL-V1 immutable planning baseline and task-owned Evidence contracts are consistent with Program Plan
exit 0

python specs/poc/test_program.py
Ran 85 tests in 49.148s
OK
exit 0

git diff --check
exit 0
```

Unexpected skips: `0`.

The suite covers the planning contract, schema-valid positive fixtures and fail-closed cases for mappings, duplicate YAML keys with merge compatibility, path ownership, identities, Active Work role synchronization, secrets, symlink/path escape, structured commands, raw outputs, planned resources, approvals, compliance references, provenance, measurements, concurrency, row ownership, timestamps and template integrity.

## Exact plan-completeness candidate

Governance Gate `34920195916` (#552), job `104226389757`, tested source `056b17fb730e334ed8b45bc887870b0918cfaa8f` through merge ref `353afdd504abb9ecb49993f8f46baf469b14aac4`:

- 267 governance tests collected and passed;
- 0 failed;
- 0 skipped;
- duration 25.77 seconds;
- every Gate step completed successfully;
- Task, Readiness, Program lifecycle, coordination, schema, secret, Evidence, scope, spec-sync and static CI checks passed.

The source commit adds missing structured measurements and exit criteria to eight canonical plans only. It leaves validator, schemas and regression code unchanged. The repository Governance workflow did not separately execute the POC commands on this plan-only commit; this limitation is explicit.

## Non-execution statement

All canonical plans remain `planned`, result-index rows remain `not_started`, and no experiment result or downstream `evidence/POC-*` directory is added.

# GZ-003 Evidence Summary

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Status: COMPLETED
Maintenance: OPS-005 #50 / validation pending

## Original identity

GZ-003 remains completed. This Harness maintenance does not reopen the Foundation task, alter Program Plan/Active Work/Completion Ledger, or create a second completion record. The original completion identity remains PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`.

## Trigger

GZ-010 PR #48 requires two explicit contract-validation commands:

```bash
python specs/poc/check_program.py
python specs/poc/test_program.py
```

The existing Governance Gate installs the required pinned PyYAML/jsonschema dependencies but does not execute those commands. Therefore a green Governance Gate cannot by itself prove the POC Program validator/regression suite was executed.

## OPS-005 minimal repair

Branch: `fix/GZ-003-poc-program-gate`
Base: `main@219d7096756ad75717a46d85baf7d2b216e2472b`
Issue: #50

The maintenance adds:

- `.github/workflows/poc-program-gate.yml` — an independent, pinned, fail-closed CI gate;
- `tests/governance/test_poc_program_workflow_contract.py` — workflow contract regression tests;
- refreshed canonical GZ-003 maintenance Evidence only.

The new gate:

- runs on pull requests and every `main` push;
- uses immutable checkout/setup-python action SHAs and `persist-credentials: false`;
- installs `requirements-governance.txt`;
- succeeds without POC validation only when **both** validator/test files are absent;
- fails if exactly one validation file exists;
- executes both POC commands when the contract is present;
- exposes the validation outcome in its job summary;
- does not use `continue-on-error`, `|| true`, auto-push or auto-merge.

## Scope boundary

No POC contract/plan/result, product requirement, Program Plan, Active Work, Completion Ledger, business code, deployment, Secret, permission or production data is changed by OPS-005.

## Validation state

This Evidence refresh records the implementation intent and repository writes only. It does **not** claim exact-head Gate success, review success, merge success, post-main success, or GZ-010 test success before GitHub executes them.

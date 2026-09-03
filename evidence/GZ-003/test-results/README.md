# GZ-003 Test Results

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Result: COMPLETED
Maintenance: OPS-005 #50 / PR #51

## Workflow contract coverage

`tests/governance/test_poc_program_workflow_contract.py` adds six checks for triggers, immutable action pins/checkout credentials, mandatory execution of both POC commands, fail-closed partial-contract behavior, absent-contract semantics, summary reporting and stale-run cancellation.

## PR #51 POC Program Gate #1

Run: `33711974636`
Observed result: **SUCCESS**

The runner installed `requirements-governance.txt`, then evaluated:

```bash
CHECKER="specs/poc/check_program.py"
TESTS="specs/poc/test_program.py"
```

Both files are absent in this completed-GZ-003 maintenance checkout because GZ-010 PR #48 is not merged. The gate emitted the explicit no-contract message and completed successfully. The partial-contract failure branch remained present immediately afterwards and was not bypassed.

## PR #51 Governance Gate #416

Run: `33711974616`
Observed results:

- governance tests: **265/265 PASS**;
- all 6 new POC workflow-contract tests: PASS;
- Program execution integrity: PASS;
- Program history: PASS;
- Program transitions: PASS;
- Program finalization: PASS;
- Agent Coordination: PASS;
- Markdown / Schema / Secret / Evidence / Evidence integrity / linkage / Scope / Spec Sync / parent-dir / CI static: PASS;
- sole red condition: completed-GZ-003 lifecycle guard rejects the two new Harness files `.github/workflows/poc-program-gate.yml` and `tests/governance/test_poc_program_workflow_contract.py` as outside completed-task metadata scope.

This is a self-hosting maintenance boundary, not a failed functional or regression test. No reusable checker bypass is added.

## Remaining validation

This Evidence update changes the PR HEAD, so the observed #416/#1 results are historical evidence for the prior exact HEAD only. New exact-head Governance Gate, POC Program Gate and fresh review are mandatory. No merge or post-main success is pre-claimed.

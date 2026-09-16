# GZ-010 Test Results

Task: `GZ-010`
Issue: `#15`
Pull request: `#48`
Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
Validated plan-completeness implementation commit: `0f5cfd73d4ae6592f6e773caae3bba4dac34ff46`
Validated clean product/Evidence-parent HEAD: `c8a4e0fc4839f009484a808ea2e7ee451f5f614c`

## Direct POC validation

GitHub Actions run `35053181259`, job `104657763581`, Ubuntu 24.04 / Python 3.11:

```text
python -m py_compile specs/poc/check_program.py specs/poc/test_program.py
exit 0

python specs/poc/check_program.py
PASS: POC-PROTOCOL-V1 immutable planning baseline and task-owned Evidence contracts are consistent with Program Plan
exit 0

python specs/poc/test_program.py
Ran 86 tests in 153.468s
OK
exit 0
```

Unexpected skips: `0`.

The suite includes a generic regression that iterates every current frozen measurement ID for POC-01 through POC-10. For each ID it first proves the complete fixture passes, removes exactly one measurement, and requires the validator to report `missing frozen required measurements`.

The final 86-test suite covers:

- Program/Task/Requirement/Module/Wave/risk/Evidence mapping;
- immutable nonterminal plans and result index;
- duplicate YAML keys while preserving merge keys;
- resource/sample identities and approvals;
- structured commands, raw outputs and expected/actual exit codes;
- live task/role synchronization and terminal fixture validity;
- path and symlink escape rejection;
- secrets and compound credential fields;
- provenance and measurement domains;
- concurrency and critical-standalone policy;
- row ownership and timestamp validation;
- all existing and newly added frozen POC measurement gates.

## Historical intermediate `make verify`

The same one-shot repair run executed `make verify` before deleting its two temporary workflow files. The POC validator and all 86 tests were already green, but task scope correctly rejected those two workflow paths. That result is retained as historical diagnostic evidence and is not claimed as final success.

## Clean-head Governance Gate

After deleting all temporary repair workflows, Governance Gate run `35053458023` (#561), job `104658598246`, validated source HEAD `c8a4e0fc4839f009484a808ea2e7ee451f5f614c`:

- 267 governance tests collected and passed;
- 0 failed;
- 0 skipped;
- duration 29.86 seconds;
- Task Spec, Project Readiness, Program integrity/history/transitions/finalization/lifecycle and Agent Coordination: PASS;
- Markdown: 188 files, PASS;
- schema, secret, Evidence, Evidence integrity, linkage, scope, spec sync, repository boundary and CI-static validation: PASS;
- 38 allowed cumulative paths, 0 forbidden, 0 out of scope.

## Non-execution statement

All ten canonical plans remain `planned`, all result-index rows remain `not_started`, and no downstream `evidence/POC-*` experiment/result directory is added. These tests validate the planning baseline; they do not constitute a POC result.

## Pending release control

This Evidence-only refresh requires its own successful Governance Gate and a fresh independent exact-head review before any merge decision.

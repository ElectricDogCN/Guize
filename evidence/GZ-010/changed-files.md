# GZ-010 Implementation Changed Files

Task: `GZ-010`  
PR: `#48`  
Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`  
Validated implementation commit: `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`

## Expected final PR paths

The implementation and this Evidence update are limited to the following paths:

1. `poc/README.md`
2. `specs/coordination/active-work.yaml`
3. `specs/poc/check_program.py`
4. `specs/poc/compliance-review.schema.yaml`
5. `specs/poc/execution-record.schema.yaml`
6. `specs/poc/plan.schema.yaml`
7. `specs/poc/plans/POC-001.yaml`
8. `specs/poc/plans/POC-002.yaml`
9. `specs/poc/plans/POC-003.yaml`
10. `specs/poc/plans/POC-004.yaml`
11. `specs/poc/plans/POC-005.yaml`
12. `specs/poc/plans/POC-006.yaml`
13. `specs/poc/plans/POC-007.yaml`
14. `specs/poc/plans/POC-008.yaml`
15. `specs/poc/plans/POC-009.yaml`
16. `specs/poc/plans/POC-010.yaml`
17. `specs/poc/policy.yaml`
18. `specs/poc/program.schema.yaml`
19. `specs/poc/program.yaml`
20. `specs/poc/protocol.schema.yaml`
21. `specs/poc/resources.yaml`
22. `specs/poc/result-index.schema.yaml`
23. `specs/poc/result-record.schema.yaml`
24. `specs/poc/results-index.yaml`
25. `specs/poc/sample-approval.schema.yaml`
26. `specs/poc/samples.yaml`
27. `specs/poc/templates/compliance-review.yaml`
28. `specs/poc/templates/execution-record.yaml`
29. `specs/poc/templates/plan-template.yaml`
30. `specs/poc/templates/result-record.yaml`
31. `specs/poc/templates/sample-approval.yaml`
32. `specs/poc/test_program.py`
33. `specs/tasks/GZ-010.md`
34. `evidence/GZ-010/summary.md`
35. `evidence/GZ-010/commands.txt`
36. `evidence/GZ-010/test-results/README.md`
37. `evidence/GZ-010/changed-files.md`
38. `evidence/GZ-010/handoff.md`

## Necessary coordination exception

The only changes outside `specs/poc/**`, `poc/README.md`, and `evidence/GZ-010/**` are the synchronized GZ-010 lease timestamps in:

- `specs/coordination/active-work.yaml`;
- `specs/tasks/GZ-010.md`.

They renew the same in-progress work lease from the expired 2026-09-01/2026-09-08 interval to `2026-09-14T06:00:00Z` through `2026-09-21T06:00:00Z`. They do not change task status, identities, role, branch, dependency, output ownership, integration strategy, or lifecycle state. A live matching lease is required by the validator before any running or terminal POC record can be accepted.

## Explicit exclusions

The final PR diff must not contain:

- any temporary GZ-010 repair workflow;
- Program Plan or Completion Ledger changes;
- product, business, deployment, or production configuration code;
- secrets or credential values;
- any `evidence/POC-*` experiment result;
- any terminal POC result or fabricated execution claim.

The six temporary repair workflows were removed in commit `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3` and must remain absent.

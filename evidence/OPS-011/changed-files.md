OPS-011 bounded Agent Edge scope implementation

Issue: [#108](https://github.com/ElectricDogCN/Guize/issues/108).
State: in_progress / implementer. Base: `39afaf007d800bab43d7703ac082df2bbc7e8e87`.
Branch: `chore/OPS-011-agent-edge-104-scope`. PR: [#111](https://github.com/ElectricDogCN/Guize/pull/111). Current source/tree is bound by its actual execution entry; this revision is not yet accepted.
Source gates/JUnit/same-head CI/independent source acceptance/actual-main implementation acceptance: PENDING.

Prerequisites are accepted metadata only: original reservation PR109 and scope amendment [PR110](https://github.com/ElectricDogCN/Guize/pull/110). PR110 actual main `39afaf007d800bab43d7703ac082df2bbc7e8e87` passed six main checks and CI748's 637 governance tests; independent acceptance is retained in [portable amendment history](history/amendment-39af/README.md). Neither prior result transfers to this new implementation. Two merged remote metadata branches were removed after acceptance; local history and original declarations remain.

Implementation scope inventory (the actual execution entry records its complete pinned-source diff):

- `evidence/OPS-011/assumptions.md`
- `evidence/OPS-011/commands.txt`
- `evidence/OPS-011/follow-ups.md`
- `evidence/OPS-011/handoff.md`
- `evidence/OPS-011/risks.md`
- `evidence/OPS-011/scope.md`
- `evidence/OPS-011/summary.md`
- `scripts/check-program-plan-history.py`
- `scripts/check-program-plan-integrity.py`
- `scripts/check-program-plan-transitions.py`
- `scripts/check-project-readiness.py`
- `scripts/check-task-file.py`
- `scripts/program-planning-revision.py`
- `specs/coordination/README.md`
- `specs/coordination/active-work.schema.yaml`
- `specs/coordination/active-work.yaml`
- `specs/coordination/planning-revision.schema.yaml`
- `specs/coordination/program-plan.schema.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/OPS-011.md`
- `tests/governance/test_check_project_readiness.py`
- `tests/governance/test_check_task_file.py`
- `tests/governance/test_program_plan_execution_integrity.py`
- `tests/governance/test_program_plan_transitions.py`
- `tests/governance/test_program_planning_revision.py`

Own Evidence refresh and additive portable accepted-phase archive are task metadata; actual source execution will record its Git diff inventory.

## Prior implementation source failures

Source `af290fd5b69ff09aff31ca086cbac2ca5c998d71` passed the first eleven commands, then scope exited 1 because the Task omitted its already authorized OwnEvidence path. The final three commands did not start and no JUnit exists; [its original failure](history/af290fd/README.md) is retained. Successor `20366b0546c09a2ec776ab801f8efa2aea45713f` corrected that path, passed the first thirteen commands, then make verify exited 2: 667 passed, 7 failed, 0 errors and 0 skipped across 674 cases. Docs did not start and both source snapshots remained unchanged. Its same-head CI750 completed as cancelled at approximately thirty minutes, with no final test summary; it provides no CI acceptance. The [complete failed execution](history/20366b0/README.md) is retained.

The current successor narrows global scope checks to their relevant transactions and real membership, restores legacy endpoint compatibility while preserving mandatory history checks, and adds bounded regressions for membership and original typed catalogs. Heavy schema dependencies load within their validating functions to avoid repeated loading by pure Task binding checks; all validation and exception behavior remains. All sixteen Registry claims, original roles, lease and first-use declaration remain unchanged. Current complete gates, JUnit, same-head CI and independent acceptance are PENDING; neither failed source supplies acceptance for this successor.

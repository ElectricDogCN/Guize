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

## Prior implementation source failure

OPS-011 source `af290fd5b69ff09aff31ca086cbac2ca5c998d71` passed the first eleven commands, then the scope command exited 1 because the Task allowed-scope section omitted its already authorized OwnEvidence path. Evidence, make verify and docs did not start; no JUnit result exists. Source snapshots remained unchanged. The [original failure and partial raw outputs](history/af290fd/README.md) are retained. This revision explicitly lists OwnEvidence for that checker without adding a Registry implementation claim; all sixteen claims and mechanism bytes are unchanged. Run all fifteen commands against the new actual source; prior partial results do not transfer.

OPS-011 normal reserved/coordinator scope amendment
Status: RESERVED
Base: 1d2cb080d56176e26375a7b373a3cf3ef548b3dd
Registration branch: chore/OPS-011-agent-edge-104-scope-registration
Task/Registry implementation branch: chore/OPS-011-agent-edge-104-scope
Original accepted reservation: PR #109 / 1d2cb080d56176e26375a7b373a3cf3ef548b3dd
Original accepted reservation receipt: [relative copy](reservation-history/actual-main-independent-acceptance.json) / SHA256 c3d293bee5d126ee73c64293423ff5527c349de8bbd7693761e8535c8df59b0f
Current amendment source/tree/PR: PENDING_ACTUAL_PUBLICATION
Current gates/JUnit/CI/independent review/actual-main: PENDING

Only add `scripts/check-program-plan-history.py` as claim 16 and set Own baseSha to the actual accepted main. Roles, reserved/coordinator, implementation branch, lease and all prior fifteen claims remain unchanged. Program/Ledger/foreign, firstUse and original inputs/review bytes remain unchanged. No mechanism or business implementation occurs here.

Exactly sixteen future implementation claims; OwnEvidence is metadata, not claim 17:

- `specs/coordination/program-plan.yaml`
- `specs/coordination/program-plan.schema.yaml`
- `specs/coordination/planning-revision.schema.yaml`
- `specs/coordination/active-work.schema.yaml`
- `specs/coordination/README.md`
- `scripts/program-planning-revision.py`
- `scripts/check-program-plan-integrity.py`
- `scripts/check-program-plan-transitions.py`
- `scripts/check-project-readiness.py`
- `scripts/check-task-file.py`
- `tests/governance/test_program_planning_revision.py`
- `tests/governance/test_program_plan_execution_integrity.py`
- `tests/governance/test_program_plan_transitions.py`
- `tests/governance/test_check_project_readiness.py`
- `tests/governance/test_check_task_file.py`
- `scripts/check-program-plan-history.py`

Original immutable [inputs](reservation-inputs.json), [scope review](reservation-inputs-independent-review.json) and [first-use intent](agent-edge-104-first-use.json) are retained. Prior prepared commands are preserved byte-exact in [reservation history](reservation-history/commands.txt).

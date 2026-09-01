# GZ-003 Schema Fixture Active-Work Compatibility Repair

Status: IMPLEMENTED / VALIDATION PENDING

Tracking issue: OPS-003 #43
Trigger: failed GZ-010 Reservation PR #42 / Gate #374
Base: `main@7c78c15097046d02ce04959b56c485ef76943c49`
Branch: `fix/GZ-003-schema-fixture-active-work`

## Problem

`tests/governance/test_check_schemas.py::_activate_gz004()` replaced the copied Active Work list with only its synthetic GZ-004 registry. When the real repository contains another legitimate active/reserved task, the fixture leaves that task active in the copied Program Plan but removes its Lease, manufacturing a schema failure.

Gate #374 demonstrated the failure with GZ-010: production Program lifecycle/Agent Coordination/direct Schema/Evidence/Scope all passed, while governance test `test_regular_program_task_activation_passes` failed because the fixture removed GZ-010 from Active Work.

## Repair

The helper now keeps synthetic GZ-004 at index 0 so existing tests that mutate `active["tasks"][0]` remain valid, and appends every existing non-GZ-004 Active Work entry:

```python
active["tasks"] = [registry] + [
    item for item in active.get("tasks", []) if item.get("taskId") != "GZ-004"
]
```

Production checker code, schemas, Program Plan, Active Work, Completion Ledger and business/POC contracts are unchanged.

## Validation contract

- repair branch Governance Gate and 259-test suite must pass except for any explicitly diagnosed completed-GZ-003 scope self-hosting condition;
- post-merge `main` Governance Gate must be fully green;
- GZ-010 Reservation must then be rebuilt from that new green main and its own Gate must prove `test_regular_program_task_activation_passes` stays green while GZ-010 is truly reserved.

No future Gate/merge success is pre-claimed.

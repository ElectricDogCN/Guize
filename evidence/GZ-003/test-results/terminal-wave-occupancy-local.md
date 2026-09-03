# Terminal Wave Occupancy Local Regression Result

## Baseline fidelity

The test harness was reconstructed from exact GitHub blobs at
`main@219d7096756ad75717a46d85baf7d2b216e2472b` before applying the patch:

| Repository file | Verified Git blob |
| --- | --- |
| `scripts/check-project-readiness.py` | `a8180a9aab1e68c3322b2d3014dc4ddb69f2c205` |
| `tests/governance/test_check_project_readiness.py` | `9697550ef04744d770ad4ce109d72874c9cd49fd` |
| `specs/coordination/program-plan.schema.yaml` | `4a78255c66419758e53588dce7edabe9cbc8e11d` |

The original checker was byte-verified before modification. Python compilation
succeeded for the patched checker and the focused test module.

## Command

```bash
cd /tmp/ops007
python -m unittest -v tests/governance/test_terminal_wave_occupancy.py
```

## Result

```text
Ran 8 tests in 14.306s

OK
```

Passed cases:

- `test_only_terminal_states_release_wave_occupancy`
- `test_completed_history_releases_slot_for_active_and_planned_tasks`
- `test_cancelled_history_releases_capacity_and_path_claims`
- `test_third_non_terminal_task_still_fails_capacity`
- `test_non_terminal_high_risk_limit_remains_fail_closed`
- `test_non_terminal_critical_task_still_requires_standalone_wave`
- `test_non_terminal_path_conflict_remains_fail_closed`
- `test_terminal_task_remains_in_dependency_validation`

## Authority and limitation

This is reproducible local pre-commit Evidence against exact reconstructed
fixtures. It is not a substitute for the GitHub Actions Governance Gate. The
PR's exact-head run, changed-file inventory, independent review, and post-merge
`main` run remain authoritative.

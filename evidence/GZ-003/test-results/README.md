# GZ-003 Test Results

## Original delivery verification

- PR：#11
- Conclusion：`success`
- Original governance suite：106 passed, 0 skipped
- Merge：`9e3a821ada292ac3ef69b7c059384d17f6530b48`

## Post-completion maintenance — PR #35

### Historical failures

- Gate #303：`FAIL` — completed-task finalization required refreshed Evidence.
- Gate #306：`FAIL` — stale whole-file test overwrite produced `251 passed, 10 failed`.
- Gate #312 on `d6253b00a5dfb22aa0aa5a85af69ba3499a801e1`：`FAIL`, but governance suite was `259 passed, 0 failed, 0 skipped`; only lifecycle scope correctly rejected completed GZ-003 changing governance tests.

### Gate #318

- Exact HEAD：`4562805eeac43ad8997c48f3ff4e3f95ed02a6eb`
- Workflow：`33345090625`
- Result：`PASS`
- All mandatory Gate steps succeeded, including Program integrity/history/transitions/finalization/lifecycle and the governance regression suite.

Fresh Codex Review on that exact HEAD nevertheless found two design blockers:

1. repository smoke test could pass with `affectedTaskIds: []`, so it did not prove the real migration path was exercised;
2. a fixed authorization-base constant inside the exempted checker could theoretically be redefined together with the checker in a later PR.

### Current fix

- repository smoke test explicitly runs with `--task GZ-003` and asserts `affectedTaskIds` contains GZ-003;
- the authorization base is derived from immutable Git first-parent history as the first fully completed/released GZ-014 snapshot instead of a mutable constant;
- exact seven-file equality, completed→completed state, and unchanged Program/Registry/Ledger/GZ-003 Task Spec remain mandatory;
- focused rejection tests for wrong base, extra path, state-document drift and Task Spec drift remain.

## Current validation boundary

`PENDING LATEST EXACT-HEAD VALIDATION`。

The current PR #35 HEAD is newer than Gate #318. #303/#306/#312/#318 remain historical evidence and do not prove the latest HEAD. A new Governance Gate and fresh review are mandatory before merge.

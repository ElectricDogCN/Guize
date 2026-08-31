# GZ-003 Evidence Summary

## Original delivery

任务：GZ-003。PR #11 最终合并为 `9e3a821ada292ac3ef69b7c059384d17f6530b48`，Foundation/Task 保持 `completed`。

## Post-completion bootstrap maintenance — PR #35

### Trigger

GZ-004 Reservation PR #34 首次让普通 Program Task 进入 `reserved` 后，暴露治理测试仍绑定历史 GZ-014 活动态的旧假设。GZ-004 禁止 `tests/**`，所以 #34 被关闭并保留失败 Evidence，而不是扩大需求任务范围。

### Remote validation history

- Gate #303 / `6ba34e972cd3d7eb5e07a6d8d8eb9b2e263a7998`：`FAIL`，completed-task finalization 要求刷新 GZ-003 Evidence。
- Gate #306 / `a4609ed7dcdb01147e66ad41dc72d2c8bb45e3bd`：`FAIL`，旧整文件覆写导致 `251 passed, 10 failed`。
- Gate #312 / `d6253b00a5dfb22aa0aa5a85af69ba3499a801e1`：治理测试 `259 passed, 0 failed, 0 skipped`；唯一失败是正常 completed-task lifecycle scope 拒绝 GZ-003 修改治理测试。
- Gate #318 / `4562805eeac43ad8997c48f3ff4e3f95ed02a6eb`：`PASS`，但 fresh Codex Review 找到两个仍需修复的问题：
  1. repository smoke test 未显式传 GZ-003，七文件纯维护 Diff 可能得到空 `affectedTaskIds`；
  2. 固定 base 常量位于可豁免修改的 checker 内，理论上可被后续 PR 与 checker 一起重新定义。

### Current repair

当前实现不再把授权 base 存在可修改常量中，而是从不可改写的 Git first-parent 历史推导：找到**第一个**同时满足以下条件的提交：

- Program 中 GZ-014 Foundation 为 `completed`；
- GZ-014 Task Spec 为 `completed`；
- Active Work 中不存在 GZ-014 Lease。

该历史提交为 `3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`。后续 `main` 前进不会改变这个 first-completion 历史事实，因此后续 PR 的 target base 不再等于授权 base。

一次性迁移还必须同时满足：

- task 精确为 GZ-003；
- GZ-003 保持 `completed -> completed`；
- Program Plan、Active Work、Completion Ledger、GZ-003 Task Spec 完全不变；
- changed-file set **恰好**为七个审核文件。

repository smoke test 现在显式传 `--task GZ-003` 并断言 `affectedTaskIds` 非空，保证实际执行到迁移 predicate。

### Exact seven-file scope

1. `scripts/check-program-lifecycle-guards.py`
2. `tests/governance/test_check_schemas.py`
3. `tests/governance/test_program_lifecycle_guards.py`
4. `evidence/GZ-003/summary.md`
5. `evidence/GZ-003/commands.txt`
6. `evidence/GZ-003/handoff.md`
7. `evidence/GZ-003/test-results/README.md`

不修改 Program Plan、Active Work、Completion Ledger、Task Spec、Schema、Workflow、Makefile、GZ-004 metadata、requirements、contracts、business code、deployment、Secrets、permissions 或 production data。

### Current state

`MAINTENANCE_NEEDS_REVALIDATION`。

当前 HEAD 晚于 Gate #318。#303/#306/#312/#318 均保留为历史证据，不证明当前 HEAD。必须重新执行 exact-head Governance Gate 与 fresh Review。

# GZ-003 Evidence Summary

## Original delivery

任务：GZ-003

目标：审计 Guize V1 的需求、设计、契约、WBS、测试和风险，并建立可由 CI 验证的多 Agent 协作、路径租约、依赖、交接与集成机制。

原始基线：`main@70984201e8d01ad75b6aa0fa0ee5ffe141087b52`。

PR #11 的早期 branch head `602856cf83554703f8aafd8f98f3eeddcbfa9698` 在 Governance Gate run `33199139029` 上成功。GZ-003 最终通过 PR #11 合并为 `9e3a821ada292ac3ef69b7c059384d17f6530b48`，Task 状态保持 `completed`。

## Post-completion bootstrap maintenance — PR #35

### Trigger

GZ-004 Reservation PR #34 首次让普通 Program Task 进入 `reserved` 后，暴露了治理测试仍绑定历史 GZ-014 活动态的旧假设：

- Schema fixture 只复制 GZ-014 Task Spec，而不是当前 Active Work 中所有任务；
- 一个缺 Lease 的负向用例没有先清空当前真实 Registry；
- lifecycle repository smoke test 硬编码历史 GZ-014，而不是从真实 diff 推导受影响任务。

GZ-004 禁止 `tests/**`，所以 #34 被关闭并保留为失败 Evidence，而不是扩大需求任务范围。

### Remote validation history

- Gate #303 / `6ba34e972cd3d7eb5e07a6d8d8eb9b2e263a7998`：`FAIL`，completed-task finalization 要求刷新 GZ-003 Evidence。
- Gate #306 / `a4609ed7dcdb01147e66ad41dc72d2c8bb45e3bd`：`FAIL`，旧整文件覆写导致 `251 passed, 10 failed`，同时 `test-results/README.md` 尚未刷新。
- Gate #312 / `d6253b00a5dfb22aa0aa5a85af69ba3499a801e1`：`FAIL`，但治理测试已为 `259 passed, 0 failed, 0 skipped`。除 lifecycle scope 外，Task、Readiness、Program integrity/history/transitions/finalization、Coordination、Markdown、Schema、Secret、Evidence、linkage、scope、spec-sync 和 CI static validation 均通过。

#312 唯一失败为：已完成的 GZ-003 按正常规则只能修改完成态元数据，不能修改两份治理测试。该失败证明 completed-task 默认边界仍然 fail-closed。

### Current one-time migration repair

本 PR 不开放通用 completed-task 维护权限，只增加一个绑定固定基线的一次性自举迁移：

- 固定 target base：`3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`；
- GZ-003 必须保持 `completed -> completed`；
- Program Plan、Active Work、Completion Ledger、GZ-003 Task Spec 必须完全不变；
- changed-file set 必须**恰好**等于七个审核文件；
- `main` 一旦前进，固定 base 条件自动使例外失效。

七文件范围：

1. `scripts/check-program-lifecycle-guards.py`
2. `tests/governance/test_check_schemas.py`
3. `tests/governance/test_program_lifecycle_guards.py`
4. `evidence/GZ-003/summary.md`
5. `evidence/GZ-003/commands.txt`
6. `evidence/GZ-003/handoff.md`
7. `evidence/GZ-003/test-results/README.md`

Focused tests additionally prove wrong base、额外路径、Program/Registry/Ledger drift 和 Task Spec drift 均拒绝该例外。所有原有负向 lifecycle tests 保留。

### Current state

`MAINTENANCE_NEEDS_REVALIDATION`。

最新 HEAD 晚于 Gate #312，因此 #303/#306/#312 只作为历史失败证据。必须对最新 exact HEAD 再执行 Governance Gate 与 fresh Review，成功后才允许合并和重新建立 GZ-004 Reservation。

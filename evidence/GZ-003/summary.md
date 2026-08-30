# GZ-003 Evidence Summary

## Original delivery

任务：GZ-003

目标：审计 Guize V1 的需求、设计、契约、WBS、测试和风险，并建立可由 CI 验证的多 Agent 协作、路径租约、依赖、交接与集成机制。

原始基线：`main@70984201e8d01ad75b6aa0fa0ee5ffe141087b52`。

主要产物：

- `docs/24-requirements-design-readiness-audit.md`；
- `docs/25-multi-agent-collaboration-protocol.md`；
- `adr/0014-multi-agent-coordination-and-integration.md`；
- 需求、模块、计划和活动任务机器可读索引；
- schemaVersion 2 Task 与角色化 Prompt；
- 协作和项目就绪检查器、测试、Makefile 和 Governance Gate；
- Issue/PR 表单、CODEOWNERS、README/AGENTS/MANIFEST 同步。

PR #11 的早期 branch head `602856cf83554703f8aafd8f98f3eeddcbfa9698` 在 Governance Gate run `33199139029` 上成功。GZ-003 最终通过 PR #11 合并为 `9e3a821ada292ac3ef69b7c059384d17f6530b48`，Task 状态保持 `completed`。

## Post-completion maintenance — PR #35

### Problem

GZ-004 的旧 Reservation PR #34 暴露了两处治理回归测试仍绑定历史 GZ-014 状态：

- Schema fixture 假设 Active Work 永远存在一个 GZ-014 Foundation 条目；
- lifecycle repository test 在任何非-main diff 上硬编码 GZ-014 task/branch，而不是从实际 diff 推导任务上下文。

这些假设会错误阻断后续普通 Program Task 的合法 Reservation。

### Functional change

PR #35 的功能变更限于：

- `tests/governance/test_check_schemas.py`；
- `tests/governance/test_program_lifecycle_guards.py`。

它没有重开 GZ-003、重新占用 Active Work、修改 Program Plan、产品需求、业务机器契约或业务实现。

### Observed remote result

HEAD `6ba34e972cd3d7eb5e07a6d8d8eb9b2e263a7998` 的 Governance Gate run #303 (`33327335520`) 失败。唯一失败原因是 Program finalization 要求已完成任务的维护 PR 同步刷新本任务的 canonical Evidence；缺失文件为 `handoff.md`、`summary.md` 和 `commands.txt`。其他 Gate 区域成功。

### Current state

`MAINTENANCE_NEEDS_REVALIDATION`。

本 Evidence 更新满足已观察到的 finalization 要求，但会产生新的 PR HEAD。不得将 run #303 或原始 PR #11 的成功结果当作新 HEAD 已通过；以 PR #35 最新 exact-head Gate 和 fresh review 为最终依据。

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

GZ-004 Reservation PR #34 首次让普通 Program Task 进入 `reserved` 后，暴露了治理测试仍绑定历史 GZ-014 活动态的旧假设：

- Schema fixture 只复制 GZ-014 Task Spec，而不是当前 Active Work 中所有任务；
- 一个缺 Lease 的负向用例没有先清空当前真实 Registry；
- lifecycle repository test 在非-main diff 上硬编码 GZ-014，而不是让 wrapper 从实际 diff 推导任务。

这些缺陷会错误阻断合法的普通 Program Task Reservation，因此必须在重新启动 GZ-004 前修复。

### Maintenance scope

功能修改严格限于：

- `tests/governance/test_check_schemas.py`；
- `tests/governance/test_program_lifecycle_guards.py`。

完成态 Evidence 同步限于：

- `evidence/GZ-003/summary.md`；
- `evidence/GZ-003/commands.txt`；
- `evidence/GZ-003/handoff.md`；
- `evidence/GZ-003/test-results/README.md`。

不修改 Program Plan、Active Work、Task Spec、生产 checker、Schema、Workflow、Makefile、GZ-004 元数据、需求、业务契约/代码、部署、Secret、权限或生产数据。

### Observed remote failures

- Gate run #303 (`33327335520`) on `6ba34e972cd3d7eb5e07a6d8d8eb9b2e263a7998` failed because completed-task finalization required refreshed GZ-003 canonical Evidence.
- Gate run #306 (`33327893886`) on `a4609ed7dcdb01147e66ad41dc72d2c8bb45e3bd` also failed. Program finalization still required `evidence/GZ-003/test-results/README.md`, and the stale whole-file test overwrite produced `251 passed, 10 failed`.
- The 10 failures were fixture/API drift in the maintenance test files, not a reason to weaken production governance checkers.

### Current repair

The branch is rebuilt from the current `main` versions of both test files:

- all current negative lifecycle tests and production API expectations are preserved;
- Schema fixtures now resolve/copy the current Active Work Task Specs while retaining explicit Foundation fixtures for Foundation-negative tests;
- the missing-Lease test explicitly removes active leases before testing the missing GZ-004 lease;
- the current-repository lifecycle test lets the wrapper derive affected tasks from the actual diff instead of hard-coding GZ-014.

### Current state

`MAINTENANCE_NEEDS_REVALIDATION`。

The latest PR #35 HEAD is newer than runs #303/#306. Those failed runs are retained as evidence and do not prove the rebuilt HEAD. A fresh exact-head Governance Gate and independent review are mandatory before merge.

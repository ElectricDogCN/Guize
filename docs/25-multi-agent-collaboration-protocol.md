# 25. 多 Agent 协作、交接与集成协议

> 初始机制：GZ-003 / ADR-0014
> Program Plan 与公共契约加固：GZ-014
> 适用范围：所有需求、设计、契约、POC、代码、测试、部署和治理任务

## 1. 目标

本协议解决多个 Agent 在 Guize 仓库协作时的主要风险：

- Issue、PR、聊天和仓库文件分别维护不同任务定义；
- 两个任务修改同一路径、Schema 或机器契约；
- consumer 在 producer 契约尚未合并时提前实现；
- 下游任务使用过期 `main` 或未进入目标基线的依赖；
- 一个巨大 POC/实现分支同时覆盖多个风险域；
- high/critical 变更由同一 Agent 实现、审查和集成；
- Handoff 只有说明，没有真实 Commit、测试和 Evidence；
- GitHub 平台保护未启用却被文档写成已强制。

本协议不追求最大并发，而是把单人最终审查能力作为约束，让有限并行可证明安全、可中断恢复、可审查、可回滚。

## 2. 协作事实源

### 2.1 长期 Program Plan

`specs/coordination/program-plan.yaml` 是 V1 长期交付计划的唯一机器可读入口，描述：

- Task ID、名称、类型和状态；
- Wave、风险、并行容量和集成顺序；
- `dependsOn` DAG；
- Requirement 和 Module；
- exclusive output path 和 shared path；
- contract producer/consumer；
- 验收和 POC；
- Issue、branch pattern 和 exit gate；
- external blockers 和 release policy。

Program Plan 不能修改冻结需求，只能安排如何交付已批准范围。Program Plan 变更本身属于高风险治理任务，必须 reservation、独立 Review 和 Gate。

### 2.2 当前活动任务

`specs/coordination/active-work.yaml` 只记录已经 reservation 或正在执行的少量任务：

- 固定 base SHA；
- Coordinator/Implementer/Reviewer/Integrator；
- 风险；
- 独占/共享路径；
- 租约；
- Handoff；
- Integration Strategy/Order。

不得把全部未来任务预先写入 Active Work；未开工任务留在 Program Plan。

### 2.3 Task Spec、Issue 与 Evidence

- `specs/tasks/<TASK-ID>.md`：本次任务的精确边界；
- GitHub Issue：人类可见的目标、决策和状态；
- `evidence/<TASK-ID>/` 或 `evidence/POC-XXX/`：执行与验证事实；
- PR：实际变更、Review 和 Merge 载体。

这些对象必须使用同一 Task ID、标题、风险、依赖、输出路径和退出门禁。发生不一致时停止实现，以 Program Plan + Task Spec + Registry 为准修复 Issue/PR 元数据。

## 3. 权威边界

协作治理不覆盖产品和架构权威：

```text
已批准需求规格
→ 已批准 API / Event / Data Schema
→ 已批准 ADR
→ 系统和模块设计
→ AGENTS.md
→ Never Rules
→ Program Plan / Task Spec / Active Work
→ 代码现状
→ Agent 推断
```

如果 Program Plan 与更高层冲突，不得“按计划继续”；必须先建立需求、契约或 ADR 决策。

## 4. 角色与职责

### 4.1 Coordinator

- 从 Program Plan 选择满足启动条件的 Task；
- 确认依赖、Wave、风险和外部 blocker；
- 创建 Issue、Task Spec、Evidence 和 reservation PR；
- 指定精确 base SHA、角色、租约、路径和 integration order；
- 控制并行数量和审查容量；
- 处理过期、取消、阻塞、范围调整和计划变更；
- 不替代 Implementer 完成功能，也不替代 Reviewer 给出独立结论。

### 4.2 Implementer

- 从 reservation 合并后的最新 `main` 创建 Registry 指定分支；
- 只修改登记路径；
- 先契约/测试后实现；
- 记录成功、失败、限制和未解决项；
- 维护 Evidence 和 Handoff；
- 不自行合并，不把自测当作独立 Review。

### 4.3 Independent Reviewer

- 默认只读，不承担同一 high/critical 任务的主要实现；
- 检查权威顺序、范围、契约、数据、权限、安全、并发、幂等、失败和恢复；
- 读取真实 Diff、Commit、CI、日志和 Evidence；
- 发现问题时明确 blocker 严重度和可验证修复条件；
- 修复后重新审查最新 HEAD，不能沿用旧结论。

### 4.4 Integrator

- 检查依赖是否进入目标基线；
- 检查公共契约、Migration、行为和配置冲突；
- 检查分支是否过期、Review 是否针对最新 HEAD、Gate 是否成功；
- 按 `integrationOrder` 集成；
- 不在集成阶段静默重写业务行为；发现冲突退回 Coordinator/Implementer；
- 合并后推动 Registry 释放、Program Plan 状态和 final Handoff 更新。

### 4.5 Human Owner

ElectricDogCN 保留最终人工决策权，尤其包括：

- 合并 high/critical PR；
- 生产部署；
- 正式 Migration；
- Secrets 和权限策略；
- 删除/覆盖正式数据；
- 灾难恢复；
- Release 签署。

## 5. Task 启动条件

一个新 Task 只有全部满足下列条件才能 reservation：

1. Program Plan 中存在唯一 Task ID；
2. Task 状态允许启动；
3. `dependsOn` 已完成，或 producer 产物已作为冻结机器契约进入 `main`；
4. 当前 Wave 已开放，不依赖后续 Wave；
5. Wave 和全局并行容量未超限；
6. high/critical 数量未超限；critical Task 独立 Wave；
7. Requirement、Module、output/shared path、contract producer/consumer 明确；
8. 外部 blocker 不禁止该 Task；
9. high/critical 有不同的 Implementer 和 Reviewer；
10. Issue、Task Spec、Evidence 和 branch pattern 一致。

不满足时状态为 `BLOCKED`，不得通过扩大 allowlist、删除依赖或降低风险等级开工。

## 6. 两阶段启动协议

### 6.1 Reservation PR

Reservation PR 先把协作状态写入 `main`，通常只包含：

- Task Spec；
- `active-work.yaml` 唯一记录；
- canonical Evidence 骨架；
- 必要的最小索引修复。

必须声明：

```text
Task ID
Issue
Program Wave
Risk
Base Branch / Base SHA
Coordinator / Implementer / Reviewer / Integrator
DependsOn
Exclusive Paths
Shared Paths
Lease
Handoff
Integration Strategy / Order
```

Reservation PR 不得提前实现业务功能，也不能宣称整个 Task 完成。

### 6.2 Implementation Branch

Reservation 合并后：

1. 从包含 reservation 的最新 `main` 创建 Registry 指定分支；
2. Task/Registry 状态改为 `in_progress`；
3. `baseSha` 更新为 reservation merge commit；
4. `agentRole` 改为 `implementer`；
5. 不改变已审查路径、风险和角色；确需改变时先修订 reservation。

## 7. 路径租约

### 7.1 独占路径

`exclusivePaths` 表示活动期间只有该 Task 可写。与其他 Task 的独占或共享路径重叠时 fail-closed。

禁止：

- `**`、`/` 或整个仓库；
- 为“以后可能用到”预占大目录；
- Task Spec 声明窄范围、Registry 登记宽范围；
- 实际 Diff 超出路径后再补文档解释。

### 7.2 共享路径

共享写入只有同时满足以下条件才允许：

- 双方都在 `sharedPaths` 显式声明；
- `coordinationGroup` 相同；
- `integrationOrder` 不同；
- Handoff 明确合并语义；
- 公共契约 ownership 允许 shared writer。

“无共享范围”必须单独写：

```markdown
## 共享修改范围

- 无。
```

不得写成“无；当前 `active-work.yaml` 中没有其他任务”，否则路径解析器可能把内联代码误识别为共享路径。

## 8. 模块、Schema 与公共契约 ownership

`specs/designs/module-ownership.yaml` 记录：

- 模块 owned path；
- PostgreSQL Schema owner；
- 模块依赖；
- public Contract Namespace；
- Namespace 唯一 owner；
- consumer modules；
- explicit shared writers。

规则：

1. 模块不直接写其他模块的 Repository/Schema；
2. Contract Namespace 默认只有唯一 owner；
3. consumer 可读/生成客户端，但不能修改 owner 契约；
4. shared writer 必须显式登记；
5. Contract producer Task 先合并，consumer Task 才能实现；
6. 同一机器契约不得由多个并行 Task 分别创建不兼容版本；
7. 破坏性变更必须版本化、迁移、消费者分析和回滚。

## 9. Program Wave 与并行策略

默认约束：

- 最多 3 个活动 Task；
- 最多 1 个 high/critical Task；
- critical Task 独立 Wave；
- 同 Wave exclusive output path 不得重叠；
- shared path 必须协调；
- 未冻结共同机器契约前不并行实现消费者；
- 实际审查容量不足时，Coordinator 应低于最大并发，而不是填满上限。

GZ-014 Program Plan 使用 W1～W17，先需求/契约/POC，再工程骨架与 M1～M6。Wave 是允许的最早并行窗口，不是强制同时启动。

## 10. POC 协作

GZ-010 只负责统一 POC Protocol，不执行十项实验。每项 POC 使用独立 Task：

```text
POC-001 ↔ POC-01
...
POC-010 ↔ POC-10
```

POC Task 需要独立：

- 分支和 Issue；
- 环境/版本；
- 原始数据；
- 命令和配置；
- 风险与安全边界；
- 退出条件；
- 失败替代；
- Evidence；
- Handoff；
- ADR/Program Plan 影响。

不得只提交结论摘要或用 Agent 推断替代实测。

## 11. Handoff Contract

Handoff 至少包含：

```text
Task / Issue / Branch / HEAD
Base SHA / Main SHA
Program Wave / Integration Order
Role / Lease
Completed Scope
Changed Files
Produced Contracts
Consumed Contract Versions
Commands / Exit Codes / CI Runs
Known Failures / Limitations
Security / Migration / Rollback
Open Questions
Next Role Exact Action
```

Handoff 不等于完成声明。Reviewer 和 Integrator 必须独立读取 GitHub Diff/CI/Evidence。

## 12. Review 协议

Reviewer 按以下顺序检查：

1. 权威需求、机器契约、ADR；
2. Program Plan/Task/Registry/Issue 一致性；
3. 实际 Diff 与路径；
4. 模块/Schema/Contract ownership；
5. 成功和失败路径；
6. 权限、安全、Secrets、SSRF、文件和供应链；
7. 幂等、并发、状态机和数据一致性；
8. Migration、兼容、回滚和恢复；
9. 测试、CI、Evidence；
10. 未解决项和发布边界。

Review 结论：

- `APPROVE`：无 blocker，且 Reviewer 有权限正式批准；
- `COMMENT / NEEDS_REVIEW`：审查结论完整但不构成正式批准；
- `REQUEST_CHANGES`：存在 blocker；
- `BLOCKED`：依赖/环境/平台设置未满足。

旧 HEAD 的 Review 不能自动覆盖新提交。

## 13. Integration 协议

Integrator 必须确认：

- PR 基于可接受的 `main`；
- 所有 producer 已进入 base；
- `integrationOrder` 正确；
- shared changes 按顺序应用；
- 无重复 Migration/version/event type/error code；
- 最新 HEAD 的 Governance/Language/Contract/E2E Gate 成功；
- Review threads 全部解决；
- high/critical 有独立 Review 和人工批准；
- 回滚路径可执行。

发现行为冲突时，不得在 Merge 按钮前临时改代码；退回新 Commit 和重新验证。

## 14. 完成与释放

实现 PR 合并后，Task 还需要完成状态收口：

1. 记录真实 merge SHA；
2. Task Spec 状态改为 `completed`；
3. Active Work 条目删除或改为 `completed` 后按策略归档；
4. Program Plan 状态更新；
5. Handoff/summary/commands/test results 更新；
6. Issue 以 `completed` 关闭；
7. 若有后续任务，更新其依赖事实；
8. 通过单独 cleanup/release PR 合并，避免在实现 PR 中预写未知 merge SHA。

## 15. 过期、取消和阻塞

### Lease 过期

- 自动 Gate 失败；
- Coordinator 决定续租、释放或取消；
- 不允许 Agent 静默继续提交。

### Cancelled

- 记录原因和可复用产物；
- 关闭实现 PR；
- 释放路径；
- 更新 Program Plan；
- 不删除历史。

### Blocked

- 指明 blocker ID、负责人和解除条件；
- 不得通过删测试/降风险/跳过 Gate 绕过。

## 16. GitHub 外部强制层

仓库内协议无法阻止有写权限者直接推送。OPS-001（Issue #20）需要真实配置并验证：

- `main` 只允许 PR；
- Required Check：`Governance Gate / Governance Checks`；
- 至少 1 个批准；
- high/critical 独立 Reviewer；
- require conversation resolution；
- dismiss stale approvals；
- branch up to date；
- 禁止 force push/delete；
- 管理员遵守规则；
- 紧急绕过有审计。

Issue #20 未关闭前，只能称为“协作流程和 CI 可用”，不能称为“GitHub 平台已强制”。

## 17. 验证命令

```bash
python scripts/check-schemas.py
python scripts/check-project-readiness.py
python scripts/check-agent-coordination.py
python scripts/check-agent-coordination.py --task <TASK-ID> \
  --base-ref origin/main \
  --head-ref HEAD \
  --branch-name <branch>
python scripts/check-task-file.py --task <TASK-ID>
python scripts/check-evidence.py --task <TASK-ID>
make verify TASK=<TASK-ID> BRANCH=<branch> BASE=origin/main
```

最终 RC 还必须执行：

```bash
python scripts/check-project-readiness.py --strict-ready
```

在机器契约、实现、POC、验收或 external blocker 未完成时，`--strict-ready` 失败是正确行为。

## 18. 最小示例

```text
Program Plan: GZ-005 / W2 / high
DependsOn: GZ-004 completed
Produces: OPENAPI-V1
Reservation:
  branch chore/GZ-005-openapi-reservation
  exclusive contracts/openapi/**
  reviewer independent-contract-review-agent
Merge reservation
Implementation:
  branch chore/GZ-005-openapi-baseline
  baseSha = reservation merge SHA
  produce OpenAPI + tests + Evidence
Independent review
Integration merge
Cleanup:
  Task completed
  Registry released
  Program Plan updated
```

禁止示例：

```text
Issue 中叫 GZ-005，Program Plan 中叫 GZ-004
两个 Agent 同时改 contracts/openapi/common/**
consumer 基于未合并 producer 分支开发
GZ-010 在一个 PR 中执行十项 POC
Implementer 自己作为 high-risk 唯一 Reviewer
Gate 失败后删除断言并宣称完成
文档写 main protected，但 API 实际为 false
```

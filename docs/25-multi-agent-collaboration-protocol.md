# 25. 多 Agent 协作、交接与集成协议

> 初始机制：GZ-003 / ADR-0014  
> Program Plan 与公共契约加固：GZ-014  
> Program Task Registration 生命周期：OPS-008 / Issue #57  
> 适用范围：所有需求、设计、契约、POC、代码、测试、部署和治理任务

## 1. 目标

本协议用于控制多个 Agent 在 Guize 仓库中的并行协作风险：

- Issue、PR、聊天和仓库文件分别维护不同任务定义；
- 两个任务同时修改同一路径、Schema 或机器契约；
- consumer 在 producer 契约尚未合并时提前实现；
- 下游任务使用过期 `main` 或未进入目标基线的依赖；
- 一个巨大 POC 或实现分支同时覆盖多个风险域；
- high/critical 变更由同一 Agent 实现、审查和集成；
- Handoff 只有说明，没有真实 Commit、测试和 Evidence；
- GitHub 平台保护未启用，却被文档写成已强制；
- 任务在未完成 Registration、Reservation 或 Activation 时获得实现权限。

本协议不追求最大并发。目标是让每次任务启动、实现、审查、集成、完成和回滚都可证明、可中断恢复、可审计。

## 2. 协作事实源

### 2.1 长期 Program Plan

`specs/coordination/program-plan.yaml` 是 V1 长期交付计划的唯一机器可读入口，描述：

- Task ID、名称、类型和状态；
- Wave、风险、并行容量和集成顺序；
- `dependsOn` DAG；
- Requirement 和 Module；
- exclusive output path 和 shared path；
- contract producer/consumer；
- acceptance 和 POC；
- Issue、branch pattern 和 exit gate；
- external blockers 和 release policy。

Program Plan 不能修改冻结需求，只能安排如何交付已批准范围。任何 Program Plan 变更均按 high/critical 治理变更处理。

### 2.2 当前活动任务

`specs/coordination/active-work.yaml` 只记录已经 Reservation 或正在执行的少量任务，包括：

- 固定 base SHA；
- Coordinator、Implementer、Reviewer、Integrator；
- 风险；
- 独占和共享路径；
- Lease；
- Handoff；
- Integration Strategy 和 Order。

不得把全部未来任务预先写入 Active Work。`planned` Registration 不得创建 Active Work 条目，也不得持有 Lease。

### 2.3 Task Spec、Issue 与 Evidence

- `specs/tasks/<TASK-ID>.md`：任务的精确边界和机器身份；
- GitHub Issue：人类可见目标、决策和状态；
- `evidence/<TASK-ID>/` 或 `evidence/POC-XXX/`：执行与验证事实；
- PR：实际变更、Review 和 Merge 载体。

这些对象必须使用同一 Task ID、标题、风险、依赖、输出路径和退出门禁。出现不一致时停止实现，先修复元数据。

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

如果 Program Plan 与更高层权威冲突，不得“按计划继续”；必须先形成需求、契约或 ADR 决策。

## 4. 角色与职责

### 4.1 Coordinator

- 从 Program Plan 选择满足启动条件的 Task；
- 确认依赖、Wave、风险和 external blocker；
- 先完成 Registration，再分别组织 Reservation 和 Activation；
- 指定精确 base SHA、角色、路径、Lease 和 integration order；
- 控制并行数量和审查容量；
- 处理过期、取消、阻塞、范围调整和计划变更；
- 不替代 Implementer 完成功能，也不替代 Reviewer 给出独立结论。

### 4.2 Implementer

- 只在 Activation 已合并且 post-main Gate 成功后开始实现；
- 从 Activation 后的精确 `main` 创建 Registry 指定分支；
- 只修改登记路径；
- 先契约和测试，后实现；
- 记录成功、失败、限制和未解决项；
- 维护 Evidence 和 Handoff；
- 不自行合并，不把自测当作独立 Review。

### 4.3 Independent Reviewer

- 默认只读，不承担同一 high/critical 任务的主要实现；
- 检查权威顺序、范围、契约、数据、权限、安全、并发、幂等、失败和恢复；
- 读取真实 Diff、Commit、CI、日志和 Evidence；
- 发现问题时明确 blocker 严重度和可验证修复条件；
- 修复后重新审查最新 HEAD，旧 HEAD 结论不得沿用。

### 4.4 Integrator

- 检查依赖是否进入目标基线；
- 检查公共契约、Migration、行为和配置冲突；
- 检查分支是否过期、Review 是否针对最新 HEAD、Gate 是否成功；
- 按 `integrationOrder` 集成；
- 不在 Merge 前静默重写业务行为；发现冲突退回 Coordinator 或 Implementer；
- 合并后验证 post-main Gate，再推动下一生命周期阶段。

### 4.5 Human Owner

ElectricDogCN 保留最终人工决策权，尤其包括：

- 合并 high/critical PR；
- 生产部署；
- 正式 Migration；
- Secrets 和权限策略；
- 删除或覆盖正式数据；
- 灾难恢复；
- Release 签署。

人工授权不能替代最新 HEAD 的机器 Gate、独立 Review 和线程解决。

## 5. 普通 Program Task 启动条件

一个普通 Task 只有全部满足下列条件，才可依次进入启动生命周期：

1. 需求、模块和预期契约已存在于更高层权威；
2. `dependsOn` 已完成，或 producer 产物已作为冻结机器契约进入 `main`；
3. 当前 Wave 已开放，不依赖后续 Wave；
4. Wave 和全局并行容量未超限；
5. high/critical 数量未超限，critical Task 满足独立执行约束；
6. Requirement、Module、output/shared path、contract producer/consumer 明确；
7. external blocker 不禁止该 Task；
8. high/critical 有不同的 Implementer 和 Reviewer；
9. Issue、Task Spec、Evidence、branch pattern 和 exit gate 可形成一致身份；
10. 每个前置生命周期 PR 和对应 post-main Gate 均已完成。

不满足时必须 `BLOCKED`，不得通过扩大 allowlist、删除依赖、降低风险或组合阶段开工。

## 6. 四阶段启动协议

普通 Program Task 的唯一合法启动顺序是：

```text
Registration → Reservation → Activation → Implementation
```

四个阶段必须使用独立 PR。不得在一个 PR 中组合 Registration 与 Reservation、Reservation 与 Activation，或 Activation 与 Implementation。

### 6.1 Registration PR：`absent → planned`

Registration 将一个此前不存在的普通 Task 加入 Program Plan。它是 high/critical、历史感知、纯元数据阶段。

合法 Registration 必须同时证明：

- 目标 base 中不存在该 Task，候选中恰好新增一个 `planned` Task；
- 恰好新增一个匹配的 schemaVersion 2 Task Spec；
- Program 与 Task Spec 的 Task ID、标题、类型、Wave、顺序、风险、依赖、Requirement、Module、路径、契约、Acceptance、POC、Issue、分支和 exit gate 一致；
- base SHA 与实际目标 base 相同，work branch 与实际 source branch 相同；
- Active Work 和 Completion Ledger 逐字节不变；
- Diff 只包含 Program Plan、新 Task Spec 和该 Task 的 Evidence；
- 只允许向仍为 `planned` 的同 Wave 或后续 Wave 下游任务尾部追加新依赖；
- 原有依赖顺序和值不变，DAG、Wave 方向和 final-task closure 有效；
- task-aware PR 和 push/no-task 模式得出相同结论；
- rename、copy、symlink、路径遍历和宽泛 glob 无法逃逸范围。

Registration Task Spec 必须使用：

```yaml
status: planned
coordinationMode: registration
agentRole: coordinator
riskLevel: high # 或 critical
```

Registration 不得包含 `leaseExpiresAt`，不得创建 Active Work，不得授予实现、结果、Review、Integration 或 Completion 权限。

### 6.2 Reservation PR：`planned → reserved`

Registration 及其 post-main Gate 成功后，Reservation 才可开始。Reservation PR 只登记协作资源，通常包含：

- Program Task 状态 `planned → reserved`；
- 同步后的 Task Spec；
- `active-work.yaml` 中恰好一个唯一、有效、未过期的 Lease；
- canonical Evidence 骨架和必要的最小任务元数据。

Reservation 必须声明 Task ID、Issue、Wave、Risk、Base Branch/SHA、四类角色、DependsOn、Exclusive/Shared Paths、Lease、Handoff 和 Integration Strategy/Order。

Reservation 不得实现功能，也不能宣称整个 Task 完成。

### 6.3 Activation PR：`reserved → in_progress`

Reservation 合并且 post-main Gate 成功后，使用独立 metadata-only Activation PR：

- Program 和 Task Spec 从 `reserved` 迁移到 `in_progress`；
- `baseSha` 绑定精确 Reservation merge 后的 `main`；
- `agentRole` 迁移为 `implementer`；
- 唯一 Active Work Lease、风险、角色、路径、依赖和契约保持不变；
- 不添加实现代码、业务配置或运行时行为。

Activation 必须经过独立 Review、正常 merge commit 和绿色 post-main Gate。

### 6.4 Implementation

只有 Activation merge 和对应 post-main Gate 都成功后，Implementer 才获得登记范围内的实现权限：

1. 从精确 Activation 后的 `main` 创建实现分支；
2. 只修改 Task Spec 和 Active Work 已登记的路径；
3. 保持角色、风险、依赖和契约边界；
4. 运行任务直接测试、完整仓库 Gate 和 skip audit；
5. 提交 Draft PR 和真实 Evidence；
6. 由独立 Reviewer 审查当前 exact HEAD；
7. 条件满足后由 Integrator 正常合并。

## 7. 已完成 Foundation 的治理维护

已完成 Foundation 不得重新打开、不得重新获得 Lease，也不得通过普通 Completion 元数据范围修改治理实现。

确需自托管维护时，必须使用显式、机器校验的 completed-Foundation maintenance 模式：

- 保持 Foundation、Task Spec、Program Plan、Active Work 和 Completion Ledger 逐字节不变；
- 提交 task-bound maintenance manifest，绑定 Task、Issue、base SHA、source branch、high/critical 风险、独立 Review 和 post-main Gate；
- manifest 逐项列出允许路径，且路径必须属于对应 Module ownership；
- 禁止临时文件、探针、宽泛仓库范围、symlink、rename/copy 逃逸和业务路径；
- exact-head Gate 必须成功；人工授权不得把红色 Gate 解释为可合并；
- 合并后必须验证同一 merge SHA 的 post-main Gate。

该模式是受约束的治理维护生命周期，不是 completed-task bypass。

## 8. 路径 Lease

### 8.1 独占路径

`exclusivePaths` 表示活动期间只有该 Task 可写。与其他活动 Task 的独占或共享路径重叠时 fail-closed。

禁止：

- `**`、`./**`、`*`、`/` 或任何等价的整个仓库模式；
- 为“以后可能用到”预占大目录；
- Task Spec 声明窄范围、Active Work 登记宽范围；
- 实际 Diff 超出路径后再补文档解释。

### 8.2 共享路径

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

## 9. 模块、Schema 与公共契约 Ownership

`specs/designs/module-ownership.yaml` 记录：

- Module owned path；
- PostgreSQL Schema owner；
- Module 依赖；
- public Contract Namespace；
- Namespace 唯一 owner；
- consumer modules；
- explicit shared writers。

规则：

1. Module 不直接写其他 Module 的 Repository 或 Schema；
2. Contract Namespace 默认只有唯一 owner；
3. consumer 可读或生成客户端，但不能修改 owner 契约；
4. shared writer 必须显式登记；
5. contract producer Task 先合并，consumer Task 才能实现；
6. 同一机器契约不得由多个并行 Task 分别创建不兼容版本；
7. 破坏性变更必须版本化，并提供 Migration、消费者分析和回滚。

## 10. Program Wave 与并行策略

默认约束：

- 最多 3 个活动 Task；
- 最多 1 个 high/critical Task；
- critical Task 满足独立执行规则；
- 同 Wave exclusive output path 不得重叠；
- shared path 必须协调；
- 未冻结共同机器契约前不得并行实现消费者；
- 实际审查容量不足时，Coordinator 应低于最大并发。

终态 `completed` 和 `cancelled` 历史保留在 Program Plan 中，但不占用结构性 Wave 容量；非终态任务仍必须参与容量、风险、路径和依赖校验。

## 11. POC 协作

GZ-010 只负责统一 POC Protocol，不执行十项实验。每项 POC 使用独立 Task：

```text
POC-001 ↔ POC-01
...
POC-010 ↔ POC-10
```

每个 POC Task 需要独立分支、Issue、环境和版本、原始数据、命令和配置、风险与安全边界、退出条件、失败替代、Evidence、Handoff，以及 ADR/Program Plan 影响。

不得只提交结论摘要或用 Agent 推断替代实测。

## 12. Handoff Contract

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

Handoff 不等于完成声明。Reviewer 和 Integrator 必须独立读取 GitHub Diff、CI 和 Evidence。

## 13. Review 协议

Reviewer 按以下顺序检查：

1. 权威需求、机器契约和 ADR；
2. Program Plan、Task、Active Work、Issue 一致性；
3. 实际 Diff 与路径；
4. Module、Schema 和 Contract ownership；
5. 成功和失败路径；
6. 权限、安全、Secrets、SSRF、文件和供应链；
7. 幂等、并发、状态机和数据一致性；
8. Migration、兼容、回滚和恢复；
9. 测试、CI 和 Evidence；
10. 未解决项和发布边界。

Review 结论：

- `APPROVE`：无 blocker，且 Reviewer 有权限正式批准；
- `COMMENT / NEEDS_REVIEW`：审查结论完整，但不构成正式批准；
- `REQUEST_CHANGES`：存在 blocker；
- `BLOCKED`：依赖、环境或平台设置未满足。

旧 HEAD 的 Review 不能自动覆盖新提交。

## 14. Integration 协议

Integrator 必须确认：

- PR 基于可接受的 `main`；
- 所有 producer 已进入 base；
- `integrationOrder` 正确；
- shared changes 按顺序应用；
- 无重复 Migration、version、event type 或 error code；
- 最新 HEAD 的 Governance、Language、Contract、POC、E2E Gate 按阶段成功；
- Review threads 全部解决；
- high/critical 有独立 Review 和人工批准；
- 回滚路径可执行。

发现行为冲突时，不得在 Merge 按钮前临时改代码；必须退回新 Commit 并重新验证。

## 15. Review、Integration 与 Completion 状态

实现合并后，Task 仍需通过独立 metadata-only 生命周期 PR：

```text
in_progress → review → integration → completed
```

每次状态迁移均使用独立 PR、保持实现字节不变、保留唯一 Lease，并验证精确前置 merge 和 post-main Gate。

Completion PR 只能从允许的前置状态进入 `completed`，并且：

1. 记录真实、已进入目标 base 的 implementation/integration merge SHA；
2. Task Spec 与 Program 状态同步为 `completed`；
3. 删除且只删除本 Task 的 Active Work 条目；
4. 追加且只追加一个不可变 Completion Ledger 记录；
5. 刷新 Summary、Commands、Test Results、Security、Rollback 和 Handoff；
6. 关闭对应 Issue；
7. 不预写未知的自身 merge SHA；
8. 通过 exact-head Review、正常 merge commit 和 post-main Gate。

## 16. 过期、取消和阻塞

### Lease 过期

- 自动 Gate 失败；
- Coordinator 决定续租、释放或取消；
- Agent 不得静默继续提交。

### Cancelled

- 记录原因和可复用产物；
- 关闭实现 PR；
- 释放路径；
- 更新 Program Plan；
- 保留全部历史。

### Blocked

- 指明 blocker ID、负责人和解除条件；
- 不得通过删测试、降风险或跳过 Gate 绕过。

## 17. GitHub 外部强制层

仓库内协议无法阻止有写权限者直接推送。OPS-001（Issue #20）需要真实配置并验证：

- `main` 只允许 PR；
- Required Check：`Governance Gate / Governance Checks`；
- 至少 1 个批准；
- high/critical 独立 Reviewer；
- require conversation resolution；
- dismiss stale approvals；
- branch up to date；
- 禁止 force push 和 delete；
- 管理员遵守规则；
- 紧急绕过有审计。

Issue #20 未关闭前，只能称为“协作流程和 CI 可用”，不能称为“GitHub 平台已强制”。

## 18. 验证命令

```bash
python scripts/check-schemas.py
python scripts/check-project-readiness.py
python scripts/run-agent-coordination-gate.py
python scripts/run-agent-coordination-gate.py --task <TASK-ID> \
  --base-ref origin/main \
  --head-ref HEAD \
  --branch-name <branch>
python scripts/check-task-file.py --task <TASK-ID>
python scripts/check-evidence.py --task <TASK-ID>
python scripts/run-task-scope-gate.py --task <TASK-ID> \
  --base origin/main \
  --head-ref HEAD \
  --branch-name <branch>
make verify TASK=<TASK-ID> BRANCH=<branch> BASE=origin/main HEAD_REF=HEAD
```

最终 RC 还必须执行：

```bash
python scripts/check-project-readiness.py --strict-ready
```

机器契约、实现、POC、验收或 external blocker 未完成时，`--strict-ready` 失败是正确行为。

## 19. 最小示例

```text
Program Plan: GZ-005 / W2 / high
DependsOn: GZ-004 completed
Produces: OPENAPI-V1

Registration PR:
  absent → planned
  no Lease / no Active Work / metadata only
Merge + post-main Gate

Reservation PR:
  planned → reserved
  one Active Work Lease
Merge + post-main Gate

Activation PR:
  reserved → in_progress
  preserve Lease and scope
Merge + post-main Gate

Implementation PR:
  baseSha = Activation merge SHA
  produce OpenAPI + tests + Evidence
Independent exact-head Review
Normal merge + post-main Gate

Review / Integration / Completion:
  separate metadata-only PRs
  release Lease only at valid Completion
```

禁止示例：

```text
Issue 中叫 GZ-005，Program Plan 中叫 GZ-004
Registration 同时创建 Active Work Lease
Reservation PR 同时写业务实现
Activation 与 Implementation 在一个 PR 中完成
两个 Agent 同时改 contracts/openapi/common/**
consumer 基于未合并 producer 分支开发
GZ-010 在一个 PR 中执行十项 POC
Implementer 自己作为 high-risk 唯一 Reviewer
Gate 失败后删除断言并宣称完成
人工授权把红色 exact-head Gate 解释为可合并
文档写 main protected，但 API 实际为 false
```

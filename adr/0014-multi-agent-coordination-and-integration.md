# ADR-0014: Repository-native multi-agent coordination and integration

- Status: Proposed
- Date: 2026-08-29
- Task: GZ-003

## Context

ADR-0012 建立了仓库内生的单任务 Agent Harness，但多个 Agent 并行时仍可能在不同分支修改同一路径、依赖未合并契约、使用过期基线或缺少可复现交接。Guize 由 Agent 主开发、单人最终审查，审查容量和高风险任务数量必须显式受控。

## Decision

采用仓库内生、两阶段的多 Agent 协作机制：

1. Task Spec schemaVersion 2 描述角色、风险、依赖、base SHA、路径、交接和集成策略；
2. `specs/coordination/active-work.yaml` 保存已预留的活动任务；
3. reservation PR 先进入 `main`，实现分支再从该基线创建；
4. 独占路径禁止重叠，共享路径要求同一协调组和不同集成顺序；
5. 同时最多 3 个活动任务、最多 1 个 high/critical 任务；
6. high/critical 的 Implementer 与唯一 Reviewer 不得是同一 Agent；
7. handoff 和 Evidence 是角色交接的事实来源；
8. CI fail-closed 验证登记、依赖、租约、路径和 Task Spec 一致性；
9. GitHub Ruleset 作为外部强制层，由管理员单独启用并验证。

## Alternatives

### 仅依赖聊天或 Agent 内存

拒绝。上下文不可版本化，Agent 中断后无法恢复，审查者无法证明协作边界。

### 仅依赖 GitHub Project/Issue

拒绝作为唯一来源。外部状态不随代码版本检出，本地验证和历史重放不足；Issue 仍用于人类任务视图。

### 每个 Agent 独立工作，合并时再处理冲突

拒绝。Git 冲突只能发现文本重叠，不能发现契约、数据所有权和行为冲突。

### 允许无限低风险并行

拒绝。单人审查容量是系统约束，过多 PR 会降低审查质量并增加基线漂移。

## Consequences

正面：

- Agent 可从仓库恢复活动任务和交接；
- CI 在合并前发现路径和依赖冲突；
- 高风险工作被串行化；
- 需求、模块、工作包和 Task 可追踪。

代价：

- 每个实现任务增加 reservation/release 步骤；
- 过期租约需要 Coordinator 维护；
- 保守路径算法可能要求更细的任务拆分；
- GitHub 设置仍需要管理员操作。

## Rollback

若机制导致不可接受的阻塞，可通过 Revert PR 移除 coordination checker、registry 和模板扩展，恢复 ADR-0012 的单任务 Harness。不得删除本 ADR；应新增后续 ADR 说明替代方案和失败证据。

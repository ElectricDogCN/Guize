# ADR-0014: Repository-native multi-agent coordination and integration

- Status: Accepted
- Date: 2026-08-29
- Initial Task: GZ-003
- Accepted/Extended by: GZ-014

## Context

ADR-0012 建立了仓库内生的单任务 Agent Harness，但多个 Agent 并行时仍可能在不同分支修改同一路径、依赖未合并契约、使用过期基线或缺少可复现交接。Guize 由 Agent 主开发、单人最终审查，审查容量和高风险任务数量必须显式受控。

GZ-003 已通过 PR #11 将活动任务登记、路径租约和协作检查接入 `main`。GZ-014 的真实 reservation 首次运行进一步暴露：仅有活动 Registry 仍不足以防止“未来 Task ID、依赖、波次和公共契约所有权”在 Issue、PR 描述与仓库计划之间发生漂移。因此本 ADR 的已接受实现包含活动协作层和长期 Program Plan 层。

## Decision

采用仓库内生、两阶段、双层事实源的多 Agent 协作机制：

1. `specs/coordination/program-plan.yaml` 是未来任务、波次、依赖、风险、输出路径、契约生产/消费、POC 和发布阻断项的唯一 Program Plan；
2. `specs/coordination/active-work.yaml` 只保存已预留或正在执行的活动任务，不承担长期路线图；
3. Task Spec schemaVersion 2 描述角色、风险、依赖、base SHA、路径、交接和集成策略；
4. reservation PR 先进入 `main`，实现分支再从包含该 reservation 的最新基线创建；
5. 独占路径禁止重叠，共享路径要求同一协调组、显式 shared 声明和不同集成顺序；
6. Program Plan 同一波次与 Registry 均同时最多 3 个活动任务、最多 1 个 high/critical 任务；critical 任务必须独立波次；
7. high/critical 的 Implementer 与唯一 Reviewer 不得是同一 Agent；
8. 公共契约目录必须具有唯一 owner；consumer 和 shared writer 必须在 `module-ownership.yaml` 显式声明；
9. contract consumer 任务必须把 producer 任务置于依赖祖先链，不能仅依赖“计划上会先完成”；
10. handoff 和 Evidence 是角色交接的事实来源；CI fail-closed 验证登记、依赖、租约、路径、Task Spec、Program Plan、契约 ownership 与状态一致性；
11. GitHub Ruleset 是仓库外部强制层，由 OPS-001（Issue #20）单独启用和 API 验证；仓库文件不能冒充该设置已生效。

## Authority boundary

本机制是执行与协作治理层，不能覆盖更高优先级的已批准需求、机器契约和 ADR：

```text
已批准需求
→ 已批准 API/Event/Data Schema
→ 已批准 ADR
→ 系统/模块设计
→ AGENTS.md / Never Rules
→ Program Plan / Task Spec / Registry
→ 代码现状
→ Agent 推断
```

Program Plan 只能安排如何交付冻结范围；产品范围变化必须先按更高权威层批准。

## Alternatives

### 仅依赖聊天或 Agent 内存

拒绝。上下文不可版本化，Agent 中断后无法恢复，审查者无法证明协作边界。

### 仅依赖 GitHub Project/Issue

拒绝作为唯一来源。外部状态不随代码版本检出，本地验证和历史重放不足；Issue 仍用于人类任务视图，但必须与 Program Plan 一致。

### 只使用 active-work 作为长期计划

拒绝。活动 Registry 适合少量当前任务，不适合表达十项 POC、M0～M6 依赖和 release blockers；混用会造成长期计划与临时租约互相污染。

### 每个 Agent 独立工作，合并时再处理冲突

拒绝。Git 冲突只能发现文本重叠，不能发现契约、数据所有权和行为冲突。

### 允许无限低风险并行

拒绝。单人审查容量是系统约束，过多 PR 会降低审查质量并增加基线漂移。

## Consequences

正面：

- Agent 可从仓库恢复长期计划、活动任务和交接；
- CI 在开工与合并前发现路径、依赖、契约和波次冲突；
- 十项 POC 使用独立 Task/Evidence，不再由单个巨大分支串行堆叠；
- 高风险工作被串行化；
- 需求、模块、契约、工作包、Task、POC 和验收可追踪。

代价：

- 每个实现任务增加 reservation/release 步骤；
- 过期租约需要 Coordinator 维护；
- Program Plan 变更本身属于高风险治理任务；
- 保守路径算法可能要求更细的任务拆分；
- GitHub 设置仍需要管理员操作。

## Rollback

若机制导致不可接受的阻塞，可通过 Revert PR 移除 Program Plan/coordination checker、registry 和模板扩展，恢复 ADR-0012 的单任务 Harness。不得删除或改写本 ADR 隐藏历史；应新增后续 ADR 说明替代方案、迁移路径和失败证据。

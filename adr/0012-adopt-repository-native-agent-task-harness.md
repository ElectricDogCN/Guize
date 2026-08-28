# ADR-0012: Adopt repository-native agent task harness / 采用仓库内生的 Agent 任务 Harness

- Status: Accepted
- Date: 2026-07-23

## Context

当前归泽・Guize 项目采用 Agent 主开发、单人审查模式。Agent（Codex、Trae Solo/Work 等）需要明确的任务上下文、可验证的执行边界和可追溯的交付证据。如果任务规格、Prompt 模板、证据目录和治理脚本分散在外部系统或完全缺失，Agent 将难以自发现上下文，审查者也无法在单一仓库内完成端到端验证。因此，我们需要在仓库内部建立一套原生的 Agent 任务执行 Harness，使任务规格与代码同版本、同分支、同生命周期。

## Decision

我们将任务规格（task specs）、动态 Prompt 模板、证据目录（evidence/）、治理脚本（scripts/）以及 CI 门禁（.github/workflows/）统一保存在 monorepo 内，作为仓库原生基础设施持续维护。

## Alternatives

1. **外部任务追踪器唯一来源**：仅使用外部 Issue/Project 管理任务，不在仓库内保留任务规格和证据。缺点是 Agent 无法通过仓库自发现完整上下文，审查者需要在多个系统间切换。
2. **外部 CI 模板**：治理脚本和 CI 配置存放在独立模板仓库，通过引用或拷贝使用。缺点是版本与业务代码解耦，难以针对具体任务做定制化校验。
3. **无证据框架**：不强制要求 evidence/ 目录和结构化检查。缺点是交付质量不可复现，审查者只能依赖主观判断。

## Consequences

- Agent 可通过仓库内的 `specs/tasks/`、`prompts/` 和 `evidence/` 自发现任务上下文，减少对外部系统的依赖。
- 任务规格与代码同版本控制，历史变更可追溯。
- 仓库体积会因任务规格、Prompt 模板和证据文件而增长。
- 需要持续维护治理脚本和 CI 配置，避免模板腐烂（template rot）。

## Risks

1. **模板腐烂**：Prompt 模板和任务规格长期不更新，导致 Agent 执行偏离实际代码现状。
2. **脚本维护成本**：治理脚本需要随仓库结构演变而同步更新，否则会产生误报或漏报。
3. **初始开销**：建立完整的 Harness 需要投入设计和验证时间，短期内可能降低迭代速度。

## Rollback or alternative conditions

如果未来 Agent 工具（如 Trae、Codex 或后续平台）自带标准化的任务 Harness，并能在不依赖仓库内模板的前提下提供同等或更高的可验证性，我们可以逐步废弃仓库内的模板和脚本，仅保留最小化的契约和 ADR 记录。

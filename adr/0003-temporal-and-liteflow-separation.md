# ADR-0003 LiteFlow 与 Temporal 职责分离

- Status: Accepted
- Date: 2026-07-21

## Decision
LiteFlow 负责同步决策和轻量编排；Temporal 负责下载、转码、AI、索引、备份和迁移等长任务。

## Consequences
规则和执行边界清晰；需要定义从 Policy Decision 到 Workflow Command 的契约。

# ADR-0002 Java 控制面采用模块化单体

- Status: Accepted
- Date: 2026-07-21

## Context
用户规模较小，但业务和数据治理复杂。团队为 Agent 主开发、一人审查。

## Decision
使用 Java 17 + Spring Boot 3 模块化单体，按领域隔离模块和 Schema，后续按独立扩容、故障、安全或团队边界拆分。

## Consequences
降低分布式复杂度；必须严格禁止跨模块 Repository 和表访问。

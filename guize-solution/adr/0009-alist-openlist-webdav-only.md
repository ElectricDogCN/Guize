# ADR-0009 AList/OpenList 仅通过 WebDAV 接入

- Status: Accepted
- Date: 2026-07-21

## Decision
不开发专有 API 连接器。建设独立 WebDAV 兼容插件处理 AList V2/OpenList 差异。

## Consequences
降低维护面，但能力受 WebDAV 暴露范围限制。

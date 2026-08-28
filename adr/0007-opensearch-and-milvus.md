# ADR-0007 OpenSearch 与 Milvus 分工

- Status: Accepted
- Date: 2026-07-21

## Decision
OpenSearch 负责全文、聚合和混合召回；Milvus 负责文本、图像和多模态向量；PostgreSQL 保持权威。

## Consequences
索引可重建，但需要 Outbox、版本和一致性对账。

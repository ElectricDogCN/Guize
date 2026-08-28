# ADR-0004 五层资产模型

- Status: Accepted
- Date: 2026-07-21

## Decision
采用 Asset、SourceObject、AssetVersion、Rendition、Replica 模型。

## Consequences
能够处理多来源、移动、版本、转码和副本；实现复杂度高于路径表，但避免身份错误。

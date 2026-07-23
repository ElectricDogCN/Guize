# ADR-0005 ATS 与完整文件缓存分离

- Status: Accepted
- Date: 2026-07-21

## Decision
ATS 只承担可重建 HTTP/Range 缓存；完整文件由 Content Cache Manager 管理，正式副本单独治理。

## Consequences
避免缓存命中被误判为备份或保留。

# OpenAPI Guidelines

1. Base path: `/api/v1`.
2. Machine identifiers are English only.
3. Every title/description/example has Chinese and English.
4. Every operation declares authentication and authorization intent.
5. Long operations return `202` and `taskId`.
6. Write operations support `Idempotency-Key`.
7. Error response uses stable `code` and localized `message`.
8. All responses contain `traceId`.
9. Breaking changes require a major API version.
10. Contract compatibility is a required CI gate.

Example i18n:

```yaml
title: Asset ID
x-i18n:
  zh-CN:
    title: 资产 ID
  en-US:
    title: Asset ID
```

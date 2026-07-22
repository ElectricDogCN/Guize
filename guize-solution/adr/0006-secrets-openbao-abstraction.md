# ADR-0006 Secrets 使用 OpenBao/Vault 抽象

- Status: Accepted
- Date: 2026-07-21

## Decision
业务库只保存 CredentialReference；明文凭据、Token、密钥由 OpenBao/Vault 抽象管理。

## Consequences
需要恢复和审计流程；插件和服务必须使用受控身份读取。

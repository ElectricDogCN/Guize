# ADR-0011 允许公网管理员密码登录并增加补偿控制

- Status: Accepted
- Date: 2026-07-21

## Decision
允许密码单因素登录管理入口，可由配置关闭。高风险操作再次认证，异常登录检测、限流、通知和审计强制。

## Consequences
攻击面高于仅 Passkey/VPN，必须纳入持续安全测试。

# 决策日志

| ID | 决策 | 状态 | 说明 |
|---|---|---|---|
| D-001 | 项目名为“归泽・Guize” | 冻结 | 归墟 + 白泽 |
| D-002 | Java 17 + Spring Boot 3 模块化单体 | 冻结 | 后续按压力拆分 |
| D-003 | Python/FastAPI 承担媒体与 AI | 冻结 | 逻辑独立、部署可组合 |
| D-004 | Go 实现 `guizectl` | 冻结 | CLI + 配置中心部署向导 |
| D-005 | PostgreSQL 为权威数据库 | 冻结 | JSONB 仅用于扩展 |
| D-006 | ATS 与完整缓存分离 | 冻结 | 独立计量、状态和淘汰 |
| D-007 | LiteFlow 负责轻量决策 | 冻结 | 不运行长任务 |
| D-008 | Temporal 负责长任务 | 冻结 | Control VM 单节点起步 |
| D-009 | OpenSearch + Milvus 分工 | 冻结 | 全文/聚合与向量检索 |
| D-010 | Secrets 使用 OpenBao/Vault 抽象 | 冻结 | 业务库只存引用 |
| D-011 | SWR 为主镜像仓库 | 冻结 | Digest、签名、验签 |
| D-012 | V1 所有纳入能力生产级 | 冻结 | 无对外 Beta |
| D-013 | AList/OpenList 仅通过 WebDAV | 冻结 | 独立兼容插件 |
| D-014 | 管理员允许公网密码登录 | 冻结 | 可配置关闭并增加补偿控制 |
| D-015 | API 机器标识英文唯一 | 冻结 | 所有说明和示例中英文 |
| D-016 | Agent 主开发、单人审查 | 冻结 | 强制规格、门禁和证据 |
| D-017 | GitHub 私有仓库 | 冻结 | `git bundle` 加密异地备份 |
| D-018 | 前端通过 Vue/React POC 决定 | 待 POC | 共享设计 Token |
| D-019 | 百度云接入方式通过 POC 决定 | 待 POC | 仍为 V1 生产级目标 |
| D-020 | ESXi 6.7 + A380 直通 | 待 POC | 物理兼容性未验证 |

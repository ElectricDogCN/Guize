# 登记结果

固定源与实际合并主线分别记录检查命令和退出码。

## 模块命名空间迁移

固定源码 `ce3d59c4e5c3460594ccd6909906cc6b2ba46d82` 使用 PostgreSQL 16.15 和 Flyway 13.12.1。新库仅监听私有 Unix socket，采用本地 peer 认证。依次执行 Flyway `migrate`、`validate` 和再次 `migrate`，三步均退出 0。第二次迁移没有待执行项。

`flyway_schema_history` 只有一条成功的版本 1。`pg_namespace` 返回 `ai,asset,audit,config,iam,media,outbox,policy,search,source,storage,task`，`listen_addresses` 为空。数据库已关闭。原始输出清单的 SHA-256 为 `26a3aae2371201c2880152241065ab4cf2e3ae44a7c9ba3b6e36e435438b542b`。

此次验证覆盖命名空间与迁移重跑。业务表、唯一约束、任务事务与备份恢复随各自迁移验收。

# 登记结果

固定源与实际合并主线分别记录检查命令和退出码。

## 模块命名空间迁移

固定源码 `ce3d59c4e5c3460594ccd6909906cc6b2ba46d82` 使用 PostgreSQL 16.15 和 Flyway 13.12.1。新库仅监听私有 Unix socket，采用本地 peer 认证。依次执行 Flyway `migrate`、`validate` 和再次 `migrate`，三步均退出 0。第二次迁移没有待执行项。

`flyway_schema_history` 只有一条成功的版本 1。`pg_namespace` 返回 `ai,asset,audit,config,iam,media,outbox,policy,search,source,storage,task`，`listen_addresses` 为空。数据库已关闭。原始输出清单的 SHA-256 为 `26a3aae2371201c2880152241065ab4cf2e3ae44a7c9ba3b6e36e435438b542b`。

此次验证覆盖命名空间与迁移重跑。业务表、唯一约束、任务事务与备份恢复随各自迁移验收。

## 来源与资产迁移升级

固定源码 `cc3fe71c04aea729d4e099300d889bd0fc47388d` 使用同版 PostgreSQL 和 Flyway。先将 `flyway.target` 设为 `1` 后执行 `migrate`，查到一条成功迁移。解除目标版本后实际应用 V2，校验两条迁移并重跑 `migrate`，没有待执行项。

[数据库验收语句](../../../specs/contracts/data/verify_source_asset.sql) 验证长 UTF-8 路径的重命名保留来源标识和内容版本，拒绝同来源重复提供方标识、同资产重复版本号及错误的当前版本归属。断言、回滚与实例关闭成功。回滚后来源对象和资产版本记录均为 0。实测清单 SHA-256 为 `0b0fb0c4a604370f5a7ba5fd93f7be05ff6a6d82c315db6899c5c9e0cebf7182`。

## 任务计划与执行尝试迁移

固定源码 `3890b3fadf7c389da106aaa2d263b2de2902d504` 在仅监听私有 Unix socket 的 PostgreSQL 16.15 上通过 Flyway 13.12.1 从 V2 升级至 V3。三条迁移校验通过，重复执行没有待迁移项。

[任务验收语句](../../../specs/contracts/data/verify_task_plan_and_attempt.sql) 检查同一任务幂等键、活动租约排他、过期重派和递增 fencing、绑定不符和取消拒绝、一次接受及精确重放、旧计划拒绝。来源与资产断言一起通过。合成事务回滚后任务和接受结果均为 0，实例已关闭。原始输出清单 SHA-256 为 `f5519670311524021d97382365ced8d71b9d114e18fde6a1962fd6c80c8b42f0`。

## 节点资源账本与恢复

固定源码 `cac01529378224d886bbc0e0e945ffb35d5da358` 在相同 PostgreSQL 和 Flyway 版本上完成 V3 到 V4 升级、校验及重复迁移。[资源账本断言](../../../specs/contracts/data/verify_task_resource_accounting.sql) 检查池上限、节点归属、扣记、释放及精确重放。样本事务回滚后池和预留记录均为 0。

两个独立 PostgreSQL 会话争用容量为 1 的编解码槽。观测到第二个会话实际等待数据库行锁。首个会话提交后，第二个尝试收到拒绝。释放后，该尝试正常预留，最终占用为 1。另用 `pg_dump -Fc` 和 `pg_restore --exit-on-error` 把实际合成样本恢复到全新实例。两边的资源池、预留和尝试查询内容逐字节一致，恢复库通过四条 Flyway 迁移校验。两个实例均已关闭。

查询结果 SHA-256 为 `f37ed7eca6ce1640ffd0122e05399f0f1111216d5e88e8021828b8f1b2e8e2f6`，完整原始清单 SHA-256 为 `c3771fc669a4b316f0c0c734b944467073c99ebb228609556a983da158dfcc6c`。

## 派生物血缘与事务 Outbox

固定源码 `a7d97a06f07bc4fb2a8ef87c9a06b5bcafb5f88b` 使用 PostgreSQL 16.15、Flyway 13.12.1 和私有 Unix socket 完成 V4 到 V5 升级。五条迁移校验全部通过，重复迁移没有待执行项。严格校验拒绝测试副本中缺失以及校验和不符的 V5。两组拒绝均使用隔离环境中的迁移副本。

[派生物与事件验收 SQL](../../../specs/contracts/data/verify_artifact_lineage_and_outbox.sql) 实际注入 Outbox 插入失败，结果接受、租约关闭、派生物发布及其新增版本分别回滚。检查未接受尝试、错输入、错摘要、重复清单条目和历史修订写入。独立初审发现缩略图类型与生成标志缺少一致性约束，已补齐。两种错配尝试回滚，两个有效缩略图均生成合规的发布事件。随后在已提交的隔离样本中验证结果重放和逐事件消费记录的幂等性。

单独数据库先在 V4 真实接受结果，升级后接受记录、时间与清单摘要逐字节保持。V5 补写一个事件，精确重放返回 `REPLAYED` 且事件数保持 1。[有限控制角色验收 SQL](../../../specs/contracts/data/verify_attempt_outbox_control_role.sql) 以非超级用户角色完成接受和事件写入，再回滚测试角色。

回滚组和提交组各生成五个事件，与补写组和有限角色组的两个事件合计 12 个，逐个通过现行 GZ-006 信封及相应事件 Schema。提交组的派生物、不可变修订、事件和逐事件消费记录经 `pg_dump` 恢复到独立新库，原库与恢复查询逐字节相同，恢复库五条迁移再次通过校验。所有实例均已关闭。

原始清单 SHA-256 为 `c8a2e458b4e65ca3862e055e8e75d36a1e514b0763f5768c2fedec44ac6716a1`，信封校验回执 SHA-256 为 `fef442d6027f619ee617eb7f86d69dab0bb968e27b8ad55bd4804ca63a31e92c`，恢复状态 SHA-256 为 `687e9a0f655f88ad7a62744b1a046218f07dc2bf3b4218975dce92bf2a8f9dd9`。

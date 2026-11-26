# PostgreSQL 数据契约

DDL 由 `data/migrations` 中的 Flyway 迁移维护。每个模块拥有自己的 PostgreSQL 命名空间。跨域外键用于数据库必须始终维护的身份关系，跨域业务操作仍通过平台接口执行。数据库标识沿用 OpenAPI 的不透明字符串格式，数据库中的修订号从 1 开始。

## 来源与资产身份

| 逻辑实体 | PostgreSQL 表 | 约束 |
| --- | --- | --- |
| `source_data_source` | `source.data_source` | 来源默认私有，所有者为 IAM 标识 |
| `source_object` | `source.object` | 来源与提供方标识组合唯一；缺少提供方稳定标识时，由来源模块生成稳定标识 |
| `source_object_history` | `source.object_history` | 每条记录对应来源对象的一次修订 |
| `asset_asset` | `asset.asset` | 当前内容版本必须属于该资产；新资产可在同一事务内先生成身份再绑定版本 |
| `asset_version` | `asset.version` | 版本号在资产内唯一，来源对象和前序版本可查 |
| `asset_duplicate_group` | `asset.duplicate_group` | 相同内容可共享重复组，资产仍保留自身身份 |
| `asset_content_hash` | `asset.content_hash` | 完整、抽样及提供方摘要分别记录 |

当前路径支持长 UTF-8 路径和等值查找，采用 Hash 索引避免对长路径使用 B-tree 键。重命名和移动更新来源对象并追加历史，资产版本只在内容变化时创建。来源停用或删除的业务流程保留来源身份与历史，通过状态反映可用性。

[来源与资产数据库验证](../../specs/contracts/data/verify_source_asset.sql) 在已迁移的隔离数据库执行，只使用合成记录并在结束时回滚。

## 任务计划、租约与结果

- `task.task` 以所有者与操作作用域内的幂等键去重，引用同一任务的当前计划。`task.execution` 保存外部工作流与运行标识。
- `task.plan` 和 `task.plan_step` 保留历史版本。每个计划和步骤标识只有一个当前步骤版本。尝试绑定实际节点、能力版本、协议、输入及步骤版本，fencing 在该步骤版本内递增。
- 控制面按任务行、步骤行、租约行的顺序锁定并更新。修改当前计划、步骤或任务状态的事务先锁同一任务行，修改租约的事务遵循同一锁顺序。任务领取使用 `task.lease_attempt`，返回新 fencing。已有活动租约或步骤已经接受结果时返回空值。节点心跳与执行租约分别保存。
- 控制面验证调用主体后使用 `task.accept_attempt_result`。过期、换代、已请求取消或绑定不符的尝试返回 `REJECTED`。首次存储返回 `ACCEPTED`，精确重放返回 `REPLAYED` 且无写入。记录结果与关闭租约在同一事务执行。节点通过平台协议提交，数据库函数仅供有权限的控制面调用。

[任务计划与尝试验证](../../specs/contracts/data/verify_task_plan_and_attempt.sql) 使用合成任务检查上述约束并回滚。

## 节点资源账本

`task.resource_pool` 以节点和资源标识记录容量、占用及已扣记预算。`task.resource_reservation` 绑定实际尝试、数量和有效期。控制面在同一派发事务取得任务租约与必需的容量预留，任一预留失败时回滚整个派发。多资源预留按资源标识排序，预留有效期受执行租约约束。

`task.reserve_resource` 在同一资源池行锁中核算余额并建立单条预留。相同预留请求返回 `REPLAYED`，复用既有记录。控制面通过 `task.settle_resource` 一次记录实际扣记量及释放理由，同时更新资源池。临时槽位和空间按预留量归还。执行时长预算保留实耗，未使用部分归还本预算池。已过期的记录仍须由控制面结算或回收。两个函数只授予控制面所需权限。

[资源账本验证](../../specs/contracts/data/verify_task_resource_accounting.sql) 覆盖节点归属、共享编解码槽、预算上限、释放及重复调用。

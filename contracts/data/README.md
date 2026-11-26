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

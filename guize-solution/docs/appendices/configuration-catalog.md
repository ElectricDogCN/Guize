# 配置目录 / Configuration Catalog

## 1. 分类

| 分类 | 示例 | 存储 |
|---|---|---|
| 静态部署 | 端口、服务、挂载 | Git |
| 动态业务 | TTL、预算、路由 | PostgreSQL |
| Secret | Token、密码、密钥 | OpenBao |
| 规则 | DSL、决策表、EL | PostgreSQL + Git 导出 |
| 模型 | Endpoint、能力 | PostgreSQL，Secret 引用 |
| 运行发现 | GPU、磁盘 | PostgreSQL |
| 用户设置 | 语言、偏好 | PostgreSQL |

## 2. 配置对象

```text
DataSourceConfig
SyncPolicy
CachePolicy
StorageWatermarkPolicy
RetentionPolicy
MediaProfile
ABRLadderPolicy
AIProviderConfig
AIRoutingPolicy
SearchPolicy
WorkerPolicy
SecurityPolicy
AnonymousAccessPolicy
AlertRouting
BackupPolicy
DeploymentProfile
```

## 3. 配置元数据

每项配置必须有：

```text
key
type
default
required
scope
risk
i18n title/description
validation
secret flag
restart requirement
owner module
introduced version
deprecated version
```

## 4. 风险级别

- LOW：即时发布可选；
- MEDIUM：测试后发布；
- HIGH：审批、灰度、观察；
- CRITICAL：二次认证、审批、备份和回滚。

## 5. 示例

```yaml
key: storage.safetyFloorBytes
type: integer
default: 536870912000
risk: CRITICAL
owner: storage-lifecycle
validation:
  minimum: 536870912000
x-i18n:
  zh-CN:
    title: 存储绝对安全水位
  en-US:
    title: Absolute storage safety floor
```

# 08. 缓存、存储与生命周期 / Cache and Storage Lifecycle

## 1. 四类存储语义

| 类型 | 是否完整 | 可淘汰 | 是否备份 | 责任 |
|---|---:|---:|---:|---|
| ATS 缓存 | 不保证 | 是 | 否 | HTTP/Range 加速 |
| 完整文件缓存 | 是 | 是 | 否 | 转码、AI、重复访问 |
| 正式副本 | 是 | 受策略控制 | 是/可 | 长期保留 |
| 灾备副本 | 是 | 严格控制 | 本身即备份 | 故障恢复 |

## 2. ATS

ATS 缓存：

- 视频 Range/Slice；
- 图片；
- 字幕；
- 文档预览；
- 公共静态结果。

ATS 状态不进入 Replica 的正式保留语义。缓存命中不表示拥有完整文件。

### 缓存键

必须包含影响正文的稳定因素：

```text
assetVersion / sourceVersion
rendition
range/slice
authorization scope
content negotiation
```

私人内容不能因错误缓存键泄露给其他用户。优先使用内部签名资源标识，而非直接把用户 Token 放入缓存键。

## 3. 完整缓存

状态：

```text
REMOTE_ONLY
DOWNLOAD_QUEUED
DOWNLOADING
COMPLETE_CACHE
PINNED_CACHE
VALIDATING
PROMOTING
FORMAL_REPLICA
EVICTING
EVICTED
```

默认 TTL：7 天，动态调整：

```text
基础 TTL
+ 热度
+ 回源成本
+ AI/转码复用价值
- 文件大小
- 存储压力
```

## 4. 热温冷超冷

### 热

- 高频播放；
- 本地正式副本；
- 已生成常用 ABR；
- 低延迟访问。

### 温

- 最近访问；
- 完整缓存；
- 可较快恢复；
- 部分 Rendition。

### 冷

- 云端完整副本；
- 本地只保留元数据和关键衍生物；
- 恢复需要时间和流量。

### 超冷

- 高压缩或归档；
- 离线硬盘；
- 对象归档层；
- 需要管理员恢复流程。

## 5. 提升为正式副本

触发：

- 用户固定；
- 长期保留策略；
- 源站不稳定；
- 热度持续；
- 回源成本高；
- AI/转码成本高；
- 来源准备删除。

流程：

```text
完整缓存
→ 完整哈希
→ 安全扫描
→ 存储空间预留
→ 复制到正式数据集
→ 回读/哈希验证
→ 创建 Replica
→ 事务发布
```

## 6. 淘汰

淘汰候选评分：

- 最近访问；
- 访问次数；
- 大小；
- 回源速度；
- 回源费用；
- 是否有其他可用副本；
- 是否有未完成任务；
- 是否处于删除保护期；
- 是否被固定；
- 存储水位。

淘汰服务只能操作缓存级副本，不能拥有正式副本删除权限。

## 7. 500GB 安全水位

建议水位：

```text
NORMAL
WARNING
CRITICAL
SAFETY_FLOOR
```

动作：

| 状态 | 行为 |
|---|---|
| NORMAL | 正常调度 |
| WARNING | 减少预热和 P6～P8 |
| CRITICAL | 停止普通离线任务，积极淘汰 |
| SAFETY_FLOOR | 只允许核心播放、清理和恢复 |

硬水位不可由 AI 自行突破。

## 8. 流量预算

对象：

- 数据源；
- 用户；
- 匿名池；
- Worker；
- FRP/Tunnel；
- 商业 API；
- 冷恢复；
- 云备份。

阈值：

- 软阈值：降速；
- 高阈值：停止后台任务；
- 硬阈值：只保留必要任务；
- 管理员可追加一次性额度；
- AI 只能建议，不突破硬限制。

## 9. 来源删除保护

来源对象删除时：

1. 标记来源不可用；
2. 检查其他来源；
3. 检查完整缓存；
4. 检查正式和备份副本；
5. 进入保护期；
6. 只有策略和审批允许时清理。

不得因同步发现“源站不存在”立即级联删除本地内容。

## 10. 多云备份

长期保留源文件目标：

- Google Drive；
- OneDrive；
- 百度云。

关键数据库、Secrets、AI 结果和 TrueNAS 关键数据：

- 后续 S3/OSS/COS/OBS；
- 离线硬盘。

每个副本必须有：

```text
UPLOADING
UPLOADED_UNVERIFIED
VERIFIED
DEGRADED
UNAVAILABLE
CORRUPTED
REPAIRING
```

上传成功不等于验证成功。必须进行大小校验、哈希或抽样回读。

## 11. 客户端加密

首期：

- 单一主密钥；
- 离线恢复副本；
- 分片；
- 断点续传；
- 内容哈希。

后续：

- 信封加密；
- 每对象/备份集 DEK；
- KEK 轮换；
- 主密钥和备份分离。

## 12. 生命周期决策

LiteFlow/决策表输入：

```text
asset type
size
heat
source cost
source reliability
available replicas
storage pressure
user hold
AI value
budget
security status
```

输出：

```text
cache TTL
download priority
transcode profile
formal retention
backup targets
migration action
deletion protection
```

所有决定记录策略版本和解释。

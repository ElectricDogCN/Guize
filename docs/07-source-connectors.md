# 07. 数据源连接器设计 / Source Connectors

## 1. 目标

连接器将不同来源归一为统一的只读或受控写入能力，不把提供方差异泄露到资产核心。

统一能力：

```text
probe
authenticate
list
stat
readRange
readFull
getDownloadUrl
getChangeCursor
listChanges
subscribeEvents
getProviderHash
getVersion
```

## 2. 插件模型

所有连接器使用独立插件 Manifest：

```yaml
apiVersion: guize.plugin/v1
kind: SourceConnector
metadata:
  id: source-webdav
  version: 1.0.0
spec:
  capabilities:
    - LIST
    - STAT
    - RANGE_READ
    - FULL_READ
  credentialTypes:
    - BASIC
    - BEARER
  runtime:
    mode: EXTERNAL_SERVICE
    healthEndpoint: /health
```

连接器不得：

- 直连核心数据库；
- 自行改变资产身份；
- 自行公开文件；
- 保存凭据明文；
- 无限重试；
- 忽略数据源预算。

## 3. 验收顺序

1. 标准 WebDAV；
2. 本地文件系统；
3. 百度云；
4. Google Drive；
5. HTTP/HTTPS；
6. S3；
7. SMB/NFS；
8. OneDrive。

## 4. 标准 WebDAV

必须验证：

- PROPFIND 分页或大目录行为；
- Range；
- 重定向；
- ETag；
- Unicode 文件名；
- 路径编码；
- 认证；
- 超时；
- 大文件；
- 移动和重命名识别。

AList/OpenList 仅通过 WebDAV 兼容插件接入。兼容插件处理版本差异，但对核心暴露标准接口。

## 5. 本地文件系统

必须限制根目录，防止路径穿越和软链接逃逸。

支持：

- 文件监听作为优化；
- 定期扫描作为最终一致性保障；
- inode/文件 ID 辅助识别；
- Range；
- 原子读取；
- 网络挂载异常处理。

不得让连接器拥有任意系统路径访问权限。

## 6. 百度云

最终技术路径由 POC 决定，候选包括：

- 官方开放平台/API；
- 受支持的第三方授权方式；
- 通过 WebDAV 聚合层；
- 作为冷存储的受控外部上传。

POC 必须验证：

- 合法授权；
- API 稳定性；
- 文件列表；
- 大文件读取；
- Range 或临时 URL；
- 配额和限流；
- 版本和删除；
- 商业/个人使用条款；
- 可持续维护性。

若无法满足生产级条件，V1 不得用不稳定私有接口冒充正式连接器；必须调整产品接入方式并新增 ADR。

## 7. Google Drive

重点：

- OAuth；
- Refresh Token；
- 稳定文件 ID；
- Change API；
- Shortcut；
- Shared Drive；
- 下载限制；
- Google 文档原生格式导出；
- API 配额；
- 版本历史；
- 权限和用户撤销。

## 8. HTTP/HTTPS

分为：

- 直接 URL；
- 可解析目录；
- Manifest；
- 受认证 URL。

安全要求：

- 防止 SSRF；
- 禁止访问受限内部网段，除非显式批准；
- 限制重定向；
- 限制协议；
- DNS 重绑定防护；
- Content-Length 和 Range 探测；
- URL Token 脱敏。

HTTP 目录不是统一标准，需要插件化解析器。

## 9. S3

支持：

- AWS S3；
- S3 兼容接口；
- 分页；
- ETag；
- Versioning；
- Range；
- Multipart；
- Glacier 类恢复状态；
- Prefix；
- 临时签名 URL；
- 对象锁和保留。

OSS/COS/OBS 可先使用兼容接口，厂商扩展后续独立 Adapter。

## 10. SMB/NFS

SMB/NFS 连接器运行在隔离容器或 Worker：

- 只挂载允许路径；
- 映射统一 UID/GID；
- 处理断开和重连；
- 避免阻塞控制面；
- 限制并发；
- 支持大目录检查点；
- 防止符号链接和路径逃逸。

## 11. OneDrive

重点：

- Microsoft OAuth；
- DriveItem ID；
- Delta Query；
- Shared Folder；
- 临时下载 URL；
- 限流；
- 版本；
- 用户撤销和租户策略。

## 12. 同步策略

默认：

```text
每日基线检查
+ 热门目录高频
+ 浏览时刷新
+ Webhook/Change 优先
+ AI/规则动态调整
```

递归扫描：

- 限速；
- 限并发；
- 可暂停；
- 检查点；
- 源站压力升高自动降速；
- 搜索可触发后台深层扫描；
- 管理员可手动完整扫描。

## 13. 能力探测

每个数据源启用前生成报告：

```text
认证状态
稳定 ID
列表能力
分页
Range
完整读取
变更游标
Webhook
提供方哈希
版本
限流
预计扫描成本
已知限制
```

平台根据能力选择策略，不假设所有来源一致。

## 14. 连接器生产验收

- Mock 测试；
- 真实账号集成；
- 大目录；
- 大文件；
- Unicode；
- 限流；
- 5xx；
- Token 失效；
- 删除和恢复；
- 路径移动；
- 断点；
- 权限；
- 流量统计；
- 长时间稳定性。

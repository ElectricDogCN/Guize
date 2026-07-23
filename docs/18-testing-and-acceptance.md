# 18. 测试与验收 / Testing and Acceptance

## 1. 原则

- 测试覆盖行为，不仅覆盖代码行；
- 成功和失败路径同等重要；
- 权限和数据完整性优先；
- POC 数据不能替代生产验收；
- Agent 说明不能替代证据；
- 主分支和发布必须通过门禁。

## 2. 测试层级

### 单元

- 领域规则；
- 状态机；
- 哈希和归一化；
- TTL；
- 权限；
- 预算；
- LiteFlow Node；
- DTO/Schema。

### 集成

- PostgreSQL；
- Flyway；
- Redis；
- OpenBao Stub/测试实例；
- Connector Mock；
- Temporal Test Server；
- ATS；
- OpenSearch；
- Milvus；
- 文件系统。

### 契约

- OpenAPI；
- Event Schema；
- Plugin Manifest；
- Deployment Profile；
- Provider API；
- Webhook。

### 端到端

- 数据源→资产→播放；
- 数据源→缓存→AI→搜索；
- 删除→保护→恢复；
- 规则→Workflow→副本；
- 权限→搜索→播放；
- 部署→升级→回滚。

## 3. PR 门禁

- 单元测试；
- 静态分析；
- 格式；
- Flyway 校验；
- OpenAPI 兼容；
- Event Schema；
- Manifest；
- Secrets 扫描；
- SBOM；
- 许可证；
- 关键权限；
- 文档链接。

## 4. 主分支门禁

增加：

- PostgreSQL 集成；
- Connector 模拟；
- Temporal；
- LiteFlow；
- 缓存一致性；
- 媒体 Golden Sample；
- AI 固定样本；
- 容器漏洞。

## 5. 发布候选

- E2E；
- 性能；
- 压力；
- 故障注入；
- 数据恢复；
- 数据库迁移/回滚；
- GPU；
- 云盘限流；
- 安全；
- 签名；
- 离线部署；
- 恢复演练。

## 6. 关键验收矩阵

| 能力 | 验收 |
|---|---|
| 资产归一 | 移动、改名、版本、重复、合并、拆分 |
| 权限 | 无标题/摘要/缩略图泄漏 |
| ATS | Range 命中、源更新、权限隔离 |
| 完整缓存 | 断点、哈希、水位、淘汰 |
| AV1 | 兼容、质量、重试、产物追踪 |
| 临时转码 | 首分片、取消、清理、抢占 |
| AI | 固定样本、指标、人工抽检 |
| 搜索 | 相关性、权限、重建、降级 |
| 规则 | 模拟、冲突、灰度、回滚 |
| Temporal | 幂等、重试、取消、Worker 离线 |
| 备份 | 实际恢复，不只检查文件存在 |
| 部署 | Bundle、验签、回滚、离线 |

## 7. AI 质量

按能力使用：

- WER/CER；
- DER；
- COMET/BLEU；
- OCR 字符/字段准确率；
- 摘要事实一致性；
- 标签 F1；
- Recall@K/MRR/NDCG；
- 缩略图人工选择率；
- 多模态修正错误引入率。

必须按语言、媒体质量、时长、场景分层。

## 8. 性能测试

### API

- 并发；
- P95/P99；
- 大分页；
- 权限过滤；
- Outbox。

### 元数据

- 100万/1000万级模拟对象；
- 目录深度；
- 扫描检查点；
- 增量；
- 数据库增长。

### 播放

- 首帧；
- Range；
- 热/冷；
- 多用户；
- 源站慢；
- A380。

### 搜索

- 索引规模；
- Query 延迟；
- 混合；
- 权限；
- 重建。

### AI

- 队列；
- GPU；
- 批处理；
- Token；
- 超时；
- 回退。

不在实测前填写承诺性数字。

## 9. 故障注入

- Connector 429/5xx；
- 网络中断；
- Worker 消失；
- Temporal 重启；
- PostgreSQL 主动终止连接；
- Redis 清空；
- OpenSearch/Milvus 不可用；
- ATS 磁盘满；
- TrueNAS 水位；
- GPU OOM/重置；
- 云备份失败。

## 10. 安全测试

- SAST；
- DAST；
- 依赖漏洞；
- 容器；
- Secrets；
- SSRF；
- 路径；
- 压缩；
- IDOR；
- ACL；
- 签名 URL；
- OAuth；
- Webhook；
- 镜像签名；
- 备份解密。

## 11. V1 退出标准

全部成立：

1. 所有范围能力通过验收；
2. 无 Critical/High 未处理漏洞，或有批准例外；
3. 数据库和 Secrets 恢复成功；
4. 关键文件副本回读；
5. 核心播放链路稳定；
6. 权限泄漏率 0；
7. AI 指标达到已批准阈值；
8. 文档和 Runbook 完整；
9. 镜像和 Bundle 可验证；
10. 单人审查者签署发布。

# 18. 测试与验收 / Testing and Acceptance

## GZ-021：本地完整 V1 与异构媒体执行

机器声明固定 `local-v1` version 1 / revision 1 → GZ-018，以及 `production` version 1 / revision 1 → GZ-020；两者均覆盖原 10 项需求和 12 项验收。GZ-018 依赖 GZ-019 及完整功能集成，仍须真实依赖、AI/搜索、权限、规则、恢复、供应链及故障测试。路线定义通过不等于这些运行验收已经通过。

| POC | 本地执行 | 保留的生产义务 |
|---|---|---|
| 001/002 | 实际异构节点能力、并行 AV1、HLS、租约/取消/优先级/权限 | A380/ESXi、质量/并发/长期稳定性、功耗温度 |
| 003 | 隔离 ATS Range/Slice、版本、缓存完整性与 ACL | 原协议全部测量 |
| 004 | OpenList、本地容量预留/水位、完整性与恢复 | TrueNAS/iSCSI/ZFS、500GB |
| 005 | 有界元数据与 OpenList 扫描/来源特征 | 原规模测量与生产容量目标 |
| 006 | 通用 OpenList 接入、明确注入的故障、幂等同步与删除保护 | 百度真实 API、许可/隐私与恢复 |
| 007 | 隔离 TLS/Range/ACL/限流/直接回源拒绝 | 公网 IPv6/DDNS/高端口/tunnel/CDN |
| 008/009/010 | 原前端、AI 与恢复协议继续适用 | 同一共享安全/质量义务 |

本地/历史 POC 执行记录保持原 Schema 1，在 `environmentCaptured.acceptanceProfile` 中绑定 `{id, version, bindingRevision, scope}`，并用 `acceptanceProfileConfigurationRef` 指向同任务 Evidence 的配置。配置必须匹配 POC/Task、所选资源与全部测量 ID。结果记录经 executionRef 绑定该范围；未知范围、版本错配、本地记录冒充生产、缺安全测量及通用来源结果冒充百度生产均拒绝。安全门单位必须保持 boolean。本地存储配置以整数 bytes 绑定实际正水位、高低水位及预留预算；实际最小空闲量减去最大在途预留量必须保持安全水位，不能用零配置或文字说明获得 PASS。

配置要求的隐私/许可审查必须有实际独立批准文件，并绑定任务、类型、被测版本及范围；不能只填通过布尔值。Range 字节正确率须在 0～100% 范围内，PASS 必须为 100%。本地专属环境字段不可删除。生产 POC-001/002 在保留原 A380/ESXi 测量的基础上增加异构执行组及真实 Android 温升/后台生存性测量，NFR-V1-COMP-003 同时由 GZ-020 验证。

原共享 POC 索引只表示任务进度；完整 GZ-018/GZ-020 分别执行 `check_program.py --profile local-v1 --milestone GZ-018` / `--profile production --milestone GZ-020`，要求各自全部十项合格证据，不能选择子集。local-v1 证据保留在原 POC 自身目录；生产重测由 GZ-020 在自身 Evidence 下保存独立版本 2 的记录和范围索引，不重开或覆盖已完成 POC。结果/执行引用必须留在其所选目录，并由实际所有者的 Implementer/Reviewer 绑定。POC 前置验证不替代完整平台验收或生产发布。

跨 OS 小样本、WSL、多进程或模拟故障必须报告实际范围，不冒充物理多机、Android、长时负载、完整浏览器播放或生产测量。

本地 POC-001 按用户决定先用Android虚拟机，须有实际 guest 编码、输入/输出哈希及原始输出，身份与 worker 清单一致并记录 hypervisor 和物理宿主机；真实 Android 明确标记未测试。本地 PASS 不授予真机或物理多宿主机支持。生产仍须真实 Android 编码及温升/功耗、后台生存性记录，未测或模拟器不能授予生产 PASS。限定 profile 的资源配置/预约使用自身版本化 Schema，绑定任务、POC、资源与 profile，由独立审查者在执行前批准且有效期覆盖真实执行区间；不能只检查文件存在。AI 审查绑定模型身份/版本与实际运行工具栈。数值域按单位和指标含义校验，模型/评审量程需独立批准的定义记录，不虚构统一分数上限或性能通过阈值。

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

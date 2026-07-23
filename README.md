# 归泽・Guize

> 海量多媒体统一入库、镜像缓存、智能加工、统一检索与在线播放平台。  
> An AI-powered media fabric for unified ingestion, caching, storage, understanding, search, and streaming.

## 1. 文档状态

- 文档基线：V1 方案冻结版
- 冻结日期：2026-07-21
- 当前阶段：需求冻结，进入 POC、架构细化与迭代实施
- 开发模式：Codex、Trae Solo/Work 等 Agent 主导实现，由一人审查、确认、部署与发布
- 交付要求：V1 纳入范围的能力全部达到生产级，不设置对外 Beta

## 2. 产品定位

“归泽”组合自：

- **归墟**：万流汇聚，代表海量、多源、异构媒体的统一汇入和收纳。
- **白泽**：识万物，代表 AI 对媒体内容的识别、理解、翻译、分类、检索与治理。

归泽不是单纯的网盘、播放器、转码器或 AI 内容分析工具，而是面向大规模媒体资产的统一控制面与执行平台。平台覆盖：

1. 多数据源接入与元数据同步；
2. 逻辑资产、来源、版本、媒体表现与物理副本治理；
3. Apache Traffic Server 分片缓存与完整文件缓存；
4. 热、温、冷、超冷存储生命周期；
5. AV1 标准化、ABR、自适应播放与兼容转码；
6. ASR、OCR、多模态理解、翻译、摘要、标签和缩略图；
7. 全文、向量、混合检索和内容推荐；
8. 用户、角色、ACL、匿名访问与审计；
9. LiteFlow 决策编排与 Temporal 长任务；
10. 配置中心、GitOps、可观测性、备份和灾难恢复。

## 3. V1 关键技术基线

| 领域 | V1 基线 |
|---|---|
| 控制面 | Java 17、Spring Boot 3、模块化单体 |
| 媒体与 AI | Python、FastAPI，逻辑服务独立、物理部署可组合 |
| 部署工具 | Go CLI `guizectl` + 配置中心部署向导 |
| 数据库 | PostgreSQL；核心关系规范化，扩展元数据使用 JSONB |
| 缓存与临时状态 | Redis |
| 数据库迁移 | Flyway |
| 轻量规则与同步决策 | LiteFlow、决策表、JSON/YAML DSL |
| 长任务 | 自托管 Temporal + PostgreSQL |
| HTTP 缓存 | Apache Traffic Server |
| 搜索 | PostgreSQL FTS、OpenSearch、Milvus、Reranker |
| Secrets | OpenBao/Vault 抽象，数据库仅存引用 |
| 可观测性 | Prometheus、Grafana、Loki、OpenTelemetry、Alertmanager |
| 镜像仓库 | 华为云 SWR，Digest 固定、签名、部署验签 |
| 部署 | Docker Compose、Ansible、GitOps，预留 Kubernetes |
| 代码托管 | GitHub 私有仓库 |
| 播放器 | 独立 Guize Player SDK，优先评估 Shaka Player |
| 前端 | Vue 3 与 React POC 后选择主框架；共享设计 Token |

## 4. 文档索引

| 文档 | 内容 |
|---|---|
| [总体执行摘要](docs/00-executive-summary.md) | 结论、范围、核心原则和实施重点 |
| [总体解决方案](docs/01-overall-solution.md) | 平台能力与端到端闭环 |
| [需求和范围](docs/02-requirements-and-scope.md) | 目标、非目标、约束与生产级定义 |
| [系统架构](docs/03-system-architecture.md) | 分层架构、模块边界、数据流 |
| [部署拓扑](docs/04-deployment-topology.md) | ESXi、TrueNAS、Control、Media、AI Worker |
| [领域和数据模型](docs/05-domain-and-data-model.md) | Asset、Version、Rendition、Replica 等 |
| [API 与事件契约](docs/06-api-and-event-contracts.md) | REST、SSE、WebSocket、Outbox、幂等 |
| [数据源连接器](docs/07-source-connectors.md) | WebDAV、本地、百度云、Google Drive 等 |
| [缓存和生命周期](docs/08-cache-and-storage-lifecycle.md) | ATS、完整缓存、热温冷超冷 |
| [媒体、AV1 与播放](docs/09-media-av1-and-streaming.md) | AV1、ABR、临时 H.264、播放器 |
| [AI 多模态流水线](docs/10-ai-multimodal-pipeline.md) | ASR、OCR、翻译、摘要、Embedding |
| [搜索与推荐](docs/11-search-and-recommendation.md) | FTS、OpenSearch、Milvus、混合检索 |
| [安全、身份与权限](docs/12-security-identity-and-permissions.md) | Passkey、密码、ACL、公开策略 |
| [配置中心](docs/13-configuration-center.md) | 页面信息架构与治理功能 |
| [规则与工作流](docs/14-rules-and-workflows.md) | LiteFlow、Temporal、规则发布模型 |
| [可观测性与运维](docs/15-observability-and-operations.md) | 指标、日志、追踪、告警 |
| [备份与灾难恢复](docs/16-backup-and-disaster-recovery.md) | RPO/RTO、恢复顺序、备份落点 |
| [DevOps 与供应链](docs/17-devops-gitops-and-supply-chain.md) | GitOps、SWR、Cosign、SBOM |
| [测试与验收](docs/18-testing-and-acceptance.md) | 测试矩阵、质量门禁、生产验收 |
| [风险和 POC](docs/19-risk-assumptions-and-poc.md) | 假设、风险、实机验证清单 |
| [路线图与 WBS](docs/20-roadmap-and-wbs.md) | Agent 驱动、单人审查下的实施顺序 |
| [Low Level Design](docs/21-low-level-design.md) | 模块、表、接口、状态机与执行细节 |
| [仓库与目录规划](docs/22-repository-and-directory-plan.md) | Monorepo、独立 Worker 仓库与治理目录 |
| [官方资料核验](docs/23-source-references.md) | 组件官方资料和核验日期 |

## 5. 强制工程治理

任何实现任务必须遵循：

- 先更新需求、设计和契约，再编码；
- 每个需求具备可执行、可验证的验收标准；
- 修改关联 Issue、分支、提交、测试与证据；
- 遵守 [AGENTS.md](AGENTS.md)；
- 遵守 [Never Rules](rules/never-rules.md)；
- 架构变化必须新增或更新 ADR；
- 文档、代码、配置和测试同步修改；
- AI Agent 生成的修改必须通过自动化门禁；
- 未验证的结论不得标记为完成；
- 每个里程碑必须能独立部署、回滚和验收。

## 6. 建议阅读顺序

```text
README
→ 00 执行摘要
→ 02 需求范围
→ 03 系统架构
→ 04 部署拓扑
→ 05 数据模型
→ 21 LLD
→ 20 WBS
→ AGENTS / Never Rules
```

## 7. 当前必须先完成的 POC

1. Arc A380 在浪潮 5212 与 ESXi 6.7 上的 GPU 直通；
2. A380 AV1/H.264 编码能力、并发与首分片时间；
3. TrueNAS iSCSI 与 ESXi 内部网络吞吐；
4. ATS Range/Slice 缓存命中与大文件稳定性；
5. 700TB 数据源规模下的目录扫描与元数据增长；
6. 百度云受支持的可持续接入方式；
7. IPv6、公网高端口、CDN/Tunnel 的实际播放效果；
8. Vue 3 与 React POC；
9. 本地与商业 AI 的质量、成本和回退基线；
10. 备份恢复演练与密钥恢复路径。

## 8. 术语

- 中文正式名：**归泽**
- 英文代号：**Guize**
- CLI：`guizectl`
- 管理控制台：**Guize Console**
- 播放器：**Guize Player**
- 逻辑资产：`Asset`
- 来源对象：`SourceObject`
- 内容版本：`AssetVersion`
- 媒体表现：`Rendition`
- 物理副本：`Replica`

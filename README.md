# 归泽・Guize

> 海量多媒体统一入库、镜像缓存、智能加工、统一检索与在线播放平台。
> An AI-powered media fabric for unified ingestion, caching, storage, understanding, search, and streaming.

## 1. 当前文档基线

- 产品基线：V1 需求冻结版。
- 当前阶段：POC、研发详细设计与迭代实施。
- 交付约束：V1 不设置对外 Beta；所有纳入 V1 范围的能力必须通过生产级门禁后才能发布。
- 研发主文档：[`docs/00-guize-engineering-design-baseline.md`](docs/00-guize-engineering-design-baseline.md)。
- 交付审计与多 Agent 协作：[`docs/24-requirements-design-audit-and-multi-agent-delivery.md`](docs/24-requirements-design-audit-and-multi-agent-delivery.md)。
- 机器可读协作计划：[`specs/collaboration/program-plan.yaml`](specs/collaboration/program-plan.yaml)。
- 文档组织：主文档采用 ePROHub 规则引擎 V2 的“编号 + 追踪 + 模块 + 契约 + 数据 + 状态 + 工作包 + 验收”格式。
- 开发模式：Agent 主导实现，人工审查、批准、部署与发布。
- 机器契约：`contracts/**`、正式 Migration、`deployment/**` Schema 的机器可执行内容优先于说明文档。

> `docs/00～23`、`docs/appendices/**` 与旧合并版继续保留，作为专题设计来源和历史参考；研发开工不再要求按 24 份文档顺序阅读。

## 2. 研发第一入口

### [归泽・Guize V1——研发设计总基线](docs/00-guize-engineering-design-baseline.md)

总文档统一覆盖：

```text
产品范围与硬约束
→ 端到端全链路
→ 系统/模块边界
→ Asset/SourceObject/AssetVersion/Rendition/Replica 数据模型
→ API / Event / SSE / WebSocket / Plugin 契约
→ LiteFlow / Temporal / Task
→ 状态机 / 幂等 / Outbox
→ ATS / PostgreSQL / Redis / OpenBao / OpenSearch / Milvus
→ 部署 / 安全 / Secrets / 备份恢复
→ 模块级代码规划与伪代码
→ 测试 / POC / 验收
→ WBS / 工作包 / 追踪矩阵
```

统一追踪编号：

```text
需求ID
→ 模块ID
→ 领域模型ID
→ 接口ID
→ 事件ID / 工作流ID
→ 数据库ID
→ 代码项ID
→ 工作包ID
→ 验收ID
```

当前仓库仍以方案和治理为主，因此总文档中的 Class、Interface、数据库表和 Worker 默认属于**研发规划基线**；只有仓库真实存在并通过验证的实现才可标记为“已实现”。

### 2.1 多 Agent 协作入口

多 Agent 开发必须先阅读：

1. [`AGENTS.md`](AGENTS.md) 与 [`rules/never-rules.md`](rules/never-rules.md)；
2. [`docs/24-requirements-design-audit-and-multi-agent-delivery.md`](docs/24-requirements-design-audit-and-multi-agent-delivery.md)；
3. [`specs/collaboration/README.md`](specs/collaboration/README.md)；
4. [`specs/collaboration/program-plan.yaml`](specs/collaboration/program-plan.yaml)；
5. 当前 Task Spec、Coordination Descriptor、上游机器契约和 Handoff。

协作顺序：

```text
需求/NFR/验收
→ OpenAPI/Event/DDL/Workflow Contract
→ 阻断性 POC
→ 模块骨架
→ 并行实现
→ 纵向集成
→ 独立 Review
→ Governance Gate + Collaboration Gate
→ 人工合并/发布批准
```

常用命令：

```bash
python scripts/check-collaboration.py --task GZ-XXX --base origin/main
python scripts/render-multi-agent-prompt.py \
  --task GZ-XXX \
  --role implementation-agent \
  --output .agent/GZ-XXX-implementation-agent.md
```

禁止多个 Agent 在机器契约未冻结时分别猜测 API、事件、表、状态或错误语义。一个活动 Task 的独占路径只能有一个 Owner，最终 Reviewer 必须与 Owner 分离。

## 3. 产品定位

“归泽”取意于：

- **归墟**：万流汇聚，对应多源、异构、海量媒体统一接入和收纳；
- **白泽**：识万物，对应 AI 对媒体的识别、理解、翻译、分类、检索和治理。

归泽不是单一网盘、播放器、转码器或 AI 内容分析工具，而是统一媒体资产控制面与执行平台。

核心能力：

1. 多数据源接入与元数据同步；
2. 逻辑资产、来源、版本、媒体表现和物理副本治理；
3. Apache Traffic Server Range/Slice 缓存与完整文件缓存；
4. 热、温、冷、超冷生命周期；
5. AV1、ABR、自适应播放与兼容转码；
6. ASR、OCR、多模态、翻译、摘要、标签和缩略图；
7. 全文、向量、混合检索和推荐；
8. IAM、ACL、匿名访问、Secrets 与审计；
9. LiteFlow 同步决策与 Temporal 长任务；
10. 配置中心、GitOps、可观测性、备份与灾难恢复。

## 4. V1 技术基线

| 领域 | V1 基线 |
|---|---|
| 控制面 | Java 17、Spring Boot 3、模块化单体 |
| 媒体与 AI | Python、FastAPI，逻辑服务独立、物理部署可组合 |
| 部署工具 | Go CLI `guizectl` + 配置中心部署向导 |
| 权威数据库 | PostgreSQL + Flyway |
| 缓存与短期状态 | Redis |
| 规则 | LiteFlow、决策表、JSON/YAML DSL |
| 长任务 | Self-hosted Temporal + PostgreSQL |
| HTTP 缓存 | Apache Traffic Server |
| 搜索 | PostgreSQL FTS、OpenSearch、Milvus、Reranker |
| Secrets | OpenBao/Vault 抽象；业务数据库只保存引用 |
| 可观测性 | Prometheus、Grafana、Loki、OpenTelemetry、Alertmanager |
| 供应链 | 华为云 SWR、Digest、SBOM、Cosign |
| 部署 | Docker Compose、Ansible、GitOps；预留 Kubernetes |
| 播放器 | 独立 Guize Player SDK；Shaka Player 为候选基线 |
| 前端 | Vue 3 / React 通过 POC 决定主框架 |

## 5. 专题参考文档

以下文件不再承担“研发总入口”，用于深入某一专题或追溯原始设计：

- `docs/00-executive-summary.md`～`docs/04-deployment-topology.md`：产品、架构、部署来源。
- `docs/05-domain-and-data-model.md`～`docs/08-cache-and-storage-lifecycle.md`：数据、接口、连接器、存储来源。
- `docs/09-media-av1-and-streaming.md`～`docs/14-rules-and-workflows.md`：媒体、AI、搜索、安全、配置和编排来源。
- `docs/15-observability-and-operations.md`～`docs/20-roadmap-and-wbs.md`：运维、灾备、DevOps、测试、风险和路线图来源。
- `docs/21-low-level-design.md`：原始 LLD 来源。
- `docs/22-repository-and-directory-plan.md`：仓库规划来源。
- `docs/23-source-references.md`：组件官方资料核验记录。
- `docs/appendices/**`：专题附录。
- `docs/guize-complete-solution.md`：旧版合并阅读稿，不作为后续维护权威入口。

## 6. 强制工程治理

任何实现任务必须：

- 先更新需求、设计和契约，再编码；
- 建立 Task Spec、Issue、独立分支、提交、测试和 Evidence；
- 遵守 [`AGENTS.md`](AGENTS.md)；
- 遵守 [`rules/never-rules.md`](rules/never-rules.md)；
- 架构长期变化使用 ADR，不改写旧 ADR 隐藏历史；
- API、Event、DB、Policy、Plugin、Deployment 行为变化同步机器契约；
- 未验证结论不得标记为完成；
- 不自动合并、生产部署或执行高风险不可逆操作；
- 每个里程碑必须可独立验证和回滚。

## 7. 当前阻断性 POC

1. `POC-01` Arc A380 + 浪潮 5212 + ESXi 6.7 GPU 直通；
2. `POC-02` A380 AV1/H.264 编码、并发、首分片、稳定性；
3. `POC-03` ATS Range/Slice、大文件、权限缓存键；
4. `POC-04` TrueNAS iSCSI、吞吐、延迟和故障恢复；
5. `POC-05` 700TB 数据源真实文件数量、目录规模和元数据增长；
6. `POC-06` 百度云合法、稳定、可维护的生产接入路径；
7. `POC-07` IPv6、高端口 HTTPS、Tunnel/CDN 和 Range 播放；
8. `POC-08` Vue 3 / React 管理端场景 POC；
9. `POC-09` 本地/商业 AI 的质量、成本、隐私和硬件吞吐；
10. `POC-10` PostgreSQL、OpenBao、正式副本和部署 Bundle 恢复。

POC 未完成前，不得把对应性能、兼容性和容量数字升级为生产承诺。

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

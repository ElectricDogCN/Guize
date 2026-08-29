# 归泽・Guize

> 海量多媒体统一入库、镜像缓存、智能加工、统一检索与在线播放平台。
> An AI-powered media fabric for unified ingestion, caching, storage, understanding, search, and streaming.

## 1. 当前文档基线

- 产品基线：V1 需求冻结版。
- 当前阶段：需求/NFR 细化、机器契约冻结、阻断性 POC 与工程骨架准备。
- 交付约束：V1 不设置对外 Beta；所有纳入 V1 范围的能力必须达到冻结需求定义的生产级门禁后方可发布。
- 研发主文档：[`docs/00-guize-engineering-design-baseline.md`](docs/00-guize-engineering-design-baseline.md)。
- 就绪审计：[`docs/24-requirements-design-readiness-audit.md`](docs/24-requirements-design-readiness-audit.md)。
- 多 Agent 协作：[`docs/25-multi-agent-collaboration-protocol.md`](docs/25-multi-agent-collaboration-protocol.md)。
- V1 Program Plan：[`specs/coordination/program-plan.yaml`](specs/coordination/program-plan.yaml)。
- 开发模式：Agent 主导实现，独立 Agent 审查与集成，ElectricDogCN 进行最终人工批准、部署与发布。
- 权威优先级遵循 [`AGENTS.md`](AGENTS.md)：已批准需求规格 → 已批准 API/事件/数据 Schema 契约 → 已批准 ADR → 系统/模块设计 → `AGENTS.md` → Never Rules → Program Plan/当前任务说明 → 代码现状 → Agent 推断。

> `docs/00～23`、`docs/appendices/**` 与旧合并版继续保留，作为专题设计来源和历史参考；索引和计划不能覆盖更高优先级的冻结需求、机器契约或 ADR。

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

当前仓库仍以方案、治理和机器契约准备为主，因此总文档中的 Class、Interface、数据库表和 Worker 默认属于**研发规划基线**；只有仓库真实存在并通过验证的实现才可标记为“已实现”。

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
- `docs/24-requirements-design-readiness-audit.md`：需求、设计、机器契约、POC、实现和验收就绪缺口。
- `docs/25-multi-agent-collaboration-protocol.md`：Program Plan、任务预留、路径、依赖、交接、审查和集成协议。
- `docs/appendices/**`：专题附录。
- `docs/guize-complete-solution.md`：旧版合并阅读稿，不作为后续维护权威入口。

## 6. 强制工程治理

任何实现任务必须：

- 先更新需求、设计和契约，再编码；
- 在 Program Plan 中存在唯一任务定义；
- 建立 Task Spec、Issue、reservation PR、独立实现分支、测试、Evidence 和 Handoff；
- 遵守 [`AGENTS.md`](AGENTS.md) 与 [`rules/never-rules.md`](rules/never-rules.md)；
- 按 [`specs/designs/module-ownership.yaml`](specs/designs/module-ownership.yaml) 的模块、Schema 和公共契约 ownership 修改；
- 架构长期变化使用 ADR，不改写旧 ADR 隐藏历史；
- API、Event、DB、Policy、Plugin、Worker、Deployment 行为变化先同步机器契约；
- 未验证结论不得标记为完成；
- 不自动生产部署或执行高风险不可逆操作；
- 每个里程碑必须可独立验证和回滚。

## 7. 当前阻断性 POC

Program Plan 把十项 POC 映射为十个独立 Task 和 Evidence：

1. `POC-001 / POC-01`：Arc A380 + 浪潮 5212 + ESXi 6.7 GPU 直通；
2. `POC-002 / POC-02`：A380 AV1/H.264 编码、并发、首分片、稳定性；
3. `POC-003 / POC-03`：ATS Range/Slice、大文件、权限缓存键；
4. `POC-004 / POC-04`：TrueNAS iSCSI、吞吐、延迟和故障恢复；
5. `POC-005 / POC-05`：700TB 数据源真实文件数量、目录规模和元数据增长；
6. `POC-006 / POC-06`：百度云合法、稳定、可维护的生产接入路径；
7. `POC-007 / POC-07`：IPv6、高端口 HTTPS、Tunnel/CDN 和 Range 播放；
8. `POC-008 / POC-08`：Vue 3 / React 管理端场景 POC；
9. `POC-009 / POC-09`：本地/商业 AI 的质量、成本、隐私、许可证和硬件吞吐；
10. `POC-010 / POC-10`：PostgreSQL、OpenBao、正式副本和部署 Bundle 恢复。

GZ-010 只负责统一 POC 模板、样本、资源与排程，不代替十个实验任务。POC 未完成前，不得把对应性能、兼容性和容量数字升级为生产承诺。

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

## 9. 实施就绪与多 Agent 开发

### 机器可读入口

- 冻结需求权威：[`specs/requirements/product-requirements.md`](specs/requirements/product-requirements.md)
- 需求追踪：[`specs/requirements/requirements-index.yaml`](specs/requirements/requirements-index.yaml)
- 模块与公共契约所有权：[`specs/designs/module-ownership.yaml`](specs/designs/module-ownership.yaml)
- V1 Program Plan：[`specs/coordination/program-plan.yaml`](specs/coordination/program-plan.yaml)
- Program Plan Schema：[`specs/coordination/program-plan.schema.yaml`](specs/coordination/program-plan.schema.yaml)
- 当前活动任务：[`specs/coordination/active-work.yaml`](specs/coordination/active-work.yaml)
- schemaVersion 2 Task 模板：[`specs/tasks/task-template.md`](specs/tasks/task-template.md)

`program-plan.yaml` 负责长期 Task/Wave/DAG/POC/contract/release blocker；`active-work.yaml` 只记录已预留或正在执行的少量任务。禁止再创建第二份后续任务计划。

### 开始新任务

```text
Program Plan 任务满足依赖和 Wave 容量
→ Issue + Task Spec + Evidence
→ Reservation PR 登记风险/baseSha/角色/路径/租约
→ Reservation Gate/Review/Merge
→ 从 reservation 后最新 main 创建登记分支
→ Implementer
→ Handoff
→ Independent Reviewer
→ Integrator
→ Human Merge Approval
→ Registry 释放 + Program Plan 状态同步
```

验证：

```bash
python scripts/check-schemas.py
python scripts/check-project-readiness.py
python scripts/check-agent-coordination.py
make verify TASK=<TASK-ID> BRANCH=<branch> BASE=origin/main
```

### 外部平台阻断项

当前 GitHub `main` 尚未启用 Branch Protection/Ruleset，Required Check 和审批不能由仓库文件自行强制。该缺口由 OPS-001（Issue #20）持续跟踪；在真实设置和 API 验证完成前，只能称为“流程与 CI 约束可用”，不能称为“平台已强制阻止直接推送”。

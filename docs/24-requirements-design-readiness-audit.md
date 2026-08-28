# 24. 需求、设计与实施就绪审计

> 任务：GZ-003  
> 审计基线：`main@70984201e8d01ad75b6aa0fa0ee5ffe141087b52`  
> 结论类型：查缺补漏与实施门禁，不修改冻结产品范围

## 1. 结论

Guize V1 的产品范围、核心领域模型、控制面/执行面分层、LiteFlow/Temporal 职责、缓存/正式副本边界、安全原则、测试类型和 WBS 已形成较完整的**设计基线**。但仓库尚不能直接进入大规模并行业务编码，原因不是“缺少更多概念”，而是以下实施前产物仍未冻结：

1. 完整 OpenAPI、Event Payload、Workflow/Activity、DDL、错误码、Plugin/Worker 等机器契约；
2. Java/Python/前端/Go 的真实工程骨架、依赖锁定和语言级 CI；
3. POC-01～10 的实测结论；
4. AI、搜索、媒体、性能和安全的固定样本与批准阈值；
5. 多 Agent 活动任务登记、路径租约、依赖、交接和集成顺序；
6. GitHub `main` 分支保护、Required Check 和 Ruleset。

因此当前整体状态为：

```text
产品范围          已冻结
总体设计          已形成
机器契约          部分/缺口
阻断性 POC        未完成
业务实现          未开始
生产验收阈值      未冻结
单任务治理        可用
多 Agent 并行治理 GZ-003 建设中
生产发布          不就绪
```

## 2. 审计方法与权威顺序

审计按 `AGENTS.md` 的权威顺序执行：已批准需求 → 已批准机器契约 → ADR → 系统/模块设计 → Agent 治理 → Task → 代码。`specs/requirements/requirements-index.yaml` 只做追踪，不成为第二份需求权威来源；`specs/designs/module-ownership.yaml` 只做所有权和依赖索引，不覆盖 ADR 或真实机器契约。

## 3. 一致性审计

### 3.1 产品定位与范围

`specs/requirements/product-requirements.md`、`docs/02-requirements-and-scope.md` 与研发总基线在以下方面一致：

- 多来源媒体统一为 Asset/SourceObject/AssetVersion/Rendition/Replica；
- Range/ATS/完整缓存/兼容转码提供按需访问；
- AI、搜索、生命周期、安全、配置、规则、任务、运维均在 V1；
- Agent 主开发、单人最终审查；
- 700TB、ESXi 6.7、A380、500GB 水位是当前约束；
- V1 不设置对外 Beta，所有范围能力必须通过生产门禁。

缺口：同一需求过去同时使用 `G-01`、`需求V1-0001` 和自然语言标题，容易导致 Agent 建立重复任务。GZ-003 用 `REQ-V1-0001～0010` 建立别名映射，不改写原需求。

### 3.2 架构与模块边界

总体架构在专题设计、LLD 和研发总基线中一致：Java 模块化单体保存权威决策；Python/插件/Worker 不直连核心数据库；LiteFlow 做同步决策；Temporal 做长任务；PostgreSQL 是事实源；OpenSearch/Milvus 可重建。

缺口：模块拥有的路径、Schema、公开契约和允许依赖此前仅存在于自然语言，无法供多个 Agent 自动检查。`module-ownership.yaml` 将其结构化，但当前大多数路径仍是 planned，不代表代码已存在。

### 3.3 领域模型与数据库

Asset 聚合、来源删除不等于资产删除、移动/改名不创建内容版本、缓存不等于正式副本、只有 VERIFIED 副本计入恢复等原则一致。

阻断缺口：尚无正式 Flyway DDL、字段字典、索引基线、外键策略、迁移性能计划和 Testcontainers 集成验证。任何业务 Entity/Repository 开发前必须先由 GZ-004 类任务冻结对应机器契约。

### 3.4 API、事件与任务

API 命名、统一响应、`traceId`、幂等、长任务返回 `taskId`、Event Envelope 和 at-least-once 消费原则一致。

阻断缺口：`contracts/openapi/` 当前只有 guidelines，事件只有通用 Envelope；各资源 Endpoint、错误码、Event Payload、兼容基线和消费者契约尚未形成可执行文件。

### 3.5 LiteFlow 与 Temporal

职责分离清晰，主要 Workflow 和状态机已经规划。

阻断缺口：没有 Node/Chain/EL 输入输出契约、Workflow/Activity 类型、Retry/Timeout/Heartbeat/Cancellation、版本升级和补偿的机器可读定义，也没有 Temporal/LiteFlow 测试工程。

### 3.6 安全与权限

默认拒绝、ACL 前置、衍生内容继承权限、Secrets 引用、SSRF/路径/文件扫描、高风险再次认证等原则完整。

缺口：尚无 Threat Model、权限矩阵、固定越权测试数据、管理员密码风险阈值和安全例外流程。仓库目前为 public，文档暴露部署拓扑与安全假设；是否保持公开必须作为所有者显式决策，而不是由 Agent 自动改变可见性。

### 3.7 测试与验收

测试层级、故障注入、安全类别和 V1 退出门禁完整。

阻断缺口：大多数指标没有批准的数值阈值或固定 Golden Dataset。测试“类型”已定义，但测试“通过标准”尚未冻结，尤其包括 WER/DER/OCR、Recall@K/NDCG、首帧、并发、数据库规模和恢复时间。

### 3.8 POC 与环境

POC-01～10 覆盖了关键未知项。

阻断缺口：POC 尚未拆成独立 Task/Issue、环境清单、原始数据格式和退出决策。`work-package-plan.yaml` 建立建议顺序，但计划不等于已执行。

### 3.9 GitHub 与供应链

Governance Gate 已能检查 Task、Scope、Evidence、Schema、Secret 和文档。

当前外部缺口：

- `main` 的 `protected=false`；
- Ruleset 列表为空；
- Required Check 未配置；
- CODEOWNERS 尚未生效为强制审批；
- GitHub Actions 使用版本标签而非不可变 SHA；
- 未配置依赖更新、代码扫描、容器扫描和 merge queue。

GZ-003 可提交 CODEOWNERS 和配置清单，但不能把仓库设置建议写成已启用事实。

## 4. 缺口优先级

### P0：开始业务并行开发前必须完成

1. GZ-003 多 Agent 协作治理与路径冲突门禁；
2. 管理员启用 `main` 分支保护/Ruleset；
3. GZ-004 冻结核心机器契约骨架；
4. GZ-005 建立真实工程骨架和语言级 CI；
5. POC-01～07 中影响拓扑、播放、来源和存储的项目；
6. GZ-012 固定验收样本、阈值和测量方法。

### P1：M1/M2 前必须完成

- IAM/ACL 权限矩阵和越权测试；
- 数据库 DDL、迁移、恢复和容量计划；
- Connector/Worker/Plugin 契约；
- Task/Temporal/LiteFlow 机器契约；
- Source/Asset/Playback 的 E2E 测试架构；
- 威胁模型和安全例外流程。

### P2：进入 RC 前完成

- Actions 固定 SHA、Dependabot、CodeQL、SBOM/许可证自动门禁；
- Merge Queue、环境保护、发布签署；
- 文档归档策略和历史 ZIP 清理决策；
- 生产 Runbook、值班、容量和成本看板。

## 5. 实施就绪矩阵

| 需求 | 设计 | 机器契约 | POC | 代码 | 通过标准 | 当前结论 |
|---|---|---|---|---|---|---|
| 统一接入 | 较完整 | 部分 | POC-05/06 未完成 | 无 | 未冻结 | 阻断 |
| 统一资产 | 较完整 | 缺 | POC-05 影响容量 | 无 | 概念级 | 阻断 |
| 播放 | 较完整 | 缺 | POC-01/02/03/07 未完成 | 无 | 未冻结 | 阻断 |
| AI | 较完整 | 缺 | POC-09 未完成 | 无 | 未冻结 | 阻断 |
| 搜索推荐 | 较完整 | 缺 | 依赖 AI/规模 | 无 | 未冻结 | 阻断 |
| 生命周期/备份 | 较完整 | 缺 | POC-04/10 未完成 | 无 | 部分 | 阻断 |
| 规则/长任务 | 较完整 | 部分 | 测试环境未建 | 无 | 部分 | 阻断 |
| 安全权限 | 较完整 | 部分 | 公网/恢复待测 | 无 | 未冻结 | 阻断 |
| 配置发布 | 较完整 | 部分 | Bundle 未恢复 | 无 | 部分 | 阻断 |
| 生产治理 | 治理可用 | 部分 | 恢复未完成 | 仅治理 | 部分 | 部分就绪 |

## 6. 推荐顺序与并行策略

```text
GZ-003 协作治理
├── GZ-004 核心机器契约（高风险，独占）
│   └── GZ-005 工程骨架与语言 CI（高风险，独占）
├── GZ-007 ATS POC（中风险）
├── GZ-009 规模探测（中风险）
├── GZ-010 百度云 POC（中风险）
├── GZ-011 公网 POC（中风险）
├── GZ-006 A380/编码 POC（高风险，与其他高风险不并行）
├── GZ-008 TrueNAS POC（高风险，与其他高风险不并行）
├── GZ-012 验收样本/阈值（中风险）
└── GZ-013 恢复 POC（依赖 GZ-004/005/008）
```

同一时间最多一个 high/critical 任务，或最多三个完全独立的 low/medium 任务。只有机器契约冻结后，才允许多个 Agent 分别实现其消费者和提供者。

## 7. GitHub 管理员配置阻断项

建议启用：

1. `main` 必须通过 PR；
2. 至少 1 个批准，high/critical 要求独立 Reviewer；
3. Required Check：`Governance Gate / Governance Checks`；
4. Require conversation resolution；
5. Dismiss stale approvals；
6. 禁止 force push 和 branch deletion；
7. 要求分支在合并前与 `main` 同步；
8. CODEOWNERS 审批；
9. 管理员也遵守规则，紧急绕过必须审计。

当前实际状态仍是未启用，需管理员完成并再次通过 API 验证。

## 8. 审计结论

GZ-003 完成后，仓库将达到“可安全拆分下一阶段任务”的治理就绪状态，而不是“业务系统已经可开发完毕”。后续应先执行机器契约、工程骨架、验收阈值和 POC，再进入 M1 资产与可播放闭环。任何 Agent 不得绕过这些门禁，直接依据概念 LLD 批量生成生产代码。

# 24. 需求、设计与实施就绪审计

> 当前审计任务：GZ-014
> 初始审计任务：GZ-003
> 审计基线：GZ-014 reservation merge `d731ce09fbf2535948bc1864490539d06ce1f139`
> 结论类型：查缺补漏、依赖收敛与实施门禁，不修改冻结产品范围

## 1. 执行结论

Guize V1 已完成“产品范围与总体设计”层面的主要梳理，并已经具备可运行的单任务治理和多 Agent 活动任务登记。GZ-014 在此基础上补齐长期交付计划、公共机器契约 ownership、POC 拆分和任务依赖校验。

当前准确状态：

```text
产品范围                    已冻结
总体设计                    已形成
需求追踪                    已结构化
模块与 Schema 所有权        已结构化
公共机器契约 owner/consumer  已结构化
V1 Program Plan             已建立，GZ-014 审查中
活动任务 reservation         可执行并已真实验证
OpenAPI/Event/DDL/Runtime    未冻结
十项阻断性 POC              未执行
多语言工程骨架              未建立
业务实现                    未开始
Golden Dataset/阈值         未冻结
GitHub 平台保护              未启用，Issue #20 阻断
生产发布                    不就绪
```

因此，仓库已经接近“可以安全启动机器契约和独立 POC 任务”，但尚不允许多个 Agent 直接依据概念 LLD 批量生成业务实现。

## 2. 审计权威顺序

发生冲突时按 `AGENTS.md` 处理：

```text
已批准需求规格
→ 已批准 API / Event / Data Schema
→ 已批准 ADR
→ 系统和模块设计
→ AGENTS.md
→ Never Rules
→ Program Plan / Task Spec / Registry
→ 代码现状
→ Agent 推断
```

关键边界：

- `requirements-index.yaml` 只做追踪，不是第二份产品需求；
- `module-ownership.yaml` 只做模块、Schema 和公共契约 ownership；
- `program-plan.yaml` 只安排如何交付冻结范围；
- `active-work.yaml` 只登记当前已预留/执行的任务；
- Issue/PR 是人类协作视图，必须与仓库事实源一致。

## 3. 产品需求审计

### 3.1 已冻结范围

V1 的十个需求域保持不变：

1. 多来源统一接入；
2. Asset/SourceObject/AssetVersion/Rendition/Replica 统一资产；
3. Range/ATS/完整缓存/兼容转码的按需访问；
4. ASR/OCR/VLM/翻译/摘要/标签等智能理解；
5. PostgreSQL FTS/OpenSearch/Milvus/Reranker 检索推荐；
6. 热温冷超冷、正式副本、保留、备份与恢复；
7. LiteFlow 同步决策与 Temporal 可恢复长任务；
8. IAM、ACL、匿名访问、Secrets 与审计；
9. 配置、审批、灰度、发布和回滚；
10. 可观测、GitOps、供应链和生产治理。

冻结交付不变量：**V1 不设置对外 Beta**。所有纳入 V1 的能力必须达到生产级门禁后方可发布。

### 3.2 已修复的追踪缺口

- `G-01`、`需求V1-0001` 等旧标识统一映射为 `REQ-V1-0001～0010`；
- Requirement ↔ Module 映射双向校验；
- Requirement `nextTasks` 必须存在于 canonical Program Plan；
- Requirement、POC、Task、Module 和验收之间可追踪；
- 需求索引首次在真实 reservation Gate 中发现并修复四处非对称关系，证明检查器实际生效。

### 3.3 仍需完成

GZ-004 需在不改变产品范围的前提下冻结：

- 统一需求别名和术语；
- NFR：安全、容量、性能、恢复、可观测、供应链；
- 需求—验收—POC—Task 追踪；
- 可执行验收描述和明确“不适用”规则。

## 4. 架构与模块边界审计

### 4.1 已确认架构

- Java 17/Spring Boot 3 模块化单体承担控制面和权威业务决策；
- Python/FastAPI/Worker/插件承担媒体、AI、连接器和执行能力；
- Python 服务和插件不直连核心 PostgreSQL；
- PostgreSQL 是事实源，Redis 不是最终一致性来源；
- LiteFlow 做同步、可解释决策，Temporal 做长任务；
- ATS 普通缓存、完整缓存、正式副本和灾备副本严格分层；
- OpenSearch/Milvus 可重建，不是权威资产或 ACL 数据源；
- OpenBao 保存 Secret 正文，业务数据库仅保存引用。

### 4.2 模块所有权

`specs/designs/module-ownership.yaml` 当前记录：

- 21 个逻辑/物理模块；
- 模块 owned path；
- PostgreSQL Schema owner；
- 模块依赖；
- 37 个公共 Contract Namespace；
- 每个 Namespace 的唯一 owner、consumer 和可选 shared writer。

这解决了过去 `contracts/openapi/playback/**`、`contracts/workflows/**`、部署 Profile 等路径可能被多个 Agent 同时当作“自己拥有”的问题。

### 4.3 仍需完成

- GZ-005～GZ-008 将 ownership 具体化为可执行 OpenAPI/Event/DDL/Runtime Contract；
- GZ-012 建立真实工程模块和语言级 CI；
- 后续实现 Task 需要更细的 Class/Interface/DTO/Repository/Service/Controller 设计，但必须按工作包分批冻结，不一次性虚构全平台代码。

## 5. API、事件、数据和运行时契约审计

### 5.1 当前已有

- OpenAPI guidelines；
- 通用 Event Envelope；
- Plugin Manifest 和 Deployment Profile 基础 Schema；
- API 命名、`traceId`、幂等键、长任务 `taskId`、at-least-once + consumer 幂等原则；
- 概念表、状态机、Workflow 和 LiteFlow 职责。

### 5.2 阻断缺口

| Task | 机器契约输出 |
|---|---|
| GZ-005 | 完整 OpenAPI、错误码、HTTP 示例、权限与幂等 |
| GZ-006 | Event Payload Schema、生产者/消费者、版本与兼容 |
| GZ-007 | PostgreSQL/Flyway DDL、索引、唯一约束、迁移与恢复 |
| GZ-008 | Temporal Workflow/Activity、LiteFlow Node/Chain/EL、Worker/Plugin 权限与运行时契约 |
| GZ-009 | 页面/Action/API/权限/状态/错误/验收映射 |

未完成这些任务前，不允许并行实现依赖同一契约的多个模块。consumer Task 必须依赖已合并 producer，不能仅以“计划上先做”为依据。

## 6. POC 审计

过去 POC-01～10 只有自然语言清单，可能被单个巨大 GZ-010 分支执行。GZ-014 将其拆成：

```text
GZ-010  POC 统一模板、样本、资源和排程
POC-001 POC-01 A380 直通
POC-002 POC-02 A380 编码
POC-003 POC-03 ATS Range/Slice
POC-004 POC-04 TrueNAS
POC-005 POC-05 700TB 元数据规模
POC-006 POC-06 百度云
POC-007 POC-07 公网 IPv6/TLS/Tunnel/CDN
POC-008 POC-08 Vue 3 / React
POC-009 POC-09 AI 基线
POC-010 POC-10 恢复与回读
```

每个实验具有独立 Task、风险、Wave、Evidence 和退出门禁。高风险 POC 串行执行；critical 恢复 POC 独立 Wave。

每个 POC 必须包含：

- 环境和版本；
- 配置和命令；
- 原始结果；
- 失败和限制；
- 替代方案；
- 退出决策；
- ADR/计划影响；
- 可复现脚本和回滚。

## 7. 测试、验收与发布审计

### 7.1 已形成

- 单元、集成、契约、E2E、性能、故障注入、安全和恢复测试层级；
- 资产、权限、ATS、缓存、媒体、AI、搜索、Policy、Temporal、备份和部署的验收类别；
- 统一 Evidence Contract；
- Governance Gate 对 Task、Scope、Evidence、Schema、Secret、Readiness 和 Coordination 的检查。

### 7.2 仍未冻结

GZ-011 需要冻结：

- Golden Dataset；
- WER/DER/OCR/相关性/VMAF/首帧/吞吐/恢复等测量方法；
- 质量和性能阈值；
- 隐私、许可证和人工抽检规则；
- 批准与变更流程。

GZ-020 是唯一 RC/Production Task，必须依赖 M1～M5、全部十项 POC、验收基线和 OPS-001。任何中间里程碑通过都不能提前对外发布 V1。

## 8. 多 Agent 协作就绪审计

### 8.1 已可执行机制

```text
Program Plan
→ Issue + Task Spec + Evidence
→ reservation PR
→ 活动 Registry + path lease
→ 实现分支
→ Implementer
→ Handoff
→ Independent Reviewer
→ Integrator
→ Human Approval
→ Merge
→ Registry 释放 + Program 状态同步
```

当前机制可以 fail-closed 检查：

- Task/Branch/Registry/base SHA 一致；
- 租约过期；
- 独占路径重叠；
- 未协调共享路径；
- 依赖环；
- 波次越序；
- 同 Wave 并行和 high-risk 超限；
- critical 非独立执行；
- 公共契约 owner/consumer/shared writer；
- contract consumer 未依赖 producer；
- POC 映射漂移；
- 外部 release blocker。

### 8.2 真实验证结果

GZ-014 reservation PR #18 首次运行并未直接通过，而是发现了 GZ-003 基线中的真实缺陷：

1. 四处 Requirement/Module 映射非对称；
2. “无共享范围”同一 bullet 中含反引号路径，被解析成伪共享路径。

修复后 reservation Gate 全部通过并合并。这说明两阶段协作不是文档约定，而是已经经过真实失败—修复—复验的执行机制。

### 8.3 外部平台缺口

GitHub 当前实测仍是：

- `main.protected=false`；
- Ruleset 为空；
- Required Check 未配置；
- CODEOWNERS 无平台强制力。

该问题由 OPS-001（Issue #20）跟踪。仓库内 CI 可发现违规，但不能阻止有权限人员绕过 PR 直接推送。Issue #20 未关闭前，生产发布保持阻断。

## 9. Canonical Program Plan

唯一计划：`specs/coordination/program-plan.yaml`。

Program Plan 当前覆盖：

- GZ-004～GZ-020；
- POC-001～POC-010；
- W1～W17；
- Requirement、Module、Contract producer/consumer；
- output/shared paths；
- risk、owner/reviewer role、integration order；
- release policy 和 external blockers。

旧 `specs/coordination/work-package-plan.yaml` 已删除。Issue、PR、聊天或 Agent 内存不得建立第二套未来任务定义。

主要顺序：

```text
GZ-004 需求/NFR/验收追踪
├─ GZ-005 OpenAPI
│  └─ GZ-006 Event
│     └─ GZ-007 DDL
│        └─ GZ-008 Runtime Contract
├─ GZ-009 UI/API 映射
└─ GZ-010 POC Program
   └─ POC-001～010（按风险与依赖分 Wave）

GZ-011 Golden Dataset/阈值
GZ-012 工程骨架与语言 CI
GZ-013 M1 可播放闭环
GZ-015 M2 存储闭环
GZ-016 M3 媒体/AI
GZ-017 M4 搜索推荐
GZ-018 M5 配置/规则/运维/部署
GZ-019 剩余 Connector
GZ-020 M6 RC/Production
```

## 10. 最终审计结论

GZ-014 完成后，Guize 将达到：

> **需求和总体设计可追踪、长期计划唯一、活动任务可预留、公共契约写入者明确、POC 可独立执行、Agent 能从仓库恢复上下文。**

这不等于业务系统已实现，也不等于生产就绪。下一步应按 Program Plan 先执行 GZ-004 和 GZ-010 的 reservation，再根据 Wave 容量推进机器契约与独立 POC；不能跳过契约、POC、验收和外部 GitHub 保护直接进入大规模并行业务编码。

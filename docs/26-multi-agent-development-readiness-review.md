# 26. Guize 需求、设计与多 Agent 开发启动审查

> 任务：GZ-014
> 审查基线：`main@9e3a821ada292ac3ef69b7c059384d17f6530b48`
> 范围：需求、设计、机器契约、POC、实现、验收、协作治理与 GitHub 平台控制

## 1. 执行结论

Guize 已具备较完整的产品与架构设计基线，也已经建立仓库原生的 Task、Evidence、Requirement Index、Module Ownership、Active Work Registry、路径租约、角色分离、Handoff 和 Governance Gate。GZ-014 修复后，仓库可安全地**预留和拆分下一阶段任务**。

但这不等于可以立即大规模并行业务编码，也不等于 GitHub 已平台强制保护 `main`。当前准确状态：

```text
冻结产品需求             已存在
研发设计总基线           已存在
需求/模块双向索引         GZ-014 修复后可验证
多 Agent 仓库内协议       已存在
活动任务 Registry         已存在
冲突/依赖/租约检查        已接入 Governance Gate
真实业务机器契约          大量缺口
工程代码骨架与语言 CI     未建立
阻断性 POC                未执行
Golden Sample/阈值        未冻结
GitHub Ruleset            未启用（外部阻断）
业务实现                   未开始
生产发布                   不就绪
```

## 2. GZ-003 合并后事件

GZ-003 的 PR 审查和 fixture 测试通过，但合并后的 `main` run #106 失败。根因是 Module Index 声明了以下关系，而 Requirement Index 未登记反向关系：

- `MOD-PLATFORM ↔ REQ-V1-0001`
- `MOD-PLATFORM ↔ REQ-V1-0002`
- `MOD-PLATFORM ↔ REQ-V1-0007`
- `MOD-ASSET ↔ REQ-V1-0003`

这说明仅测试人工构造的有效 fixture 不足以证明仓库实际数据有效。GZ-014 增加 `test_repository_indexes_pass`，后续任何真实索引漂移都会直接使治理测试失败。

## 3. 需求与设计梳理

| 需求 | 主要模块 | 设计成熟度 | 机器契约 | POC/阈值 | 实现结论 |
|---|---|---|---|---|---|
| REQ-V1-0001 统一接入 | Platform/Source/Connector/Task | 较完整 | 部分 | POC-05/06 | 未开始 |
| REQ-V1-0002 统一资产 | Platform/Asset/Source | 较完整 | 缺口 | 规模输入待测 | 未开始 |
| REQ-V1-0003 播放 | Asset/IAM/Storage/Media/Player/Edge | 较完整 | 缺口 | POC-01/02/03/07 | 未开始 |
| REQ-V1-0004 AI | AI/Task/Storage | 较完整 | 缺口 | POC-09/Golden Set | 未开始 |
| REQ-V1-0005 搜索推荐 | Search/Asset/IAM | 较完整 | 缺口 | 相关性阈值待冻 | 未开始 |
| REQ-V1-0006 生命周期/备份 | Storage/Task/Data | 较完整 | 缺口 | POC-04/10 | 未开始 |
| REQ-V1-0007 规则/长任务 | Platform/Policy/Task/Worker | 较完整 | 部分 | 执行测试环境缺 | 未开始 |
| REQ-V1-0008 安全权限 | IAM/Audit/Edge | 较完整 | 部分 | Threat Model/越权样本缺 | 未开始 |
| REQ-V1-0009 配置发布 | Config/Policy/Deploy/CLI | 较完整 | 部分 | Bundle 恢复待测 | 未开始 |
| REQ-V1-0010 生产治理 | Gov/Audit/Obs/Deploy/Data | 治理可用 | 部分 | 恢复/平台保护缺 | 仅治理 |

需求索引只是追踪层。发生冲突时仍按 `AGENTS.md`：已批准需求 → 已批准机器契约 → ADR → 系统/模块设计 → Agent 治理 → Task → 代码。

## 4. 当前必须补齐的产物

### P0：任何业务实现前

1. GZ-014 恢复真实 Readiness 和协作入口；
2. GitHub 管理员启用 `main` Ruleset；
3. GZ-004 冻结 OpenAPI/Event/Workflow/DDL 治理骨架；
4. GZ-005 建立 Java/Python/前端/Go 工程骨架与语言级 CI；
5. GZ-006～GZ-011 完成影响拓扑、播放、存储、来源的阻断 POC；
6. GZ-012 冻结样本、阈值、隐私规则和测量方法。

### P1：M1/M2 实现前

- IAM/ACL 权限矩阵、越权样本与 Threat Model；
- Source/Asset/Task/Playback 正式 OpenAPI、Event Payload 与错误码；
- Flyway DDL、索引、迁移、恢复与容量设计；
- Temporal Workflow/Activity 与 LiteFlow Node/Chain/EL 契约；
- Connector/Worker/Plugin Manifest、能力和安全边界；
- Testcontainers、契约测试和 E2E 测试骨架。

### P2：RC 前

- Dependabot、CodeQL、依赖/容器/许可证扫描；
- SBOM、Cosign、环境保护与发布签署；
- Merge Queue、Runbook、值班、容量和成本看板；
- POC-10 和正式恢复演练。

## 5. 多 Agent 协作的唯一权威入口

```text
需求索引       specs/requirements/requirements-index.yaml
模块所有权     specs/designs/module-ownership.yaml
任务 DAG       specs/coordination/work-package-plan.yaml
活动 Registry  specs/coordination/active-work.yaml
Task 模板      specs/tasks/task-template.md
协调检查       scripts/check-agent-coordination.py
就绪检查       scripts/check-project-readiness.py
统一 CI        .github/workflows/governance-gate.yml
协作协议       docs/25-multi-agent-collaboration-protocol.md
```

不得再建立平行的 `specs/collaboration/**`、第二套 checker 或第二套协作 Workflow。PR #13 已关闭并保留历史。

## 6. 启动与并行规则

### 6.1 每个任务的两阶段启动

```text
Issue + schemaVersion 2 Task Spec + Evidence
→ Reservation PR 写 active-work.yaml
→ Gate + 人工合并预留
→ 从含预留的最新 main 创建实现分支
→ Implementer
→ Handoff
→ Independent Reviewer
→ Integrator
→ Human Merge Approval
```

### 6.2 硬上限

- 活动任务总数最多 3；
- high/critical 同时最多 1；
- high/critical 的 Implementer 与 Reviewer 必须不同；
- 机器契约、Migration、全局配置和模块核心包默认独占；
- 共享路径必须相同 `coordinationGroup` 且 `integrationOrder` 不同；
- 租约过期、依赖环、未知文件或 stale base 均失败关闭。

### 6.3 推荐波次

```text
Wave 0  GZ-014（单独执行）

Wave 1A GZ-004 核心机器契约（high，建议单独执行）
Wave 1B GZ-007 + GZ-009 + GZ-010（三个独立 medium POC，可并行）
Wave 1C GZ-011 + GZ-012（medium，可在路径无冲突时并行）

Wave 2  GZ-005（依赖 GZ-004，high）
Wave 3  GZ-006、GZ-008（均 high，串行）
Wave 4  GZ-013（依赖 GZ-004/GZ-005/GZ-008）
```

当一个 high 任务活动时，即使 Registry 技术上仍允许 medium，也应由 Coordinator 根据单人 Review 容量决定是否保守串行。

## 7. GitHub 平台控制缺口

当前 Ruleset API 返回空列表。CODEOWNERS 和 Actions 只能提供审查路由与红绿状态，不能阻止管理员绕过。

管理员需要为 `main` 创建 Ruleset，至少配置：

1. Require pull request before merging；
2. 至少 1 个批准；high/critical 保留独立 Reviewer 证据；
3. Required status check：`Governance Gate / Governance Checks`；
4. Require conversation resolution；
5. Dismiss stale approvals；
6. Require branch to be up to date；
7. Require review from CODEOWNERS；
8. Block force pushes；
9. Restrict deletions；
10. Include administrators；紧急 bypass 必须留下审计原因。

验证方式：Ruleset API 不再为空，且用故意失败的测试 PR 验证红灯不可合并。完成前状态必须保持 `BLOCKED_EXTERNAL`。

## 8. Definition of Ready

任务只有同时满足以下条件才能进入实现：

- Requirement/Design/ADR 引用明确；
- 必要机器契约已合并或版本固定；
- Task Spec/Registry/Issue/Branch/Base SHA 一致；
- 独占/共享路径已预留；
- 依赖已完成且无环；
- 风险、角色、租约、集成顺序明确；
- Given/When/Then 验收和失败路径可执行；
- Evidence/Handoff 已建立；
- 最新 `main` Governance Gate 为成功；
- 未触碰未完成的阻断性 POC 假设。

## 9. Definition of Done

- 所有修改在声明路径内；
- 真实测试命令、退出码、日志和 Evidence 可复现；
- 契约/文档/代码/测试同步；
- 独立 Reviewer 完成 high/critical 审查；
- Review Thread 全部解决；
- PR 最新 HEAD Gate 成功；
- Integrator 按依赖与顺序合并；
- 合并后 `main` Gate 再次成功；
- Registry 状态完成或释放；
- 回滚路径实际可执行。

## 10. 最终判断

GZ-014 完成且 `main` Gate 成功后，Guize 可以开始**受控的任务预留、机器契约冻结和独立 POC**。在 GZ-004、GZ-005、必要 POC 和 GZ-012 完成前，不应启动大规模业务实现。GitHub Ruleset 未启用前，协作机制只能称为“仓库内可验证、人工治理可用”，不能称为“平台强制不可绕过”。

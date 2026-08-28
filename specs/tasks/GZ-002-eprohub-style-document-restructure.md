---
id: GZ-002
title: Restructure Guize engineering documentation in ePROHub rule-engine style
titleZh: 按 ePROHub 规则引擎格式重构 Guize 研发设计文档
type: docs
status: approved
baseBranch: main
workBranch: docs/GZ-002-engineering-design-baseline-clean
evidencePath: evidence/GZ-002
issue: 6
---

# GZ-002 按 ePROHub 规则引擎格式重构 Guize 研发设计文档

## 背景

Guize V1 已形成需求、架构、数据、接口、连接器、缓存、媒体、AI、搜索、安全、配置、规则、运维、灾备、DevOps、测试、风险、WBS 和 LLD 等专题文档，但同一事实分散在 `docs/00～23`、`docs/appendices`、`docs/guize-complete-solution.md` 与 README 中，研发需要频繁跨文档定位。

本任务仅重构文档信息架构，不改变已经冻结的产品范围、技术决策和机器契约。GZ-001 已通过 clean-recovery 合并进入 `main`，本任务从该治理基线重新建立干净分支，不继承旧 GZ-002 分支的治理历史。

## 目标

1. 建立面向研发开工的一份统一设计总基线；
2. 采用 ePROHub 规则引擎 V2 文档的编号、追踪和章节组织方式；
3. 建立 `需求ID → 模块ID → API ID → 数据模型ID → 事件/工作流ID → 代码项ID → 工作包ID → 验收ID` 追踪链；
4. 用一张端到端总图串起数据源、资产、缓存、媒体、AI、搜索、播放、生命周期与治理；
5. 对尚未实现的类、接口、表和 Worker 明确标注“规划基线”，不伪装为真实代码；
6. README 将新总文档作为研发主入口；
7. 旧专题文档保留为专题来源和历史参考，不删除。

## 允许范围

- `docs/**`
- `README.md`
- `specs/tasks/GZ-002-eprohub-style-document-restructure.md`
- `evidence/GZ-002/**`

## 禁止范围

- `backend/**`
- `frontend/**`
- `plugins/**`
- `guizectl/**`
- `contracts/**`
- `deployment/**`
- `scripts/**`
- `tests/**`
- `.github/**`
- `rules/**`
- `adr/**`

## 文档格式要求

- 中文为主，技术标识保持代码/配置原值；必要英文采用 `English(中文解释)`。
- 大表只用于索引和追踪矩阵；详细说明优先采用分节、列表、代码块和 Mermaid。
- 每个模块说明职责、边界、依赖、主要数据、主要接口、事件/Workflow、状态和验收。
- Java 规划项提供 Java 17 伪代码；Python Worker 规划项提供 Python/FastAPI/Worker 伪代码；不得把伪代码标成已实现。
- HTTP 接口给出请求/响应示例；事件给出 Envelope 示例；数据库先给概念表和关键约束，不虚构尚未冻结的完整 DDL。
- 任何未验证性能、硬件、第三方兼容结论必须保留 POC/待验证标识。

## 验收标准

- [ ] 新增 `docs/00-guize-engineering-design-baseline.md`。
- [ ] 文档包含用途、状态、编号规则、范围、架构、端到端流程。
- [ ] 文档包含物理/逻辑模块索引与依赖方向。
- [ ] 文档包含核心领域模型和概念数据库设计。
- [ ] 文档包含 API、Event、SSE/WebSocket、Plugin、Worker 契约索引及示例。
- [ ] 文档包含 LiteFlow/Temporal 职责和关键 Workflow。
- [ ] 文档包含 Task、Replica、Cache、Policy 等关键状态机。
- [ ] 文档包含 ATS/PostgreSQL/Redis/Temporal/OpenBao/OpenSearch/Milvus/Observability 等中间件职责。
- [ ] 文档包含部署拓扑、Secrets、安全、备份恢复。
- [ ] 文档包含测试分层、验收矩阵、POC 门禁。
- [ ] 文档包含 WBS/工作包及依赖。
- [ ] 文档包含规划代码项和伪代码示例。
- [ ] README 将新总文档列为研发第一入口。
- [ ] 旧专题文档明确为专题/历史参考且未删除。
- [ ] 未修改业务代码、机器契约、部署配置和治理实现。
- [ ] Governance Gate 对 GZ-002 最新 HEAD 成功。

## 必须执行的测试

```bash
python scripts/check-task-file.py --task GZ-002
python scripts/check-task-scope.py --task GZ-002 --base origin/main
python scripts/check-evidence.py --task GZ-002
python scripts/check-markdown.py
python scripts/check-spec-sync.py --base origin/main
python -m pytest tests/governance/ -v
make verify TASK=GZ-002 BASE=origin/main BRANCH=docs/GZ-002-engineering-design-baseline-clean
```

远端必须额外确认 GitHub Actions `Governance Gate` 对最新 HEAD 为 `success`。

## Evidence

规范路径：`evidence/GZ-002/`。本任务直接使用 GZ-001 已冻结的 canonical Evidence Contract，不再使用旧 GZ-002 的单文件兼容结构。

## 风险

- 当前仓库尚无业务实现，因此类、接口、数据库表均只能作为研发规划基线。
- 旧文档中存在 POC 前假设，重构不得把假设升级为事实。
- 一份总文档过长时必须依赖清晰索引和阅读层次，而不是再次拆成大量碎片。

## 回滚

PR 合并前直接关闭 PR 并删除任务分支即可；若已合并，必须从 `main` 创建独立 `fix/GZ-002-...` 回滚分支，通过 Revert PR 恢复 README 并删除新增总文档，不直接推送 `main`，不改写旧专题文档。

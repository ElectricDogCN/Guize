# GZ-002 Evidence

## 任务

按 ePROHub 规则引擎 V2 文档格式重构 Guize 研发文档入口。

## 实际变更

- 新建 Issue #6：GZ-002 文档重构。
- 新建分支：`docs/GZ-002-eprohub-style-restructure`，基于 `chore/GZ-001-repository-baseline`。
- 新建任务规范：`specs/tasks/GZ-002-eprohub-style-document-restructure.md`。
- 新建统一研发设计总文档：`docs/00-guize-engineering-design-baseline.md`。
- 更新 `README.md`，将总文档设为研发第一入口，并将旧专题文档降级为专题/历史参考。
- 未删除 `docs/00～23`、appendices、ADR、contracts 或 deployment 文件。
- 未修改业务代码。

## 来源

本次整理读取并对照了：

- `README.md`
- `MANIFEST.md`
- `docs/02-requirements-and-scope.md`
- `docs/03-system-architecture.md`
- `docs/04-deployment-topology.md`
- `docs/05-domain-and-data-model.md`
- `docs/06-api-and-event-contracts.md`
- `docs/07-source-connectors.md`
- `docs/08-cache-and-storage-lifecycle.md`
- `docs/09-media-av1-and-streaming.md`
- `docs/10-ai-multimodal-pipeline.md`
- `docs/11-search-and-recommendation.md`
- `docs/12-security-identity-and-permissions.md`
- `docs/13-configuration-center.md`
- `docs/14-rules-and-workflows.md`
- `docs/15-observability-and-operations.md`
- `docs/16-backup-and-disaster-recovery.md`
- `docs/17-devops-gitops-and-supply-chain.md`
- `docs/18-testing-and-acceptance.md`
- `docs/19-risk-assumptions-and-poc.md`
- `docs/20-roadmap-and-wbs.md`
- `docs/21-low-level-design.md`
- `docs/22-repository-and-directory-plan.md`
- `docs/23-source-references.md`
- `AGENTS.md`
- `rules/never-rules.md`
- GZ-001 Task Spec 与 ADR 目录
- ePROHub 规则引擎 V2 类级模块拆分文档
- ePROHub 规则引擎 V2 数据库、事件与中间件设计文档

## 格式对齐

采用 ePROHub 风格的：

- 文档编号/状态/基线头；
- 统一中文追踪 ID；
- 端到端线性总图；
- 物理模块与依赖方向；
- 领域模型/数据库/API/Event/Workflow 映射；
- 状态机与幂等；
- 中间件职责；
- 规划 Class/Interface/Worker 与伪代码；
- 工作包/WBS/验收追踪。

## 未验证项

- 未执行 Java/Python/Go 业务测试，因为当前任务不包含业务代码且仓库尚无对应实现。
- 未把概念表转换为正式 PostgreSQL DDL；正式 DDL 应在各实现工作包中冻结。
- 未把 API 索引转换为完整 OpenAPI；机器契约应由后续功能工作包维护。
- A380、ATS、TrueNAS、700TB 元数据、百度云、公网、前端和 AI 仍保持 POC 状态。

## 回滚

关闭 GZ-002 PR 并删除任务分支即可完整回滚；旧专题文档未被删除，因此无需恢复历史设计内容。
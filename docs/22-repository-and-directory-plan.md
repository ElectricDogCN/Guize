# 22. 仓库与目录规划 / Repository and Directory Plan

## 1. GitHub 组织

建议：

```text
guize-platform          核心 Monorepo
guize-media-worker      媒体能力
guize-ai-services       AI 能力集合或模板
guize-model-deployments 大模型部署定义
guize-infrastructure    可选的跨仓库基础设施
guize-docs              如需公开开发者文档
```

初期应尽量减少仓库数量。只有大型依赖、独立发布和硬件边界明确时分仓。

## 2. Monorepo

```text
guize-platform/
├── AGENTS.md
├── README.md
├── backend/
├── frontend/
├── player/
├── plugins/
│   ├── sdk/
│   ├── source-webdav/
│   ├── source-local/
│   └── compatibility-alist-openlist/
├── guizectl/
├── contracts/
│   ├── openapi/
│   ├── events/
│   ├── plugins/
│   └── deployment/
├── deployment/
│   ├── compose/
│   ├── ansible/
│   ├── profiles/
│   └── offline/
├── docs/
├── specs/
├── adr/
├── rules/
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── e2e/
│   ├── performance/
│   ├── security/
│   └── golden/
├── evidence/
└── .github/
```

## 3. 分支

- `main`：可发布；
- 短生命周期任务分支；
- 不建立长期 develop 分支作为集成垃圾场；
- 发布使用 Tag 和不可变制品；
- Hotfix 仍从已发布基线建立。

## 4. Issue

Issue 必须包含：

```text
背景
目标
非目标
规格链接
契约链接
验收标准
风险
测试
证据
回滚
```

## 5. PR

PR 模板要求：

- 关联 Issue；
- 变更类型；
- 范围；
- 契约；
- 迁移；
- 权限；
- 安全；
- 测试；
- 证据；
- 回滚；
- 文档；
- Never Rules。

## 6. Specs

```text
specs/requirements/GUIZE-xxx.md
specs/designs/GUIZE-xxx.md
specs/contracts/GUIZE-xxx/
specs/tasks/GUIZE-xxx.md
```

规格状态：

```text
DRAFT
REVIEWED
APPROVED
IMPLEMENTED
VERIFIED
SUPERSEDED
```

## 7. ADR

格式：

```text
Context
Decision
Alternatives
Consequences
Security
Migration
Validation
Status
```

关键技术、数据所有权、外部协议和生产假设必须 ADR。

## 8. Evidence

证据不应无限提交大文件到 Git。小型结果直接保存，大型产物保存外部位置并在 `summary.md` 记录哈希和引用。

## 9. 版本

- 平台语义化版本；
- API 主版本；
- Event 版本；
- Plugin API 版本；
- Deployment Profile 版本；
- Model/Prompt/Pipeline 独立版本；
- 数据库 Flyway 版本。

## 10. CI 模板

统一：

- Java；
- Python；
- Go；
- Frontend；
- Container；
- Contract；
- Security；
- Release。

独立仓库必须复用可版本化 Workflow，不能复制后长期漂移。

## 11. 代码所有权

即使只有一名人工审查者，也建议 CODEOWNERS 按领域定义，便于未来扩展：

```text
/backend/ @guize/core
/plugins/ @guize/connectors
/deployment/ @guize/ops
/contracts/ @guize/architecture
```

## 12. 文档同步

行为变化对应：

| 变化 | 必须更新 |
|---|---|
| API | OpenAPI、示例、SDK、契约测试 |
| Event | Schema、消费者测试 |
| DB | Flyway、数据模型、恢复 |
| Policy | DSL、测试、说明 |
| Plugin | Manifest、兼容矩阵 |
| Deployment | Profile、Bundle、Runbook |
| Security | 威胁模型、测试、审计 |

# 交付清单 / Delivery Manifest

> 状态：持续维护的逻辑清单
> 更新任务：GZ-003
> 说明：Git 当前提交树是完整文件清单、Blob SHA 和大小的唯一事实来源；本文件只维护稳定结构、权威入口和验证方式。

## 1. 生成与核验

```bash
git ls-files
git ls-tree -r HEAD
```

关键入口验证：

```bash
test -f AGENTS.md
test -f README.md
test -f Makefile
test -f .github/workflows/governance-gate.yml
test -f .github/CODEOWNERS
test -f specs/tasks/task-template.md
test -f specs/coordination/active-work.yaml
test -f specs/requirements/requirements-index.yaml
test -f specs/designs/module-ownership.yaml
test -f scripts/check-agent-coordination.py
test -f scripts/check-project-readiness.py
test -f docs/00-guize-engineering-design-baseline.md
test -f docs/24-requirements-design-readiness-audit.md
test -f docs/25-multi-agent-collaboration-protocol.md
```

## 2. 权威入口

| 路径 | 用途 | 权威层级 |
|---|---|---|
| `specs/requirements/product-requirements.md` | 冻结产品需求 | 已批准需求规格 |
| `contracts/**` | OpenAPI/Event/Schema 等机器契约 | 已批准机器契约 |
| `adr/**` | 长期架构决策 | ADR |
| `docs/00-guize-engineering-design-baseline.md` | 研发设计总基线 | 系统/模块设计 |
| `AGENTS.md` | Agent 强制工程规则 | Agent 治理 |
| `rules/never-rules.md` | 禁止事项 | Agent 治理 |
| `specs/tasks/<TASK-ID>.md` | 当前任务边界 | Task |
| `evidence/<TASK-ID>/` | 执行与验证证据 | Evidence |

发生冲突时严格遵守 `AGENTS.md` 第 3 节，不以 MANIFEST、索引或当前代码覆盖更高优先级来源。

## 3. 根目录结构

```text
Guize/
├── .agent/                  # Agent 临时生成物（不提交任务结果）
├── .github/                 # Issue/PR 模板、CODEOWNERS、Governance Gate
├── .trae/                   # Trae 工具适配规格
├── adr/                     # Architecture Decision Records
├── contracts/               # 业务机器契约
├── deployment/              # 部署 Profile 与示例
├── docs/                    # 产品、架构、审计与协作设计
├── evidence/                # canonical Task Evidence
├── prompts/                 # 执行/审查/交接/集成 Prompt
├── rules/                   # Never Rules 与演进日志
├── scripts/                 # 治理检查器
├── specs/                   # Requirement/Design/Task/Coordination 规格
├── tests/                   # Governance 回归测试
├── AGENTS.md
├── MANIFEST.md
├── Makefile
├── README.md
└── requirements-governance.txt
```

`guize-solution/` 包装目录已退出当前结构；历史迁移记录保留在 Git 历史和 `evidence/GZ-001/`。

## 4. 需求、设计与实施就绪

| 路径 | 内容 |
|---|---|
| `README.md` | 项目总入口和当前阶段 |
| `docs/00～23` | 需求、架构、数据、API、媒体、AI、安全、运维、测试、风险和 WBS 专题来源 |
| `docs/24-requirements-design-readiness-audit.md` | 需求/设计/契约/POC/实现就绪审计 |
| `docs/25-multi-agent-collaboration-protocol.md` | 多 Agent 预留、路径、依赖、交接、审查和集成协议 |
| `specs/requirements/requirements-index.yaml` | 冻结需求别名、设计、模块、验收、缺口和下一任务追踪 |
| `specs/designs/module-ownership.yaml` | 模块路径、Schema、公开契约、依赖和工作包所有权 |
| `specs/coordination/work-package-plan.yaml` | GZ-004～GZ-013 推荐顺序与并行关系 |

这些索引只做追踪，不成为覆盖需求、机器契约或 ADR 的第二权威来源。

## 5. 多 Agent 协作

| 路径 | 内容 |
|---|---|
| `specs/coordination/active-work.yaml` | 已预留活动任务登记 |
| `specs/coordination/active-work.schema.yaml` | 活动登记 Schema |
| `specs/coordination/README.md` | 两阶段 reservation/implementation 协议 |
| `specs/tasks/task-template.md` | schemaVersion 2 Task Spec |
| `prompts/templates/task-execution.md` | Implementer 模板 |
| `prompts/templates/task-review.md` | Reviewer 模板 |
| `prompts/templates/task-handoff.md` | Handoff 模板 |
| `prompts/templates/task-integration.md` | Integrator 模板 |
| `.github/CODEOWNERS` | 审查路由；需 Ruleset 才能强制 |
| `.github/ISSUE_TEMPLATE/agent-task.yml` | Agent Task 表单 |
| `.github/pull_request_template.md` | 协作与集成 PR 模板 |

## 6. 自动化治理

| 路径 | 检查 |
|---|---|
| `scripts/check-task-file.py` | Task Spec、schemaVersion 2、base SHA 和 Handoff |
| `scripts/check-task-scope.py` | Allowed/Forbidden Scope |
| `scripts/check-agent-coordination.py` | 活动任务、租约、路径、依赖和并行上限 |
| `scripts/check-project-readiness.py` | 需求、模块、任务计划和冻结不变量 |
| `scripts/check-evidence.py` | canonical Evidence Contract |
| `scripts/check-evidence-integrity.py` | Evidence 提交存在性/可达性 |
| `scripts/check-pr-task-link.py` | PR/Branch/Task 关联 |
| `scripts/check-spec-sync.py` | 规范同步 |
| `scripts/check-schemas.py` | Workflow 和机器 Schema |
| `scripts/check-markdown.py` | Markdown 与内部链接 |
| `scripts/check-secrets.py` | 高风险 Secret 扫描 |
| `tests/governance/**` | 治理回归测试 |
| `.github/workflows/governance-gate.yml` | 远端 Governance Gate |
| `Makefile` | 本地统一入口 |

统一命令：

```bash
make coordination-check TASK=GZ-XXX
make readiness-check
make task-verify TASK=GZ-XXX BRANCH=<branch> BASE=origin/main
make verify TASK=GZ-XXX BRANCH=<branch> BASE=origin/main
```

## 7. 机器契约与部署状态

| 路径 | 当前状态 |
|---|---|
| `contracts/events/event-envelope.schema.json` | 已有通用 Envelope；具体 Payload 待冻结 |
| `contracts/openapi/openapi-guidelines.md` | 已有规则；完整 OpenAPI 尚未冻结 |
| `contracts/schemas/plugin-manifest.schema.yaml` | 已有基础 Schema |
| `contracts/schemas/deployment-profile.schema.yaml` | 已有基础 Schema |
| `deployment/profiles/**` | 规划/示例；生产结论依赖 POC 和后续实现 |

机器契约是否有效由 Schema/Contract Test 判断，不由自然语言或文件存在本身判断。

## 8. Task 与 Evidence

任务权威目录：`specs/tasks/`。

| Task | 状态 | 结果 |
|---|---|---|
| GZ-001 | 已合并 | Repository Governance/Harness |
| GZ-002 | 已合并 | ePROHub 风格研发设计总基线 |
| GZ-003 | 进行中 | 需求设计审计与多 Agent 协作治理 |

每个 Task 使用 `evidence/<TASK-ID>/` canonical Evidence。测试数量、文件大小和提交 SHA 不在 MANIFEST 中写死，以 Git 和 CI 实际结果为准。

## 9. GitHub 外部设置

当前已验证：`main` 未启用 Branch Protection，Ruleset 为空。CODEOWNERS 和 Governance Gate 不能单独阻止直接推送。管理员仍需启用 PR、Required Check、独立审批、对话解决、禁止 force push/delete、过期批准失效和管理员受约束，并在设置后重新记录 API 证据。

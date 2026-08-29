# 交付清单 / Delivery Manifest

> 状态：持续维护的逻辑清单
> 更新任务：GZ-014
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
test -f specs/coordination/program-plan.yaml
test -f specs/coordination/program-plan.schema.yaml
test -f specs/coordination/active-work.yaml
test -f specs/coordination/active-work.schema.yaml
test -f specs/requirements/requirements-index.yaml
test -f specs/designs/module-ownership.yaml
test -f scripts/check-agent-coordination.py
test -f scripts/check-project-readiness.py
test -f scripts/check-schemas.py
test -f docs/00-guize-engineering-design-baseline.md
test -f docs/24-requirements-design-readiness-audit.md
test -f docs/25-multi-agent-collaboration-protocol.md
test ! -e specs/coordination/work-package-plan.yaml
```

## 2. 权威入口

| 路径 | 用途 | 权威层级 |
|---|---|---|
| `specs/requirements/product-requirements.md` | 冻结产品需求 | 已批准需求规格 |
| `contracts/**` | OpenAPI/Event/Data/Runtime 等机器契约 | 已批准机器契约 |
| `adr/**` | 长期架构决策 | ADR |
| `docs/00-guize-engineering-design-baseline.md` | 研发设计总基线 | 系统/模块设计 |
| `AGENTS.md` | Agent 强制工程规则 | Agent 治理 |
| `rules/never-rules.md` | 禁止事项 | Agent 治理 |
| `specs/coordination/program-plan.yaml` | V1 Task/Wave/DAG/POC/Contract/Release 计划 | 执行计划 |
| `specs/tasks/<TASK-ID>.md` | 当前任务边界 | Task |
| `specs/coordination/active-work.yaml` | 当前活动任务租约 | 活动协调 |
| `evidence/<TASK-ID>/` | 执行与验证证据 | Evidence |

发生冲突时严格遵守 `AGENTS.md` 第 3 节，不以 MANIFEST、索引、Program Plan、Task 或当前代码覆盖更高优先级来源。

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
├── evidence/                # canonical Task/POC Evidence
├── prompts/                 # 执行/审查/交接/集成 Prompt
├── rules/                   # Never Rules 与演进日志
├── scripts/                 # 治理检查器
├── specs/                   # Requirement/Design/Task/Coordination 规格
├── tests/                   # Governance 与后续工程测试
├── AGENTS.md
├── MANIFEST.md
├── Makefile
├── README.md
└── requirements-governance.txt
```

`guize-solution/` 包装目录已退出当前结构；历史迁移记录保留在 Git 历史和 `evidence/GZ-001/`。

## 4. 需求、设计与实施计划

| 路径 | 内容 |
|---|---|
| `README.md` | 项目总入口、当前阶段与多 Agent 开工方式 |
| `docs/00～23` | 需求、架构、数据、API、媒体、AI、安全、运维、测试、风险和 WBS 专题来源 |
| `docs/24-requirements-design-readiness-audit.md` | 需求/设计/契约/POC/实现就绪审计 |
| `docs/25-multi-agent-collaboration-protocol.md` | Program Plan、预留、路径、契约、交接、审查和集成协议 |
| `specs/requirements/requirements-index.yaml` | 冻结需求别名、设计、模块、验收、缺口和下一任务追踪 |
| `specs/designs/module-ownership.yaml` | 21 个模块、Schema、37 个公共 Contract Namespace、owner/consumer/shared writer |
| `specs/coordination/program-plan.yaml` | GZ-004～GZ-020、POC-001～010、W1～W17、DAG、契约生产/消费和发布阻断 |
| `specs/coordination/program-plan.schema.yaml` | Program Plan 机器结构契约 |

旧 `specs/coordination/work-package-plan.yaml` 已删除并由 canonical Program Plan 替代。禁止重新创建第二份后续任务计划。

这些索引和计划只做追踪与执行协调，不成为覆盖需求、机器契约或 ADR 的第二权威来源。

## 5. 多 Agent 协作

| 路径 | 内容 |
|---|---|
| `specs/coordination/active-work.yaml` | 已预留/执行中的活动任务登记 |
| `specs/coordination/active-work.schema.yaml` | 活动登记 Schema |
| `specs/coordination/README.md` | Program Plan→reservation→implementation→review→integration 生命周期 |
| `specs/tasks/task-template.md` | schemaVersion 2 Task Spec 和 Program Plan 对齐字段 |
| `prompts/templates/task-execution.md` | Implementer 模板 |
| `prompts/templates/task-review.md` | Reviewer 模板 |
| `prompts/templates/task-handoff.md` | Handoff 模板 |
| `prompts/templates/task-integration.md` | Integrator 模板 |
| `.github/CODEOWNERS` | 审查路由；需 Ruleset 才能强制 |
| `.github/ISSUE_TEMPLATE/agent-task.yml` | Agent Task 表单 |
| `.github/pull_request_template.md` | 协作与集成 PR 模板 |

默认上限：最多 3 个活动任务、最多 1 个 high/critical；critical 独立执行。公共机器契约必须先由唯一 owner 冻结，consumer Task 只依赖已合并 producer 或冻结版本。

## 6. 自动化治理

| 路径 | 检查 |
|---|---|
| `scripts/check-task-file.py` | Task Spec、schemaVersion 2、base SHA 和 Handoff |
| `scripts/check-task-scope.py` | Allowed/Forbidden Scope |
| `scripts/check-agent-coordination.py` | 活动任务、租约、路径、依赖和并行上限 |
| `scripts/check-project-readiness.py` | Requirement、Module、Contract Namespace、Program Plan、POC、Wave、DAG 与发布 blocker |
| `scripts/check-evidence.py` | canonical Evidence Contract |
| `scripts/check-evidence-integrity.py` | Evidence 提交存在性/可达性 |
| `scripts/check-pr-task-link.py` | PR/Branch/Task 关联 |
| `scripts/check-spec-sync.py` | 规范同步 |
| `scripts/check-schemas.py` | Workflow、业务 Schema、Program Plan 与 Active Work instance |
| `scripts/check-markdown.py` | Markdown 与内部链接 |
| `scripts/check-secrets.py` | 高风险 Secret 扫描 |
| `tests/governance/**` | 治理回归测试 |
| `.github/workflows/governance-gate.yml` | 远端 Governance Gate |
| `Makefile` | 本地统一入口 |

统一命令：

```bash
make coordination-check TASK=GZ-XXX
make readiness-check
python scripts/check-schemas.py
make task-verify TASK=GZ-XXX BRANCH=<branch> BASE=origin/main
make verify TASK=GZ-XXX BRANCH=<branch> BASE=origin/main
```

## 7. 机器契约与部署状态

| 路径 | 当前状态 |
|---|---|
| `contracts/events/event-envelope.schema.json` | 已有通用 Envelope；具体 Payload 待 GZ-006 冻结 |
| `contracts/openapi/openapi-guidelines.md` | 已有规则；完整 OpenAPI 待 GZ-005 冻结 |
| `contracts/schemas/plugin-manifest.schema.yaml` | 已有基础 Schema；运行时边界待 GZ-008 冻结 |
| `contracts/schemas/deployment-profile.schema.yaml` | 已有基础 Schema；工程和恢复验证待后续任务 |
| `contracts/data/**` | 待 GZ-007 建立 DDL/索引/迁移机器契约 |
| `deployment/profiles/**` | 规划/示例；生产结论依赖 POC 和后续实现 |

机器契约是否有效由 Schema/Contract Test 判断，不由自然语言或文件存在本身判断。

## 8. Task、POC 与 Evidence

| Task | 状态 | 结果 |
|---|---|---|
| GZ-001 | completed | Repository Governance/Harness |
| GZ-002 | completed | ePROHub 风格研发设计总基线 |
| GZ-003 | completed | 需求设计审计与多 Agent 协作基线 |
| GZ-014 | in_progress | Program Plan 和协作一致性加固 |

GZ-010 只建立十项 POC 的统一模板和排程；POC-001～POC-010 分别执行 POC-01～POC-10，并使用独立 `evidence/POC-XXX/`。测试数量、文件大小和提交 SHA 不在 MANIFEST 中写死，以 Git 和 CI 实际结果为准。

## 9. GitHub 外部设置

当前已验证：`main` 未启用 Branch Protection，Ruleset 为空。CODEOWNERS 和 Governance Gate 不能单独阻止直接推送。该阻断由 OPS-001（Issue #20）跟踪；在管理员配置 PR、Required Check、独立审批、对话解决、禁止 force push/delete、过期批准失效并通过 API 验证前，不得写成已启用。

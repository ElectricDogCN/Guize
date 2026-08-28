# 交付清单 / Delivery Manifest

> GZ-001 clean recovery 基线。
>
> 本文件描述仓库交付结构和关键入口；**Git 当前提交树是完整文件清单与内容哈希的唯一事实来源**。不再手工冻结每个文件的字节数，避免文件正常演进后 MANIFEST 立即失真。

## 1. 生成与核验规则

完整文件清单：

```bash
git ls-files
```

带对象哈希的完整树：

```bash
git ls-tree -r HEAD
```

验证关键文件存在：

```bash
test -f AGENTS.md
test -f README.md
test -f Makefile
test -f .github/workflows/governance-gate.yml
test -f specs/tasks/task-template.md
test -f scripts/check-task-file.py
test -f scripts/check-task-scope.py
test -f scripts/check-evidence.py
test -f tests/governance/test_repository_boundary.py
test -f docs/guize-complete-solution.md
```

## 2. 根目录交付结构

```text
Guize/
├── .agent/                  # Agent 生成物工作目录（仅保留占位）
├── .github/                 # Issue/PR 模板与 Governance Gate
├── .trae/                   # Trae 工具适配规格
├── adr/                     # Architecture Decision Records
├── contracts/               # Event/OpenAPI/Schema 机器契约
├── deployment/              # 部署 Profile 与示例
├── docs/                    # 产品、架构、LLD 与专题设计文档
├── evidence/                # 可复现任务 Evidence
├── prompts/                 # Agent Prompt 模板与归档
├── rules/                   # Never Rules 与演进日志
├── scripts/                 # 治理检查与 Prompt 生成工具
├── specs/                   # Requirement/Design/Task/Contract 规格
├── tests/                   # Governance 回归测试
├── AGENTS.md                # Agentic/Harness 工程治理权威入口
├── MANIFEST.md              # 本交付结构说明
├── Makefile                 # 统一治理命令入口
├── README.md                # 项目入口
└── requirements-governance.txt
```

`guize-solution/` 包装目录已经退出当前根目录结构；历史迁移记录保留在 Git 历史和 `evidence/GZ-001/` 中。

## 3. GitHub 原生配置

当前关键 GitHub 文件：

- `.github/ISSUE_TEMPLATE/agent-task.yml`
- `.github/ISSUE_TEMPLATE/architecture-decision.yml`
- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/feature.yml`
- `.github/ISSUE_TEMPLATE/poc.yml`
- `.github/ISSUE_TEMPLATE/security.yml`
- `.github/pull_request_template.md`
- `.github/workflows/README.md`
- `.github/workflows/governance-gate.yml`

注意：历史 MANIFEST 中的 `.github/ISSUE_TEMPLATE/feature.md` 已失效，当前真实文件为 `feature.yml`。

## 4. 架构决策

当前 ADR 基线包含：

- `adr/0001-record-architecture-decisions.md`
- `adr/0002-modular-monolith-control-plane.md`
- `adr/0003-temporal-and-liteflow-separation.md`
- `adr/0004-asset-source-version-rendition-replica.md`
- `adr/0005-ats-and-complete-cache-separated.md`
- `adr/0006-secrets-openbao-abstraction.md`
- `adr/0007-opensearch-and-milvus.md`
- `adr/0008-swr-cosign-supply-chain.md`
- `adr/0009-alist-openlist-webdav-only.md`
- `adr/0010-api-machine-identifiers.md`
- `adr/0011-public-admin-password-login.md`
- `adr/0012-adopt-repository-native-agent-task-harness.md`
- `adr/0013-normalize-governance-repository-root.md`

## 5. 机器契约

关键契约：

- `contracts/events/event-envelope.schema.json`
- `contracts/openapi/openapi-guidelines.md`
- `contracts/schemas/deployment-profile.schema.yaml`
- `contracts/schemas/plugin-manifest.schema.yaml`

契约是否有效由 Governance Gate/Schema Check 判断，不由本文件中的静态字节数判断。

## 6. 文档交付

正式专题设计位于 `docs/`。原完整方案合并阅读版的当前真实路径为：

- `docs/guize-complete-solution.md`

历史 MANIFEST 中根目录 `guize-complete-solution.md` 路径已经失效。

主要专题仍包括 `docs/00-executive-summary.md` 至 `docs/23-source-references.md`，以及 `docs/appendices/` 下的验收、组件、配置、决策、部署、术语和状态机附录。

## 7. Governance Harness

### 7.1 脚本

`script/` 不作为路径；当前治理工具统一位于 `scripts/`，包括：

- Task 文件验证；
- Task Scope 验证；
- Evidence 验证与完整性检查；
- PR/Task 关联检查；
- Spec 同步检查；
- Markdown 检查；
- Secret 扫描；
- Pytest skip 审计；
- Agent Prompt 渲染。

完整脚本名以 `git ls-files scripts/` 为准。

### 7.2 测试

治理测试统一位于 `tests/governance/`，覆盖：

- task file；
- allowed/forbidden scope；
- Evidence contract/integrity；
- Markdown；
- Secret scan；
- spec sync；
- PR/task linkage；
- fixture compatibility；
- repository boundary/root layout；
- CI workflow static validation；
- Agent Prompt render。

测试数量不在 MANIFEST 中写死，以 CI 实际收集结果为准。

## 8. Task 与 Evidence

任务权威目录：

```text
specs/tasks/
```

GZ-001 权威任务：

```text
specs/tasks/GZ-001-repository-baseline.md
```

Evidence：

```text
evidence/GZ-001/
```

Evidence 的规范路径及历史兼容映射由 `AGENTS.md` 与 `evidence/GZ-001/EVIDENCE-STRUCTURE.md` 共同约束，并由 `scripts/check-evidence.py` 验证。

## 9. 防漂移原则

MANIFEST 只维护**稳定结构和关键入口**，不再手工维护所有文件的字节数。新增、删除或迁移关键入口时必须同步更新本文件；完整文件清单、Blob SHA 和大小始终从 Git tree 计算。

因此任何审查或打包流程应使用：

```text
MANIFEST.md      → 检查期望结构
Git tree         → 获取实际完整清单/哈希
Governance Gate  → 验证结构、范围、契约与 Evidence
```

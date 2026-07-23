# ADR-0013: Normalize Governance Repository Root / 规范化治理仓库根目录

- Status: Accepted
- Date: 2026-07-23

## Context

当前归泽・Guize 仓库存在一个历史遗留的包装目录 `guize-solution/`，所有治理内容（AGENTS.md、Makefile、scripts/、tests/、.github/ 等）都嵌套在该目录下。这种结构导致以下问题：

1. **GitHub 原生配置无法被识别**：GitHub 仅在仓库根目录查找 `.github/workflows/`、`.github/ISSUE_TEMPLATE/` 和 `pull_request_template.md`，嵌套在子目录中的这些文件不会生效。

2. **Agent 发现困难**：Trae 和其他 Agent 期望在仓库根目录找到 `AGENTS.md` 作为项目规则的入口点，嵌套目录增加了发现和配置的复杂性。

3. **路径混乱**：所有文件路径引用都需要 `guize-solution/` 前缀，CI 工作流需要设置 `working-directory: guize-solution`，导致配置和脚本复杂化。

4. **仓库定位不一致**：本仓库的正式定位是"归泽核心设计、规范、契约、模板、治理和项目生命周期仓库"，不应再嵌套另一个"解决方案"目录。

5. **多仓库架构冲突**：未来 Java、Python、Go 等业务工程将使用独立仓库，当前仓库作为治理仓库应保持简洁的根目录结构，不应与业务工程目录混淆。

## Decision

我们将 `guize-solution/` 目录下的所有内容迁移到 Git 仓库根目录，并删除空的 `guize-solution/` 包装目录。

迁移后的目标结构：

```
/
├── .agent/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── workflows/
│   └── pull_request_template.md
├── .trae/
├── AGENTS.md
├── MANIFEST.md
├── README.md
├── Makefile
├── requirements-governance.txt
├── adr/
├── contracts/
├── deployment/
├── docs/
├── evidence/
├── prompts/
├── rules/
├── scripts/
├── specs/
└── tests/
    └── governance/
```

## Alternatives

1. **保留嵌套结构**：继续使用 `guize-solution/` 作为工作目录，通过 GitHub Actions 的 `working-directory` 设置来规避 GitHub 配置识别问题。缺点是 GitHub Issue/PR 模板仍无法被识别，且路径引用复杂。

2. **创建独立治理仓库**：将治理内容迁移到一个全新的独立仓库。缺点是增加了仓库管理成本，且当前仓库作为治理仓库的定位已经明确。

3. **使用 Git Submodule**：将 `guize-solution/` 作为子模块。缺点是增加了开发复杂度，且不符合当前单仓库治理的设计理念。

## Consequences

### Positive

- GitHub 原生配置（Workflow、Issue 模板、PR 模板）将被正确识别和使用
- Agent 可以直接在仓库根目录发现 `AGENTS.md`
- 所有路径引用简化，不再需要 `guize-solution/` 前缀
- CI 工作流不再需要设置 `working-directory`
- 与未来多仓库架构保持一致，当前仓库专注于治理和规范

### Negative

- 需要更新所有路径引用（Markdown 链接、脚本、测试、配置）
- 需要修复 Workflow 中的路径和触发条件
- 需要更新 Evidence 和文档中的历史路径描述

## Migration Plan

1. 使用 `git mv` 将 `guize-solution/*` 和 `guize-solution/.*` 移动到仓库根目录
2. 删除空的 `guize-solution/` 目录
3. 更新所有文件中的路径引用
4. 修复 GitHub Workflow 配置
5. 更新任务规范和 Evidence
6. 运行完整验证测试

## Rollback

如果迁移导致不可恢复的问题，可以通过以下方式回滚：

1. 如果尚未推送：使用 `git reset --hard <base-commit>` 回退到迁移前的提交
2. 如果已推送但未合并：创建 revert 提交或删除分支
3. 如果已合并：通过 GitHub Revert 操作生成反向 PR

## Old Path Convention (Deprecated)

以下路径约定已废弃，不再使用：

- `guize-solution/AGENTS.md` → `AGENTS.md`
- `guize-solution/Makefile` → `Makefile`
- `guize-solution/.github/` → `.github/`
- `guize-solution/scripts/` → `scripts/`
- `guize-solution/tests/governance/` → `tests/governance/`
- `guize-solution/evidence/` → `evidence/`
- `guize-solution/specs/tasks/` → `specs/tasks/`
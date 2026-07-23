---
id: GZ-001
title: Repository baseline and agent execution harness
titleZh: 仓库基线与 Agent 执行 Harness 初始化
type: chore
status: approved
baseBranch: main
workBranch: chore/GZ-001-repository-baseline
evidencePath: evidence/GZ-001
---

# GZ-001 仓库基线与 Agent 执行 Harness 初始化

## 背景

当前归泽・Guize 仓库是一个以方案文档为主的仓库，缺少可供 Codex、Trae Solo/Work 等 Agent 持续、受控、可验证开发的工程执行基础。本任务将现有文档仓库转化为具备任务规范、动态 Prompt、治理门禁、证据框架和 CI 的正式工程仓库。

## 目标

1. 建立可机器读取的正式任务规范格式；
2. 建立动态 Prompt 模板体系和生成器；
3. 建立治理检查脚本（任务文件、范围、证据、PR 关联、规范同步）；
4. 建立治理脚本单元测试；
5. 建立统一 Makefile 治理入口；
6. 建立基础仓库配置（.editorconfig、.gitattributes、.gitignore）；
7. 建立 GitHub Issue 和 PR 模板；
8. 建立首个治理 CI；
9. 建立 GZ-001 证据目录；
10. 记录新的长期架构决策到 ADR。

## 允许范围

- `AGENTS.md`
- `README.md`
- `MANIFEST.md`
- `.editorconfig`
- `.gitattributes`
- `.gitignore`
- `Makefile`
- `.github/**`
- `.agent/.gitkeep`
- `.trae/specs/GZ-001-repository-baseline/**`
- `prompts/**`
- `scripts/**`
- `specs/tasks/**`
- `specs/schemas/**`
- `tests/**`
- `evidence/GZ-001/**`
- `requirements-governance.txt`
- `rules/**`
- `adr/**`
- `docs/**`
- `contracts/**`
- `deployment/**`

### R3 迁移路径（Git 识别为删除旧路径、新增新路径）

- `guize-solution/**`

只允许对已有方案文档做与治理机制直接相关的最小同步。

### R3 新增允许范围

- `adr/0013-normalize-governance-repository-root.md` — 仓库根目录规范化决策记录
- `tests/governance/test_repository_root_layout.py` — 仓库根结构回归测试
- `evidence/GZ-001/remote-sync-analysis.md` — 远程同步分析
- `evidence/GZ-001/repository-root-migration.md` — 根目录迁移记录
- `evidence/GZ-001/final-report-r3.md` — R3 最终报告
- `evidence/GZ-001/pr-update-commands.md` — PR 更新命令

## 禁止范围

- `backend/**`
- `services/**`
- 前端业务工程
- `tools/guizectl` 业务实现
- 数据库迁移
- 媒体处理代码
- AI 模型代码
- 数据源连接器
- ATS
- Temporal Workflow
- LiteFlow 规则
- OpenSearch
- Milvus
- 生产部署配置
- 真实云账号配置
- 真实 Secret

## 实施要求

1. 所有脚本优先使用 Python 标准库，可在 Windows/Linux 常见 Python 环境运行；
2. 所有脚本必须有清晰帮助、明确退出码、结构化错误；
3. 治理测试必须使用临时目录和 Fixture，不依赖真实仓库状态；
4. 不在 Makefile 中自动下载或执行不受信任的远程脚本；
5. CI 不硬编码真实 Secret，不自动部署，不自动合并 PR；
6. 证据内容必须来自真实执行；
7. 未验证内容必须明确标记；
8. 禁止自动推送、合并或部署；
9. 禁止自动开始 GZ-002。

## 验收标准

- [x] 已建立正式 GZ-001 任务规范；
- [x] 已建立通用动态 Prompt 模板；
- [x] 已建立 `render-agent-prompt.py`；
- [x] 已建立任务文件检查；
- [x] 已建立修改范围检查；
- [x] 已建立 Evidence 检查；
- [x] 已建立 PR 与任务关联检查；
- [x] 已建立规范同步检查；
- [x] 已建立治理脚本测试；
- [x] 已建立统一 Makefile 命令；
- [x] `make agent-prompt TASK=GZ-001` 能生成 Prompt；
- [x] `make task-verify TASK=GZ-001` 可执行；
- [x] `make verify` 可执行；
- [x] GitHub Issue 模板完整；
- [x] PR 模板完整；
- [x] 治理 CI 文件语法有效；
- [x] 没有真实 Secret；
- [x] 没有业务功能越界实现；
- [x] Evidence 内容完整且来自真实执行；
- [x] 新增长期决策已通过 ADR 记录；
- [x] 未验证内容被明确标记；
- [x] 回滚步骤明确；
- [x] 没有自动推送、合并或部署。

### R3 新增验收标准

- [x] 本地与远程提交差异已明确（remote-sync-analysis.md）；
- [x] 仓库根目录规范化完成（`guize-solution/` 已删除）；
- [x] `AGENTS.md` 位于仓库根目录；
- [x] `.github/workflows/governance-gate.yml` 位于仓库根目录；
- [x] Issue 模板和 PR 模板位于仓库根目录；
- [x] CI Workflow 使用正确根路径（无 `working-directory: guize-solution`）；
- [x] CI Checkout 使用 `fetch-depth: 0`；
- [x] Secret 扫描逻辑正确（不使用 `|| true`）；
- [x] 已增加仓库根结构回归测试（`test_repository_root_layout.py`）；
- [x] 所有原有治理测试保留并通过；
- [x] 治理测试全部通过（52 项）；
- [x] 临时 Git 克隆验证通过；
- [x] R3 Evidence 完整；
- [x] PR 更新草稿完整；
- [x] 未执行 Push、Force Push、PR 修改或合并。

## 必须执行的测试

1. `python scripts/check-task-file.py --task GZ-001`
2. `python scripts/check-task-scope.py --task GZ-001 --base main`
3. `python scripts/check-evidence.py --task GZ-001`
4. `python scripts/check-pr-task-link.py --branch chore/GZ-001-repository-baseline`
5. `python scripts/check-spec-sync.py`
6. `python -m pytest tests/governance/ -v`
7. `make agent-prompt TASK=GZ-001`
8. `make task-verify TASK=GZ-001`
9. `make verify`

## 风险

1. 当前仓库尚未有业务代码，部分 CI 步骤（如 Java/Python/Go 构建）只能建立占位；
2. GitHub Actions 在本环境中无法实际运行，需通过语法检查和静态验证确认；
3. 治理脚本在后续真实任务中才能充分验证；
4. 单人审查模式下，治理机制本身也需要被审查。

## 回滚方式

### PR 尚未合并

保留当前分支，不执行破坏性 Reset，使用 Revert 提交撤销具体迁移提交，或删除未推送分支。

```bash
git checkout main
git branch -D chore/GZ-001-repository-baseline
```

### PR 已合并

优先 Revert PR 的合并提交或通过 GitHub Revert 操作生成反向 PR。

```bash
git revert -m 1 <merge-commit-hash>
```

### Hard Reset（仅作为最后手段）

仅在明确确认：
- 分支未推送；
- 无未提交修改；
- 无其他用户提交；

时使用：

```bash
git reset --hard <base-commit>
```

### R3 根目录迁移回滚

若需回滚根目录迁移（恢复 `guize-solution/` 包装目录）：

```bash
git revert <r3-migration-commit-hash>
```

或手动恢复目录结构：

```bash
mkdir guize-solution
mv AGENTS.md MANIFEST.md Makefile requirements-governance.txt guize-solution/
mv .github workflows/ ISSUE_TEMPLATE/ pull_request_template.md guize-solution/.github/
mv adr/ contracts/ deployment/ docs/ evidence/ prompts/ rules/ scripts/ specs/ tests/ guize-solution/
mv .trae/ guize-solution/
```

> **警告**：回滚可能影响路径引用，需同步更新所有相关文件。

## 后续任务边界

- GZ-002：建立 Java、Python、Go 最小工程骨架；
- GZ-003：A380 与 ESXi 直通 POC；
- GZ-004：ATS Range/Slice 缓存 POC；
- GZ-005：TrueNAS 存储和网络 POC；
- GZ-006：WebDAV 大规模目录扫描 POC；
- GZ-007：百度云接入 POC；
- GZ-008：Vue 3 与 React 前端 POC。

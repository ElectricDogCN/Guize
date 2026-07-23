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
- `prompts/**`
- `scripts/**`
- `specs/tasks/**`
- `specs/schemas/**`
- `evidence/GZ-001/**`
- `rules/**`
- `adr/**`
- `docs/17-devops-gitops-and-supply-chain.md`
- `docs/18-testing-and-acceptance.md`
- `docs/20-roadmap-and-wbs.md`
- `docs/22-repository-and-directory-plan.md`

只允许对已有方案文档做与治理机制直接相关的最小同步。

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

- [ ] 已建立正式 GZ-001 任务规范；
- [ ] 已建立通用动态 Prompt 模板；
- [ ] 已建立 `render-agent-prompt.py`；
- [ ] 已建立任务文件检查；
- [ ] 已建立修改范围检查；
- [ ] 已建立 Evidence 检查；
- [ ] 已建立 PR 与任务关联检查；
- [ ] 已建立规范同步检查；
- [ ] 已建立治理脚本测试；
- [ ] 已建立统一 Makefile 命令；
- [ ] `make agent-prompt TASK=GZ-001` 能生成 Prompt；
- [ ] `make task-verify TASK=GZ-001` 可执行；
- [ ] `make verify` 可执行；
- [ ] GitHub Issue 模板完整；
- [ ] PR 模板完整；
- [ ] 治理 CI 文件语法有效；
- [ ] 没有真实 Secret；
- [ ] 没有业务功能越界实现；
- [ ] Evidence 内容完整且来自真实执行；
- [ ] 新增长期决策已通过 ADR 记录；
- [ ] 未验证内容被明确标记；
- [ ] 回滚步骤明确；
- [ ] 没有自动推送、合并或部署。

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

1. 删除新增目录：`prompts/`, `scripts/`, `tests/governance/`, `.agent/`, `evidence/GZ-001/`；
2. 删除新增文件：`Makefile`, `.editorconfig`, `.gitattributes`, `.gitignore`（若之前不存在则删除；若修改过则回退到基础提交）；
3. 删除新增 GitHub 模板和 CI；
4. 删除新增 ADR 和任务规范；
5. 恢复对现有文档的最小同步修改；
6. 切换回 `main` 分支；
7. 不删除用户未提交的修改。

安全回滚命令示例：

```bash
git checkout main
git branch -D chore/GZ-001-repository-baseline
```

或从基础提交恢复：

```bash
git reset --hard <base-commit>
```

## 后续任务边界

- GZ-002：建立 Java、Python、Go 最小工程骨架；
- GZ-003：A380 与 ESXi 直通 POC；
- GZ-004：ATS Range/Slice 缓存 POC；
- GZ-005：TrueNAS 存储和网络 POC；
- GZ-006：WebDAV 大规模目录扫描 POC；
- GZ-007：百度云接入 POC；
- GZ-008：Vue 3 与 React 前端 POC。

---
schemaVersion: 2
id: GUIZE-000
title: Replace with concise English task title
titleZh: 替换为简洁中文任务标题
type: feat
status: draft
baseBranch: main
baseSha: REPLACE_WITH_40_CHARACTER_MAIN_COMMIT_SHA
workBranch: feat/GUIZE-000-short-name
evidencePath: evidence/GUIZE-000
issue: 0
workPackage: WP-MX-00
taskOwner: REPLACE_WITH_GITHUB_OWNER
agentRole: implementer
riskLevel: medium
coordinationMode: registry
coordinationGroup: REPLACE_WITH_GROUP
dependsOn: NONE
handoffPath: evidence/GUIZE-000/handoff.md
integrationStrategy: merge
---

# GUIZE-000 任务规格

> 替换所有占位值。GZ-003 之后的新任务必须使用 schemaVersion 2，并在实现前通过 reservation PR 写入 `specs/coordination/active-work.yaml`。任务 ID 必须符合 `<大写前缀>-<数字>`。

## 背景

说明问题现状、触发原因和必要上下文。

## 目标

明确本任务需要实现或验证的结果。

## 非目标

明确本任务不处理的相邻问题，防止 Agent 自动扩展范围。

## 关联

- Requirement：
- Design：
- ADR：
- OpenAPI/Event/Data Schema：
- Issue：
- Never Rules：
- Module Ownership：`specs/designs/module-ownership.yaml`
- Active Work：`specs/coordination/active-work.yaml`

## 允许范围

- `path/to/allowed/**`

## 禁止范围

- `path/to/forbidden/**`
- 其他无法仅通过路径表达的禁止事项，请在此以文字补充；路径型禁止项必须使用代码标记。

## 输入与输出

### 输入

- 待补充。

### 输出

- 待补充。

## 依赖与集成顺序

- 列出 `dependsOn` 的合并状态、共同机器契约和 `integrationOrder`；无依赖时写明“无”。

## 独占写范围

- `path/owned/by/this/task/**`

## 共享修改范围

- 无；若存在，必须与其他任务使用相同 `coordinationGroup`，并指定不同 `integrationOrder`。

## 协作与交接

- Coordinator：
- Implementer：
- Reviewer：
- Integrator：
- 基线 SHA：
- 租约到期：
- Handoff：`evidence/GUIZE-000/handoff.md`
- 下一角色需要执行的动作：

## 验收标准

- [ ] Given / When / Then 的核心成功路径可验证。
- [ ] 关键失败路径可验证。
- [ ] 权限、安全、幂等或并发约束按适用范围验证。
- [ ] Task Spec、活动登记、分支、base SHA 和 handoff 一致。
- [ ] 依赖已合并或已冻结为可版本化机器契约。
- [ ] 相关文档、契约和 Evidence 同步完成。

## 必须执行的测试

```bash
python scripts/check-task-file.py --task GUIZE-000
python scripts/check-agent-coordination.py --task GUIZE-000
python scripts/check-project-readiness.py
make task-verify TASK=GUIZE-000 BRANCH=feat/GUIZE-000-short-name BASE=origin/main
```

## Evidence

规范路径：`evidence/GUIZE-000/`

```text
summary.md
commands.txt
test-results/
screenshots/
api-samples/
migration-report/
performance/
security/
rollback-verification/
handoff.md
```

不适用项必须显式说明原因；不得用空目录、计划命令或 Agent 说明冒充执行结果。

## 风险

- 待补充；必须与 `riskLevel` 一致。

## 回滚

说明可执行的回滚步骤、触发条件和回滚后验证方式。合并后回滚必须通过独立分支和 Revert PR。

## 未解决问题

- 无，或列出仍需决策的问题、负责人和阻断状态。

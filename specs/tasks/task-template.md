---
schemaVersion: 2
id: GUIZE-000
title: Replace with concise English task title
titleZh: 替换为简洁中文任务标题
type: feat
status: reserved
baseBranch: main
baseSha: REPLACE_WITH_40_CHARACTER_MAIN_COMMIT_SHA
workBranch: feat/GUIZE-000-short-name
evidencePath: evidence/GUIZE-000
issue: 0
workPackage: WP-MX-00
programPlan: specs/coordination/program-plan.yaml
programTaskId: GUIZE-000
wave: W0
requirementIds: REQ-V1-0000
moduleIds: MOD-REPLACE
producesContracts: NONE
consumesContracts: NONE
exitGate: REPLACE_WITH_EXACT_PROGRAM_PLAN_EXIT_GATE
taskOwner: REPLACE_WITH_GITHUB_OWNER
coordinator: REPLACE_WITH_COORDINATOR
implementer: REPLACE_WITH_IMPLEMENTER_AGENT
reviewer: REPLACE_WITH_REVIEWER_AGENT
integrator: REPLACE_WITH_INTEGRATOR
agentRole: coordinator
riskLevel: medium
coordinationMode: registry
coordinationGroup: REPLACE_WITH_GROUP
dependsOn: NONE
handoffPath: evidence/GUIZE-000/handoff.md
integrationStrategy: merge
integrationOrder: 1
leaseExpiresAt: 2026-09-01T00:00:00Z
---

# GUIZE-000 任务规格

> 替换所有占位值。GZ-014 之后，非治理修复任务必须先存在于 `specs/coordination/program-plan.yaml`，并且依赖、波次、风险、Requirement、Module、输出路径、契约关系和 `exitGate` 完全一致；实现前再通过 reservation PR 写入 `specs/coordination/active-work.yaml`。任务 ID 必须符合 `<大写前缀>-<数字>`。

## 背景

说明问题现状、触发原因和必要上下文。

## 目标

明确本任务需要实现或验证的结果。

## 非目标

明确本任务不处理的相邻问题，防止 Agent 自动扩展范围。

## 关联

- Program Plan：`specs/coordination/program-plan.yaml` 中的任务 ID、Wave、`integrationOrder` 与 `exitGate`
- Requirement：
- Design：
- ADR：
- OpenAPI/Event/Data/Runtime Contract：
- Produced Contract Namespace：
- Consumed Contract Namespace：
- Issue：
- Never Rules：
- Module Ownership：`specs/designs/module-ownership.yaml`
- Active Work：`specs/coordination/active-work.yaml`
- Completion Ledger：`specs/coordination/task-completions.yaml`

## 允许范围

- `path/to/allowed/**`

## 禁止范围

- `path/to/forbidden/**`
- 其他无法仅通过路径表达的禁止事项，请在此以文字补充；路径型禁止项必须使用代码标记。

## 输入与输出

### 输入

- 已合并依赖 Task/机器契约及精确版本。

### 输出

- Program Plan 中声明的 `outputPaths`、机器契约、代码、文档和 Evidence。

## 依赖与集成顺序

- 列出 Program Plan `dependsOn` 的合并状态、共同机器契约、Wave 和 `integrationOrder`；无依赖时写明“无”。
- consumer Task 不得依赖未合并 producer 的分支；必须依赖已合并提交或冻结机器契约。

## 独占写范围

- `path/owned/by/this/task/**`

## 共享修改范围

- 无。

若确有共享路径，删除上面的“无”，逐项列出代码标记路径；所有相关任务必须使用相同 `coordinationGroup`、显式 shared 声明和不同 `integrationOrder`。

## 协作与交接

- Coordinator：
- Implementer：
- Reviewer：
- Integrator：
- Program Wave：
- Program Exit Gate：必须与 front matter `exitGate` 和 Program Plan 完全一致
- 基线 SHA：
- 租约到期：
- Handoff：`evidence/GUIZE-000/handoff.md`
- 下一角色需要执行的动作：

## 验收标准

- [ ] Given / When / Then 的核心成功路径可验证。
- [ ] 关键失败路径可验证。
- [ ] 权限、安全、幂等或并发约束按适用范围验证。
- [ ] Program Plan、Task Spec、活动登记、分支、base SHA、角色、exit gate 和 handoff 一致。
- [ ] 实际修改文件全部落在 Registry 独占/共享路径或本任务治理元数据例外内。
- [ ] Requirement/Module/Contract producer-consumer 与 Program Plan 一致。
- [ ] 依赖已完成，或已冻结为 Program Plan 明确允许的可版本化机器契约。
- [ ] 相关文档、契约和 Evidence 同步完成。
- [ ] 完成后由独立 completion PR 写入 `task-completions.yaml`，保留 Reservation、Merge、Task Spec、Evidence 与 Handoff 记录。

## 必须执行的测试

```bash
python scripts/check-task-file.py --task GUIZE-000
python scripts/check-agent-coordination.py --task GUIZE-000 --base-ref origin/main --head-ref HEAD --branch-name feat/GUIZE-000-short-name
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python scripts/check-program-plan-integrity.py
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

- 待补充；必须与 Program Plan 和 `riskLevel` 一致。

## 回滚

说明可执行的回滚步骤、触发条件和回滚后验证方式。合并后回滚必须通过独立分支和 Revert PR。

## 未解决问题

- 无，或列出仍需决策的问题、负责人和阻断状态。

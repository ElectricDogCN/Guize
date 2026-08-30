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

> 替换所有占位值。非治理修复任务必须先存在于 `specs/coordination/program-plan.yaml`，并且依赖、波次、风险、Requirement、Module、输出路径、契约关系和 `exitGate` 完全一致；实现前再通过纯 Reservation PR 写入 `specs/coordination/active-work.yaml`。

## 背景

说明问题现状、触发原因和必要上下文。

## 目标

明确本任务需要实现或验证的结果。

## 非目标

明确本任务不处理的相邻问题，防止 Agent 自动扩展范围。

## 关联

- Program Plan：`specs/coordination/program-plan.yaml`
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
- 其他无法仅通过路径表达的禁止事项，请在此以文字补充。

## 输入与输出

### 输入

- 已合并依赖 Task/机器契约及精确版本。

### 输出

- Program Plan 中声明的 `outputPaths`、机器契约、代码、文档和 Evidence。

## 依赖与集成顺序

- 列出 Program Plan `dependsOn` 的完成状态、共同机器契约、Wave 和 `integrationOrder`；
- consumer Task 不得依赖未合并 producer 的分支；
- 依赖完成记录必须已存在于目标分支，并包含在本任务 Reservation `baseSha` 中；
- 当前 Wave 只有在所有更早 Wave 的任务均为 `completed` 或 `cancelled` 后才可激活；同一 Wave 可在容量和路径约束内并行。

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
- Program Exit Gate：必须与 front matter 和 Program Plan 完全一致
- 基线 SHA：
- 租约到期：
- Handoff：`evidence/GUIZE-000/handoff.md`
- 下一角色需要执行的动作：

## 验收标准

- [ ] Given / When / Then 的核心成功路径可验证。
- [ ] 关键失败路径可验证。
- [ ] 权限、安全、幂等或并发约束按适用范围验证。
- [ ] Program Plan、Task Spec、活动登记、分支、base SHA、角色、exit gate 和 handoff 一致。
- [ ] Active Work 的 Requirement、Module、Contract、`exclusivePaths`、`sharedPaths` 与 Program Plan 完全一致。
- [ ] 实际修改文件全部落在 Registry 独占/共享路径或经过窄范围验证的 Completion 元数据例外内。
- [ ] Requirement/Module/Contract producer-consumer 与 Program Plan 一致。
- [ ] 依赖已完成，且其 merge commit 已进入 Reservation 基线。
- [ ] 当前 Wave 已开放，未跳过尚未完成的更早 Wave。
- [ ] 相关文档、契约和 Evidence 同步完成。
- [ ] 完成后由独立 Completion PR 写入永久完成记录并释放自己的 Lease。

## 必须执行的测试

```bash
python scripts/check-task-file.py --task GUIZE-000
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python scripts/check-program-plan-integrity.py --base-ref origin/main
python scripts/check-program-plan-history.py --base-ref origin/main --head-ref HEAD --task GUIZE-000 --branch-name feat/GUIZE-000-short-name
python scripts/check-program-plan-transitions.py --base-ref origin/main --head-ref HEAD --task GUIZE-000 --branch-name feat/GUIZE-000-short-name
python scripts/check-program-plan-finalization.py --base-ref origin/main --head-ref HEAD --task GUIZE-000
python scripts/run-agent-coordination-gate.py --task GUIZE-000 --base-ref origin/main --head-ref HEAD --branch-name feat/GUIZE-000-short-name
python scripts/run-task-scope-gate.py --task GUIZE-000 --base origin/main
make task-verify TASK=GUIZE-000 BRANCH=feat/GUIZE-000-short-name BASE=origin/main HEAD_REF=HEAD
```

## Evidence

规范路径：`evidence/GUIZE-000/`

```text
summary.md
commands.txt
test-results/README.md
screenshots/
api-samples/
migration-report/
performance/
security/
rollback-verification/
handoff.md
```

不适用项必须显式说明原因；不得用空目录、计划命令或 Agent 说明冒充执行结果。

## Reservation PR 约束

Reservation PR 只能：

1. 将当前普通 Program Task 从 `planned`/`blocked` 转为 `reserved`；
2. 在 Active Work 中新增当前任务唯一的 `reserved` Lease；
3. 创建或更新当前 Task Spec；
4. 创建或更新 `evidence/<TASK-ID>/**`。

Reservation PR 不得包含业务/实现文件，不得修改其他 Program Task、Registry policy、其他 Lease 或无关治理文件。记录到 Completion Ledger 的 `reservationCommit` 必须通过其第一父提交 Diff 重新证明上述约束。

Reservation 之后的活动状态转换只能修改当前任务的合法状态字段和自己的 Lease 状态/角色/基线/到期时间，不得重写稳定的 Program/Registry 身份、范围或其他任务。

## Completion PR 约束

Implementation PR 合入目标分支且其 post-merge Gate 成功后，才能从最新目标分支创建同一 Task ID 的 Completion PR。Completion PR 只能：

1. 将当前普通 Program Task 的状态改为 `completed`，或更新当前 Foundation 的完成身份；
2. 删除当前任务自己的 Active Work Lease，不能修改 policy 或其他任务；
3. 普通任务只追加一条不可变、任务绑定的 Completion Ledger 记录；Foundation 不修改普通 Ledger；
4. 更新当前 Task Spec 的 `status`、Completion 分支和基线，同时保持 Program 身份、依赖、Requirement、Module、Contract 和 `exitGate` 不变；
5. 更新 `evidence/<TASK-ID>/**`。

Completion PR 必须刷新并实际修改以下文件：

```text
evidence/<TASK-ID>/handoff.md
evidence/<TASK-ID>/summary.md
evidence/<TASK-ID>/commands.txt
evidence/<TASK-ID>/test-results/README.md
```

四个文件都必须：

- 明确记录 Task ID；
- 记录完整的 Implementation merge SHA；
- 说明 Completion 验证和结果；
- 不复用 Reservation 阶段的旧结论。

记录的 Implementation merge 必须已经是 Completion PR 目标分支的祖先；不能引用 Completion 分支上尚未合并的提交。GitHub Ruleset 外部 blocker 只有经过实时 API 校验、根据 live default branch 正确解析 `~DEFAULT_BRANCH`、没有排除 `main`，并满足最新目标分支检查与最新推送独立批准时才能标记 resolved。

## 风险

- 待补充；必须与 Program Plan 和 `riskLevel` 一致。

## 回滚

说明可执行的回滚步骤、触发条件和回滚后验证方式。合并后回滚必须通过独立分支和 Revert PR。

## 未解决问题

- 无，或列出仍需决策的问题、负责人和阻断状态。
---
id: GUIZE-000
title: Replace with concise English task title
titleZh: 替换为简洁中文任务标题
type: feat
status: draft
baseBranch: main
workBranch: feat/GUIZE-000-short-name
evidencePath: evidence/GUIZE-000
---

# GUIZE-000 任务规格

> 使用时先将 `GUIZE-000`、标题、任务类型、分支名和 Evidence 路径替换为真实值。任务 ID 必须符合 `<大写前缀>-<数字>`。

## 背景

说明问题现状、触发原因和必要上下文。

## 目标

明确本任务需要实现或验证的结果。

## 关联

- Requirement：
- Design：
- ADR：
- OpenAPI/Event：
- Issue：
- Never Rules：

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

## 验收标准

- [ ] Given / When / Then 的核心成功路径可验证。
- [ ] 关键失败路径可验证。
- [ ] 权限、安全、幂等或并发约束按适用范围验证。
- [ ] 相关文档、契约和 Evidence 同步完成。

## 必须执行的测试

```bash
# 替换为本任务真实、可复现的验证命令。
make task-verify TASK=GUIZE-000
```

## Evidence

规范路径：`evidence/GUIZE-000/`

优先遵循 `AGENTS.md` 的规范 Evidence Contract：

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
```

不适用项必须显式说明原因；历史兼容命名必须通过 `EVIDENCE-STRUCTURE.md` 映射，不得静默替代。

## 风险

- 待补充。

## 回滚

说明可执行的回滚步骤、触发条件和回滚后验证方式。

## 未解决问题

- 无，或列出仍需决策的问题。

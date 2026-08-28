# Agent 任务交接 — {{TASK_ID}}

## 身份与基线

- Task：{{TASK_ID}} — {{TASK_TITLE}}
- Issue：{{ISSUE_REFERENCE}}
- Branch：{{BRANCH_NAME}}
- Base：{{BASE_BRANCH}} / {{BASE_SHA}}
- Work Package：{{WORK_PACKAGE}}
- Risk：{{RISK_LEVEL}}
- Coordination Group：{{COORDINATION_GROUP}}
- Depends On：{{DEPENDS_ON}}
- Integration Strategy：{{INTEGRATION_STRATEGY}}

## 角色

- Coordinator：
- Implementer：
- Reviewer：
- Integrator：
- 当前交出角色：
- 下一接收角色：

## 实际提交

| Commit SHA | 目的 | 是否已推送 |
|---|---|---|
| 待填写 | 待填写 | 否 |

## 实际修改

- Changed files：
- 机器契约/Schema 版本：
- 数据迁移：
- 配置影响：
- 安全影响：

## 验证证据

| 命令 | 退出码 | 结果 | Evidence |
|---|---:|---|---|
| 待填写 | - | 未执行 | {{EVIDENCE_PATH}} |

禁止填写预期结果；只记录已经执行的命令和观测值。

## 协作范围

### 独占路径

{{EXCLUSIVE_SCOPE}}

### 共享路径与集成顺序

{{SHARED_SCOPE}}

### 依赖与顺序

{{DEPENDENCIES_AND_ORDER}}

## 已知问题

- 失败：
- 限制：
- 未解决决策：
- 过期或待续租：

## 回滚与恢复

- 回滚命令：
- 恢复验证：
- 不得直接推送 `main`。

## 下一角色的精确动作

1. 获取最新分支和 `main`；
2. 运行 Task/Coordination/Readiness 检查；
3. 核对提交、Evidence 和 Review Thread；
4. 完成此处列出的具体工作；
5. 更新本 handoff，而不是依赖聊天记忆。

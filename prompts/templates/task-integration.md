# Agent 集成检查 — {{TASK_ID}}

## 上下文

- Task：{{TASK_ID}} — {{TASK_TITLE}}
- Issue：{{ISSUE_REFERENCE}}
- Branch：{{BRANCH_NAME}}
- Base：{{BASE_BRANCH}} / {{BASE_SHA}}
- Risk：{{RISK_LEVEL}}
- Depends On：{{DEPENDS_ON}}
- Handoff：{{HANDOFF_PATH}}
- Integration Strategy：{{INTEGRATION_STRATEGY}}

## 集成前硬门禁

- [ ] `{{TASK_FILE}}` 与活动登记、分支、base SHA 一致；
- [ ] 所有 `dependsOn` 已进入目标基线；
- [ ] 最新 HEAD 的 Required Check 全部成功；
- [ ] Review Thread 全部解决；
- [ ] high/critical 具有独立 Reviewer 和人工批准；
- [ ] Scope、Module Ownership、Contract、Evidence 均通过；
- [ ] Shared 路径按照 `integrationOrder` 处理；
- [ ] 活动任务登记将在本次集成中完成或释放；
- [ ] 回滚和合并后验证可执行。

## 必须执行

```bash
python scripts/check-task-file.py --task {{TASK_ID}}
python scripts/check-agent-coordination.py --task {{TASK_ID}}
python scripts/check-project-readiness.py
make verify TASK={{TASK_ID}} BRANCH={{BRANCH_NAME}} BASE=origin/{{BASE_BRANCH}}
```

## 冲突处理

- 文本冲突且无行为影响：可按已批准设计解决并记录；
- API、DDL、事件、状态机、安全或业务行为冲突：停止集成，退回 Implementer/Coordinator；
- 不允许在合并过程中创造未经审查的新行为；
- 不允许 force push 隐藏已审查提交。

## 输出

- 依赖状态：
- 最新 HEAD / Gate：
- Review 状态：
- Shared path 集成顺序：
- Registry 释放方式：
- 合并方式：
- 合并后验证：
- 建议：`READY_FOR_HUMAN_MERGE` / `BLOCKED` / `NEEDS_CHANGES`

本模板不授权 Agent 自动合并 `main`、生产部署或高风险操作。

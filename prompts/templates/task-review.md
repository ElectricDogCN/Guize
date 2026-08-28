# Agent 审查任务 — {{TASK_ID}}

## 任务上下文

- **任务 ID**：{{TASK_ID}}
- **任务规范**：{{TASK_FILE}}
- **Issue**：{{ISSUE_REFERENCE}}
- **工作包**：{{WORK_PACKAGE}}
- **审查角色**：{{AGENT_ROLE}}
- **风险等级**：{{RISK_LEVEL}}
- **工作分支**：{{BRANCH_NAME}}
- **基础分支/SHA**：{{BASE_BRANCH}} / {{BASE_SHA}}
- **协调模式/组**：{{COORDINATION_MODE}} / {{COORDINATION_GROUP}}
- **依赖**：{{DEPENDS_ON}}
- **Handoff**：{{HANDOFF_PATH}}
- **集成方式**：{{INTEGRATION_STRATEGY}}

## 默认权限

本任务是审查任务，默认只检查和报告，不修改文件。只有 Task Spec 明确授权且修改无行为影响时，才允许修复拼写、格式或链接；所有修复必须重新运行 Gate 并记录。

high/critical 任务必须确认 Reviewer 与唯一 Implementer 不是同一 Agent。无法证明角色分离时，结论只能是 `NEEDS_REVIEW`。

## 审查顺序

1. 按 `AGENTS.md` 权威顺序读取批准需求、机器契约、ADR、系统/模块设计、Task Spec；
2. 运行：

```bash
python scripts/check-task-file.py --task {{TASK_ID}}
python scripts/check-agent-coordination.py --task {{TASK_ID}}
python scripts/check-project-readiness.py
```

3. 对比 `{{BRANCH_NAME}}` 与最新 `{{BASE_BRANCH}}`，检查 `{{BASE_SHA}}` 是否过期；
4. 检查活动登记、独占/共享路径、模块所有权、依赖和 `integrationOrder`；
5. 检查代码、配置、OpenAPI/Event/DDL/Workflow 与 Task 目标一致；
6. 检查成功、失败、安全、权限、并发、幂等、迁移和恢复路径；
7. 核对命令、退出码、测试报告、提交 SHA、Evidence 和 `{{HANDOFF_PATH}}`；
8. 检查文档、示例、回滚和未解决项；
9. 检查 PR 是否释放或完成活动任务登记。

## 协作审查重点

### 依赖与顺序

{{DEPENDENCIES_AND_ORDER}}

### 独占写范围

{{EXCLUSIVE_SCOPE}}

### 共享修改范围

{{SHARED_SCOPE}}

审查者不得接受以下情况：

- 依赖仅存在于聊天或其他 Agent 未合并分支；
- 两个活动任务修改同一独占路径；
- Shared 路径无相同协调组或无明确集成顺序；
- Task Spec、Registry、Branch、base SHA、handoff 不一致；
- 为通过 CI 删除测试、改低阈值或改写冻结需求；
- 用 Agent 说明替代真实执行证据。

## 输出格式

### Blockers

按严重度列出文件/行、违反的需求/契约/规则、影响和可验证修复条件。

### Warnings

列出非阻塞风险、技术债和后续任务。

### Verified

列出实际检查并通过的范围、命令和证据。

### Integration Recommendation

只能是：

- `READY_FOR_INTEGRATION`
- `NEEDS_CHANGES`
- `BLOCKED_BY_DEPENDENCY`
- `NEEDS_HUMAN_DECISION`

不得自行合并、部署或声称生产可用。

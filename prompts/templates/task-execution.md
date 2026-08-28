# Agent 执行任务 — {{TASK_ID}}

## 任务上下文

- **任务 ID**：{{TASK_ID}}
- **任务标题**：{{TASK_TITLE}}
- **任务规范**：{{TASK_FILE}}
- **关联 Issue**：{{ISSUE_REFERENCE}}
- **工作包**：{{WORK_PACKAGE}}
- **任务所有者**：{{TASK_OWNER}}
- **Agent 角色**：{{AGENT_ROLE}}
- **风险等级**：{{RISK_LEVEL}}
- **工作分支**：{{BRANCH_NAME}}
- **基础分支**：{{BASE_BRANCH}}
- **基础提交**：{{BASE_SHA}}
- **协调模式/组**：{{COORDINATION_MODE}} / {{COORDINATION_GROUP}}
- **依赖任务**：{{DEPENDS_ON}}
- **Handoff**：{{HANDOFF_PATH}}
- **集成方式**：{{INTEGRATION_STRATEGY}}
- **执行模式**：{{EXECUTION_MODE}}

## 执行前必读

1. 阅读 `AGENTS.md`、`rules/never-rules.md` 和 `docs/25-multi-agent-collaboration-protocol.md`。
2. 阅读 `{{TASK_FILE}}`，确认目标、非目标、允许/禁止范围、验收、风险和回滚。
3. 阅读 `specs/coordination/active-work.yaml` 与 `specs/designs/module-ownership.yaml`。
4. 执行：

```bash
python scripts/check-task-file.py --task {{TASK_ID}}
python scripts/check-agent-coordination.py --task {{TASK_ID}}
python scripts/check-project-readiness.py
```

5. 确认当前分支是 `{{BRANCH_NAME}}`，基线与 `{{BASE_SHA}}` 一致，且工作区无未知修改。
6. `coordinationMode=registry` 时，必须确认活动登记唯一、租约未过期、路径无冲突。禁止先开发后补登记。

## 协作边界

### 依赖与集成顺序

{{DEPENDENCIES_AND_ORDER}}

### 独占写范围

{{EXCLUSIVE_SCOPE}}

### 共享修改范围

{{SHARED_SCOPE}}

### Handoff 规则

{{HANDOFF_RULES}}

- 不读取或复制其他 Agent 未提交的本地状态；
- 不修改其他活动任务的独占路径；
- 共同机器契约未合并前，不实现其消费者的猜测版本；
- 发现范围、契约、依赖或所有权冲突时，停止并交回 Coordinator；
- high/critical 任务不得自行充当唯一 Reviewer。

## 实施原则

### 规格与契约先行

- 按权威顺序解析需求、机器契约、ADR 和设计；
- API、Event、DDL、Workflow、Plugin 或 Worker 行为变化先更新机器契约；
- 架构长期变化先建立 ADR；
- 不把规划类、表或接口伪装为已实现。

### 最小变更

- 只修改任务允许且已登记的路径；
- 提交保持单一目的和可审查顺序；
- 不自动开始相邻工作包；
- 不通过扩大 Shared/Common 模块规避所有权。

### 测试与证据

- 先补契约测试、单元测试和关键失败路径，再完成行为；
- 执行任务中的全部命令，记录真实退出码和提交 SHA；
- 失败结果保留，不删除测试、放宽断言或跳过门禁；
- 更新 `{{HANDOFF_PATH}}`，记录提交、文件、契约、测试、限制、共享路径和下一角色动作。

## 完成前检查

```text
需求/契约一致
Task/Registry/Branch/Base SHA 一致
依赖已合并
范围与模块所有权无冲突
成功/失败/安全/并发路径已验证
Evidence 可复现
Handoff 完整
最新 main 已同步
回滚可执行
```

只有全部满足时标记 `NEEDS_REVIEW`，而不是自行标记已合并或已发布。否则状态必须是 `PARTIAL` 或 `BLOCKED`。

# Guize 多 Agent 协作契约

## 1. 目的

本目录把“多个 Agent 一起开发”从口头约定变为可检查的工程契约。它不替代 `AGENTS.md`、Never Rules、Task Spec、机器契约或 GitHub Review，而是补充以下信息：

- 谁是任务唯一写入 Owner；
- 谁执行独立 Review；
- 任务从哪个不可变 Git SHA 开始；
- 依赖哪些已合并任务和机器契约；
- 哪些路径由本任务独占；
- 哪些路径属于共享集成面；
- 按什么顺序进入集成；
- 交给下一 Agent 的证据在哪里。

## 2. 权威顺序

发生冲突时仍严格遵守根目录 `AGENTS.md`：

```text
已批准需求
→ 已批准 API / Event / Data Schema
→ ADR
→ 系统和模块设计
→ AGENTS.md
→ Never Rules
→ 当前 Task Spec
→ 代码现状
→ Agent 推断
```

Coordination Descriptor 属于当前 Task 的协调元数据，不能覆盖需求、机器契约、ADR 或系统设计。

## 3. 文件布局

```text
specs/collaboration/
├── README.md
├── task-coordination.schema.yaml
├── project-readiness.yaml
├── program-plan.yaml
└── tasks/
    └── <TASK-ID>.yaml
```

每个并行任务只维护自己的 `tasks/<TASK-ID>.yaml`。禁止让多个 Agent 高频修改一个“当前锁表”；Program Plan 仅由编排/集成任务更新。

## 4. Coordination Mode

### single-agent

适用于范围很小、无共享机器契约、无并行路径冲突的任务。仍需要独立人工或 Agent Review，但可以省略复杂工作流分解。

### multi-agent

以下任一条件成立时必须使用：

- 一个里程碑由多个 Task 并行交付；
- 修改 API、Event、DDL、Workflow、Policy、Plugin 或 Deployment Contract；
- 多个 Agent 分别承担实现、测试、安全或集成；
- 任务触及共享文件或跨模块边界；
- 结果需要交给另一 Agent 继续实现。

## 5. 单写者规则

1. 一个 Task 只有一个 Owner Role；
2. `paths.exclusive` 中的路径在任务活动期间只能由该 Task 修改；
3. Owner 可以调度子 Agent 做只读分析或生成候选补丁，但最终写入必须由 Owner 汇总；
4. Reviewer 不得直接替 Owner 扩大范围；发现问题应通过 Review 或独立 Fix Task 处理；
5. 同一执行主体不得同时担任同一 Task 的 Owner 和最终 Reviewer。

## 6. 共享路径规则

`paths.shared` 用于 README、总索引、版本目录、公共 Contract Registry 等集成面。

- 并行 Agent 不直接在各自分支随意修改同一共享文件；
- 共享修改由 Integrator 统一落盘，或按 Program Plan 指定顺序串行进入；
- 若共享文件变化会改变机器行为，必须先建立 Contract/ADR Task；
- Collaboration Checker 会拒绝“当前 Task 未声明却实际修改”的文件；
- 活动 Descriptor 之间出现独占路径重叠时，必须先拆分或串行化。

## 7. 契约优先波次

```text
Wave 0 需求/NFR/验收冻结
→ Wave 1 OpenAPI/Event/DDL/Workflow/Policy Contract
→ Wave 2 模块骨架与独立实现
→ Wave 3 纵向集成、E2E、故障与安全测试
→ Wave 4 RC、恢复演练和人工发布批准
```

没有可执行机器契约时，不允许多个实现 Agent 根据自然语言各自猜测字段、状态或错误语义。

## 8. 基线与重基

- 每个 Descriptor 必须记录 40 位 `baseCommit`；
- Base 变化后必须重新执行 Scope、Contract、测试和 Evidence；
- 不允许静默把旧分支直接合并到新基线；
- 长期分支优先从最新 `main` 重建干净分支；
- 遇到机器契约变化时，下游 Task 必须更新依赖并重新验证。

## 9. 依赖与集成顺序

- `dependencies` 只填写必须先合并的 Task；
- Program Plan 中的 DAG 是编排基线；
- `integration.order` 数值越小越先进入；
- 同一波次可以并行开发，但仍按依赖和共享路径顺序合并；
- 不使用“所有 Agent 最后一次性大合并”的方式；每个工作包必须可独立验证和回滚。

## 10. Handoff Evidence

每个多 Agent Task 必须提供非空 Handoff，至少包括：

```text
Baseline
Delivered outputs
Changed paths
Contract inputs/outputs
Executed validation and real results
Known gaps and risks
Integration order
Next owner and required follow-up
Rollback
```

Handoff 是下一 Agent 的输入，不是完成声明。只有 Git、CI、Review 和 Evidence 都一致时才能标记完成。

## 11. 独立审查

- Owner：实现并维护 Task 范围；
- Reviewer：从需求、契约、测试、风险和越权角度独立审查；
- Integrator：确认依赖、共享文件、合并顺序和回归；
- Security/Operations Reviewer：仅在对应风险域需要时加入；
- Reviewer 发现范围外缺陷时，应建立 Follow-up Task，不把当前 PR 无限扩张。

## 12. 本地命令

```bash
python scripts/check-collaboration.py --task GZ-003 --base origin/main
python scripts/render-multi-agent-prompt.py \
  --task GZ-003 \
  --role integration-agent \
  --output .agent/GZ-003-integration-agent.md
```

## 13. 使用顺序

```text
Orchestrator 选择 Program Plan 中可启动任务
→ 创建 Issue / Task Spec / Coordination Descriptor
→ 从指定 baseCommit 创建分支
→ Renderer 生成角色 Prompt
→ Owner 实现和自检
→ 写 Handoff + Evidence
→ Independent Reviewer 审查
→ Integrator 按依赖顺序合并
→ 更新任务状态和后续依赖
```

## 14. 停止条件

出现以下情况必须停止写入并上报：

- 高优先级需求或机器契约互相冲突；
- 独占路径已被另一活动 Task 占用；
- Base Commit 不可达或主分支已发生破坏性变化；
- POC 结论缺失却要求作生产承诺；
- Owner 与 Reviewer 无法保持独立；
- 无法提供真实测试、命令或 Handoff Evidence；
- 需要扩大到 Task 禁止范围。

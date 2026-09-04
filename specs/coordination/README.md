# Guize 多 Agent Program Plan 与活动任务登记

本目录包含两个不同层次的事实源，禁止混用：

- `program-plan.yaml`：V1 长期交付计划的唯一机器可读入口，描述未来 Task、Wave、依赖、风险、Requirement、Module、输出路径、契约生产/消费、POC 和发布阻断项。
- `active-work.yaml`：当前已预留或正在执行的少量任务登记，描述固定 base SHA、角色、租约、独占/共享路径、handoff 和集成顺序。

二者都不是产品需求或业务契约。发生范围冲突时，仍按 `AGENTS.md` 的权威顺序处理。

## 文件

| 文件 | 作用 |
|---|---|
| `program-plan.yaml` | canonical V1 Program Plan |
| `program-plan.schema.yaml` | Program Plan 结构契约 |
| `active-work.yaml` | 当前活动任务 Registry |
| `active-work.schema.yaml` | Registry 结构契约 |
| `task-completions.yaml` | 普通 Program Task 的不可变完成记录 |
| `task-completions.schema.yaml` | 完成记录结构契约 |

旧 `work-package-plan.yaml` 已被 Program Plan 替代，不得重新创建第二份后续任务计划。

## 从计划到合并

```text
需求/契约允许新增任务
→ Coordinator 检查依赖/Wave/外部 blocker
→ Issue + Registration Task Spec + Evidence
→ Registration PR：absent → planned，无 Lease、无实现权限
→ Registration Gate/Review/Merge + post-main Gate
→ Reservation PR：planned → reserved，创建唯一 Active Work Lease
→ Reservation Gate/Review/Merge + post-main Gate
→ Activation PR：reserved → in_progress，保持身份/范围/Lease
→ Activation Gate/Review/Merge + post-main Gate
→ Implementer 从 Activation 后 main 使用登记分支实现
→ Implement + Tests + Evidence + Handoff
→ Independent Review
→ Integrator 检查契约/迁移/行为冲突
→ Review / Integration / Completion 独立生命周期 PR
→ Registry 释放
→ Program Plan 完成状态和 Completion Ledger 同步
```

非治理紧急修复若不在 Program Plan 中，必须先通过独立 high-risk Registration；不能只创建 Issue 后直接开工，也不能借用已完成任务的身份。

## Registration 启动条件

一个尚不存在于 Program Plan 的普通任务只有同时满足以下条件才能登记为 `planned`：

1. exactly one 新 Task ID；
2. schemaVersion 2 Task Spec 与 Program task 的身份、风险、Wave、依赖、Requirement、Module、路径、契约、Issue、branch pattern 和 exit gate 完全一致；
3. `coordinationMode: registration`、`agentRole: coordinator`；
4. Program Plan 变更为 high/critical 风险，并配置不同的 Implementer 与 Reviewer；
5. Active Work 和 Completion Ledger 字节不变；
6. 不存在 `leaseExpiresAt`、Lease、实现文件、执行结果或完成声明；
7. 只允许 Program Plan、新 Task Spec、`evidence/<TASK-ID>/**`，以及经共享校验器证明的 later-planned `dependsOn` 尾追加；
8. 依赖存在、Wave 方向合法、无环，且新任务仍在 required final task 的传递闭包中；
9. exact base SHA、实际分支和 Task branch pattern 一致；
10. PR task-aware 和 push/no-task 模式产生相同结论。

`planned` 只是计划登记状态。它不得进入普通 Agent Coordination、Task Scope、执行、Review、Integration、Completion 或 Result 路径。

## Reservation 与 Activation 条件

Registration 合并且 exact post-main Gate 成功后，才允许 Reservation：

1. Program Plan 中存在唯一 Task ID，状态为 `planned`；
2. `dependsOn` 已完成或输出已冻结为机器契约；
3. 当前 Wave 的并行和 high-risk 容量未超限；
4. external blocker 不禁止该任务；
5. Requirement、Module、output/shared path 和 contract producer/consumer 与计划一致；
6. high/critical 任务具有独立 Implementer 与 Reviewer；
7. Reservation 独立 PR 仅执行 `planned -> reserved` 并创建唯一 Lease；
8. Reservation 合并且 post-main Gate 成功后，Activation 独立 PR 才能执行 `reserved -> in_progress`；
9. Activation 不得改变已审查角色、依赖、契约或路径。

## 四阶段协议

1. **Registration**：exactly one `absent -> planned`，metadata-only，无 Lease/实现权限。
2. **Reservation**：`planned -> reserved`，建立唯一、未过期 Lease。
3. **Activation**：`reserved -> in_progress`，绑定 Reservation 后绿色 main。
4. **Implementation**：只从 Activation 后 main 开始实现；Reviewer 独立审查，Integrator 在后续独立生命周期 PR 中完成集成和释放。

GZ-003 是原始机制 bootstrap；GZ-014 通过真实 reservation 验证并扩展机制。OPS-008 是一次性 self-hosting maintenance，用于建立通用 Registration，而不是给任何具体任务添加 allowlist。

## 路径与公共契约

- `exclusivePaths` 与其他活动任务的独占或共享路径重叠时失败；
- `sharedPaths` 只有在 `coordinationGroup` 相同、双方都声明 shared 且 `integrationOrder` 不同时允许重叠；
- “无共享范围”必须单独写为 `- 无。`，不得在同一 bullet 中混入反引号路径；
- 不允许使用 `**` 预占整个仓库；
- `module-ownership.yaml` 中每个公共 Contract Namespace 只有一个 owner；
- consumer 只能依赖已合并 producer Task 或冻结契约；
- shared writer 必须显式登记，不能因为多个 Agent 都能提交文件而推断为允许共同写入。

## 并行上限

- Program Plan 和 Registry 默认最多 3 个并行任务；
- 默认最多 1 个 high/critical 风险任务；
- critical 任务单独一个 Wave；
- 终态 `completed` / `cancelled` 历史不占结构性 Wave 槽位，但仍参加 Schema、DAG、契约和发布闭包校验；
- 未冻结共同机器契约前，不并行实现同一契约的多个消费者；
- 审查者只能按可实际处理的容量放行任务，不能为追求并发填满上限。

## 验证

```bash
python scripts/check-schemas.py
python scripts/check-project-readiness.py
python scripts/check-program-task-registration.py \
  --base-ref origin/main \
  --head-ref HEAD \
  --task GZ-XXX \
  --branch-name chore/GZ-XXX-registration
python scripts/check-agent-coordination.py
python scripts/check-agent-coordination.py --task GZ-XXX
```

`python scripts/check-project-readiness.py --strict-ready` 用于最终生产就绪检查；在机器契约、实现或外部 GitHub Ruleset 未完成时应失败。

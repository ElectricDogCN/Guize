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

旧 `work-package-plan.yaml` 已被 Program Plan 替代，不得重新创建第二份后续任务计划。

## 从计划到合并

```text
Program Plan 中任务可启动
→ Coordinator 检查依赖/Wave/外部 blocker
→ Issue + Task Spec + Evidence
→ reservation PR 写入 active-work
→ reservation Gate/Review/Merge
→ Implementer 从 reservation 后最新 main 创建登记分支
→ Implement + Tests + Evidence + Handoff
→ Independent Review
→ Integrator 检查契约/迁移/行为冲突
→ Integration PR Merge
→ Registry 完成/释放
→ Program Plan 状态更新
```

非治理紧急修复若不在 Program Plan 中，必须先用独立高风险治理任务修订 Program Plan，不能只创建 Issue 后直接开工。

## 启动条件

一个任务只有同时满足以下条件才可 reservation：

1. `program-plan.yaml` 中存在唯一 Task ID；
2. `dependsOn` 已完成或输出已冻结为机器契约；
3. 当前 Wave 的并行和 high-risk 容量未超限；
4. external blocker 不禁止该任务；
5. Requirement、Module、output/shared path 和 contract producer/consumer 与计划一致；
6. high/critical 任务具有独立 Implementer 与 Reviewer；
7. Task Spec、Registry、Issue 和 branch name 使用同一任务定义。

## 两阶段协议

1. Coordinator 创建 Issue、schemaVersion 2 Task Spec 和 Evidence；
2. 通过独立 reservation PR 把任务写入 `active-work.yaml`；
3. reservation PR 合并后，Implementer 从最新 `main` 创建实现分支；
4. 实现阶段把登记状态改为 `in_progress`，不得改变已审查角色和路径而不修订 reservation；
5. Reviewer 只审查，不在同一高风险任务中兼任 Implementer；
6. Integrator 复核依赖、公共契约、Migration、行为冲突和 Handoff；
7. 合并后通过治理提交把 Registry 标记完成或释放，并同步 Program Plan 状态；
8. 过期、取消或阻塞登记由 Coordinator 通过独立治理 PR 清理。

GZ-003 是机制 bootstrap，列入 `policy.bootstrapTasks`；GZ-014 通过真实 reservation 验证并扩展该机制。

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
- 未冻结共同机器契约前，不并行实现同一契约的多个消费者；
- 审查者只能按可实际处理的容量放行任务，不能为追求并发填满上限。

## 验证

```bash
python scripts/check-schemas.py
python scripts/check-project-readiness.py
python scripts/check-agent-coordination.py
python scripts/check-agent-coordination.py --task GZ-XXX
```

`python scripts/check-project-readiness.py --strict-ready` 用于最终生产就绪检查；在机器契约、实现或外部 GitHub Ruleset 未完成时应失败。

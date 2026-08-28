# 多 Agent 活动任务登记

`active-work.yaml` 是多个 Agent 并行工作时的仓库内协调登记，不是产品需求或业务契约。

## 两阶段协议

1. Coordinator 创建 Issue、schemaVersion 2 Task Spec 和 Evidence；
2. 通过独立 reservation PR 把任务写入 `active-work.yaml`，声明依赖、风险、角色、基线 SHA、独占/共享路径、租约和集成顺序；
3. reservation PR 合并后，Implementer 从最新 `main` 创建实现分支；
4. 实现 PR 在合并时删除或完成对应活动登记，并提交 handoff；
5. 过期、取消或阻塞登记由 Coordinator 通过独立治理 PR 清理。

GZ-003 是机制 bootstrap，列入 `policy.bootstrapTasks`，不要求对尚未存在的登记机制自登记。

## 路径规则

- `exclusivePaths` 与任何其他活动任务的独占或共享路径重叠时失败；
- `sharedPaths` 只有在 `coordinationGroup` 相同且 `integrationOrder` 不同时允许重叠；
- 路径重叠判断是保守的，无法证明互斥时按冲突处理；
- 不允许使用 `**` 预占整个仓库；任务必须尽可能缩小写范围。

## 并行上限

- 最多 3 个活动任务；
- 最多 1 个 high/critical 风险活动任务；
- 高风险任务的 Reviewer/Integrator 不应与 Implementer 是同一 Agent；
- 未冻结共同机器契约前，不并行实现同一契约的多个消费者。

## 验证

```bash
python scripts/check-agent-coordination.py
python scripts/check-agent-coordination.py --task GZ-XXX
```

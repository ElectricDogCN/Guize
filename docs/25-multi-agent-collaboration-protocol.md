# 25. 多 Agent 协作、交接与集成协议

## 1. 目标

本协议解决多个 Agent 同时在 Guize 仓库工作时的四类风险：

- 两个任务修改同一路径或同一机器契约；
- 下游任务基于未合并或已过期的依赖开发；
- 实现者自行审查和集成高风险变更；
- 交接只留下说明，没有真实提交、测试和 Evidence。

本协议不提高并行数量上限，而是让必要的有限并行可证明安全。

## 2. 角色

### Coordinator

- 拆分 Task、确认依赖和风险；
- 分配路径租约与 `integrationOrder`；
- 控制并行上限；
- 处理过期/取消/阻塞登记；
- 不能用协调权限覆盖冻结需求或机器契约。

### Implementer

- 只在 Task 和活动登记允许范围内修改；
- 从登记的 `baseSha` 建立分支；
- 维护测试、Evidence 和 handoff；
- 发现越界依赖时停止并交回 Coordinator。

### Reviewer

- 默认只读；
- 检查需求优先级、契约、范围、失败路径、安全和 Evidence；
- high/critical 任务不得由同一 Agent 同时充当唯一 Implementer 和唯一 Reviewer；
- 不通过删除测试、放宽断言或改需求来消除阻塞项。

### Integrator

- 检查依赖已合并、基线新鲜、共享路径顺序和 Review Thread；
- 只集成已批准的行为；
- 冲突涉及行为时退回 Implementer，不在合并时静默选择；
- 不执行生产发布。

单人项目中，ElectricDogCN 可以承担最终人工批准，但 Agent 角色和执行记录仍需分离。

## 3. 生命周期

```text
PROPOSED
→ RESERVATION_PR
→ RESERVED
→ IN_PROGRESS
→ REVIEW
→ INTEGRATION
→ COMPLETED

任意活动状态
→ BLOCKED / CANCELLED / EXPIRED
```

`active-work.yaml` 只记录 `RESERVED` 之后的活动任务；提议阶段保留在 Issue/Task Spec。

## 4. 两阶段任务启动

### 阶段 A：预留

Coordinator：

1. 创建 Issue；
2. 创建 schemaVersion 2 Task Spec 和 Evidence；
3. 声明 `baseSha`、依赖、风险、角色、独占/共享路径、租约和集成顺序；
4. 通过小型 reservation PR 更新 `active-work.yaml`；
5. Governance Gate 通过并合并 reservation PR。

### 阶段 B：实现

Implementer 从包含预留记录的最新 `main` 创建工作分支。禁止先开发后补登记；紧急安全修复需要 Coordinator 记录例外和缩短租约。

## 5. 路径租约

### 独占路径

- 一个活动任务拥有写权限；
- 与其他任务独占或共享声明重叠均失败；
- 机器契约、Migration、模块核心包、全局配置默认独占；
- 禁止用 `**` 预占整个仓库。

### 共享路径

仅适用于不可避免的索引、聚合文档、版本目录或共同生成文件。要求：

- 相同 `coordinationGroup`；
- 不同 `integrationOrder`；
- 明确谁先合并、谁基于谁刷新；
- handoff 记录冲突处理；
- 共享路径不得掩盖真实模块边界不清。

### 保守重叠

脚本无法证明两个通配模式互斥时按冲突处理。任务应缩小路径，而不是放宽检查。

## 6. 依赖与契约

- `dependsOn` 的 Task 必须存在；
- 活动依赖图不得有环；
- 下游只可依赖已合并契约或明确版本的稳定分支；
- 多个 Agent 可以并行实现不同消费者，但共同 Provider 契约必须先冻结；
- 禁止从其他 Agent 未提交的本地状态复制行为定义；
- 依赖变化后，Coordinator 更新登记和集成顺序。

## 7. 风险与并行上限

| 风险 | 典型任务 | 并行规则 |
|---|---|---|
| low | 单模块文档/无行为重构 | 可与独立 low/medium 并行 |
| medium | 单模块功能、独立 POC | 总活动任务不超过 3 |
| high | 机器契约、数据库、权限、核心架构、硬件拓扑 | 同时最多 1 个 |
| critical | 生产数据、Secrets、恢复、公开权限 | 单独执行并需人工批准 |

单人审查容量是硬约束；不能通过增加 Agent 数量绕过。

## 8. 基线新鲜度

Task Spec 和活动登记都保存 `baseSha`。进入 Review 前：

- 获取最新 `main`；
- 检查是否落后或依赖已变化；
- 重新运行 Scope、Contract、Tests 和 Evidence；
- 更新后原批准失效，需要重新审查；
- 禁止 force push 隐藏已审查历史。

## 9. Handoff Contract

`handoffPath` 至少包含：

```text
Task / Issue / Branch / Base SHA
角色和执行者
提交 SHA 与目的
实际 changed files
契约/Schema 版本
测试命令、退出码与结果
Evidence 路径
已知失败、限制和未解决项
共享路径和 integrationOrder
回滚与恢复
下一角色需要执行的精确动作
```

“已完成”“测试通过”“可合并”等结论必须链接真实证据。

## 10. Review Contract

Reviewer 依次检查：

1. 权威需求和 ADR；
2. 机器契约兼容性；
3. Task/Registry/Branch/Base SHA 一致；
4. 允许/禁止范围；
5. 模块和 Schema 所有权；
6. 成功、失败、安全、并发、幂等、迁移；
7. 测试是否真实执行；
8. Evidence 是否可复现；
9. 共享路径和集成顺序；
10. 回滚是否可执行。

输出必须区分 blocker、warning 和 non-blocking suggestion。

## 11. Integration Contract

Integrator 合并前确认：

- 所有依赖已进入目标基线；
- 最新 HEAD 的所有 Required Check 成功；
- Review Thread 全解决；
- high/critical 具有独立 Reviewer 和人工批准；
- 分支未过期、无未知范围修改；
- 活动任务登记在本 PR 中完成或释放；
- shared path 按 `integrationOrder` 集成；
- 合并方式与 Task Spec 一致；
- 合并后 main 的 Gate 再次运行。

## 12. 冲突和失败

- 路径冲突：后登记任务缩小范围或等待；
- 契约冲突：暂停消费者，先建立 ADR/契约任务；
- Git 冲突涉及行为：退回 Implementer；
- 租约过期：任务自动视为阻塞，Coordinator 决定续期或释放；
- Agent 中断：新 Agent 必须从 handoff、Git 和 Evidence 恢复，不能依赖聊天记忆；
- CI 失败：保留失败证据，修复后重新执行，不覆盖历史。

## 13. GitHub 设置

CODEOWNERS 只能路由审查，不能自行强制。管理员仍需在 GitHub 配置 `main` Ruleset：PR、批准、Required Check、对话解决、禁止 force push/delete、过期批准失效和管理员受约束。未启用前，仓库只能称为“流程约束可用”，不能称为“平台强制阻止直接推送”。

## 14. 最小并行示例

```text
GZ-007 ATS POC
  exclusive: poc/ats/**, evidence/GZ-007/**

GZ-009 元数据规模 POC
  exclusive: poc/metadata-scale/**, evidence/GZ-009/**

两者无重叠、均 medium、依赖 GZ-003，可并行。

GZ-004 核心机器契约
  high risk，独占 contracts/**

GZ-005 工程骨架
  dependsOn GZ-004，不可与 GZ-004 提前并行实现共同接口。
```

## 15. 完成定义

多 Agent 协作正常不等于“多个 Agent 都产生了提交”，而是：任务独立、路径无冲突、依赖无环、角色有交接、测试可复现、集成顺序明确、失败可恢复、最终人工批准可基于证据完成。

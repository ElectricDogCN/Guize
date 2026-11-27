# Workflow 与 Activity V1

保留工程基线的十个 Workflow 类型和 ID。`catalog.yaml` 绑定活动类别。`activity-options.schema.yaml` 固定部署配置的形状。发布时固定 `policyVersion` 和完整配置摘要，后续变更通过新版本生效。仓库的合成验证配置只用于检查约束，实际运行限额来自对应环境已批准的配置。

Workflow 从 TASK 提供的同一任务、计划和计划版本执行，接受的计划版本固定输入和允许的步骤。Workflow ID 由 TASK 的任务与计划版本派生，重复 Outbox 消费复用其执行身份。工作流重放只使用历史结果、确定性的流程状态和 Temporal API。真实外部操作进入 Activity。执行器写入用受控 TASK 命令，业务接受和 Outbox 保持同一事务。Temporal 成功仅表示编排本身完成，客户端状态读取 TASK 的结果。

活动重试次数包含首次尝试，调度截止时间覆盖所有尝试。单次执行上限不超过调度截止时间。长活动必须在单次上限之前心跳，心跳记录可验证、可恢复的进度引用。Worker 的在线心跳和尝试租约分别管理。外部操作使用任务、计划版本、当前步骤和操作类型组成的稳定幂等键，重试共享该键。新的执行尝试仍由 TASK 更新 fencing。业务拒绝、输入身份不一致、权限失效和取消按不可重试结果处理。

取消先持久化 TASK 意图并停止派发。通过心跳或适配器通知运行中的活动，等待其取消结果；到期后的节点结果仍由 TASK 拒绝。补偿活动也受版本、授权、预算和幂等约束。Task Queue 由部署配置选择，播放优先级沿用平台 P0 至 P8。只记录可重放引用和必要公开索引，不写入内容、凭据或原始输入。升级需对受影响的历史回放并验证活动幂等。

使用 [本地验证入口](../../../specs/contracts/runtime/check_workflow_contract.py) 校验固定目录和指定的部署策略。[工程基线](../../../docs/00-guize-engineering-design-baseline.md) · [Temporal Activity](https://docs.temporal.io/activity-definition)

`replay.schema.yaml` 定义 TASK 提供的规范化重放输入。计划按拓扑顺序记录稳定的步骤、依赖和不可变输入引用。历史快照逐步骤绑定原策略版本和业务幂等键，已调度步骤由原执行继续，已完成的步骤读取已保留结果。独立就绪步骤可同时派发。取消意图停止生成新的派发候选，执行全部结束后仍须向 TASK 对账。

# Worker V1

`protocol.schema.yaml` 定义 `worker-v1` 的派发和回应，可由 Android、Windows 和 Linux 适配器读取同一份 schema 和一致性向量。TASK 在确认当前计划/步骤及能力发布版本后分配节点、尝试和 fencing。每个回应重述同一元组，节点会话通过既有 IAM 验证，独立的执行租约才绑定具体资源和读写范围。

CLAIM 只能领取仍可用的 offer，使用对应节点、执行组、资源预留及时效观测。首次分配与续租的执行期限均由任务截止时间、授权和资源预留共同约束。报告不可观测能力时显式提供原因。RENEW 只能请求延长当前执行租约，由 TASK 决定截止时间。PROGRESS 按序递增，且单位数受 offer 限制。仅登记为 INDEPENDENT_UNIT 的能力可使用 TASK 验证过的独立单元检查点。

输入引用及版本、摘要、字节和可选帧跨度通过受限数据面访问。输出仅可写入已批准的 scope、字节上限及目的地。处理、网络、成本、scratch 和后台配额由节点与 TASK 的同一资源账本约束。P0 至 P8 优先级由 TASK 决定并绑定已通过准入的策略版本、动作及决策轨迹。CANCEL_ACK 对应权威取消请求，停止确认不产生结果，迟到结果继续由当前状态和 fencing 检查。

节点提交成功候选时提供已验证的产物清单身份、摘要和用量。TASK 在同一事务内校验当前版本、租约及 fencing 并去重，随后写入权威结果与 Outbox。相同的已接受结果返回 ALREADY_ACCEPTED，冲突或过期的新结果均拒绝。失败按明确类别上报，重派和结算由 TASK 决定。协议验证器返回现有事实下的判定，持久写入及通知由实际适配器完成。

`trustedSnapshot` 是 TASK 适配器从权威存储组合的内部输入，不是 Worker 消息。节点验证、授权状态、资源预留、截止时间及实际结果先按定义校验。无效输入返回 `TRUSTED_SNAPSHOT_INVALID`，有效布尔值 `false` 则按相应业务拒绝处理。

一致性向量以同一个 offer、消息和可信状态为基础，逐例调整字段并比对预期结果。`message.binding` 按键替换，其余消息字段整体替换。`trusted` 的 session、observation、reservation、admittedPolicy、verifiedArtifact 按键替换，其他字段整体替换。所有向量均是合成输入。[固定向量](../../../specs/contracts/runtime/fixtures/worker-conformance-v1.json) · [本地验证入口](../../../specs/contracts/runtime/check_worker_contract.py) · [SDK 构建](../../../specs/contracts/runtime/build_worker_sdk.py) · [任务及边缘执行要求](../../../specs/requirements/agent-edge-104.md)

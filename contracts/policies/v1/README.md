# Policy V1

已发布的 `policyId` 与 `policyVersionId` 固定 Node、Chain、EL 和配置摘要。摘要使用按键排序、无多余空白的 ASCII JSON。权威发布、灰度选择、回滚和审计沿用 POLICY/CONFIG 模块及数据库 `policy.published` 事务。运行时只接收已授权的版本选择、已验摘要和冻结事实。CANARY_SELECTED 表示调用方已按同一版本的灰度条件选择执行，SIMULATION 的输出仅供核对。

判定节点读取单个已声明的布尔事实，决策节点给出推荐或拒绝，可附原有 0 至 8 优先级。结构化 Chain 固定 `THEN` 的顺序与 `IF` 的两条分支，EL 必须与结构化表达式逐字一致。分支只使用已登记节点。缺事实、无权限、版本不符、预算缺失或超额均生成确定性失败。`THEN` 遇到拒绝即返回，LiteFlow 适配器通过决策上下文结束后续节点。[LiteFlow 条件编排](https://liteflow.cc/pages/v2.12.X/e76999/)

高风险动作消耗带动作、版本及有效期的权威审批记录。适配器在执行前重新检查当前授权及预算，TASK 负责资源预留和执行。Node 与模拟过程只产生建议和轨迹，外部副作用由受控 Activity 完成。任何地区时间、当前时钟、凭据和外部事实均由调用方准备，不从规则表达式读取。

测试入口位于 [check_policy_contract.py](../../../specs/contracts/runtime/check_policy_contract.py)。[规则与长任务设计](../../../docs/14-rules-and-workflows.md)

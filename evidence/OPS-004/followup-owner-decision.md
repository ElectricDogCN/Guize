# OPS-004 具体后续恢复决定

Owner ElectricDogCN 已在本会话委托最高决策权，本记录执行该委托。
Event: OPS-004-FOLLOWUP-RECOVERY-20261010
Recorded UTC: 2026-10-10T01:09:53Z
Deadline: 2026-10-10T03:09:53Z 或 OPS-004 Completion merge，取先到者。
Anchor: 1dd347521445a712e0873dc762692b445373e88a

原事件 OPS-004-LIFECYCLE-ADMISSION-20261009 已在 2026-10-10T01:09:31Z 截止。原 owner-decision.md/blob e25670a161ff6c33104b24d3bb8f22ce4fb06eac、开始时间和期限逐字保留。
截止真实状态见 original-window-end-state.json：实现 PR77 已合入，PR78 未合入且 Task collaboration bullet 检查失败；正式本地检查首项失败，CI 还存在 maxHigh=1 的真实容量失败。旧失败不是 PASS；未完成 Review/Completion/主线全通过。
失败 PR78 实际源 b2cb1839598ee445c3cbacf9761340f3800042c7 和本地修正草稿分别保留在引用、bundle 与失败原始记录中，新实现直接以 Anchor 为父来源，不继承失败 Task 节点。
唯一范围：同一 OPS-004、原 reservation d0e9e256552f9d1d47fb24d2e5a4530476b19a5f、既有六条 claims 及其自身 Task/Evidence。仅增加这个具体事件的精确历史来源识别和边界回归；其后独立 Review/Completion。允许窗口内保留原 GZ-005 reserved high 快照与同一 OPS-004 high Lease，仅 OPS-004 工作。
GZ-005 的所有 Program/Registry/Task/Evidence/业务接口不变；永久 policy/maxHigh=1、并发计数、普通 Ledger、旧完成身份不变。原 OPS-004 Lease/身份/六条 claims 不续期、不扩展；不授权其他任务、全局豁免、其他 Peer 准入重放或数据/POC。
每个真实候选运行全部真实门禁、完整治理、同头 CI 与独立审查；除精确两 high 容量 FAIL 外任何失败必须修正。历史识别只记录 capacityResult FAIL；协调计数与 CI 的容量失败继续原样归档。
新实现是新的最后代码 PR，Completion 必须绑定它的实际 merge，不能沿用 PR77。Review 必须独立合入；Completion 仅移除自身 Lease且全部门禁/CI为零；真实主线全部验证通过后才恢复 GZ-005。
此刻新候选验证 NOT_EXECUTED。所有实际 UTC/源/tree/命令/退出码/JUnit/CI 原始记录完整保存。截止尚未收口则停止新变更，记录状态后另作具体恢复决定。此决定不是 V1 或 POC 完成声明。

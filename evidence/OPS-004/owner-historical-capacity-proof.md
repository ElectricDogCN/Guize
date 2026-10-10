# OPS-004 原有容量失败事件的历史来源承认

Owner: ElectricDogCN（本会话已委托最高决策权）
Task: OPS-004 / Issue71
Event: OPS-004-LIFECYCLE-ADMISSION-20261009

本记录明确既有 Owner 决定在历史来源证明中的处理，不更改原 owner-decision.md、永久 policy/schema/计数、租约或窗口。原决定 blob 为 e25670a161ff6c33104b24d3bb8f22ce4fb06eac，真实登记为 d0e9e256552f9d1d47fb24d2e5a4530476b19a5f，第一父为 413a6a4dd91b5d79a3d2b7d1e5f03f8121848170。登记时 maxActive=3/count=2、maxHigh=1/high=2：容量结果仍为 FAIL。

通用原登记和工作节点必须按适用 policy 检查容量。仅对以上不可变真实 OPS-004 登记及其主线后代，承认原事件已授权并完整保留的容量失败：原决定 blob 不变；观测提交必须在 2026-10-09T13:09:31Z 至 2026-10-10T01:09:31Z 之间；Program active；policy 与原基线一致；Registry 只能含 GZ-005 reserved high 原条目和 OPS-004 high，GZ-005 条目与原基线完全相同，且不超 maxActive。不能用于其他 Task、合成 fixture、额外参与者、修改原决定、扩大 policy、冻结或窗口后的工作。

历史检查结果必须记录 AUDITED_OWNER_EVENT / capacityResult: FAIL，不能把这项历史失败写为容量 PASS。当前 coordination、make verify 与 CI 的真实容量失败继续保留；本处理不修改它们的计数或返回码，不构成一般准入豁免。

只有 OPS-004 可以在已登记治理范围内实施。最终实现仍须独立审查、完整治理零失败/错误/跳过、真实 PR77 merge 身份，以及随后独立 Review/Completion。移除 OPS-004 Lease 后 Completion 与主线全部门禁必须真实通过，才能恢复 GZ-005。窗口不延长；到期未完成则遵原决定停止新增变更并另作具体恢复决定。

# OPS-004 有界治理修复窗口决定

Owner ElectricDogCN 在本地会话明确要求“你在这个项目有最高决策权，我只要求你能实现目标”，承接者据此作出本项具体决策。此记录是执行已委托的决策权，不冒称用户另行批准过本候选，也不冒称检查器接受例外。

- Event: OPS-004-LIFECYCLE-ADMISSION-20261009
- 基线：413a6a4dd91b5d79a3d2b7d1e5f03f8121848170；Issue #71；登记先于实现，独立 Implementer/Reviewer。
- 原因：GZ-005 的正常 reserved→in_progress 被 coordination 判 Program 未登记；Task Scope 对自身 Task/Registry 也无 metadata 许可。原高风险 reserved Lease 无可恢复让位路径，新 Foundation 必须 high，造成修复准入死锁。
- 唯一例外：从 2026-10-09T13:09:31Z 起到 OPS-004 Completion 合并或 2026-10-10T01:09:31Z（取先到者），允许 Registry 同时保留 GZ-005 reserved high 快照与 OPS-004 high 修复 Lease。只有 OPS-004 可实施；GZ-005 的 Program、Registry 条目、Task、Evidence 与业务契约在修复分支中保持原样。
- 修复窗口覆盖独立登记、实现、审查和 Completion；不把持续容量失败说成过时的登记失败。每个精确候选都运行真实门禁，maxHigh=1 的失败与实际 CI 结果完整保留，并列出其他意外失败。
- 永久 policy/schema/maxHigh 不变；不新增通用豁免或改并发计数；不触及 Secrets、实际数据、业务接口、旧 completed 身份与 Ledger。
- 独立审查是必需；完整治理回归零失败/错误/跳过为必需。若出现例外以外失败，先修正，不以本事件豁免。实现只能在已登记的四个治理路径及自身 Task/Evidence 内修改。
- 收口：仅以实际已合入的实现 PR/merge 身份完成 OPS-004；移除 OPS-004 Lease 后容量限制恢复，Completion、CI 与主线 make verify 均须真实全通过，才继续 GZ-005 激活。若窗口截止尚未完成，不新增变更，记录当前状态并重新作具体恢复决定。
- 这不是 PASS，不代表业务功能或任何真实 POC 完成，也不改变最终 V1 全门禁验收要求。

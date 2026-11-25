Task: GZ-006
Issue: 128
Base: 90b017c0627cc0aede19900cad664e918ac5a716
Branch: chore/GZ-006-event-catalog-reservation
Work Branch: chore/GZ-006-event-catalog-v1
Status: RESERVED; current source results PENDING

Roles: {"coordinator": "program-coordinator-agent", "implementer": "task-owner-agent", "reviewer": "independent-review-agent", "integrator": "integration-agent"}
Lease: {'acquiredAt': '2026-11-25T13:11:35Z', 'expiresAt': '2026-12-02T13:11:35Z'}
Contract: EVENT-CATALOG-V1; consumes REQ-V1/OPENAPI-V1. No shared paths. Order1. Source/tree/PR/commands/exits/CI pending. Next role independently reviews exact source, then Integrator normal merge and actual-main verification; implementation follows accepted reservation. Rollback: withdraw unmerged; lawful cancellation after reservation; forward versioned repair after publication.

## Implementation baseline

Reservation PR #279 merged on main at f290739965dc90fe6466cb871b2dd51b9bf694fb. Full official main CI 45625411208 and six task-specific controls passed. The independent reservation review SHA-256 is 82aebe6ff383522f43a0c6f95847e27da195704c6524332bfd436d58adeeae9b. The event catalog implementation is bound to this accepted reservation and scope.

## 实施核对

事件目录共 19 种 V1 事件，保留十种基础事件，新增计划、步骤、尝试、取消、结果接受、能力绑定与资源预留和释放。模块归属检查覆盖全部 19 个 Schema 和声明的消费者。公共 Envelope 与登记基线字节一致。

固定源复验后再提交完整官方 CI。独立审查核对消费者许可、Schema 引用闭包、fencing、租约时效、取消意图与已接受结果的语义。整体验收中的 POC 资格范围问题见 [Issue #280](https://github.com/ElectricDogCN/Guize/issues/280)。

## 独立审查修正

审查在初稿 `a4f9f25d18747d22d54351ee36ed396dbb1b3482` 上复现布尔值与数值被当作同一 Schema 常量的问题。原审查记录 SHA-256 为 `459f74d19a8434791083d7d48a6cb90aad76fd9a74c00239f1fb5461e9da0ce0`。版本校验现比较 JSON 类型和内容，登记的事件版本也按精确类型匹配。示例按聚合版本先后排列，取消的尝试与随后获接受的尝试有各自标识，后者使用更高的 fencing。新增用例覆盖这三条边界。修订源码的固定依赖验证需重新执行。

## GZ-006 正式 Review

Status: PASS

PR #281 的实施主线为 `8b530271c91b587a3b74754dbc1c13406add10ff`，包含 19 个事件版本。本阶段基线 `8b530271c91b587a3b74754dbc1c13406add10ff`（PR #281）已通过六项相关主线检查、完整官方 CI 和独立验收。独立记录 SHA-256 为 `651c41b4f0713a3b4fd310c6699b4f6616ea37a4f0354562b3086a175249d1ce`。

Source Commit: 8b530271c91b587a3b74754dbc1c13406add10ff
Command: /var/tmp/guize-ops027-rebased-proof/python/bin/python -B scripts/check-program-plan-integrity.py --base-ref f290739965dc90fe6466cb871b2dd51b9bf694fb
Exit Code: 0
Result: PASS
Raw SHA-256: dbe33acba490765e3863c3beb682c191a8b0376eacd9a70cb217fcc44287a1a0

[基线官方 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45636836816)

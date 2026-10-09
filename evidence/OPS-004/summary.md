# OPS-004 精确登记候选

Tested Source Commit: 59dcba760bf5fc300a5ad03a0b8dae23fe6b6d5d
Tested Tree: 99d27677ba41cfe035d92113fbe2c49de40f22d1
Base: 413a6a4dd91b5d79a3d2b7d1e5f03f8121848170
Issue: #71
Phase: metadata-only reserved registration; implementation NOT_STARTED

实际 15 项检查中，13 项退出 0；coordination=1、make verify=2，均明确因 high 活动快照 2 超永久上限 1。本事件授权的是 owner-decision.md 中有界整个修复窗口；这两项仍是 FAIL，不是 PASS。没有删除或改写永久限制。独立 governance 回归 328 testcase，零失败、错误、跳过，实际 pytest 328 passed in 51.31s。

Task/readiness/schemas/integrity/history/transitions/finalization/raw-lifecycle/lifecycle/scope/evidence/unaffected 真实退出 0。实际 unaffected 检查证明旧 Ledger、GZ-005/GZ-010/OPS-003 Task/Evidence、requirements、POC、contracts、scripts/tests 与 AGENTS 不变。GZ-005 Registry 原条目与全部其他 Program 身份的语义保持不变，仅追加 OPS-004。

原始结果：test-results/registration-59dcba7/。首次 2931cf2 的格式与 Evidence 缺项实际失败保留在 registration-first-2931cf2/，已纠正后重跑；不能用最终结果改写首次历史。阻塞业务激活的真实 346c9b6 检查保留在 reproduced-activation-346c9b6/。

当前尚未合并、尚未修复实现；远端 CI 与独立最终审查待实际取得。本次没有业务功能、硬件、真实数据或 POC 成功声明。只有 OPS-004 Completion 移除自己 Lease 并取得全部主线门禁成功后，才恢复接口激活。

## 当前实现阶段

登记 PR #72 已按有界窗口合并至 d0e9e256552f9d1d47fb24d2e5a4530476b19a5f。远端 HEAD 12dd8a59c11095f9d719d50def7a66a05c152d6c 与已审归档 exact tree 一致；Gate590 唯一 coordination 容量失败，其他检查真实成功，328 passed in 35.53s。现从已合入登记基线单独实现，仅修改预留检查器与测试及自身元数据；GZ-005 保持 reserved。上文未合并/NOT_STARTED 是登记时的历史状态。实现验证尚待执行，不声明 PASS。

## 首次正式实现复验：必须修复的非例外失败

Source Commit: 2da30c011a375f08968a8f11ad0acc3b4277bbea。15 项中 capacity coordination=1 / make=2 已按窗口保留，但 governance=1 属于未被例外授权的真实缺陷：Task Issue 漂移仍被协调检查接受。实际结果 1 failed, 349 passed in 301.99s，350 个 JUnit testcase、1 failure、0 error/skip；不得称 350 PASS。原始文件完整保留在 test-results/implementation-first-2da30c0/，须补完整 schema 绑定后提交新源重新执行正式检查。

此前 f3bbfeda7ff39da9d3d3d00fbaa6e2e91411cc23 的新增 20 项探索测试通过（208.46s），JUnit 位于 test-results/exploratory-f3bbfed.xml；它只覆盖当时 20 项，不转移为当前 22 项或完整治理结果。正式验证完成后需要真实实现合并、独立 in_progress→review 元数据迁移、再以 review 基线 Completion，不能跳状态或用本次失败当验收。

## 第二次实现复验与 CI 环境缺陷

Source Commit: 6cb4c678153d5b91e8a5de5f0ed87bce18e64d61。完整本地治理测试真实 350 passed in 317.35s，JUnit 350 testcase、零失败/错误/跳过；15 项仅 coordination=1 与 make=2 为容量失败。原始输出在 test-results/implementation-local-6cb4c67/。

该结果不能证明真实 PR 环境通过：独立审查设置实际 GITHUB_HEAD_REF 后，activation 正例退出 1，1 failed in 16.23s。测试隔离仓库的 GZ-005 分支被外层 OPS-004 环境分支覆盖。原始复现在 test-results/ops004-ci-env-reproduction-6cb.txt 与同名 XML，未改生产检查器、未伪造 PASS。现仅清除隔离测试子进程继承的外层分支，另加显式错误 CI 分支必须拒绝的反例，保留生产分支身份约束；须以新提交和真实 PR 分支环境执行完整复验。

## 完整真实 CI 分支环境复验

Tested Source Commit: 751dc3db960420f64641c4edd935f7669d026c85
Tested Tree: 53970bc163ca13f5adb7d9fc89f4c25c6cb14878
Base: d0e9e256552f9d1d47fb24d2e5a4530476b19a5f
Phase: in_progress implementation

正式复验设置 GITHUB_HEAD_REF=chore/OPS-004-lifecycle-repair-implementation；15 项检查中 13 项真实退出 0，只有 coordination=1 / make verify=2 为授权窗口内容量失败，仍记录 FAIL。完整治理实际 351 passed in 325.18s (0:05:25)，JUnit 351 testcase、零失败/错误/跳过，包含显式错误 CI 分支必须拒绝的负例。原始结果位于 test-results/implementation-ci-env-751dc3d/，均以实际 Source Commit 和 Command 绑定；不转移前两次失败为通过。

生产 helper 依次执行真实 schema、Task、全局协调、history、transitions、finalization、lifecycle 检查，全部成功后才授予自身 Task/Registry/Program 元数据路径。原有分支、角色、租约、claims 与禁改路径继续检查；未弱化永久容量限制。远端实际 CI、exact tree、最新 HEAD 和独立最终审查仍须取得。真实实现合并后另提 review 元数据迁移，再从已审基线提交 Completion。

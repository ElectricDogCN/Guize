
## 当前 scope 登记精确验证

Task: OPS-004 / Issue71 reopened
Phase: metadata-only review -> blocked
Branch: chore/OPS-004-history-scope-registration
Base: 62d4ef826e0be1acb2839c3f04fe62d1894f9585
Tested Source Commit: 7f77774ea2bce6948b4de7214f49e8bbc0fc0c09
Tested Tree: 6d01c960c1b7cfd5a58e998927a79b4a119a1e72

实际15项检查13项退出0、协调1/make2仅容量失败；独立完整治理 351 passed in 322.86s (0:05:22)，JUnit351零失败/错误/跳过。make真实在容量处中止，没有声称其执行到治理；完整治理为同一未变干净源的单独真实执行。最初外部runner误预期make会产出JUnit，其归档说明保留在runner-note.txt；没有据此宣称成功。Raw commands/results: test-results/history-scope-published-7f77774/，远端Gate599实际351 passed292.37s、其他全部实质步骤成功、唯一容量失败，见test-results/history-scope-remote-599/。独立审查此前静态通过；最终archive14、同头实际CI/Review仍待执行。

只改变自身元数据及Evidence，无生产代码；claims精确6条、sharedPaths空、integrationOrder4、原Lease保留。旧身份/政策/Ledger/GZ005不变。历史c5bf真实对象须作为发布archive额外父提交保留，见source-history/history-scope-source-map.json；不把其失败或完成树采纳为当前状态。范围登记合入后从真实最新main独立blocked→in_progress实现history修复。回滚仅停止/关闭未合入候选并保留原登记/证据；窗口不延期，不准GZ005实现。

## 历史阶段记录（保留）

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

## Review 元数据候选

Phase: review
Branch: chore/OPS-004-lifecycle-repair-review
Base: 726870c8ae161eab19f94a9b96980a7d9197b633
Implementation PR: #73
Implementation merge: 726870c8ae161eab19f94a9b96980a7d9197b633

本候选仅自身Program/Registry/Task的连续合法迁移及Evidence；实现两检查器和测试保持合入字节，GZ-005与旧完成身份不变。实际远端Gate592原始记录在 test-results/implementation-remote-592/。独立Review已确认751正式351零失败/错误/跳过、c085归档仅自身Evidence且exact tree一致；不冒称容量Gate PASS。需要本Review候选真实检查、独立审查、最新HEAD和实际CI，再按有界事件集成；后续Completion绑定实现身份而非Review PR。

Review metadata tested source: 3517a9d633a534f4502938aedec9360887079903；tree e896283d321aa469fc70836aa2e1a70eeac760dc。实际14项检查13退出0，仅coordination=1为容量2>1；完整原始在 test-results/review-3517a9d/。实施代码和测试未变，已有实现阶段351本地/远端回归不冒称是在本Review提交本地重跑；本Review的实际远端CI仍须执行完整治理测试。首次b1f729a机器检查同样只有容量失败，但独立审查指出Task将登记PR72与实现PR73的merge文案混淆，已修正并重新验证；首次结果保留。当前归档只追加自身Evidence，仍需最新候选检查与独立审查。

## 远端可重建源码与原日志绑定

上述本地Source SHA不是远端祖先，原日志保持实际执行Source不改。现以公开archive分支保存完整同树复验入口：b1f729a对应远端5cb09fb1824dfc50a854456f24948b53b1696598/tree9e9876db50cf5ae1707ca834b3fed0c66157f4d3；3517a9d对应5dce717e6224e1cf955926721807cbda4db9034b/treee896283d321aa469fc70836aa2e1a70eeac760dc。两者已实际fetch，原本地Source与各自远端完整diff都退出0；真实父链为726870→5cb09→5dce7。这些远端commit是后来创建的等价入口，不冒称原测试提交、不会把归档创建称为重跑。精确映射、对象检查与fetch/独立checkout/复验命令见 [source-history/README.md](source-history/README.md) 与 `source-history/review-source-map.json`。archive分支须保留。后续检查改在实际已发布PR HEAD执行，避免新增不可达测试源；当前修正候选仍待该实际检查、CI与独立审查。

## 实际发布源复验与祖先绑定归档

Actual tested published Source: a50d2406037a496cb9c46ee359bc9f0e16cb9263；tree8848c545ed2307998c4483672d67c6d0e3685361。正确完整检出后真实14项13退出0、仅coordination=1容量2>1，原始在 test-results/review-published-a50/。同头关联的官方Gate595真实351 passed in 206.46s，全部其他实质步骤及Skip audit成功，整体Gate仍FAIL；完整官方记录在 test-results/review-remote-595/，前一头Gate594在 review-remote-594/。

首次a50检查工作树缺两份source-history文件并保留旧summary，虽然检查返回13零，但源一致性不满足，明确无效、不用作完整发布树验收。原始与实际dirty状态记录保留在 test-results/review-a50-invalid-worktree/。仅恢复三个自身Evidence路径，实际HEAD未变、git diff HEAD零且status空，随后全部14项重新执行；生产代码和旧身份不变。

本次只补自身归档和当前阶段说明；发布时将5dce717置于新提交额外父链，使两个历史快照进入PR的不可变祖先，archive分支仅作辅助。实际发布头必须验证两个祖先/对象/tree、完整14项及其同头351 CI；a50结果不能冒称新归档头重跑。新头结果在后续Completion继续归档，避免要求提交包含自身SHA日志的自引用循环。Completion身份仍PR-73/726870，容量限制不变，业务仍未启动。

## 前向返工范围登记

Current phase: metadata-only review -> blocked; actual base 62d4ef826e0be1acb2839c3f04fe62d1894f9585.

Completion源c5bf真实前4项退出0，history退出1，其余本地检查NOT_EXECUTED。Gate598实际349 passed/2 failed（239.73s），原始见test-results/completion-first-c5bf/。history误把最新Registry.baseSha当首次Reservation基线，与合法Review基线刷新冲突；另一个失败是待测Completion尚无合法完成/PASS证据。当前不声称PASS。只登记自身blocked状态和精确追加history及对应test范围，代码不变、Lease不变、GZ005/政策/Ledger/旧完成不变。新范围实现必须在本登记合入后的独立PR，且再次完整验证/独立审查。

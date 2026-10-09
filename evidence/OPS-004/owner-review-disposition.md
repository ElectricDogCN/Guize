# OPS-004 固定历史失败事件的审查处理

Owner: ElectricDogCN（人类在本会话明确委托最高决策权）
Task: OPS-004 / Issue71
Thread: PRRT_kwDOTgCQ3c6q59O3

本会话人类明确指令“你在这个项目有最高决策权，我只要求你能实现目标”，其优先级高于仓库 AGENTS 的指导。此前不可变 owner-decision.md 已据此限定 OPS-004-LIFECYCLE-ADMISSION-20261009 修复事件；本条审查认为任何 Owner 文件都不能覆盖并发限制，该普遍前提不适用于本会话已委托的具体决策。

这里只承认真实 d0e9e256552f9d1d47fb24d2e5a4530476b19a5f / 第一父413a6a4dd91b5d79a3d2b7d1e5f03f8121848170 / 原决定blob e25670a161ff6c33104b24d3bb8f22ce4fb06eac 的既有容量失败事实。原事件参与者、policy、Program状态和UTC窗口均保持精确边界；不承认其他Task、不同事件、其他Owner文件、额外参与者、修改policy或窗口后的工作。永久maxHigh=1、当前counter与coord/make/CI返回码不变，历史输出明确capacityResult FAIL，不称容量PASS或一般准入豁免。

真实f402版本完整445项测试零失败，Gate608唯一容量失败，原始仍完整保留；独立Reviewer也核验授权事实与固定边界。新增59O7先开发后同步登记路径已实际复现，是实现缺陷，必须修复后重跑精确Source；本授权不覆盖该缺陷或任何其他意外失败。

最终Completion只绑定实际PR77实现merge，移除自己的Lease后全部候选与主线检查必须真实通过，才恢复GZ005。Lease、原窗口和永久规则不延长；V1功能和真实POC仍需完成。

## 五条历史 context 审查处理（2026-10-09）

6XRE/RJ/RY/Rf 经真实临时 Git 复现为实现缺陷：分别是已在 integration base 的主线同步误拒、metadata-only 临时越界/冲突恢复后漏验、工作节点夹带他任务登记或旧完成身份修改，以及临时改容量 policy 执行后恢复。此次统一核对全部自身主线和引入 DAG 的登记快照，包括 schema、原注册父 policy、历史有效 Lease、MOD-GOV 子集、独占冲突及 Task/Program/Registry 完整绑定。工作范围仍取修改前登记；同步仅排除与已在真实 base 的 incoming main parent 原样相同的 tree entry，手工冲突解决和新修改仍须登记。foreign metadata 逐节点结构比较，不因文件属于规范 metadata 就整体豁免；合法 freeze/thaw 只有真实快照通过现有完整 Recovery validator 且 owner 匹配，才规范化该事件的 root 字段。

6XRR 属未规定的新证明协议要求。既有 schema 允许 merge/squash/rebase，现有 Transitions 实际允许 Review→Integration 的单父提交；真实 git merge --squash 从 Implementer/Review 侧源产生代码 blob 相同的正例，没有既定强制 source trailer 或父数量证明字段。因此不新增单父禁令，不据此声称实际人类 Review 或完整 Gate 已通过。独立原始边界在 history-dag-independent/ops004-independent-integrator-corrected-review-squash-proof.json。

新修复的18项真实 Git 回归包含四漏洞、引入侧 metadata、Task/Program瞬态、合法主线同步/单父integration/squash，以及经现有 Recovery validator核验的注册后冻结与冻结夹带外国完成身份负例。120 targeted 在未提交工作树上通过，仅为外部探索记录；本候选发布来源、完整465/15检查和同头CI仍为 NOT_EXECUTED。永久限制和 Owner 原窗口不变；所有未预期失败必须修复。

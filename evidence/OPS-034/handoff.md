# OPS-034 规划实施交接

- [Issue #337](https://github.com/ElectricDogCN/Guize/issues/337)，当前为 in_progress／implementer，工作分支 `chore/OPS-034-v1-core-planning`，实际登记父 `2fc6778ec0389cede37855a456202ce4ce019856`。
- 激活提交 `132b4c4e502608992740e603e0d2c98478d7fc22`，固定受检实施源 `2add3ca389c3aecfeb8366f804ad5b5f61469712`。本交接的补证只写自身 Evidence，最新源和完整官方结果由同头 PR 记录绑定。
- 仅独占 `specs/coordination/program-plan.yaml`，无共享路径，集成序号 26，租约保持至 2026-12-04T07:21:42Z。角色与契约版本见历史登记。
- [实际范围](changed-files.md) · [12 项实测命令及退出码](commands.txt) · [实测原始回执](test-results/implementation-2add3ca3-controls.json)。固定受检源 12 项原生 Linux 控制均退出 0，回执 SHA-256 `db0d1f794d880f31935887bdd4ab0e3c1cb3a2b11a7abaadac79210015c0d226`。

## 当前实施与限制

实际登记主线 `2fc6778ec0389cede37855a456202ce4ce019856` 已通过 [#1207](https://github.com/ElectricDogCN/Guize/actions/runs/45968460367) 和独立终验。独立回执 SHA-256 `da4d12c0762ff801caa08bbdcc939fba4172fe462969213f81843ea1186d1e8b`。工作分支的精确激活提交为 `132b4c4e502608992740e603e0d2c98478d7fc22`。

按 [原始声明](v1-implementation-split.json) 加入 GZ-031 与父任务 GZ-012 的一条依赖。原 GZ-012 的业务前置仍适用。GZ-031 只消费已完成的 GZ-008。实际核心启动与插件隔离由其自身登记和产品验收交付，当前规划实施精确 Git 头由 PR 与执行回执绑定。

隔离演练使用 #341 固定 GitHub 预览，实际执行 History、Lifecycle、Coordination、Scope、Readiness 五项且均退出 0。演练回执 SHA-256 `309b2acc0c1611b445f237f6b236864eb9e8fb5c4d527d7181cc3abe9e303e92`。正式实施使用精确源、完整官方 CI、独立审核以及实际主线门禁。

未合入时可以撤回实施候选，保留原登记和原始证据。实施受验后可通过正常规划修订撤回后继变更，保留原始声明及历史。Reviewer 核对提交、依赖和实际结果。Integrator 在完整官方 CI 与独立审核后集成并复核实际主线，再处理本任务的常规 Review 与 Completion。

## 历史登记交接

以下记录对应原登记阶段与当时受检源，保留当时角色、登记父和出口。

- [Issue #337](https://github.com/ElectricDogCN/Guize/issues/337)，工作分支 `chore/OPS-034-v1-core-planning`，登记父 `1fc3a8f52d58220a5047460441b16eab7e03fae7`。初始登记源码由下方固定 Git 提交和回执绑定。
- Owner 为 ElectricDogCN，Coordinator、Implementer、Integrator 为 `/root`，独立 Reviewer 为 `/root/independent_review`。集成序号 26，租约截至 `2026-12-04T07:21:42Z`，无共享路径。Task Spec schemaVersion 2，Program 与 Registry schemaVersion 1，声明 schemaVersion 2。
- 只登记自身并绑定 [原始声明](v1-implementation-split.json)。[实际文件](changed-files.md) · [执行命令与退出码](commands.txt)
- Reviewer 核对固定父、未启动定义和实际检查。Integrator 以完整官方 CI 和实际登记主线验收。Implementer 只在受验登记后启用任务，随后才修改 Program 定义。撤回通过正常生命周期办理，保留原始声明。

### 已受验登记父

OPS-033 正常结项实际主线 `1fc3a8f52d58220a5047460441b16eab7e03fae7` 已独立完成终验。实际主线 [CI #1205](https://github.com/ElectricDogCN/Guize/actions/runs/45962756356) 五个作业和 1,101 项用例通过。独立回执 SHA-256 `801d18f17eeb079c2a81a7a42391afc42902d7424c9cf4bc48ea1d3daf450889`。该回执允许按正常流程开启新登记。

### 实测与限制

初始固定登记源码 `9221962924a92c2a6b12ce066d9e794b4b2ef47e` 的 13 项原生 Linux 门禁全部退出 0。[完整命令与退出码](commands.txt) · [初始实测原始回执](test-results/initial-reservation-controls.json)。回执 SHA-256 为 `41fdd415e5237a7978ca355e2560047f1b9a71ddc540f901adc602e0b0b19e9f`。

后继提交补齐本任务的交接和真实证据。原始声明、Program 和 Registry 字节沿用上述受检提交。最新登记源由 PR 的 Git 头与精确检查回执绑定。正式官方 CI、同头终审、实际主线复验以及 GZ-031 的依次登记与运行验收各自独立执行。

### 回滚与承接

候选尚未合入时，关闭候选 PR 并核对旧头后清理其远端分支，保留固定来源和证据。登记合入后，按正常取消流程释放本任务自己的 Registry 记录和写入权限。共享计划其他记录及原始声明须保留。若实施尚未开始，回滚不涉及 GZ-012、GZ-031 的控制面行为或部署环境。

Reviewer 验证最新固定源与初始受检源码之间仅有此任务 Evidence 附记。Integrator 在完整官方 CI 和独立终审成功后正常合并并验证实际主线。Implementer 在受验登记主线后按 Task Spec 激活 OPS-034，再实施声明范围内的规划拆分。

## 正常 Review 移交

实施 [PR #342](https://github.com/ElectricDogCN/Guize/pull/342) 已普通合入 `74d653e0d1bf723382b8879f746973371216443e`。实际双父与文件树匹配固定受审预览。官方 #1208/#1209 的 1,101 个用例逐项一致，实际最长作业 1018 秒。Windows 原生实际主线 14 项本地检查通过，取得独立终验。[实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45974551103) · [独立终验原件](implementation-main-74d653e0/independent-review.original.json) · [本地检查公开摘要](implementation-main-74d653e0/actual-main-controls.summary.json)

Reviewer 验证固定 Review 源及实际合入。Integrator 在双侧完整官方 CI 和实际终验后推进结项 #337，再释放本任务分支和租约。

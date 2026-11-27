# OPS-034 登记交接

- [Issue #337](https://github.com/ElectricDogCN/Guize/issues/337)，工作分支 `chore/OPS-034-v1-core-planning`，登记父 `1fc3a8f52d58220a5047460441b16eab7e03fae7`。初始登记源码由下方固定 Git 提交和回执绑定。
- Owner 为 ElectricDogCN，Coordinator、Implementer、Integrator 为 `/root`，独立 Reviewer 为 `/root/independent_review`。集成序号 26，租约截至 `2026-12-04T07:21:42Z`，无共享路径。Task Spec schemaVersion 2，Program 与 Registry schemaVersion 1，声明 schemaVersion 2。
- 只登记自身并绑定 [原始声明](v1-implementation-split.json)。[实际文件](changed-files.md) · [执行命令与退出码](commands.txt)
- Reviewer 核对固定父、未启动定义和实际检查。Integrator 以完整官方 CI 和实际登记主线验收。Implementer 只在受验登记后启用任务，随后才修改 Program 定义。撤回通过正常生命周期办理，保留原始声明。

## 已受验登记父

OPS-033 正常结项实际主线 `1fc3a8f52d58220a5047460441b16eab7e03fae7` 已独立完成终验。实际主线 [CI #1205](https://github.com/ElectricDogCN/Guize/actions/runs/45962756356) 五个作业和 1,101 项用例通过。独立回执 SHA-256 `801d18f17eeb079c2a81a7a42391afc42902d7424c9cf4bc48ea1d3daf450889`。该回执允许按正常流程开启新登记。

## 实测与限制

初始固定登记源码 `9221962924a92c2a6b12ce066d9e794b4b2ef47e` 的 13 项原生 Linux 门禁全部退出 0。[完整命令与退出码](commands.txt) · [初始实测原始回执](test-results/initial-reservation-controls.json)。回执 SHA-256 为 `41fdd415e5237a7978ca355e2560047f1b9a71ddc540f901adc602e0b0b19e9f`。

后继提交补齐本任务的交接和真实证据。原始声明、Program 和 Registry 字节沿用上述受检提交。最新登记源由 PR 的 Git 头与精确检查回执绑定。正式官方 CI、同头终审、实际主线复验以及 GZ-031 的依次登记与运行验收各自独立执行。

## 回滚与承接

候选尚未合入时，关闭候选 PR 并核对旧头后清理其远端分支，保留固定来源和证据。登记合入后，按正常取消流程释放本任务自己的 Registry 记录和写入权限。共享计划其他记录及原始声明须保留。若实施尚未开始，回滚不涉及 GZ-012、GZ-031 的控制面行为或部署环境。

Reviewer 验证最新固定源与初始受检源码之间仅有此任务 Evidence 附记。Integrator 在完整官方 CI 和独立终审成功后正常合并并验证实际主线。Implementer 在受验登记主线后按 Task Spec 激活 OPS-034，再实施声明范围内的规划拆分。

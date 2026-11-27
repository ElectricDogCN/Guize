# OPS-033 登记交接

- Task 为 OPS-033，基础主线为 `4aa7402d5a45555fa1c063ec6366c4efd8f5c33f`，工作分支为 `chore/OPS-033-v1-split-reservation`。[问题记录 #331](https://github.com/ElectricDogCN/Guize/issues/331)
- 任务所有者为 ElectricDogCN，Coordinator、Implementer 和 Integrator 为 `/root`，独立 Reviewer 为 `/root/independent_review`。
- 本次登记的初版固定提交为 `b54476514db1531c16d50ec22274044b82605292`。当前增补仅完善交接及命令日志，14 条实际登记路径见 [变更路径](changed-files.md)。
- 使用 Program Plan 与 Active Work schemaVersion 1，以及 Task Spec schemaVersion 2。后续机制修订使用正式定义的计划声明，当前登记保持一期和 Agent Edge 的既有范围定义。
- 十一条已运行的固定初版验证命令及退出码见 [执行记录](commands.txt)。既有范围的两条拒绝已针对当前主线复现。[原范围观测](test-results/current-scope-guard.json)
- 集成顺序为 25，租约到期为 `2026-12-04T03:09:05Z`。本任务无共享路径。具体的七项未来独占路径见 [任务说明](../../specs/tasks/OPS-033.md)。
- 本次预留仅登记执行范围。官方 CI、合并后主线复验和实施验收会分别留下自己的证据。
- 登记前可撤回候选。登记合入后采用独立的治理撤回或正常释放流程，保留已形成的证据。
- Reviewer 核对固定头、原证据和当前登记，官方 CI 通过后按同头审查。Integrator 复验审查过的合并树及实际主线。Implementer 从实际合并且已验收的主线另建实施分支，按任务独占范围推进。

## 实施启用

实际登记主线 `fd90de5d1244efc016eb5871a7011704c889299f` 已完成独立复验。当前工作分支为 `chore/OPS-033-v1-split-admission`。角色、租约和独占范围沿用登记。先启用本任务，再提交可核验的实现和回归。

[实际主线 CI #1196](https://github.com/ElectricDogCN/Guize/actions/runs/45935458155)

## 实施候选

从启用提交 `76bf435d3e8287d271f77c620c430b867e35f2a7` 推进。实现涉及两个治理校验器、两份 schema、治理说明和两组回归。实现通过独立的原始声明绑定实施任务与父任务，并验证父任务依赖、原有范围与 GZ-020 最终闭合。当前计划数据只包含本任务的启用元数据。

Windows 本地定向测试通过 15 项。完整收集为 1,101 项，逐项保留此前的 1,093 项并新增 8 项验证。保持官方作业时限。继续核对保留的现有规划机制、固定候选的路径和历史，再提交完整官方 CI。[命令和结果](commands.txt)

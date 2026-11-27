# OPS-033 历史缓存校验补充登记

- Task `OPS-033`，Issue [#331](https://github.com/ElectricDogCN/Guize/issues/331)，本次提交分支 `chore/OPS-033-history-pin-scope`，唯一父为实际主线 `fd90de5d1244efc016eb5871a7011704c889299f`。本次候选提交从 Git PR 固定头解析。Registry 的原预留分支 `chore/OPS-033-v1-split-reservation` 仍处于 reserved/coordinator。
- Owner 为 ElectricDogCN，Coordinator、Implementer、Integrator 为 `/root`，独立 Reviewer 为 `/root/independent_review`。集成序号 25，租约截至 `2026-12-04T03:09:05Z`。无共享路径。沿用 Program Plan 与 Active Work schemaVersion 1、Task Spec schemaVersion 2。
- 本次变更六个自身 Registry、Task 与 Evidence 文件，逐文件路径见[变更清单](changed-files.md)。八项后续独占范围和本次保护的实际 Git 对象见[范围记录](history-cache-scope-amendment-v1.json)。第八项为 `scripts/check-program-plan-history.py`，顺序与 Task 独占路径一致。
- 前一实施候选 `1a6165051d1ccfffae657b82afc48f835880487f` 的官方 #1197 已失败，分片 1 有六项既有缓存测试因输入版本未列入精确指纹而落回常规校验。补齐精确指纹后的隔离实验中，六项定向测试退出 0。该实验属于后续实现的诊断；本次登记没有写入代码。[失败分片](https://github.com/ElectricDogCN/Guize/actions/runs/45939824377/job/140311321246)
- `git diff --check`、`python -B scripts/check-task-file.py --task OPS-033`、`python -B scripts/check-evidence.py --task OPS-033`、`python -B scripts/check-schemas.py` 在本次候选工作树退出 0。固定提交提交后重验 Program 历史与生命周期、协作和作用域。原始登记命令仍可从[历史记录](commands.txt)查阅。
- Reviewer 核对注册顺序、元数据范围、角色、租约和固定源完整官方 CI。Integrator 只合入确切受审源，再复验实际第一父主线。实际登记接受后，Implementer 从新主线单独提交激活与兼容性代码修复，保留原测试和每作业 30 分钟。撤回本次候选可关闭 PR；已合入按正式范围撤回保留证据历史。

## 原登记的历史记录

- Task 为 OPS-033，基础主线为 `4aa7402d5a45555fa1c063ec6366c4efd8f5c33f`，工作分支为 `chore/OPS-033-v1-split-reservation`。[问题记录 #331](https://github.com/ElectricDogCN/Guize/issues/331)
- 任务所有者为 ElectricDogCN，Coordinator、Implementer 和 Integrator 为 `/root`，独立 Reviewer 为 `/root/independent_review`。
- 本次登记的初版固定提交为 `b54476514db1531c16d50ec22274044b82605292`。当前增补仅完善交接及命令日志，14 条实际登记路径见 [变更路径](changed-files.md)。
- 使用 Program Plan 与 Active Work schemaVersion 1，以及 Task Spec schemaVersion 2。后续机制修订使用正式定义的计划声明，当前登记保持一期和 Agent Edge 的既有范围定义。
- 十一条已运行的固定初版验证命令及退出码见 [执行记录](commands.txt)。既有范围的两条拒绝已针对当前主线复现。[原范围观测](test-results/current-scope-guard.json)
- 集成顺序为 25，租约到期为 `2026-12-04T03:09:05Z`。本任务无共享路径。具体的七项未来独占路径见 [任务说明](../../specs/tasks/OPS-033.md)。
- 本次预留仅登记执行范围。官方 CI、合并后主线复验和实施验收会分别留下自己的证据。
- 登记前可撤回候选。登记合入后采用独立的治理撤回或正常释放流程，保留已形成的证据。
- Reviewer 核对固定头、原证据和当前登记，官方 CI 通过后按同头审查。Integrator 复验审查过的合并树及实际主线。Implementer 从实际合并且已验收的主线另建实施分支，按任务独占范围推进。

## 补充范围后的实施启用

实际范围主线 `c21dcba7844b448d523bdd40a13084471a082544` 已完成完整官方 #1199 和独立终验，1,093 项测试与 #1198 逐项相同。工作分支 `chore/OPS-033-v1-split-admission-v2` 从该主线独立启用，保留原协作身份、租约、八条独占写路径及共享边界。先提交这次纯元数据启用，再提交实现和回归。

[实际主线 CI #1199](https://github.com/ElectricDogCN/Guize/actions/runs/45943874154)

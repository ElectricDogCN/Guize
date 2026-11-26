# OPS-032 登记交接

实际基线 `29a59614a63e646060a9d2df9dba284037ffc132`，分支 `chore/OPS-032-poc-actor-reservation`，关联 [Issue #324](https://github.com/ElectricDogCN/Guize/issues/324)。任务预留一个 high 名额。实现者与集成人为 `/root`，独立审核人为 `/root/independent_review`。无共享写入范围。

两项 reserved POC 的正式身份检查在基线复现失败。[原始登记声明](reservation-intent.json) 记录两项目标、当前 Task 与 Registry、预期实际身份和精确实施路径。登记阶段仅包含本任务元数据。登记正式接受后，实施独立前瞻认证并验收真实 Git 正反例。

登记或后继阶段失败时，依协调协议撤回或前向修复并保留原件。

## 预审与后续动作

原始登记候选为 `72318f2753bf92991fa5b308e270ea433b581f4e`。本次补记交接沿用同一真实父基线和声明。精确路径在 [变更清单](changed-files.md)，实际验证命令和退出记录在 [命令记录](commands.txt)。

登记沿用 Program Plan、Active Work v1、Task Spec v2 和 OPS-015 现行身份修订协议。正式 POC 验收仍使用 POC-PROTOCOL-V1。租约从 `2026-11-26T21:55:43Z` 到 `2026-12-03T21:55:43Z`，集成顺序为 24。潜在影响仅是两个目标登记的具体角色，按批准身份事务分开交付，两项 POC 预检原件继续保留。

独立 reviewer 核对本候选的精确源、三条声明路径、两项原始登记及官方 CI。Integrator 在同头独立接受和完整官方 CI 成功后，以正常登记合并方式合入，并复验实际主线。只有实际登记主线接受后才启动实施。

## 登记格式复验

[官方 CI #1182](https://github.com/ElectricDogCN/Guize/actions/runs/45901797244) 从首候选发现任务验收复选框、验证命令和两段协作说明缺失。Task Spec 的带引号租约值与 Active Work 在文本校验中的读值也不相同。按现有任务模板补齐章节，租约时间沿用原值并去掉 Task Spec 中的引号。受影响的 Task File 与 Schema 两项在修订后的工作树均正常退出。精确声明、任务目标和登记时间范围保持原有内容。新提交须重新接受完整官方检查。

## 实施激活

实际预留主线 `5d89ae71542be66a7eda3eb02aec89623d086b24` 的两父和树与登记审查一致。主线 [CI #1184](https://github.com/ElectricDogCN/Guize/actions/runs/45904452258) 五作业成功，原 1,090 项逐项一致，最长 1,025 秒。实际主线九项本地验证及独立终验通过，独立终验回执 SHA-256 为 `86d4ad36764867960edbeb66e4a59f68c33279fe27aad1d1a6aca67a3da7eb18`。

工作分支 `chore/OPS-032-poc-actor-repair` 以该实际预留为基线。激活提交仅改变本任务状态、当前职责、工作分支与基线元数据。实施采用原始登记声明的三个治理路径，精确的 POC 角色事务另行提交。

## 实施与验证

- `scripts/reservation-role-amendment.py` 区分原 OPS-015 与本次 OPS-032 的实际主线准入，两组复用同一实际实现、Review、Completion 及事务校验。OPS-032 从固定登记读取每项 POC 的旧 Task 和 Registry 摘要、待批准角色对。
- `tests/governance/test_reservation_role_amendment.py` 以隔离 Git 历史验证两项目标的正式前瞻事务、尚未结项时的拒绝、其他目标的拒绝和同提交补批准的拒绝。三个新增用例在本地全部通过。
- `rules/reservation-role-amendment.md` 记录两项准入的关系、固定声明、事前批准和后续执行要求。

发布前完成既有 OPS-015 事务及自动导入复验、任务范围和生命周期检查。独立 Reviewer 随后对固定源核验，完整官方源 CI 和实际主线终验继续按原工作流执行。

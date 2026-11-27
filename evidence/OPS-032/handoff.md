# OPS-032 交接

## 当前正常结项候选

结项分支是 `chore/OPS-032-normal-completion`，目标基线是正式审查的实际主线 `6625b8e84e011298f2ba2365c75d921dd9e99cbf`。实施身份为 [PR #326](https://github.com/ElectricDogCN/Guize/pull/326) 和合并 `b5157a68fa16d83fc2fa44395b95cb15b3d67a35`。[Issue #324](https://github.com/ElectricDogCN/Guize/issues/324) 已以 completed 关闭。责任人为 ElectricDogCN，实施及合入由 `/root` 承担，独立审查人为 `/root/independent_review`。候选仅移除自身登记及其租约，原两项 POC 的租约与共享顺序不变。

本次实际变更九个文件。

- `evidence/OPS-032/commands.txt`
- `evidence/OPS-032/handoff.md`
- `evidence/OPS-032/summary.md`
- `evidence/OPS-032/test-results/README.md`
- `evidence/OPS-032/accepted-review-6625b8e8/actual-main-controls.original.json`
- `evidence/OPS-032/accepted-review-6625b8e8/independent-review.original.json`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/OPS-032.md`

实际审查主线的完整官方 #1188、九项已执行本地命令和独立终验均通过。固定结项提交由 PR 头和 [命令记录](commands.txt) 确定。登记 Reviewer 核对该提交的完整官方 CI，Integrator 在同头终审接受后按精确头普通合入。完成实际结项主线复验后，Integrator 按登记释放结果清理已结束远端分支，再分别处理两个 POC 的事前身份批准。结项候选如需修正，仅更新自身元数据和证据，保留已接受的实施和审查原件。

## 原始登记交接

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

### 实施路径和检查记录

代码检查绑定提交 `1bd088d628c6b78c31f9b8261b00a3da97f3d1bc`，基线 `5d89ae71542be66a7eda3eb02aec89623d086b24`。

- `evidence/OPS-032/handoff.md`
- `rules/reservation-role-amendment.md`
- `scripts/reservation-role-amendment.py`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/OPS-032.md`
- `tests/governance/test_reservation_role_amendment.py`

本地输出记录新增用例 3 通过（38.27 秒）。旧身份事务及自动导入代表性复验 3 通过（286.16 秒）。同版 Python 的收集清单保留原 1,090 项并新增 3 项，集合 SHA-256 为 `e7d41043d192ee6e12fe6b7a1b52c0cf63118c5a4786a632da8673a14a07c157`。Task、Schema、Transitions、History、Lifecycle、Finalization、Coordination、Scope、Evidence 和 Markdown 检查均成功。

```bash
B=5d89ae71542be66a7eda3eb02aec89623d086b24
BRANCH=chore/OPS-032-poc-actor-repair
python scripts/check-task-file.py --task OPS-032
python scripts/check-schemas.py
python -B -m pytest -q -p no:cacheprovider tests/governance/test_reservation_role_amendment.py -k remaining
python -B -m pytest -q -p no:cacheprovider tests/governance/test_reservation_role_amendment.py -k 'original_metadata_transaction_and_real_callers or two_accepted_poc_actor_updates_import_into_real_feature_and_callers'
python -B -m pytest --collect-only -q --color=no -p no:cacheprovider tests/governance/
python scripts/check-program-plan-transitions.py --base-ref "$B" --head-ref HEAD --task OPS-032 --branch-name "$BRANCH"
python scripts/check-program-plan-history.py --base-ref "$B" --head-ref HEAD --task OPS-032 --branch-name "$BRANCH"
python scripts/check-program-lifecycle-guards.py --base-ref "$B" --head-ref HEAD --task OPS-032 --branch-name "$BRANCH"
python scripts/check-program-plan-finalization.py --base-ref "$B" --head-ref HEAD --task OPS-032
python scripts/run-agent-coordination-gate.py --task OPS-032 --base-ref "$B" --head-ref HEAD --branch-name "$BRANCH"
python scripts/run-task-scope-gate.py --task OPS-032 --base "$B"
python scripts/check-evidence.py --task OPS-032
python scripts/check-markdown.py
git diff --check
```

## 正式审查

实施 PR #326 已普通合入 `b5157a68fa16d83fc2fa44395b95cb15b3d67a35`。实际主线的两个父及 Git 树与受审预览一致。完整官方 CI 五个作业成功，1,093 个用例逐项匹配实施源，原 1,090 项和新增 3 项均通过。九项实际主线本地检查和独立终验通过。[实施 PR #326](https://github.com/ElectricDogCN/Guize/pull/326) · [实施源 CI #1185](https://github.com/ElectricDogCN/Guize/actions/runs/45907875309) · [实际主线 CI #1186](https://github.com/ElectricDogCN/Guize/actions/runs/45910015098)

[独立终验原件](implementation-main-b5157a68/independent-review.original.json) · [九项本地检查原件](implementation-main-b5157a68/actual-main-controls.original.json)。源与实际审查主线完成同头验收后，提交结项并释放登记。两项 POC 的事前批准与身份事务随后分别办理。

## OPS-032 正常结项

OPS-032 结项绑定实施 PR #326 的实际合并 `b5157a68fa16d83fc2fa44395b95cb15b3d67a35`。正式审查 PR #327 的实际主线 `6625b8e84e011298f2ba2365c75d921dd9e99cbf` 已通过实际检查、官方 #1188 的 1,093 项及独立终验。Issue #324 按正常流程关闭为 completed。本提交释放自身活动登记，按新固定源及实际结项主线完成完整官方 CI 后验收。两项 POC 的事前批准与身份修订分别实施。[实际 Review CI #1188](https://github.com/ElectricDogCN/Guize/actions/runs/45914688074)

Status: PASS

Source Commit: 6625b8e84e011298f2ba2365c75d921dd9e99cbf
Command: python -B scripts/check-program-plan-integrity.py --base-ref b5157a68fa16d83fc2fa44395b95cb15b3d67a35
Exit Code: 0
Result: PASS
Raw SHA-256: 783a7ac8c3dcc239ff4d8a8b80c4836dbf3e0bd2c4cf0d845a12ef6076ee6ce3

[独立终验原件](accepted-review-6625b8e8/independent-review.original.json) · [实际本地检查原件](accepted-review-6625b8e8/actual-main-controls.original.json)

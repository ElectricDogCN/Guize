# GZ-007 正常结项交接

结项基线为 506cfcdc271cc0417bb91cc0bb72eeda2bed6f5c，分支 chore/GZ-007-normal-completion。集成人只处理 GZ-007 的状态和登记释放。[实际 Review 主线 CI #1170](https://github.com/ElectricDogCN/Guize/actions/runs/45855691281)

## 已接受的正式审查交接

- GZ-007 对应 [Issue #287](https://github.com/ElectricDogCN/Guize/issues/287)。正式审查使用工作分支 `chore/GZ-007-data-contract`，当前审查基线为实际主线 `e0ded7aeacd749f60bdcf9838a0f8c96ce8e1416`。正式审查提交由本轮 Review PR 的 Head 定位。原登记主线 `0cde7c3b886617dfbb89bedff0679a351e4cd970` 与实施集成基线 `4c83731f60449abd1749cb2be1568c195f42f443` 留在历史记录。[登记 PR #309](https://github.com/ElectricDogCN/Guize/pull/309) · [当前集成基线 CI #1168](https://github.com/ElectricDogCN/Guize/actions/runs/45851386217)
- 第一轮实测源为 `7cc455283a19125cb0ac6d2fa1d63d594b4deed6`。第 12 条迁移和来源配置专项实测源见 [V12 身份记录](test-results/v12-source-location/identity.txt)。[实施 PR #313](https://github.com/ElectricDogCN/Guize/pull/313) 的已审实施源为 `099435ccbbedeca5e89dfe43877135fbae476390`。
- 工作包 WP-M0-03D，执行波次 W3，集成顺序 4，独占范围为 `contracts/data/**`、`data/migrations/**`、`specs/contracts/data/**` 和 `evidence/GZ-007/**`。本轮变更仅涉及正式审查状态及自有证据。用 `git diff --name-only e0ded7aeacd749f60bdcf9838a0f8c96ce8e1416...HEAD` 核对范围。[变更分类](changed-files.md)
- 负责人 ElectricDogCN。协调、实施、独立审查与集成角色分别为 `program-coordinator-agent`、`task-owner-agent`、`independent-review-agent`、`integration-agent`。活动租约截止 `2026-12-03T10:08:10Z`。[任务说明](../../specs/tasks/GZ-007.md)
- GZ-004、005、006 已进入基线。输入为 [REQ-V1](../../specs/requirements/v1/requirements.yaml)、[OPENAPI-V1](../../contracts/openapi/common/openapi.yaml)、[EVENT-CATALOG-V1](../../contracts/events/catalog.json) 及 [领域模型](../../docs/05-domain-and-data-model.md)。产出 DATA-SCHEMA-V1 和 MIGRATION-PLAN-V1。[数据契约](../../contracts/data/README.md)

## 复核与下一角色动作

实施 PR #313 普通合入 `2733a8181e3e22a4a80b8d1097ab965bfeee8b6a`。实际主线保留受审树，七项本地检查、完整官方 1,090 项和独立终验通过。此轮办理 GZ-007 正式审查，作业证据绑定实际主线。[实施 PR #313](https://github.com/ElectricDogCN/Guize/pull/313) · [实际主线 CI #1166](https://github.com/ElectricDogCN/Guize/actions/runs/45846364097)

正式审查对照 [实际主线独立回执](implementation-main-2733a818/independent-review.json) 与 [七项主线检查](implementation-main-2733a818/source-controls.json)。审查人核对同头门禁及证据。实际 Review 主线通过完整复验后，集成人另提交 Completion，引用已接受的实施与 Review，释放 GZ-007 自身登记。

PostgreSQL 16.15 和 Flyway 13.12.1 已完成 V1 至 V11 新库、升级、严格校验、事务回滚、真实并发及备份恢复。V12 完成新库、V11 升级、来源配置提交后重读及备份恢复。核对 [执行上下文](commands.txt)、[实际结果](test-results/README.md)、[V11 证据清单](test-results/v11-native/SHA256SUMS.txt) 和 [V12 证据清单](test-results/v12-source-location/SHA256SUMS.txt)。

数据库维护角色通过备份恢复或前向修订处理已应用迁移。生产数据、真实外部数据库、对象存储、搜索集群、供应商、权限执行和 Worker 联调在各消费模块按对应任务验收。

## 结项验收

Status: PASS

此状态对应实际 Review 主线 `506cfcdc271cc0417bb91cc0bb72eeda2bed6f5c` 的验收。

[实际 Review 独立回执](accepted-review-main-506cfcdc/independent-review.json) · [实际 Review 七项检查](accepted-review-main-506cfcdc/source-controls.json)

本候选须通过完整官方 CI 和同头独立审查，合入后复验实际结项主线，再清理对应远端分支。

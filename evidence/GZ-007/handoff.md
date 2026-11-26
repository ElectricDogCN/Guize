# GZ-007 实施交接

- 本任务为 GZ-007，跟踪 [Issue #287](https://github.com/ElectricDogCN/Guize/issues/287)。工作分支 `chore/GZ-007-data-contract`，已同步待集成主线 `4c83731f60449abd1749cb2be1568c195f42f443`。登记与实施基线 `0cde7c3b886617dfbb89bedff0679a351e4cd970`。[登记 PR #309](https://github.com/ElectricDogCN/Guize/pull/309) · [当前基线 CI #1162](https://github.com/ElectricDogCN/Guize/actions/runs/45812482874)
- 第一轮实测源为 `7cc455283a19125cb0ac6d2fa1d63d594b4deed6`，第 12 条迁移和来源配置专项实测源见 [V12 身份记录](test-results/v12-source-location/identity.txt)。完整交付版本以实施 PR 当前 Head 和同头检查定位。
- 工作包 WP-M0-03D，执行波次 W3，集成顺序 4，独占范围为 `contracts/data/**`、`data/migrations/**`、`specs/contracts/data/**` 和 `evidence/GZ-007/**`。含数据契约、12 个迁移、SQL 校验、任务专属证据和 3 个仅承载 GZ-007 自有状态转移的协调文件。文件清单可用 `git diff --name-only 4c83731f60449abd1749cb2be1568c195f42f443...HEAD` 取得。[变更分类](changed-files.md)
- 负责人 ElectricDogCN。协调、实施、独立审查与集成角色分别为 `program-coordinator-agent`、`task-owner-agent`、`independent-review-agent`、`integration-agent`。活动租约截止 `2026-12-03T10:08:10Z`。[任务说明](../../specs/tasks/GZ-007.md)
- GZ-004、005、006 已进入基线。输入为 [REQ-V1](../../specs/requirements/v1/requirements.yaml)、[OPENAPI-V1](../../contracts/openapi/common/openapi.yaml)、[EVENT-CATALOG-V1](../../contracts/events/catalog.json) 及 [领域模型](../../docs/05-domain-and-data-model.md)。产出 DATA-SCHEMA-V1 和 MIGRATION-PLAN-V1。[数据契约](../../contracts/data/README.md)

## 复核与下一角色动作

PostgreSQL 16.15 和 Flyway 13.12.1 已完成 V1 至 V11 新库、升级、严格校验、事务回滚、真实并发及备份恢复。V12 完成新库、V11 升级、来源配置提交后重读及备份恢复。核对 [执行上下文](commands.txt)、[实际结果](test-results/README.md)、[V11 证据清单](test-results/v11-native/SHA256SUMS.txt) 和 [V12 证据清单](test-results/v12-source-location/SHA256SUMS.txt)。独立审查绑定实施 PR 的最终 Head。完整官方 CI 和同头审查通过后常规合并。实际主线验收后，按正规 Review 和 Completion 记录实际合并证据并释放自身登记。

数据库维护角色通过备份恢复或前向修订处理已应用迁移。生产数据、真实外部数据库、对象存储、搜索集群、供应商、权限执行和 Worker 联调在各消费模块按对应任务验收。

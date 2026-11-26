# GZ-007 登记交接

基线 4337d4a6bb1d4d01d31fa1a5875e2a1056bff9f4。登记分支 chore/GZ-007-data-contract-reservation，实施分支 chore/GZ-007-data-contract。租约 2026-11-26T10:08:10Z 到 2026-12-03T10:08:10Z。

登记阶段提交本任务描述、活动登记和证据目录。实施输出限定为已声明的数据契约、迁移、校验和自有证据。合成样本通过私有 Unix socket 连到隔离 PostgreSQL。生产数据、真实外部数据库与 Worker 数据写入另按各模块契约验收。

- evidence/GZ-007/EVIDENCE-STRUCTURE.md
- evidence/GZ-007/assumptions.md
- evidence/GZ-007/changed-files.md
- evidence/GZ-007/commands.txt
- evidence/GZ-007/follow-ups.md
- evidence/GZ-007/handoff.md
- evidence/GZ-007/risks.md
- evidence/GZ-007/scope.md
- evidence/GZ-007/summary.md
- evidence/GZ-007/test-results/README.md
- specs/coordination/active-work.yaml
- specs/coordination/program-plan.yaml
- specs/tasks/GZ-007.md

独立审查先核对实际源码、范围与全套官方 CI，再复验实际合并主线。实施阶段从验收后的主线继续。未合入候选可撤回。


## 恢复工作所需信息

- 任务为 GZ-007，跟踪 [Issue #287](https://github.com/ElectricDogCN/Guize/issues/287)。上一份本地固定候选为 `5c1d2f969d796ca859c0111979ce5445a26b9d60`。最终发布源由登记分支当前固定提交和该提交的 PR 检查定位。
- 负责人为 ElectricDogCN，协调、实施、独立审查与合入分别由 `program-coordinator-agent`、`task-owner-agent`、`independent-review-agent` 和 `integration-agent` 承担。
- GZ-004、005、006 已完成。输入为 [REQ-V1](../../specs/requirements/v1/requirements.yaml)、[OPENAPI-V1](../../contracts/openapi/common/openapi.yaml)、[EVENT-CATALOG-V1](../../contracts/events/catalog.json) 及 [领域和数据模型](../../docs/05-domain-and-data-model.md)。本工作包产生 DATA-SCHEMA-V1 和 MIGRATION-PLAN-V1。
- 登记使用 W3 集成顺序 4，独占范围见 [Task Spec](../../specs/tasks/GZ-007.md)，共享修改范围为空。实际 13 个登记文件由 [变更清单](changed-files.md) 记录。
- [固定源命令](commands.txt) 和 [验收结果](test-results/README.md) 分别绑定候选和实际合并主线。本修订固定源须重新执行并取得正式 CI 和独立审查。现有 PostgreSQL、Flyway 与合成备份恢复结果只用于环境准备，实际 DDL 与迁移将在实施阶段用隔离数据库验证。
- 独立审查先复核固定提交、依赖及作用域。验收合格后普通合入，再核验实际主线。合入后可按正常取消流程释放自身登记并保留验收记录；已实施的数据变更通过新的前向迁移恢复。

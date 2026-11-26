# GZ-008 登记交接

基线 4b192390c2b0b0697407efa177832dc11ec5437d。登记分支 chore/GZ-008-runtime-contracts-reservation，实施分支 chore/GZ-008-runtime-contracts。租约 2026-11-26T17:09:43Z 到 2026-12-03T17:09:43Z。

登记阶段提交本任务描述、活动登记和证据目录。实施范围为 Workflow、Policy、Worker、Connector 和运行时契约目录。验收使用确定性样本和离线一致性用例。真实设备、平台运行时和各模块联调分别验收。

- evidence/GZ-008/EVIDENCE-STRUCTURE.md
- evidence/GZ-008/assumptions.md
- evidence/GZ-008/changed-files.md
- evidence/GZ-008/commands.txt
- evidence/GZ-008/follow-ups.md
- evidence/GZ-008/handoff.md
- evidence/GZ-008/risks.md
- evidence/GZ-008/scope.md
- evidence/GZ-008/summary.md
- evidence/GZ-008/test-results/README.md
- specs/coordination/active-work.yaml
- specs/coordination/program-plan.yaml
- specs/tasks/GZ-008.md

## 恢复工作所需信息

- 跟踪 [Issue #317](https://github.com/ElectricDogCN/Guize/issues/317)。负责人 ElectricDogCN，协调、实施、独立审查与集成分别由 `program-coordinator-agent`、`task-owner-agent`、`independent-review-agent` 和 `integration-agent` 承担。
- GZ-004、GZ-005、GZ-006、GZ-007 已完成。固定输入为 [REQ-V1](../../specs/requirements/v1/requirements.yaml)、[OPENAPI-V1](../../contracts/openapi/common/openapi.yaml)、[EVENT-CATALOG-V1](../../contracts/events/catalog.json) 和 [DATA-SCHEMA-V1](../../contracts/data/README.md)。 [GZ-007 结项](https://github.com/ElectricDogCN/Guize/pull/319) 与 [实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45862098722) 固定该依赖。
- 登记使用 W5 集成顺序 1。四类契约及独占路径见 [任务](../../specs/tasks/GZ-008.md)。共享写入范围为空。插件使用[既有 Manifest](../../contracts/schemas/plugin-manifest.schema.yaml)。登记只提交上列文件。
- [源码验证命令](commands.txt) 与 [主线复验结果](test-results/README.md) 各自绑定固定提交。现有手机、Windows 和 WSL 原型可作为输入参考。实际硬件性能、生产供应商集成和核心启动由其消费任务验证。
- 登记先通过同头完整官方 CI 和独立审查，再普通合入、复验实际主线，随后开始实施。合入前可撤回候选。合入后使用正常取消流程释放登记并留存验收记录。

## 实施基线

登记 PR #320 的实际主线 `593ad7eea2b4d769b84490db1a98daa92f605c81` 已通过同头独立审查、完整官方 CI 和主线本地验证。实现先固定四类运行时契约及其与数据、事件和公开 API 的关系，再验证各端一致性。节点在线租约和执行租约保持独立，既有 P0 至 P8 优先级与插件 Manifest 继续适用。[登记 PR](https://github.com/ElectricDogCN/Guize/pull/320) · [实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45869097662)

## 消费方验证

编排消费方提供 TASK 已接受的不可变计划和规范化历史。执行器核对活动配置、重放和派发前置条件，通过 TASK 的持久化命令申请状态变更。Policy 消费方从可信存储提供已生效策略摘要、批准与预算快照。Worker 消费方分别提供 IAM 节点在线会话、TASK 尝试租约和输入输出授权，最终接受仍使用 TASK 的事务边界。插件消费方从平台制品锁、现有 Manifest、受信发布证明和本地可读制品计算兼容状态，节点与可选插件故障仅影响相关能力。各集成任务按自己的设备、运行时和发布环境验证真实行为。[本地复现与结果](test-results/README.md)

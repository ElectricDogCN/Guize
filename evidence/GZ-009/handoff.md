# GZ-009 登记交接

## 登记身份

Issue #299，基线 `0ab07018876d0904250399cfe6683ccbd1d3aa9d`，登记分支 `chore/GZ-009-ui-contract-reservation`，工作分支 `chore/GZ-009-ui-contract`。第一份登记源为 `ca110e2a93415085c248a1abf7f69a560d896d93`。修订后的确切审查对象以 [PR #302 的当前源提交](https://github.com/ElectricDogCN/Guize/pull/302/commits) 为准。

协调人 `program-coordinator-agent`，实现人 `task-owner-agent`，独立审核人 `independent-review-agent`，集成人 `integration-agent`。租约从 `2026-11-26T06:15:19Z` 至 `2026-12-03T06:15:19Z`。集成顺序为 2，无共享写入路径。

## 输入与证据

- GZ-004 与 GZ-005 已在基线完成。使用 `REQ-V1`、`OPENAPI-V1` 与 `ERROR-CATALOG-V1`。需求来自 [已冻结规格](../../specs/requirements/v1/requirements.yaml)，接口与错误目录均为 1.0.0。[OpenAPI](../../contracts/openapi/common/openapi.yaml) · [错误目录](../../contracts/openapi/common/errors.yaml)
- [精确 13 路径](changed-files.md) 覆盖本任务登记、任务说明及自有证据。[原生命令、退出码和输出摘要](commands.txt) 绑定首个源提交。[首源官方 CI #1145](https://github.com/ElectricDogCN/Guize/actions/runs/45767115311)
- 首源 `ca110e2a` 的 14 项本地检查均退出 0。独立审查发现首版交接缺少恢复所需的命令、版本和后续动作，本次只补齐交接与命令记录。修订源的正式检查与结论分别绑定 [PR #302 的最新检查](https://github.com/ElectricDogCN/Guize/pull/302/checks)。界面映射和运行期验收尚待实现阶段。

## 交接和回滚

独立审核人核对当前源提交、上一版证据出处、依赖、权威契约和权限输入清单、准确写入范围以及完整官方 CI。集成人在固定源通过审核后普通合并，再复验实际合并主线。实际主线独立接受后，从该主线创建工作分支，逐项冻结页面、操作、API、权限、状态、错误及验收映射。

未合入时撤回登记候选。已合入时按任务流程取消并释放自身登记，保留提交、审查和原运行记录。

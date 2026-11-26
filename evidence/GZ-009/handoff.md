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

## 界面契约实施交接

已接受的登记主线为 `b9d0a3c4d81f57925e733e4ce800bf15694d8af0`。[登记 PR #302](https://github.com/ElectricDogCN/Guize/pull/302) · [登记实际主线 CI #1147](https://github.com/ElectricDogCN/Guize/actions/runs/45770450201)

本任务进入 implementer 阶段。角色、独占范围、集成顺序与原租约保持。工作分支为 `chore/GZ-009-ui-contract`，实施源以 [分支上的当前提交](https://github.com/ElectricDogCN/Guize/commits/chore/GZ-009-ui-contract/) 和同一提交的 PR 为依据。固定输入仍为 REQ-V1、OPENAPI-V1 1.0.0 和 ERROR-CATALOG-V1 1.0.0，使用其已发布验收引用。

实际交付见 [变更清单](changed-files.md)。本地交互契约验证用到的文件如下。

- `docs/ui/README.md` 的 Git 对象为 `4863720b6e116404c8a66c7cbc2b60d9aedf5a5c`。
- `specs/ui/check_contract.py` 的 Git 对象为 `2867f008aa6c4c4201bf3132a3526ef856ecd005`。
- `specs/ui/ui-contract-v1.yaml` 的 Git 对象为 `f30ed124dcbe4535ebe465c57f8a6fb4c4da8f0e`。

- `specs/ui/test_contract.py` 的 Git 对象为 `5a71c46720e05b593f7a458bdee023a7bce1b125`。

[命令与结果](commands.txt) 记录原生检查。独立审查要求复验可以从仓库直接执行，新增七项用例均通过。源提交和实际审查见 [实施 PR #305](https://github.com/ElectricDogCN/Guize/pull/305)。界面映射验证只读取权威契约，运行期交付由后续对应阶段验收。独立审核核对 96 项向页面或节点协议的完整分配、模块状态、权限与错误来源和官方全套验证。合格源正常合并，再复验实际主线。未合入时撤回候选，已合入时按契约版本前向修正或审查回退本任务变更。

## 正式审查交接

工作分支 chore/GZ-009-ui-contract，审查基线为 dc8f7015bbdbb57a60ca49a860659e5b5ac08477。实施源 af1bb8f8f30fb599149fcd717b163b7f9ff2c526，实施实际主线 1862617a41ac12994e2b7c3d8a5b179ab78cd803。保留原租约、独占路径和独立审核角色。

- evidence/GZ-009/changed-files.md
- evidence/GZ-009/commands.txt
- evidence/GZ-009/handoff.md
- evidence/GZ-009/implementation-main-1862617a/independent-review.json
- evidence/GZ-009/implementation-main-1862617a/integrity.txt
- evidence/GZ-009/summary.md
- evidence/GZ-009/test-results/README.md
- specs/coordination/active-work.yaml
- specs/coordination/program-plan.yaml
- specs/tasks/GZ-009.md

Source Commit: 1862617a41ac12994e2b7c3d8a5b179ab78cd803
Command: /var/tmp/guize-ops027-rebased-proof/python/bin/python -B scripts/check-program-plan-integrity.py --base-ref b97135ac94360828e9d29562be593551e231ab30
Exit Code: 0
Result: PASS
Raw SHA-256: 24ebab7037a0b0f28ccfe0f89e03dad3332f28b8adc10396b07c9bd45ccbbba3

[实施 PR #305](https://github.com/ElectricDogCN/Guize/pull/305) · [实施主线完整 CI #1152](https://github.com/ElectricDogCN/Guize/actions/runs/45781198725) · [独立复验](implementation-main-1862617a/independent-review.json)

固定源通过全套官方 CI 和独立审查后合入，随后复验实际主线并进入结项。运行界面在对应实现任务验收。

## 正常结项交接

基线 0cde7c3b886617dfbb89bedff0679a351e4cd970，结项分支 chore/GZ-009-normal-completion，当前角色 integrator。实现身份为 1862617a41ac12994e2b7c3d8a5b179ab78cd803，Review 已接受于 4337d4a6bb1d4d01d31fa1a5875e2a1056bff9f4。只释放 GZ-009 本身的登记，保留已有界面契约。

- evidence/GZ-009/accepted-review-main-4337d4a6/independent-review.json
- evidence/GZ-009/accepted-review-main-4337d4a6/integrity.txt
- evidence/GZ-009/changed-files.md
- evidence/GZ-009/commands.txt
- evidence/GZ-009/handoff.md
- evidence/GZ-009/summary.md
- evidence/GZ-009/test-results/README.md
- specs/coordination/active-work.yaml
- specs/coordination/program-plan.yaml
- specs/coordination/task-completions.yaml
- specs/tasks/GZ-009.md

Source Commit: 4337d4a6bb1d4d01d31fa1a5875e2a1056bff9f4
Command: /var/tmp/guize-ops027-rebased-proof/python/bin/python -B scripts/check-program-plan-integrity.py --base-ref dc8f7015bbdbb57a60ca49a860659e5b5ac08477
Exit Code: 0
Result: PASS
Raw SHA-256: aaf883b593d7eedfa0b1c205a3141a66bfdecb6bfb1400d1bfefdd64ee0616eb

[正式审查 PR #308](https://github.com/ElectricDogCN/Guize/pull/308) · [实际主线 CI #1158](https://github.com/ElectricDogCN/Guize/actions/runs/45803035869) · [独立终验](accepted-review-main-4337d4a6/independent-review.json)

完成 Issue #299 对应结项门禁，使用固定源与实际结项主线的独立审查和完整官方检查。实际运行界面在实施阶段验收。

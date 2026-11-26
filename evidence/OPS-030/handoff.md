# OPS-030 登记交接

## 任务与固定来源

- 任务 OPS-030，跟踪 [Issue #257](https://github.com/ElectricDogCN/Guize/issues/257)。
- 登记分支 `chore/OPS-030-module-dependency-reservation`，工作分支 `chore/OPS-030-module-dependency-admission`，目标 `main`，实际基线 `29b64831411b821b1fe5f69bcbf4fa1c2e4839e9`。
- 固定登记候选由 Git 历史及该分支的官方 PR 识别，接受只绑定实际审查的 SHA。
- 登记租约 `2026-11-26T03:21:57Z` 至 `2026-12-03T03:21:57Z`，Foundation 顺序 24，采用正常 merge。

## 角色与范围

- 负责人 `ElectricDogCN`，协调、实施与集成 `/root`。独立审查 `/root/independent_review`。当前 coordinator。
- 无共享路径。独占路径见 Task Spec。Program Plan 版本 1、Active Work 版本 1，Task Spec schemaVersion 2。
- 保留已合入的前置 [OPS-031 PR #295](https://github.com/ElectricDogCN/Guize/pull/295) 与实际证据历史。

## 实际文件

- `evidence/OPS-030/api-samples/README.md`
- `evidence/OPS-030/assumptions.md`
- `evidence/OPS-030/changed-files.md`
- `evidence/OPS-030/commands.txt`
- `evidence/OPS-030/follow-ups.md`
- `evidence/OPS-030/handoff.md`
- `evidence/OPS-030/migration-report/README.md`
- `evidence/OPS-030/performance/README.md`
- `evidence/OPS-030/risks.md`
- `evidence/OPS-030/rollback-verification/README.md`
- `evidence/OPS-030/scope.md`
- `evidence/OPS-030/screenshots/README.md`
- `evidence/OPS-030/security/README.md`
- `evidence/OPS-030/summary.md`
- `evidence/OPS-030/test-results/README.md`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/OPS-030.md`

## 检查与证据

- 原本地候选 `ee0708195bd358b731cd8344ad4015783f9f284b` 缺少变更清单，`check-evidence.py --task OPS-030` 退出 1。原日志 SHA-256 为 `0d9839ce8978e069a45802746ec662baa16d9110dcb19eec21214030f3a02727`。已补齐清单和交接，当前固定源须重新跑全部检查。
- [真实基线的命令清单](commands.txt)。独立审查核对实际固定提交及退出码，登记 PR 在完整官方 CI 通过后方可合入。目前实际测试结果待验证。
- 现有简单波次复现实验在 Issue #257，GZ-009、POC-008 显式依赖已满足。组合交付仍要求实际契约及 GZ-012 的前端验收。

## 下一角色与回滚

- Reviewer 核对精确范围、身份、租约、基线、依赖及官方原测试。Integrator 在实际源通过后正常合入。实际主线复验后由 Implementer 正常激活。
- 未合入时关闭 PR。已合入时正常取消或回滚自身登记，保留原证据与审批历史。

## 历史审计范围修订

- 源 [PR #297](https://github.com/ElectricDogCN/Guize/pull/297) 的固定候选 `4b4ffbd7519aa0de798fac034752f5624b16cac9` 在后续结项历史路径上存在缺口。现行审计只在有规划清单时调用规划分类器。
- 已复现 `historical_foreign_metadata` 将策略变更判为外部策略修改。此次先在实际基线 `05fb6c55fb2f6c847ccfda9c153026bffa249a04` 登记一条额外的精确路径 `scripts/check-program-plan-history.py`。
- 保留 reserved/coordinator、独立角色、原租约和工作分支。真实写入清单见 [变更清单](changed-files.md)，受保护原件的 Git 对象见 [范围声明](history-scope-amendment-v1.json)。
- 先审核本次登记的固定源码与实际主线，再把工作分支候选基于获准的范围刷新。复验在真实初始登记、实施和后续 Review 历史路径上执行。此次未修改 Program 或代码。

## 实施交接

- 按审查后的范围登记 [PR #300](https://github.com/ElectricDogCN/Guize/pull/300) 的实际主线改动 `2cbd4ae2ec064763a25241f35ca7ffa6ce9bba71` 校验精确新增历史检查路径。保留先前独立审查身份、工作分支和原始租约。
- 初次实施 `4b4ffbd7519aa0de798fac034752f5624b16cac9` 的 [官方 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45754333857) 发现七项原有回归失败。专项复验覆盖六项历史缓存回归、只读结项检查和带真实 Program 差异的历史投影。
- 本地候选 b627f8ce85290c42ef96b2d38ff6c2aeeca21050 的协调检查拒绝 Task 与 Registry 中历史路径清单顺序不一致。原失败日志 SHA-256 773162079f949bc62a802170fc381670f9d9e4265c55dd65fefbed0b26dc9ede。将 Task 两份清单顺序与 Registry 对齐，保留同样八条路径。
- Program 明确选择依赖顺序。历史快照缺省仍用波次检查。已有依赖、契约生产者、路径与并行容量限制继续核验。
- 独立审核验证固定源码、历史实现及实际主线。实施 PR 保留初次候选的官方失败记录。

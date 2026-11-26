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

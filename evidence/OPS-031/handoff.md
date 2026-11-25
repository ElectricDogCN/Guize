# OPS-031 实施交接

任务 OPS-031 对应 [Issue #284](https://github.com/ElectricDogCN/Guize/issues/284)。工作分支 chore/OPS-031-gz007-wave-order，目标 main，实际登记及实施父提交 b789c955c351f85e1de327d9a5040764c2f53643。登记由 [PR #285](https://github.com/ElectricDogCN/Guize/pull/285) 合入。当前源 SHA 以该实施 PR 的 Git 提交记录和相应官方运行为准。公开的登记复验记录及原始完整性日志见 [独立复验原件](accepted-reservation-b789c955/independent-review.json) 与 [完整性日志](accepted-reservation-b789c955/integrity.txt)。

协调、实施与合入由 /root 负责，独立 Reviewer 为 /root/independent_review，当前角色为 implementer。唯一独占路径是 Program Plan，无共享写范围，租约和 Foundation 集成顺序 23 保持登记时原值。Program Plan 版本 1、Task Spec 版本 2、Active Work 版本 1 和原始规划声明版本 1 保持。

本轮实际文件如下。

- `evidence/OPS-031/accepted-reservation-b789c955/independent-review.json`
- `evidence/OPS-031/accepted-reservation-b789c955/integrity.txt`
- `evidence/OPS-031/commands.txt`
- `evidence/OPS-031/handoff.md`
- `evidence/OPS-031/summary.md`
- `evidence/OPS-031/test-results/README.md`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/OPS-031.md`

核心变化为执行原始规划声明，将尚未启动的 GZ-007 调到 W3、集成顺序设为 4。实际依赖、业务范围、两个 POC 以及完整官方 CI 保持。登记父提交的六项任务控制退出 0，工作分支新固定源的本地命令见 [命令记录](commands.txt)。该固定源的全官方 CI、独立审查及合并后的实际主线验证待运行。完成这些检查后，Reviewer 才进入正式 Review。GZ-007 须待规划任务结项后另行登记。当前候选如需撤回可停止合入。已合入后如需恢复排程，按新的正式规划修订保留 Git 历史。

## 原始登记交接记录

# OPS-031 登记交接

## 任务与固定来源

- 任务为 OPS-031，跟踪 [Issue #284](https://github.com/ElectricDogCN/Guize/issues/284)，登记使用 [PR #285](https://github.com/ElectricDogCN/Guize/pull/285)。
- 工作分支 `chore/OPS-031-gz007-wave-order`，目标分支 `main`，真实登记父提交 `150ee755f0583dccd747bc4d13c59f972b77ce87`。
- 初始登记候选 `6f6c26802d74c7d9c177ca94173c77847e1ce3a0` 已完成本地检查。当前补充交接的提交由 [PR 提交记录](https://github.com/ElectricDogCN/Guize/pull/285/commits) 标识，后续核对的源码、审查和官方 CI 均以该轮固定 SHA 为准。
- 保留的登记租约为 `2026-11-25T16:59:55Z` 至 `2026-12-02T16:59:55Z`；登记集成顺序为 Foundation 23，集成方式为 merge。

## 角色与范围

- 负责人 `ElectricDogCN`，协调与实施 `/root`，独立审查 `/root/independent_review`，合入 `/root`。当前角色为 coordinator。
- 独占范围为 `specs/coordination/program-plan.yaml`，无共享写范围。当前提交只更改自身登记与证据，GZ-007 定义仍为 W4、集成顺序 1。
- Program Plan 版本 1、Task Spec schemaVersion 2、Active Work 版本 1、[规划声明](planning-revision.json) schemaVersion 1。声明绑定真实登记父提交，后续只改 GZ-007 的 wave 和 integrationOrder。

## 实际文件

- `evidence/OPS-031/api-samples/README.md`
- `evidence/OPS-031/assumptions.md`
- `evidence/OPS-031/changed-files.md`
- `evidence/OPS-031/commands.txt`
- `evidence/OPS-031/follow-ups.md`
- `evidence/OPS-031/handoff.md`
- `evidence/OPS-031/migration-report/README.md`
- `evidence/OPS-031/performance/README.md`
- `evidence/OPS-031/planning-revision.json`
- `evidence/OPS-031/risks.md`
- `evidence/OPS-031/rollback-verification/README.md`
- `evidence/OPS-031/scope.md`
- `evidence/OPS-031/screenshots/README.md`
- `evidence/OPS-031/security/README.md`
- `evidence/OPS-031/summary.md`
- `evidence/OPS-031/test-results/README.md`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/OPS-031.md`

## 检查与证据

- [命令记录](commands.txt) 列出本地检查的真实基线和参数。初始候选的 Git 差异检查及 14 项原生任务检查均退出 0，结项校验参数含 `--task OPS-031`。初始候选的官方结果保存在 [CI #1118](https://github.com/ElectricDogCN/Guize/actions/runs/45660745706)。
- 审查指出初始交接字段不足。本次只补充本文件。更新后的固定源仍须独立审查和完整官方 CI，合入后再验证实际主线。
- 已接受的前置 GZ-006 记录见 [PR #283](https://github.com/ElectricDogCN/Guize/pull/283) 和 [实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45656298393)。本登记未授权执行 GZ-007 的数据库实现或变更任何独立 POC。

## 下一角色与回滚

- 独立审查人核对最新固定源的文件范围、角色租约、原始声明和完整官方 CI，接受后由合入角色按该 SHA 合并。实际登记主线通过完整 CI 和独立复验后，实施者才能依据原始声明激活 OPS-031，并提交 GZ-007 的两字段修订。
- 登记未合入时可撤回候选。登记已合入而需要终止时，按正常取消流程移除本任务登记与租约，保留证据和原始规划声明。GZ-007 的实际定义随登记保持不变。

## 实施前置的登记验收

OPS-031 的实际登记主线 b789c955c351f85e1de327d9a5040764c2f53643 已通过六项任务控制和完整官方 CI。本阶段从该主线执行固定规划声明，将 GZ-007 调到 W3、集成顺序设为 4，保留原有依赖及其他定义。

[实际登记官方 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45665934302)

[独立复验原件](accepted-reservation-b789c955/independent-review.json) 与 [完整性日志](accepted-reservation-b789c955/integrity.txt)。

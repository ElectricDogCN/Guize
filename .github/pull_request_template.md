## 关联

- Issue：
- Task ID：
- Work Package：
- Program Plan：`specs/coordination/program-plan.yaml#<TASK-ID>`
- Program Wave / Integration Order：
- Task Spec：
- Evidence：
- Handoff：

## Agent 角色与风险

- Coordinator：
- Implementer：
- Reviewer：
- Integrator：
- Risk Level：low / medium / high / critical
- high/critical 是否由独立 Reviewer 审查：是 / 否 / 不适用
- critical 是否独立 Wave：是 / 否 / 不适用

## 基线与依赖

- Base Branch：`main`
- Task `baseSha`：
- 当前 PR Base SHA：
- 是否从 reservation 合并后的最新 `main` 创建：
- `dependsOn` 是否全部进入目标基线：
- Producer Task / Contract Version：
- External Blocker：

## Program Plan 对齐

- [ ] Task ID、标题、类型、风险和 Work Package 与 Program Plan 一致
- [ ] Requirement IDs 与 Module IDs 一致
- [ ] Wave 和 `integrationOrder` 一致
- [ ] `outputPaths` / `sharedPaths` 一致
- [ ] `producesContracts` / `consumesContracts` 一致
- [ ] POC / Acceptance / Exit Gate 一致
- [ ] 本 PR 未创建第二份未来任务计划

## 活动任务登记

- `coordinationMode`：registry / bootstrap
- Registry Task ID：
- Registry Status：reserved / in_progress / review / integration
- Lease 到期时间：
- Coordination Group：
- Integration Strategy：merge / squash / rebase
- 本 PR 是 reservation / implementation / integration-cleanup：

## 路径范围

### 独占写路径

<!-- 与 Program Plan outputPaths、Task Spec 和 active-work.yaml 保持一致 -->

### 共享写路径

<!-- 无则只写“无。”；存在时双方显式 shared、同组、不同 integrationOrder -->

### 实际修改文件

<!-- 使用 GitHub diff/compare 生成，不要只写计划 -->

### 范围外修改

<!-- 应为“无”；存在时必须先更新 Program Plan/Task/Registry 并重新审查 -->

## 修改摘要

<!-- 描述可观察行为、契约、迁移、失败路径和非目标 -->

## Requirement / Module / Contract

- Requirement IDs：
- Module IDs：
- Produced Contract Namespace：
- Consumed Contract Namespace：
- Contract Owner：
- Consumer / Shared Writer 是否已在 `module-ownership.yaml` 声明：

- [ ] 已按权威顺序核对批准需求、机器契约、ADR 和设计
- [ ] 修改符合 `specs/designs/module-ownership.yaml`
- [ ] 公共契约具有唯一 owner；本模块不是未声明 writer
- [ ] consumer 的 producer Task 已合并并进入 base
- [ ] API/Event/DDL/Workflow/Plugin/Worker 行为已先更新机器契约
- [ ] 未直接访问其他模块 Repository/Schema
- [ ] 未把规划内容伪装为已实现
- [ ] 不适用，原因：

## API / Event 影响

<!-- 新增、兼容修改、破坏性修改、版本、生产者/消费者和降级影响 -->

## 数据库 / Migration 影响

<!-- 表、Schema owner、索引、约束、Expand/Contract、回填、备份、恢复 -->

## 配置 / 部署影响

<!-- 配置 Schema、环境变量、Bundle、回滚和兼容性 -->

## 安全影响

<!-- 权限、ACL、Secrets、SSRF、文件、供应链、匿名访问等 -->

## 测试命令与真实结果

| 命令 | 退出码 | 结果 | Evidence |
|---|---:|---|---|
| `python scripts/check-task-file.py --task ...` |  |  |  |
| `python scripts/check-agent-coordination.py --task ...` |  |  |  |
| `python scripts/check-project-readiness.py` |  |  |  |
| `python scripts/check-schemas.py` |  |  |  |
| `make verify TASK=... BRANCH=... BASE=origin/main` |  |  |  |

不得填写尚未执行的预期结果。最终 RC 还必须执行 `python scripts/check-project-readiness.py --strict-ready`。

## 失败、限制与未解决项

- 已知失败：
- POC/环境限制：
- External Blocker：
- 需要人工决策：
- 后续 Task：

## 回滚与恢复

<!-- 提供独立分支/Revert PR 步骤和回滚后验证；禁止直接推送 main -->

## 文档与治理同步

- [ ] README / MANIFEST / 设计文档已同步
- [ ] Program Plan / Task Spec / Registry / Handoff 已同步
- [ ] Evidence 完整且可复现
- [ ] ADR 已同步或明确无需 ADR
- [ ] Never Rules 未违反；如演进已同步 changelog
- [ ] GitHub 外部设置只按真实 API 状态记录

## Reviewer / Integrator 清单

- [ ] PR 分支、Task、Program Plan、Registry、base SHA 一致
- [ ] 无独占路径冲突或未协调 Shared 路径
- [ ] 公共契约 owner/consumer/shared writer 正确
- [ ] 依赖已合并，分支未过期
- [ ] 成功、失败、安全、并发、幂等和恢复路径已验证
- [ ] 最新 HEAD 的 Required Check 成功
- [ ] Review Thread 全部解决
- [ ] high/critical 已获独立 Reviewer 与人工批准
- [ ] critical 任务独立执行
- [ ] 合并后 Registry 释放和 Program Plan 状态更新路径明确
- [ ] 回滚路径可执行

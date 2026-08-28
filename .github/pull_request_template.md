## 关联

- Issue：
- Task ID：
- Work Package：
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

## 基线与依赖

- Base Branch：`main`
- Task `baseSha`：
- 当前 PR Base SHA：
- 是否已同步最新 `main`：
- `dependsOn` 是否全部进入目标基线：
- 共同机器契约版本：

## 活动任务登记

- `coordinationMode`：registry / bootstrap
- Registry Task ID：
- Lease 到期时间：
- Coordination Group：
- Integration Order：
- Integration Strategy：merge / squash / rebase
- 本 PR 是否完成或释放登记：

## 路径范围

### 独占写路径

<!-- 与 active-work.yaml 保持一致 -->

### 共享写路径

<!-- 无则写“无”；存在时说明同组任务和集成顺序 -->

### 实际修改文件

<!-- 使用 GitHub diff/compare 生成，不要只写计划 -->

### 范围外修改

<!-- 应为“无”；存在时必须先更新 Task/Registry 并重新审查 -->

## 修改摘要

<!-- 描述可观察行为、契约、迁移、失败路径和非目标 -->

## 契约与模块边界

- [ ] 已按权威顺序核对批准需求、机器契约、ADR 和设计
- [ ] 修改符合 `specs/designs/module-ownership.yaml`
- [ ] API/Event/DDL/Workflow/Plugin/Worker 行为已先更新机器契约
- [ ] 未直接访问其他模块 Repository/Schema
- [ ] 未把规划内容伪装为已实现
- [ ] 不适用，原因：

## API / Event 影响

<!-- 新增、兼容修改、破坏性修改、版本和消费者影响 -->

## 数据库 / Migration 影响

<!-- 表、索引、约束、Expand/Contract、回填、备份、恢复 -->

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
| `make verify TASK=... BRANCH=... BASE=origin/main` |  |  |  |

不得填写尚未执行的预期结果。

## 失败、限制与未解决项

- 已知失败：
- POC/环境限制：
- 需要人工决策：
- 后续 Task：

## 回滚与恢复

<!-- 提供独立分支/Revert PR 步骤和回滚后验证；禁止直接推送 main -->

## 文档与治理同步

- [ ] README / MANIFEST / 设计文档已同步
- [ ] Task Spec / Registry / Handoff 已同步
- [ ] Evidence 完整且可复现
- [ ] ADR 已同步或明确无需 ADR
- [ ] Never Rules 未违反；如演进已同步 changelog

## Reviewer / Integrator 清单

- [ ] PR 分支、Task、Registry、base SHA 一致
- [ ] 无独占路径冲突或未协调 Shared 路径
- [ ] 依赖已合并，分支未过期
- [ ] 成功、失败、安全、并发、幂等和恢复路径已验证
- [ ] 最新 HEAD 的 Required Check 成功
- [ ] Review Thread 全部解决
- [ ] high/critical 已获独立 Reviewer 与人工批准
- [ ] 活动任务登记将在合并时完成或释放
- [ ] 合并后 `main` Gate 和回滚路径明确

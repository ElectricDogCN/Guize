# GZ-031 登记交接

[Issue #345](https://github.com/ElectricDogCN/Guize/issues/345) 的当前阶段为 reserved／coordinator。已接受实际基线 `a02fedcc3359e6dfff68aee6de06075d4f1818c0`，登记分支 `chore/GZ-031-bootstrap-reservation`，实施分支 `chore/GZ-031-bootstrap-v1`。独立 Reviewer 为 `/root/independent_review`，租约从 2026-11-27T11:46:01Z 至 2026-12-04T11:46:01Z。登记源与实际主线通过完整官方 CI 后，由实施人从受验基线启动。

[基线验收](base-acceptance.json)

## 固定输入和写入边界

GZ-008 的实施合并为 `904a2f680fa50ad60b113e99af16181ee8844565`。消费 `PLUGIN-CONTRACT-V1`（Manifest `guize.plugin/v1`）和 `WORKER-CONTRACT-V1`（协议 v1 与 Worker SDK 1.0.0）。控制面按 [ADR-0002](../../adr/0002-modular-monolith-control-plane.md) 使用 Java 17 和 Spring Boot 3。

本任务位于 W5，集成序号 3，共享写入范围为空。登记阶段的变更路径如下。

- `evidence/GZ-031/EVIDENCE-STRUCTURE.md`
- `evidence/GZ-031/assumptions.md`
- `evidence/GZ-031/base-acceptance.json`
- `evidence/GZ-031/changed-files.md`
- `evidence/GZ-031/commands.txt`
- `evidence/GZ-031/follow-ups.md`
- `evidence/GZ-031/handoff.md`
- `evidence/GZ-031/risks.md`
- `evidence/GZ-031/scope.md`
- `evidence/GZ-031/summary.md`
- `evidence/GZ-031/test-results/README.md`
- `evidence/GZ-031/test-results/reservation-controls-80d6d4ca.json`
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/GZ-031.md`

## 本地验证记录

15 项本地检查在 [公开固定源码](https://github.com/ElectricDogCN/Guize/commit/80d6d4ca8ad25c4b8abf3f4334c11387933c26cf) `80d6d4ca8ad25c4b8abf3f4334c11387933c26cf` 实际执行，全部退出 0。[逐项命令、退出码和控制台记录](test-results/reservation-controls-80d6d4ca.json)保留可重复执行的命令、输出及原件摘要。公开记录使用可移植路径。初版曾将不支持的选项传给 Finalization，本轮用官方参数直接通过。当前交付为登记，产品启动和插件隔离由登记实际通过后的产品交付验证。

## 审查、实施和撤回

协调角色先让修订后的固定头完成适用本地检查并取得独立预审。随后把固定头推到登记分支并创建 Ready PR，走完整官方 CI 和同头审查。普通合入后复验实际主线。实际登记通过后，由 `/root` 从受验主线建立 `chore/GZ-031-bootstrap-v1`，实施空注册表启动和插件失败隔离，并验证 Worker 固定契约。

合入前可撤回登记候选。合入后按正式取消或结项流程释放自身范围并保留已验记录。POC-007 和 POC-008 的活动登记按各自计划处理。

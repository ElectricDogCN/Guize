# GZ-031 登记交接

[Issue #345](https://github.com/ElectricDogCN/Guize/issues/345) 的当前阶段为 reserved／coordinator。已接受实际基线 `a02fedcc3359e6dfff68aee6de06075d4f1818c0`，登记分支 `chore/GZ-031-bootstrap-reservation`，实施分支 `chore/GZ-031-bootstrap-v1`。独立 Reviewer 为 `/root/independent_review`，租约从 2026-11-27T11:46:01Z 至 2026-12-04T11:46:01Z。登记源与实际主线通过完整官方 CI 后，由实施人从受验基线启动。

[基线验收](base-acceptance.json)

## 固定输入和写入边界

GZ-008 的实施合并为 `904a2f680fa50ad60b113e99af16181ee8844565`。消费 `PLUGIN-CONTRACT-V1`（Manifest `guize.plugin/v1`）和 `WORKER-CONTRACT-V1`（协议 v1 与 Worker SDK 1.0.0）。控制面按 [ADR-0002](../../adr/0002-modular-monolith-control-plane.md) 使用 Java 17 和 Spring Boot 3。

本任务位于 W5，集成序号 3，共享写入范围为空。登记阶段只修改以下 14 条路径。

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
- `specs/coordination/active-work.yaml`
- `specs/coordination/program-plan.yaml`
- `specs/tasks/GZ-031.md`

## 本地验证原件

下列命令对应上一固定登记候选 `386075ff4916ffcdc780e265f254c46768cb69e9`。原始执行记录 SHA-256 为 `9a7e91bae7b2b4dceed9cf5c07630b40098c38c333ee6b990f00d80d02bebede`，更正回执 SHA-256 为 `c135eeed278f8257b4490c1186a4413ce9e6388d96d5b5f88b7c5cdd188e1d36`。记录中的本地 Python 路径在此记作 `python`。

| 检查 | 实际命令 | 退出码 |
| --- | --- | --- |
| diff | `git diff --check a02fedcc3359e6dfff68aee6de06075d4f1818c0 386075ff4916ffcdc780e265f254c46768cb69e9` | 0 |
| integrity | `python -B scripts/check-program-plan-integrity.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0` | 0 |
| history | `python -B scripts/check-program-plan-history.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0 --head-ref 386075ff4916ffcdc780e265f254c46768cb69e9 --task GZ-031 --branch-name chore/GZ-031-bootstrap-reservation` | 0 |
| transitions | `python -B scripts/check-program-plan-transitions.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0 --head-ref 386075ff4916ffcdc780e265f254c46768cb69e9 --task GZ-031 --branch-name chore/GZ-031-bootstrap-reservation` | 0 |
| finalization | `python -B scripts/check-program-plan-finalization.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0 --head-ref 386075ff4916ffcdc780e265f254c46768cb69e9 --task GZ-031` | 0 |
| lifecycle-guards | `python -B scripts/check-program-lifecycle-guards.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0 --head-ref 386075ff4916ffcdc780e265f254c46768cb69e9 --task GZ-031 --branch-name chore/GZ-031-bootstrap-reservation` | 0 |
| lifecycle | `python -B scripts/run-program-lifecycle-gate.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0 --head-ref 386075ff4916ffcdc780e265f254c46768cb69e9 --task GZ-031 --branch-name chore/GZ-031-bootstrap-reservation` | 0 |
| coordination | `python -B scripts/run-agent-coordination-gate.py --base-ref a02fedcc3359e6dfff68aee6de06075d4f1818c0 --head-ref 386075ff4916ffcdc780e265f254c46768cb69e9 --task GZ-031 --branch-name chore/GZ-031-bootstrap-reservation` | 0 |
| scope | `python -B scripts/run-task-scope-gate.py --task GZ-031 --base a02fedcc3359e6dfff68aee6de06075d4f1818c0` | 0 |
| evidence | `python -B scripts/check-evidence.py --task GZ-031` | 0 |
| readiness | `python -B scripts/check-project-readiness.py` | 0 |
| markdown | `python -B scripts/check-markdown.py` | 0 |
| task | `python -B scripts/check-task-file.py --task GZ-031` | 0 |
| schemas | `python -B scripts/check-schemas.py` | 0 |
| spec-sync | `python -B scripts/check-spec-sync.py --base a02fedcc3359e6dfff68aee6de06075d4f1818c0` | 0 |

首次 Finalization 命令带有不支持的 `--branch-name` 参数，退出 2，未执行检查。使用官方适用参数在同一候选重跑后退出 0。其余检查首轮退出 0。当前阶段尚未执行产品启动或正式官方 CI。

## 审查、实施和撤回

协调角色先让修订后的固定头完成适用本地检查并取得独立预审。随后把固定头推到登记分支并创建 Ready PR，走完整官方 CI 和同头审查。普通合入后复验实际主线。实际登记通过后，由 `/root` 从受验主线建立 `chore/GZ-031-bootstrap-v1`，实施空注册表启动和插件失败隔离，并验证 Worker 固定契约。

合入前可撤回登记候选。合入后按正式取消或结项流程释放自身范围并保留已验记录。POC-007 和 POC-008 的活动登记按各自计划处理。

---
schemaVersion: 2
id: OPS-017
title: Bound prospective POC source compatibility repair admission
titleZh: 为版本化POC源兼容性修复建立受限准入
type: chore
status: in_progress
baseBranch: main
baseSha: a55680b9d06901729fcae7f35cb167b8b59d33f4
workBranch: chore/OPS-017-source-compatibility-admission
evidencePath: evidence/OPS-017
issue: 168
workPackage: WP-M0-01
programPlan: specs/coordination/program-plan.yaml
programTaskId: OPS-017
wave: FOUNDATION
requirementIds: REQ-V1-0010
moduleIds: MOD-GOV
producesContracts: []
consumesContracts: CONTRACT-PROGRAM-PLAN,CONTRACT-TASK-SPEC,CONTRACT-ACTIVE-WORK
exitGate: 新原始授权经真实主线登记和独立正常收口后只准入OPS018五条精确路径；旧授权、冻结、全部测量、平台与生产门禁保持
taskOwner: ElectricDogCN
coordinator: /root
implementer: /root
reviewer: /root/gz022_planning_independent_review
integrator: /root
agentRole: implementer
riskLevel: high
coordinationMode: registry
coordinationGroup: poc-source-compatibility-admission
dependsOn: OPS-016
handoffPath: evidence/OPS-017/handoff.md
integrationStrategy: merge
integrationOrder: 13
leaseExpiresAt: 2026-11-05T09:16:44Z
---

# OPS-017 metadata-only reservation

## 背景与目标

完整V1后继代码会使旧POC源的全仓兼容检查失败；这不抹去历史事实，也不能直接承认新版本已测。本任务只建立唯一后继OPS-018的前瞻受限准入。后继拟采用显式版本化完整依赖闭包与真实独立兼容性审查；未知闭包或相关变化仍拒绝，原实验与批准不改写。

## 输入与输出

输入为实际main 22ab6a0668da2d64a016fccef2c3b5a634638a24、只读源适用性分析、独立语义设计与精确3592正式结果接受。prerequisites/index.json保存原件摘要及可恢复ZIP。输出仅自身Foundation、活动登记、Task/Evidence及不可变source-compatibility-admission-intent.json；本预留不实现准入、不修改冻结契约、不授实验或复用资格。

## 允许范围

当前阶段仅Own元数据预留，Program/Registry/Task变更由正常元数据门禁逐项验证。下列代码claims仅在预留实际主线接受后可实现：

- `AGENTS.md`
- `scripts/poc-contract-repair-admission.py`
- `scripts/check-program-lifecycle-guards.py`
- `tests/governance/test_poc_contract_repair_admission.py`
- `evidence/OPS-017/**`

## 独占写范围

- `AGENTS.md`
- `scripts/poc-contract-repair-admission.py`
- `scripts/check-program-lifecycle-guards.py`
- `tests/governance/test_poc_contract_repair_admission.py`

## 共享修改范围

- 无。

## 禁止范围

- 不改既有OPS-013/014原始意图与完成身份，不改两个POC的状态、角色、租约、claims或结果，不改普通账本、Program政策、模块所有权、工作流与时限；不改五个后继目标或其它业务/合同/阈值。不得以任务编号、相交路径、侧分支、晚补授权或EvidenceCorrection自授修复权。不启动新实验、重启环境、删除原件或改时钟。

## 依赖与集成顺序

- 依赖正常完成OPS-016；当前2active/0high，提案为3active/1high。原始租约2026-10-29T09:16:44Z至2026-11-05T09:16:44Z，order13。当前metadata源14项、完整同头CI、独立终审、普通merge及实际主线接受后才实现。准入实现须核最初真实父基线、原始意图摘要、四claims真实实现、独立Review、正常Completion、容量释放及不可变逐提交历史。OPS-018需随后独立预留与真实GZ-021冻结事件，完成修复验证和独立解冻；本任务不替后继建立冻结。

## 协作与交接

- Owner ElectricDogCN；Coordinator/Implementer/Integrator /root；独立Reviewer /root/gz022_planning_independent_review。Program1/Task2/Registry1契约保持。Handoff保存当前实际文件、版本、命令、退出码、失败、共享范围、回滚与下一角色动作。两个POC既有租约不因此延长，后续须按普通机制前瞻处理；不追溯延长原实验许可。

## 验收标准

- [ ] 原始metadata-only登记与四条精确Gov claims合法，所有foreign字节和旧授权不变。
- [ ] 仅独立正常收口后的新原始授权准入唯一OPS-018五路径；原OPS-014语义与历史回归不变。
- [ ] 拒假主线、晚补/改写意图、缺实现或Review/Completion、超容量/过期/角色不独立及冻结外变更；真实Git正反例与现有完整治理测试通过。
- [ ] 完整源/CI/实际main门禁、独立审查与正常Review/Completion；不把治理完成视为POC或V1完成。

## 必须执行的测试

```bash
git diff --check 22ab6a0668da2d64a016fccef2c3b5a634638a24...HEAD
python scripts/check-task-file.py --task OPS-017
python scripts/check-schemas.py
python scripts/check-program-plan-integrity.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24
python scripts/check-program-plan-history.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24 --head-ref HEAD --task OPS-017 --branch-name chore/OPS-017-source-compatibility-admission-reservation
python scripts/check-program-plan-transitions.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24 --head-ref HEAD --task OPS-017 --branch-name chore/OPS-017-source-compatibility-admission-reservation
python scripts/check-program-lifecycle-guards.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24 --head-ref HEAD --task OPS-017 --branch-name chore/OPS-017-source-compatibility-admission-reservation
python scripts/run-program-lifecycle-gate.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24 --head-ref HEAD --task OPS-017 --branch-name chore/OPS-017-source-compatibility-admission-reservation
python scripts/run-agent-coordination-gate.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24 --head-ref HEAD --task OPS-017 --branch-name chore/OPS-017-source-compatibility-admission-reservation
python scripts/check-program-plan-finalization.py --base-ref 22ab6a0668da2d64a016fccef2c3b5a634638a24 --head-ref HEAD --task OPS-017
python scripts/run-task-scope-gate.py --task OPS-017 --base 22ab6a0668da2d64a016fccef2c3b5a634638a24
python scripts/check-evidence.py --task OPS-017
python scripts/check-project-readiness.py
python scripts/check-markdown.py
```

准备阶段未执行；实现阶段另执行完整tests/governance、必要真实Git回归及零跳过审计，不删除测试或提高30分钟时限。

## Evidence

summary.md、commands.txt、handoff.md与changed-files.md提供阶段入口。原始意图只声明后继修复范围，不构成已实现权限；prerequisites保存完整原件，既有失败保持原归属。

## 风险

仅哈希少量旧文件不能证明依赖闭包完整，后继必须保护实际导入/构建搜索根新增文件并拒未知依赖。旧index严格行为保持，011能否迁移由真实后继审查决定。全部测量、样本、批准、完整平台和独立生产复测义务保持。

## 回滚

合并前撤回提案保留原件；合并后普通前向修复或合法释放。禁止reset/rebase/force及删除本地引用、工作目录、数据库和失败历史。

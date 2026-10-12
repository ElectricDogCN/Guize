---
schemaVersion: 2
id: OPS-010
title: Resolve immutable planning manifest authority from CI base aliases
titleZh: 修复规划原始manifest准入的分支基线解析
type: chore
status: review
baseBranch: main
baseSha: 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e
workBranch: chore/OPS-010-planning-base-review
evidencePath: evidence/OPS-010
issue: 97
workPackage: WP-M0-01
programPlan: specs/coordination/program-plan.yaml
programTaskId: OPS-010
wave: FOUNDATION
requirementIds: REQ-V1-0010
moduleIds: MOD-GOV
producesContracts: []
consumesContracts: CONTRACT-PROGRAM-PLAN,CONTRACT-TASK-SPEC,CONTRACT-ACTIVE-WORK
exitGate: 已有严格规划manifest准入先绑定真实不可变基线；CI分支别名与同SHA等价，invalid/noncanonical基线与manifest重写继续拒绝；当前源码全部门禁、完整零失败错误跳过测试、同头CI及独立审查通过，不改变业务计划与生产政策
taskOwner: ElectricDogCN
coordinator: program-coordinator-agent
implementer: planning-base-resolution-agent
reviewer: independent-planning-base-review-agent
integrator: integration-agent
agentRole: reviewer
riskLevel: high
coordinationMode: registry
coordinationGroup: planning-manifest-base-resolution
dependsOn: OPS-009
handoffPath: evidence/OPS-010/handoff.md
integrationStrategy: merge
integrationOrder: 6
leaseExpiresAt: 2026-10-19T18:03:26Z
---

# OPS-010 正常 Review

## 当前阶段

仅进行自身 Foundation in_progress→review、Registry/Task 的 reviewer/branch/base 更新和自身 Evidence 交接。真正实现已由 PR #99 合入 `55d7ac47f022549dd249cd0cd5a7f03a0c04db2e`；代码源 `a7b027092db1edc7dc4d63aad141de21ecce37b5`。本阶段不改变实现、测试断言、任何业务规划、契约、政策或完成历史。当前 Review 候选自身完整验证、CI及独立审查仍待执行，不能继承代码源的 PASS。

## 输入、输出与范围

输入为已独立接受的真实实现主线及最后代码身份 PR-99 / 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e。输出是正常 Review 元数据与真实交接材料；原两条 claim、独立角色、FOUNDATION/order6、sharedPaths=[]、原租约和依赖 OPS-009 保持。允许范围仅自身 Foundation/Registry/Task/Evidence；两条实现路径保持 Git 字节不变。其他任务、POC、波次、baselines、完成账本、生产政策和所有未 claim 的路径禁止修改。

## 允许范围

仅自身 Foundation 状态、Registry/Task 的正常 Review 元数据，以及 evidence/OPS-010/**。本阶段两条代码 claim 保持原 Git 字节，不新增范围。

- `specs/coordination/program-plan.yaml`（仅 OPS-010 状态）
- `specs/coordination/active-work.yaml`（仅 OPS-010）
- `specs/tasks/OPS-010.md`
- `evidence/OPS-010/**`

## 禁止范围

- 所有代码、测试断言、其他 Task/Evidence/lease、普通完成账本、Program 普通任务/POC/波次/baselines/releasePolicy、契约、AGENTS 和 Never Rules。

## 依赖与集成顺序

- OPS-009 已完成；实现 PR99 的实际 main 已验收。当前 Review 源须完整门禁、同头 CI 和独立接受后才集成；真实 Review main 验收后再正常 Completion，绑定 PR-99 / 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e。

## 独占写范围

- `scripts/program-planning-revision.py`
- `tests/governance/test_program_planning_revision.py`

## 共享修改范围

- 无。

## 协作与交接

- Owner ElectricDogCN；Coordinator program-coordinator-agent；Implementer planning-base-resolution-agent；Reviewer independent-planning-base-review-agent；Integrator integration-agent。当前 reviewer/review；base `55d7ac47f022549dd249cd0cd5a7f03a0c04db2e`；branch `chore/OPS-010-planning-base-review`；租约 2026-10-12T18:03:26Z 至 2026-10-19T18:03:26Z，没有续租。消费 CONTRACT-PROGRAM-PLAN / CONTRACT-TASK-SPEC / CONTRACT-ACTIVE-WORK 的既有版本，不生产新契约。

代码源实际18门禁、planning110/full637零失败错误跳过、同头CI675及独立最终集成已通过；真实实现主线的push/main CI与独立接受绑定输入proof。证据保存或引用于 evidence/OPS-010/；历史源结果不代替本Review源执行。下一角色核本Review实际source/命令/exit/JUnit/CI/线程后集成；真实Review main再独立接受，才可进行正常Completion并引用真正最后代码merge。GZ021和完整本地V1未完成，不提前移除Registry。

## 验收标准

- [ ] 仅合法自身Review元数据及Evidence；原claim/lease/身份、代码和所有foreign不变。
- [ ] 当前不可变Review source的全部门禁、完整零F/E/Skip测试、同头CI和独立接受。
- [ ] 实际Review main验收后再Completion，保持最后代码身份 PR-99 / 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e。

## 必须执行的测试

```bash
python scripts/check-task-file.py --task OPS-010
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python scripts/check-program-plan-integrity.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e
python scripts/check-program-plan-history.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
python scripts/check-program-plan-transitions.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
python scripts/check-program-plan-finalization.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e --task OPS-010
python scripts/check-program-lifecycle-guards.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
python scripts/run-program-lifecycle-gate.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
python scripts/run-agent-coordination-gate.py --base-ref 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
python scripts/run-task-scope-gate.py --task OPS-010 --base 55d7ac47f022549dd249cd0cd5a7f03a0c04db2e
python scripts/check-evidence.py --task OPS-010
make verify TASK=OPS-010 BASE=55d7ac47f022549dd249cd0cd5a7f03a0c04db2e HEAD_REF=HEAD BRANCH=chore/OPS-010-planning-base-review
python scripts/check-markdown.py
python -m pytest tests/governance/test_program_planning_revision.py -v -ra
python scripts/check-program-plan-history.py --base-ref origin/main --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
python scripts/check-program-lifecycle-guards.py --base-ref origin/main --head-ref HEAD --task OPS-010 --branch-name chore/OPS-010-planning-base-review
```

## 风险与回滚

Review记录不能掩盖尚未执行的当前源验证或修改完成身份。未合入可关闭当前Review PR并保留已接受实现主线；Foundation没有cancelled。review/integration可合法blocked但保留有效lease、Registry和容量；实际Completion才收口。合入后的缺陷采用正确登记前向修复，必要恢复遵循AGENTS17.8。无生产操作或凭据变化。

## 未解决项

当前Review源完整执行/CI/独审及实际main验收；后续正常Completion、GZ021需求路线登记与完整本地V1仍待推进。

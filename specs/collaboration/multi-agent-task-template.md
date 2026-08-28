---
id: GZ-XXX
title: English task title
titleZh: 中文任务标题
type: feat
status: draft
baseBranch: main
workBranch: feat/GZ-XXX-short-name
evidencePath: evidence/GZ-XXX
issue: 0
coordinationMode: multi-agent
ownerRole: implementation-agent
reviewRole: independent-review-agent
baseCommit: 0000000000000000000000000000000000000000
coordinationPath: specs/collaboration/tasks/GZ-XXX.yaml
handoffPath: evidence/GZ-XXX/handoff.md
dependsOn: GZ-YYY,GZ-ZZZ
---

# GZ-XXX 中文任务标题

## 背景

说明为什么需要此任务，以及它消费哪些已批准需求、机器契约和 ADR。

## 目标

1. 

## 非目标

- 

## 协作模式

- Owner Role：
- Independent Reviewer Role：
- Integrator Role：
- Base Commit：
- Dependencies：
- Coordination Descriptor：
- Handoff：

## 权威输入

- Requirement：
- API/Event/Data Schema：
- ADR：
- System/Module Design：

## 契约输出

- 

## 允许范围

- `path/**`

## 禁止范围

- `other/**`

## 状态、幂等与错误处理

- State machine：
- Idempotency：
- Retry/timeout：
- Error contract：
- Audit：

## 验收标准

- [ ] Given / When / Then 可验证条件。
- [ ] 负例、权限、幂等、失败和恢复场景已覆盖。
- [ ] Handoff 和 canonical Evidence 完整。
- [ ] Governance Gate 与 Collaboration Gate 成功。

## 必须执行的测试

```bash
python scripts/check-task-file.py --task GZ-XXX
python scripts/check-task-scope.py --task GZ-XXX --base origin/main
python scripts/check-evidence.py --task GZ-XXX
python scripts/check-collaboration.py --task GZ-XXX --base origin/main
python scripts/render-multi-agent-prompt.py --task GZ-XXX --output /tmp/GZ-XXX-prompt.md
python -m pytest tests/governance/ -v
```

## Evidence 与 Handoff

- Evidence：`evidence/GZ-XXX/`
- Handoff：`evidence/GZ-XXX/handoff.md`

## 风险与停止条件

- 

## 回滚

### 合并前

- 关闭 PR 并保留分支和 Evidence。

### 合并后

- 从最新 `main` 创建独立 Fix/Revert Task，通过 PR 回滚；禁止直接推送 `main`。

### 数据或外部副作用

- 

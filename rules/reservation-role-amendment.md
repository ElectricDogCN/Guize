# 前瞻 POC 具体身份修订

本机制只承接 OPS-015 原始主线预留中的 POC-003、POC-005，以及其中声明的 implementer/reviewer 两字段。它不建立角色别名，不转移旧实验、样本、资源、窗口、结果或 CI 的归属。

## 前置与原始授权

原始预留必须是实际主线 `36d8ba69581c98ab15559e5a4a7f6281435d327f`，父提交为原基线与预留源，原始 intent 按 Git 字节保持。OPS-015 的非空五路径实现、独立 Review、正常 Completion 和容量释放须已位于本次检查的真实主线基线。候选自己声称完成、只有任务号或未合入的侧分支不提供权限。Program 必须 active。

## 两次提交的元数据事务

POC 在实际 main 仍 reserved 时，另建携带自身 Task ID 的元数据分支。保留 Task workBranch、Registry branch、base、状态、agentRole、租约、claims、风险、依赖、顺序及全部其他字段。现有 reserved 分支规则允许元数据 PR 与登记实现分支名称不同，不新增分支豁免。

先把真实独立审查者的批准原件提交到 `evidence/<POC-ID>/actor-amendment-v1/approval.json`，再在后续提交同时修改 Task 与 Registry 的两个字段。批准不能与首次身份修改在同一个提交中补写。批准一经提交，其原字节与Git mode保持不变，类型固定100644；不能通过改写、删除、symlink或可执行mode后再恢复来掩盖。记录为闭合 JSON 对象：

```json
{
  "schemaVersion": 1,
  "kind": "prospective_poc_actor_amendment",
  "taskId": "POC-003",
  "admittedMain": "实际已接受主线的40位提交",
  "oldActors": {"implementer": "task-owner-agent", "reviewer": "independent-review-agent"},
  "newActors": {"implementer": "/root", "reviewer": "/root/independent_review"},
  "reviewer": "/root/independent_review",
  "approvedAt": "真实UTC批准时间",
  "decision": "approved"
}
```

POC-005 的新 reviewer 为原始 intent 中的 `/root/gz022_planning_independent_review`。批准绑定实际旧、新身份及未改变的主线预留，在有效租约内先于身份生效。JSON 字段、名称不同或 self-approval 均不能作为批准。真实独立审查仍须核验原件；机器校验不能凭一个字符串证明独立性。

整个 PR 只修改该 Task/Registry 的两条身份标量及新建的本次批准 Evidence。可在原 handoff 后追加本次交接，原字节前缀保留。不得重写旧批准、旧 raw、数据库或历史结果；不得同 PR 启动、改 branch/base/lease 或混入业务实现。Program、账本、其他登记和所有冻结 POC 合同保持原字节。

## 历史与旧实现分支同步

端点和所有新引入的实际 Git 节点均检查；早期未经批准的改名，即使后来撤回或获得同名批准，仍失败。主线正常合并保留源侧批准先提交的因果顺序。

旧实现分支只能从已位于真实主线基线中的 secondary parent 导入新身份。重新验证原主线修订、全部 merge bases 的旧身份，以及实际合并 Task 的 stage-0 mode/blob。Task 可以保留本地 in_progress、base 和正文，同时导入主线 reserved 中的新身份；不能凭新名字相同、未接受的父分支或冲突后手工挑选来冒充自动导入。一般 clean-import、Foundation、权限、冻结、scope 与生命周期检查保持。

## 新实验与验证

机制正常完成后，两个 POC 分别提交身份事务并接受其源和实际主线。随后各自固定新源、完成所需检查/CI，取得新样本、资源和窗口批准，执行真实新实验。旧 attempt-010 保持原归属，不转作新身份下的正式结果。POC-003 的原矩阵、延迟、撤权及其他冻结验收保持。

实现覆盖真实 Git 正例、事前批准、拒绝晚批/自批/额外修改、坏历史恢复、实际主线自动 hybrid 导入及拒绝非主线/手工改写。源码未通过固定源与实际主线验证前不宣称可用。回滚使用普通前向变更，保留原件。

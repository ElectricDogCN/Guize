# 416 合同缺陷的受限修复准入提案

状态：具体方案待独立审查；未创建新 Issue、登记、冻结事件或修改治理实现。
决定责任：本线程 Coordinator 在用户既有项目最高决策权、直接审批与合并授权内推进。

## 已验证的问题

POC-005/Issue132 的 sourceca1 实际 Windows OpenList10k 运行已独立批准并完成。
原始416为 `Content-Range: bytes */4096`、33B诊断正文，SHA256
`b5d780567c43a2b5d8473d84a136e7dc62ee9c494108d282cbff4801d199cf32`。
完整原件及23:37:38Z独立结果审查保持；UTC前向修复e1已经独立接受、本地检查通过、CI828运行中。
当前冻结 metadata profiling 检查却要求416空正文，与真实HTTP诊断行为不兼容。

已查真实Git来源：`fbc7598125c1601892174ed2be8284fef10bb56a`，提交正文Issue95，
Evidence为GZ-021 three-qualified-profile-observations；该提交引入metadata profiling
检查。因此后继恢复须绑定实际completed producer GZ-021，不能误记为GZ-010或POC-005。

当前 POC-005 不持有冻结合同路径。MOD-GOV 所有权也不包含这些路径；不能复用
GZ-010/GZ-021 completed 身份、GZ-014 legacy exception、变更27+EDGE8普通任务成员，
或仅给一个新Task ID加白名单。AGENTS17.8/历史/transition必须一致维护。

## 第一阶段：新的 Foundation OPS-013，只修复准入缺口

先按现有机制 metadata-only reserved 登记。MOD-GOV/high，独立执行/审查角色，
有效有限租约，现有2项medium之后不突破3活动/1high。依赖实际completed的OPS-012。
保持Program active；本阶段只建立未来的有界授权机制，不修复旧合同、不冻结或接管旧任务。

拟精确独占范围：

- `AGENTS.md`
- `scripts/check-program-lifecycle-guards.py`
- `scripts/check-program-plan-transitions.py`
- `scripts/check-program-plan-history.py`
- `scripts/poc-contract-repair-admission.py`
- `tests/governance/test_poc_contract_repair_admission.py`

自身Task/Evidence及正常Program/Registry元数据由原规则承接；不包含specs/poc、
所有权文件、普通业务计划、旧Task、POC结果、质量阈值、其他租约或工作流。
不复用planning scope-amendment，不扩展整个规划机制。

新机制只识别随OPS-013原始接受登记固定的精确授权声明。声明至少绑定：授权任务、
原始真实登记父提交、缺陷原件及摘要、受影响已完成producer及合同、被修复两文件的
原基线Git字节摘要、唯一后继身份OPS-014、精确两路径、修复目的及禁止范围。
声明原字节不可追改；代码或单个实现提交不能自发增加外域claim。

只有授权任务经过正常独立Review/Completion并在真实主线可达、已释放high容量后，
唯一后继任务才可在新的真实main基线metadata-only登记。后继的模块/角色/租约/容量、
原始登记及第一父历史、所有授权前提与逐提交路径仍必须核验；基线两文件必须仍匹配
原批准摘要。其他Task、任意路径、未完成/侧分支/晚补授权、改写声明、身份借用或错误
基线一律拒绝。旧历史的准入结果不被投影成新权限。

至少补齐真实Git历史的正例及独立负例：未登记、只有ID、侧分支/不可达、授权未完成、
原声明篡改、假父基线、文件摘要变更、路径扩大、别的后继身份、原始登记后追加claim、
角色/租约/容量失效；保持原有冻结/完成历史/普通任务全部回归。

## 第二阶段：单独的合同修复任务 OPS-014

OPS-013主线完整接受与正常Completion之后才办理，不与第一阶段自授或混合合并。
目标只承接已明确授权的：

- `specs/poc/check_program.py`
- `specs/poc/test_program.py`

目的仅为metadata profiling真实416诊断正文，保留原13项、精确状态/Content-Range、
来源/版本/时间/响应哈希长度、有界读取和篡改拒绝；不得裁剪原响应、换空字节、改标签，
或降低原时间/资源/质量门槛。具体正文准入条件在该任务自己的合同决策中先冻结，
再以真实33B原件和反例验证；本提案不提前批准其代码或实验结果。

若该已完成合同的修复适用17.8恢复，须在OPS-014具体登记前独立确定真实producer、
冻结原因/所有者/事件与single-high交接。冻结本身不赋外域权限，不临时解冻承接。
按已有独立冻结、修复验证、metadata-only解冻与后续普通工作恢复规则办理。

POC-003/005的原件、租约和共享order2→3保持；冻结期间普通任务只按规则保留或收口。
本提案不批准当前新实验，不宣称原13或本地V1通过。

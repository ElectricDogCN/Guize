# OPS-004 固定历史失败事件的审查处理

Owner: ElectricDogCN（人类在本会话明确委托最高决策权）
Task: OPS-004 / Issue71
Thread: PRRT_kwDOTgCQ3c6q59O3

本会话人类明确指令“你在这个项目有最高决策权，我只要求你能实现目标”，其优先级高于仓库 AGENTS 的指导。此前不可变 owner-decision.md 已据此限定 OPS-004-LIFECYCLE-ADMISSION-20261009 修复事件；本条审查认为任何 Owner 文件都不能覆盖并发限制，该普遍前提不适用于本会话已委托的具体决策。

这里只承认真实 d0e9e256552f9d1d47fb24d2e5a4530476b19a5f / 第一父413a6a4dd91b5d79a3d2b7d1e5f03f8121848170 / 原决定blob e25670a161ff6c33104b24d3bb8f22ce4fb06eac 的既有容量失败事实。原事件参与者、policy、Program状态和UTC窗口均保持精确边界；不承认其他Task、不同事件、其他Owner文件、额外参与者、修改policy或窗口后的工作。永久maxHigh=1、当前counter与coord/make/CI返回码不变，历史输出明确capacityResult FAIL，不称容量PASS或一般准入豁免。

真实f402版本完整445项测试零失败，Gate608唯一容量失败，原始仍完整保留；独立Reviewer也核验授权事实与固定边界。新增59O7先开发后同步登记路径已实际复现，是实现缺陷，必须修复后重跑精确Source；本授权不覆盖该缺陷或任何其他意外失败。

最终Completion只绑定实际PR77实现merge，移除自己的Lease后全部候选与主线检查必须真实通过，才恢复GZ005。Lease、原窗口和永久规则不延长；V1功能和真实POC仍需完成。

## 五条历史 context 审查处理（2026-10-09）

6XRE/RJ/RY/Rf 经真实临时 Git 复现为实现缺陷：分别是已在 integration base 的主线同步误拒、metadata-only 临时越界/冲突恢复后漏验、工作节点夹带他任务登记或旧完成身份修改，以及临时改容量 policy 执行后恢复。此次统一核对全部自身主线和引入 DAG 的登记快照，包括 schema、原注册父 policy、历史有效 Lease、MOD-GOV 子集、独占冲突及 Task/Program/Registry 完整绑定。工作范围仍取修改前登记；同步仅排除与已在真实 base 的 incoming main parent 原样相同的 tree entry，手工冲突解决和新修改仍须登记。foreign metadata 逐节点结构比较，不因文件属于规范 metadata 就整体豁免；合法 freeze/thaw 只有真实快照通过现有完整 Recovery validator 且 owner 匹配，才规范化该事件的 root 字段。

6XRR 属未规定的新证明协议要求。既有 schema 允许 merge/squash/rebase，现有 Transitions 实际允许 Review→Integration 的单父提交；真实 git merge --squash 从 Implementer/Review 侧源产生代码 blob 相同的正例，没有既定强制 source trailer 或父数量证明字段。因此不新增单父禁令，不据此声称实际人类 Review 或完整 Gate 已通过。独立原始边界在 history-dag-independent/ops004-independent-integrator-corrected-review-squash-proof.json。

新修复的18项真实 Git 回归包含四漏洞、引入侧 metadata、Task/Program瞬态、合法主线同步/单父integration/squash，以及经现有 Recovery validator核验的注册后冻结与冻结夹带外国完成身份负例。120 targeted 在未提交工作树上通过，仅为外部探索记录；本候选发布来源、完整465/15检查和同头CI仍为 NOT_EXECUTED。永久限制和 Owner 原窗口不变；所有未预期失败必须修复。

## 当前 Program 与同步冲突修复候选

Task: OPS-004 / Issue71
Phase: history repair implementation
Branch: chore/OPS-004-history-repair-implementation
Base: 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb
Actual published parent: 0b1f7f6fd3e123069cbb38622d212aaee41d7bf2
Execution Status: NOT_EXECUTED for this changed candidate; actual full-suite and same-head CI remain required.

历史实际父Source0b1f7f6fd3e123069cbb38622d212aaee41d7bf2/tree d21968b5e862ef5dcca7842b6bd5d472747a6ce8：15项13项exit0、coord1/make2唯一原容量FAIL；完整465 PASS441.52s，JUnit465零失败/错误/跳过，执行前后Source及工作树不变。同头Gate610完整465 PASS357.56s，唯一AgentCoord原容量FAIL；原始在 history-contexts-source-0b1f7f6 与 history-contexts-ci-610，不转称本候选已执行。

本批修复两个实际审查缺陷7D5h/7D5n：只有临时clone中真实所有父自动合并的无冲突stage0与approved incoming tree entry精确相同，才能排除 imported main 路径；挑选incoming旧blob的冲突解决仍按修改前登记范围核验。完整历史Program适用schema、跨Foundation/普通任务唯一ID、自身active ISSUE登记/null completion及Registry容量一致性逐快照核验。合法自身续租与main新增外国登记的文本冲突，以去除自身记录的真实共同祖先三方比较独立证明；本侧外国部分不变方可准确导入incoming，外国冲突不能借自身字段豁免。保留合法older main同步、冻结、单父/真实squash集成。

dirty工作树和实际0b的真实Git复现分别明确kind/hash，仅为问题与探索证据，不冒充新发布Source正式Gate。本候选正式完整治理与15检查、同头CI、独立真实历史prospective review仍未完成。已通过检查的结果按其原来源和执行时间归档；修改后的候选不能继承成功声明。永久政策、普通任务/已完成记录、Lease和Owner原窗口不变；不得先行激活GZ005。

Coordinator: program-coordinator-agent
Implementer: lifecycle-scope-repair-agent
Reviewer: independent-lifecycle-scope-review-agent
Integrator: integration-agent
Contract: CONTRACT-PROGRAM-PLAN; consumes CONTRACT-TASK-SPEC/CONTRACT-ACTIVE-WORK

## 当前历史 Review 与完整实现范围修复候选

Task: OPS-004 / Issue71
Phase: history repair implementation
Branch: chore/OPS-004-history-repair-implementation
Base: 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb
Actual published parent: 8c59b0a0a17249a55e9495f19e8e654da540ce8b
Execution Status: NOT_EXECUTED for this changed candidate; full-suite and same-head CI remain required.

实际父来源8c59b0a0a17249a55e9495f19e8e654da540ce8b/tree924cb6450545610c95de6bdb538d7fd6f8d70b6f，正式15项13项exit0、coord1/make2仅原容量FAIL；完整476 PASS624.81s，JUnit476零失败/错误/跳过；同头Gate611完整476 PASS667.83s，唯一必需检查失败为原AgentCoord容量。可选Python缓存清理Post Setup Python 3.11被CI跳过，未把它说成全部steps通过。原始按原实际来源归档，不冒充本候选结果。

本次仅修71Ch/71Cm/71Cq三个实证缺陷：登记base须真实可达；main进入或更新Review绑定真实集成第一父，保留实际claimed rebase Source在完整实现范围检查无错且未改变prior登记base时的Reviewer Evidence tip；复用现有ALLOWED_ACTIVE_TRANSITIONS拒非法跳转；逐完整DAG审计claimed Source之后至Completion基线的自身代码。pre/post精准exclusiveClaims只做归属，不授权新改动；登记暂时消失沿真实reservation后谱系找此前准确范围。自身canonical metadata/Evidence和其他任务不相交代码保留合法。侧Review可以绑定真实main目标而非side工作父；批准main同步仅精确继承真实已审incoming登记且该incoming可达实际集成基线。

新增13个真实Git回归。未提交工作树预检：旧131例130 PASS/1 FAIL315.36s，失败为已有合法rebase Reviewer Evidence tip被误拒；窄兼容修复后相关1旧例+11新例12 PASS32.64s，另2个side真实main目标/批准main新基线同步例PASS5.38s。分组探索不冒充最终144历史用例或完整489治理正式执行；dirty XML明确只12项。history-final-independent内固定actual8c临时Git复现显示原3漏洞；首次foreign正例夹具误删他任务记录的失败原始保留，fixed证明保留上下文后原8c能合法通过。

71Cd要求的状态→角色强制映射不在现行Schema/Transitions/Task CLI协议中；实际已有两个Role组合Transitions无错。Owner不添加该新协议，独立Reviewer仍由已登记独立执行者承接。当前候选尚未正式通过；须发布真实Source、15检查/完整489、同头CI及独立审查后集成，再独立Review/Completion并取得全部主线PASS。原Owner事件、窗口、Lease、永久政策、GZ005及旧completed/普通Ledger不变。

Coordinator: program-coordinator-agent
Implementer: lifecycle-scope-repair-agent
Reviewer: independent-lifecycle-scope-review-agent
Integrator: integration-agent
Contract: CONTRACT-PROGRAM-PLAN; consumes CONTRACT-TASK-SPEC/CONTRACT-ACTIVE-WORK

## 完整后续历史审计补齐：当前正式执行尚未开始

Task: OPS-004 / Issue71
Phase: history repair implementation
Branch: chore/OPS-004-history-repair-implementation
Base: 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb
Actual published parent: 8c59b0a0a17249a55e9495f19e8e654da540ce8b
Execution Status: NOT_EXECUTED for current full147 history / full492 governance / same-head CI.

发布前独立Reviewer对本地alias597d4ca33e5657c2b4eb4594c988944478c62547（不是已发布祖先）真实Git复现发现同批漏洞边界：从seed将reservation作为第二父合入并移除Ownentry，first-parent-only scope fallback遗漏后续Owncode；postclaim side纯metadata非法base或非法edge→还原→净diff空也漏审。本候选统一对reservation后裔的全部postclaim DAG节点复用既有历史登记上下文；没有相邻claims时沿全部真实父查此前准确范围，不能用未来scope或整个MOD-GOV代替。新增三个实际Git用例，相关17项工作树探索PASS55.29s，JUnit零失败/错误/跳过，仅探索记录dirty-targeted-17.xml，不冒充固定Source正式完整492。

597的276路径静态核验和四helper prospective errors[]、10 targeted PASS不抵消该两项P1；审查结论暂不发布，修复后须重新独立核验。597保留本地alias供证据解析。曾创建等树远端对象a0dd0cb7e5fc8342136f2ba26648e9d46fe949c3但从未更新PR head、未执行正式测试或CI，不作为已发布Source/祖先。此前实际8c全476与同头Gate611结果仍仅其自身历史结果。

history-final-independent中597 proof的旧kind字样含ACTUAL_8C时属于复用脚本标签，真实source字段为本地候选597，均为临时Git探索而非actual8c/正式Gate。missing-lineage首版noOwnEntryAtWork=false误读最终工作树已保留，corrected直接读取非法work历史blob为true，history实际漏审均为exit0。原始不覆盖、不替换；本候选Scope/Owner事件/Lease/窗口/永久规则/GZ005/旧completed/Ledger不变。

Coordinator: program-coordinator-agent
Implementer: lifecycle-scope-repair-agent
Reviewer: independent-lifecycle-scope-review-agent
Integrator: integration-agent
Contract: CONTRACT-PROGRAM-PLAN; consumes CONTRACT-TASK-SPEC/CONTRACT-ACTIVE-WORK

## 当前完整 postclaim 上下文候选：正式全量尚未执行

Task: OPS-004 / Issue71
Phase: history repair implementation
Branch: chore/OPS-004-history-repair-implementation
Base: 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb
Actual published parent: 8c59b0a0a17249a55e9495f19e8e654da540ce8b
Execution Status: NOT_EXECUTED for current full150 history / full495 governance / same-head CI.

固定未发布alias8fb的复现确认原登记删除与side非法base/edge漏洞已拒绝，但仍漏掉同批postclaim稳定字段：临时改Ownowner及同步Task、或另普通Task的title/outputPaths、恢复后merge净diff空仍exit0，现有Transitions均拒。当前补原Reservation的Own稳定投影；仅校验普通Task冻结定义（允许status变化和planned/blocked→reserved时issue赋值）、finished状态、already-completed Foundation和旧Ledger身份保护。没有采用non-main side全部foreign equality禁令，OtherTask结构化登记、不相交侧分支代码及Review元数据的归属分类正例通过；未对OtherTask执行真实Admission/Transitions或完整Gate，不称其完整Reservation合法。

20个相关真实Git用例工作树探索PASS73.71s，JUnit零失败/错误/跳过，raw dirty-targeted-20.xml，仅探索而非固定来源150或495全量。前三边界及两新实际问题复现均保留固定8fb raw；kind旧标签含ACTUAL_8C时以source=8fb本地alias字段与本说明为准，不是实际8c正式执行。8fb未更新PR head；等树远端对象0f96789aeae3be42b67d5c880f779b02453fb8c3仅创建未引用，从未正式测试/CI，不当已发布Source/祖先。local alias597/8fb都保留解析原证据。

当前所有发布前探索均不能代替正式全495、15项及同HEAD CI；独立审查必须针对最终固定树。实际已发布父8c正式476和Gate611结果仅其自身历史执行。整个历史保留原Owner事件e25670 blob、容量FAIL、原截止窗口与Lease，不更改任何永久政策、GZ005、旧completed或普通Ledger。只有后续独立Review/Completion和全部main PASS后继续GZ005与完整V1。

Coordinator: program-coordinator-agent
Implementer: lifecycle-scope-repair-agent
Reviewer: independent-lifecycle-scope-review-agent
Integrator: integration-agent
Contract: CONTRACT-PROGRAM-PLAN; consumes CONTRACT-TASK-SPEC/CONTRACT-ACTIVE-WORK

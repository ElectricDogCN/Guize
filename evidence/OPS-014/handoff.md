# OPS-014 历史归属修复正常 Review 专用交接

Task: OPS-014
Issue: #142
Branch: chore/OPS-014-history-code-normal-review
Base SHA: 2a77cbf9ad838b7b7abc7fbc5ed7aaa5f2f793d4
本次交接修正父提交: 6a18e21e50bb18da9a568477a6de79c23e61c39d
候选Source Commit / tree：本分支实际Git HEAD及其tree，由固定源清单和每份raw的Source Commit绑定完整SHA；本文件不预填尚未产生的自身提交哈希。
最新真实代码源: 52a47798e704c51db7930e72eb75b910a138ca0f
最新真实代码合并: PR150 / 2a77cbf9ad838b7b7abc7fbc5ed7aaa5f2f793d4
原416合同交付: PR145 / 09d247f97b318ebe8bdeee1dae539e26a17598ea；原冻结/独立解冻证明保持。

## 角色、原租约与容量

Owner: ElectricDogCN
Coordinator: program-coordinator-agent
Implementer: poc-contract-repair-implementation-agent
Reviewer: independent-review-agent（实际独立只读角色/root/gz022_planning_independent_review）
Integrator: integration-agent
元数据作者及集成执行：/root依据既有用户委托；作者不充当唯一独立Reviewer。
当前status/agentRole: review/reviewer；MOD-GOV / high。
原lease: 2026-10-24T21:42:30Z → 2026-10-31T21:42:30Z；未续租。
coordinationGroup: poc-contract-repair；integrationOrder: 10；integrationStrategy: merge。
独占claims保留：scripts/check-program-plan-history.py；tests/governance/test_poc_contract_repair_admission.py；本阶段不修改代码。
共享路径：无。3活动/1high仍保留，不提前完成或释放，不改变foreign任务和租约。

## 实际文件与契约版本

相对Base的完整48条库存在evidence/OPS-014/history-review-changed-files.md，与实际Git diff逐项对齐。仅Own Program status、Active当前上下文、完整Task及Evidence；本次修正相对6a18父源只修改本handoff。
消费CONTRACT-PROGRAM-PLAN（Program schemaVersion=1）、CONTRACT-TASK-SPEC（Task schemaVersion=2）、CONTRACT-ACTIVE-WORK（Registry version=1）、POC-PROTOCOL-V1（v1）。全部正式契约版本/字节固定于已接受Base 2a77cbf9ad838b7b7abc7fbc5ed7aaa5f2f793d4，无新增契约、Schema或迁移。
Gov2代码、原OPS-013授权、AGENTS、模块所有权、原POC checker/test、recovery-proof及六字段恢复事件、普通完成账本和foreign字节保持。

## 实际验证、退出码与原始证据

真实代码源52a4779的15项全部退出0，direct governance和make verify各752项、两个非空JUnit零失败/错误/跳过；源CI859的752项及最终独审通过。实际代码main2a77自己的7项、pushCI860的752项及独立主线接受完成。
上述实际完整source、argv、PID/wait、exitCode、raw SHA、两个JUnit和CI执行身份均在evidence/OPS-014/history-review-prerequisites/index.json的37份可恢复原件中；第00份是实际代码主线独立接受。原件保留自身source归属，不替代当前Review执行。
父metadata源6a18e21的13项实际全部退出0，独立内容审查仅以P2-HANDOFF-CONTEXT拒绝发布。其Git提交/bundle、13raw/results和负回执完整保留；负回执SHA256为6c171ad7b022c1852bfdc1fb4976d551503e949026f5b911d5f5e45edb996aa1。技术13通过不等于父源获内容或发布接受。
当前前向候选的13项须提交后实际执行；当前退出码UNEXECUTED，以新源原始日志为准。固定Source/tree/13raw与结果清单将按新实际Git HEAD命名保存；完整同头CI752、最终源独审及实际Review main接受仍待完成。

## 当前必须执行的命令

完整13条命令逐字列于specs/tasks/OPS-014.md的“必须执行的测试”与evidence/OPS-014/commands.txt，包括diff、Task、Schema、Program integrity/history/transitions/lifecycle/coordination/finalization、scope、Evidence、readiness和Markdown；base固定为2a77完整SHA，branch固定为本分支，head绑定实际候选。
每条raw保留Source Commit、实际Command、PID、wait完成和Exit Code，失败不能删除或跳过。纯metadata阶段的13项在本阶段开始前按正常Review确定；代码阶段两次完整752原件保留，新源仍须完整同头CI752。

## 下一角色精确动作

Implementer：只提交本handoff前向修正，冻结实际HEAD/tree；在独立native克隆实际执行13条，保存全部退出码和raw，不继承6a18的通过。确认48库存、code/proof/claims/foreign字节与Base相同，租约及共享none保持。
Reviewer：核固定新source/专用handoff/37原件及13条实际raw真实性和Own边界，决定普通验证PR是否准入；新源完整CI752结束后核零失败/错误/测试跳过、最新reviews/threads及最终源接受。
Integrator：最终源接受后重新读取main/base/head、Issue142仍open、原lease/角色/Gov2/3活动1high及Review线程，执行普通expected-head merge；再验实际Review main的有序parents/tree、自己的主线检查、pushCI和独立接受。只有实际Review main完整接受后才单独正常Completion，完成身份必须指真实代码PR150/2a77，不能用Review或Completion metadata merge替代。
后继POC：同步已完整接受的代码主线并运行各自完整源门禁；本Review不批准输入、资源、窗口、实验或资格。

## 可执行的回滚与恢复路径

未合入：撤回本Review提案，保留branch/工作目录/旧成功和失败原件；main仍保持合法in_progress登记与high，不直接改main。
已合入而元数据有误：从届时最新main创建同Task有界前向修复分支，在有效原lease与独立审查下只修Own合法状态/上下文；执行对应Task门禁和完整同头CI后普通合并，再独立验证实际主线。不回滚代码PR150、原416合同或freeze/thaw proof。
无数据库迁移、生产服务/数据或Secrets变更。不得reset/rebase历史、删除原件、本地引用和工作目录，或通过metadata伪造完成/释放容量。

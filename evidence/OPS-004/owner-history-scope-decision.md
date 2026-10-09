# OPS-004 精确前向修复范围决定

Task: OPS-004 / Issue71
Decision authority: 用户明确最高决策权委托，由 Coordinator 记录具体决定。
Existing bounded event: OPS-004-LIFECYCLE-ADMISSION-20261009
Window remains: 2026-10-09T13:09:31Z until OPS-004 Completion or 2026-10-10T01:09:31Z, earliest.

实际发布 Completion c5bf 和 Gate598 确证 history 来源校验与合法 Review 基线刷新冲突。独立 Reviewer 确认不能假写 Review PR 身份、不能在纯 Completion 越界改生产。

按现有 Foundation 自身范围调整协议，先独立 metadata-only review→blocked 登记，仅追加 scripts/check-program-plan-history.py 和 tests/governance/test_program_plan_history.py 两条精确 MOD-GOV claims。原四条、原Lease、独立角色与Issue71身份保留；本登记不实施新增代码。合入后独立 blocked→in_progress 修复真实首次登记来源证明，并保留严格可达/后代/自身任务绑定及负例。

该决定只更新原有修复事件的必要代码范围。参与者仍仅已有GZ005 reserved快照和OPS004；永久maxHighRiskTasks=1不改、窗口不延期、不准普通实现、容量FAIL仍FAIL，其他所有失败不豁免。最终Completion移除自己的Lease后，全部检查/完整治理/make/实际CI/main必须成功。Issue71重新打开；原关闭事实与全部失败原始证据保留。若窗口到期仍未收口，停止新实现并记录具体恢复决定，不能自动延期。

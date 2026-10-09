# OPS-004 当前实现范围

当前实现基线为 PR76 merge 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb；独立 blocked→in_progress 已激活。本次新增生产修改严格为 scripts/check-program-plan-history.py 与 tests/governance/test_program_plan_history.py。Registry 仍保留六条已经批准的精确 claims，sharedPaths 空；Task/Evidence 与自身 Program/Registry 生命周期元数据为自身 canonical metadata。

原先四条是 PR72 初次登记范围；两条 history/test 在 PR76 metadata-only 精确登记后获准。永久 policy、原 Lease、完整 GZ005 快照、其他 Task/Evidence、旧 completed 身份及普通 Ledger 不变。Owner 事件截止时间和参与任务不变，容量 FAIL 不改称 PASS。范围决定见 owner-history-scope-decision.md。

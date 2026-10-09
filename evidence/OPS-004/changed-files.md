# OPS-004 完整当前实现文件清单

Task: OPS-004 / Issue71
Base: 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb
Branch: chore/OPS-004-history-repair-implementation
Tested Source Commit: 6ecfcf49477341c90bc729743d05f17f2dc0dc24

覆盖当前全部 60 路径，含全部归档及本清单；最终 Source SHA/tree 与14检查/CI独立绑定。

```text
evidence/OPS-004/changed-files.md
evidence/OPS-004/commands.txt
evidence/OPS-004/handoff.md
evidence/OPS-004/scope.md
evidence/OPS-004/source-history/ops004-scope-fresh-history-proof.json
evidence/OPS-004/summary.md
evidence/OPS-004/test-results/README.md
evidence/OPS-004/test-results/history-repair-ci-603/job-log.txt
evidence/OPS-004/test-results/history-repair-ci-603/proof.json
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/clean-after.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/clean-before.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/coordination.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/evidence.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/finalization.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/governance.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/governance.xml
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/history.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/integrity.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/lifecycle.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/raw-lifecycle.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/readiness.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/schemas.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/scope.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/source.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/status.json
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/task.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/transitions.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/tree.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/unaffected.txt
evidence/OPS-004/test-results/history-repair-source-6ecfcf4/verify.txt
evidence/OPS-004/test-results/history-scope-final-90/clean-after.txt
evidence/OPS-004/test-results/history-scope-final-90/clean-before.txt
evidence/OPS-004/test-results/history-scope-final-90/coordination.txt
evidence/OPS-004/test-results/history-scope-final-90/docs.txt
evidence/OPS-004/test-results/history-scope-final-90/evidence.txt
evidence/OPS-004/test-results/history-scope-final-90/finalization.txt
evidence/OPS-004/test-results/history-scope-final-90/history.txt
evidence/OPS-004/test-results/history-scope-final-90/integrity.txt
evidence/OPS-004/test-results/history-scope-final-90/lifecycle.txt
evidence/OPS-004/test-results/history-scope-final-90/ops004-history-scope-final-ci-600-proof.json
evidence/OPS-004/test-results/history-scope-final-90/ops004-history-scope-final-ci-600.txt
evidence/OPS-004/test-results/history-scope-final-90/ops004-history-scope-inventory-ci-601-proof.json
evidence/OPS-004/test-results/history-scope-final-90/ops004-history-scope-inventory-ci-601.txt
evidence/OPS-004/test-results/history-scope-final-90/raw-lifecycle.txt
evidence/OPS-004/test-results/history-scope-final-90/readiness.txt
evidence/OPS-004/test-results/history-scope-final-90/schemas.txt
evidence/OPS-004/test-results/history-scope-final-90/scope.txt
evidence/OPS-004/test-results/history-scope-final-90/source.txt
evidence/OPS-004/test-results/history-scope-final-90/status.json
evidence/OPS-004/test-results/history-scope-final-90/task.txt
evidence/OPS-004/test-results/history-scope-final-90/transitions.txt
evidence/OPS-004/test-results/history-scope-final-90/tree.txt
evidence/OPS-004/test-results/history-scope-final-90/unaffected.txt
evidence/OPS-004/test-results/history-scope-main-602/job-log.txt
evidence/OPS-004/test-results/history-scope-main-602/proof.json
scripts/check-program-plan-history.py
specs/coordination/active-work.yaml
specs/coordination/program-plan.yaml
specs/tasks/OPS-004.md
tests/governance/test_program_plan_history.py
```

复核：git diff --name-only 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb HEAD。新增生产修改仅已登记history checker/test，其余自身canonical metadata/Evidence。

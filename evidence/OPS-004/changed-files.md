# OPS-004 本次历史来源修复完整文件清单

Task: OPS-004 / Issue71
Base: 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb
Branch: chore/OPS-004-history-repair-implementation

本清单覆盖当前全部 37 条路径，含自身全部 Evidence 与本清单。归档时须刷新为最终全部路径。正式 Source SHA 与检查结果会另行绑定，不把探索测试视作完整验收。

```text
evidence/OPS-004/changed-files.md
evidence/OPS-004/commands.txt
evidence/OPS-004/handoff.md
evidence/OPS-004/scope.md
evidence/OPS-004/source-history/ops004-scope-fresh-history-proof.json
evidence/OPS-004/summary.md
evidence/OPS-004/test-results/README.md
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

复核：git diff --name-only 31ffefe0b4ba9a8b413a590bb46ee43ae6288dfb HEAD。新增生产路径仅 history checker 与对应测试；其余为自身 canonical metadata/Evidence。

# Rollback verification

当前未合并。后续在独立分支以 diff 证明旧任务、Ledger、contracts 字节不变；不把未执行的检查当作成功。

```bash
git diff --exit-code 413a6a4dd91b5d79a3d2b7d1e5f03f8121848170 HEAD -- specs/coordination/task-completions.yaml specs/tasks/GZ-005.md evidence/GZ-005 contracts specs/poc
```

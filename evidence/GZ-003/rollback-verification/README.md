# GZ-003 Rollback Verification

PR 合并前：关闭 PR 并保留分支，无需改写 `main`。

合并后：

```bash
git checkout main
git pull --ff-only origin main
git checkout -b fix/GZ-003-revert-multi-agent-readiness
git revert -m 1 <GZ-003-merge-commit>
git push -u origin fix/GZ-003-revert-multi-agent-readiness
```

随后创建 Revert PR，并运行旧基线可用的 `make verify`。不得直接推送或强制重写 `main`。

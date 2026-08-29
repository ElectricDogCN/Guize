# GZ-014 Rollback Verification

Before reservation merge:

```bash
git switch main
git branch -D chore/GZ-014-reservation
```

After merge, create an independent revert branch and PR; do not push `main` directly. Verify rollback with:

```bash
python scripts/check-agent-coordination.py
python scripts/check-project-readiness.py
make verify TASK=GZ-003 BASE=origin/main BRANCH=chore/GZ-003-multi-agent-readiness
```

# GZ-014 Rollback Verification

Before merge, close the PR and retain the branch. After merge, create an independent revert branch and PR:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b fix/GZ-014-revert-readiness-repair
git revert <GZ-014-merge-commit>
git push origin fix/GZ-014-revert-readiness-repair
```

Then verify Project Readiness and Governance Gate. Direct push to `main` is forbidden.

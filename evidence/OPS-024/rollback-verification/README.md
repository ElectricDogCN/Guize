# OPS-024 rollback-verification

Withdraw the unmerged candidate; after merge use a separately reviewed forward correction. No destructive operation was tested.

```bash
git diff --stat 659c7ad28af040e449eb5e6700682b52ec401056...HEAD
```

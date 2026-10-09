# GZ-005 reservation rollback

NOT_EXECUTED: this candidate is unmerged. Closing its PR before merge leaves main intact.
After merge, use an independently reviewed cancellation/blocking lifecycle change for
GZ-005 and release only its lease. Never reset completed tasks or rewrite the Ledger.

Read-only scope verification against the registration base:

```bash
git diff --name-only 788e6f257d9052db81a8df793bf8b448a05011a1 HEAD
git diff --exit-code 788e6f257d9052db81a8df793bf8b448a05011a1 HEAD -- specs/coordination/task-completions.yaml specs/tasks/GZ-010.md evidence/GZ-010 contracts scripts tests AGENTS.md
```

Actual verification outputs and exit codes belong in test-results after execution.

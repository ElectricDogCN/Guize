# OPS-004 current scope registration complete file inventory

Task: OPS-004 / Issue71
Baseline: 62d4ef826e0be1acb2839c3f04fe62d1894f9585
Branch: chore/OPS-004-history-scope-registration
Last verified published head: 99b5a5bff559c6a9589554d5b251f0127a02277c

This complete47-path inventory includes the current two-file Evidence correction (this manifest and scope.md), not just the18 paths from tested7f. The final published head must be verified separately. Raw testedSource identities remain unchanged.

```text
evidence/OPS-004/changed-files.md
evidence/OPS-004/commands.txt
evidence/OPS-004/handoff.md
evidence/OPS-004/owner-history-scope-decision.md
evidence/OPS-004/scope.md
evidence/OPS-004/source-history/history-scope-reproduction.md
evidence/OPS-004/source-history/history-scope-source-map.json
evidence/OPS-004/summary.md
evidence/OPS-004/test-results/README.md
evidence/OPS-004/test-results/completion-first-c5bf/actual-ci-598.txt
evidence/OPS-004/test-results/completion-first-c5bf/clean-before.txt
evidence/OPS-004/test-results/completion-first-c5bf/history.txt
evidence/OPS-004/test-results/completion-first-c5bf/integrity.txt
evidence/OPS-004/test-results/completion-first-c5bf/readiness.txt
evidence/OPS-004/test-results/completion-first-c5bf/schemas.txt
evidence/OPS-004/test-results/completion-first-c5bf/source.txt
evidence/OPS-004/test-results/completion-first-c5bf/status.json
evidence/OPS-004/test-results/completion-first-c5bf/task.txt
evidence/OPS-004/test-results/completion-first-c5bf/tree.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/clean-after-governance.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/clean-after.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/clean-before.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/coordination.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/evidence.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/finalization.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/governance.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/governance.xml
evidence/OPS-004/test-results/history-scope-published-7f77774/history.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/integrity.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/lifecycle.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/raw-lifecycle.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/readiness.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/runner-note.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/schemas.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/scope.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/source.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/status.json
evidence/OPS-004/test-results/history-scope-published-7f77774/task.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/transitions.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/tree.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/unaffected.txt
evidence/OPS-004/test-results/history-scope-published-7f77774/verify.txt
evidence/OPS-004/test-results/history-scope-remote-599/job-log.txt
evidence/OPS-004/test-results/history-scope-remote-599/proof.json
specs/coordination/active-work.yaml
specs/coordination/program-plan.yaml
specs/tasks/OPS-004.md
```

Reconstruct and compare the complete inventory using:

```bash
git diff --name-only 62d4ef826e0be1acb2839c3f04fe62d1894f9585 HEAD
```

The canonical non-Evidence differences are only own Program blocked status, own Registry base/branch/role/six precise claims and Task context. All other listed files are own Evidence. No production checker/test is modified before this scope registration merge. No GZ005/policy/Ledger/oldcompleted identity is changed. Final archive14, same-head CI and independentReview remain required; bounded capacity remains FAIL.

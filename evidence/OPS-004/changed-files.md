# OPS-004 Implementation changed files

Actual tested source: 751dc3db960420f64641c4edd935f7669d026c85
Base: d0e9e256552f9d1d47fb24d2e5a4530476b19a5f

```text
evidence/OPS-004/handoff.md
evidence/OPS-004/summary.md
evidence/OPS-004/test-results/exploratory-f3bbfed.xml
evidence/OPS-004/test-results/implementation-first-2da30c0/coordination.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/evidence.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/finalization.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/governance.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/governance.xml
evidence/OPS-004/test-results/implementation-first-2da30c0/history.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/integrity.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/lifecycle.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/raw-lifecycle.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/readiness.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/schemas.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/scope.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/source.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/status.json
evidence/OPS-004/test-results/implementation-first-2da30c0/task.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/transitions.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/tree.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/unaffected.txt
evidence/OPS-004/test-results/implementation-first-2da30c0/verify.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/coordination.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/evidence.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/finalization.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/governance.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/governance.xml
evidence/OPS-004/test-results/implementation-local-6cb4c67/history.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/integrity.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/lifecycle.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/raw-lifecycle.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/readiness.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/schemas.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/scope.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/source.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/status.json
evidence/OPS-004/test-results/implementation-local-6cb4c67/task.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/transitions.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/tree.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/unaffected.txt
evidence/OPS-004/test-results/implementation-local-6cb4c67/verify.txt
evidence/OPS-004/test-results/ops004-ci-env-reproduction-6cb.txt
evidence/OPS-004/test-results/ops004-ci-env-reproduction-6cb.xml
evidence/OPS-004/test-results/registration-remote-590/ops004-registration-remote-ci.txt
evidence/OPS-004/test-results/registration-remote-590/ops004-registration-remote-proof.json
scripts/check-agent-coordination.py
scripts/check-task-scope.py
specs/coordination/active-work.yaml
specs/coordination/program-plan.yaml
specs/tasks/OPS-004.md
tests/governance/test_active_metadata_scope.py
```

Subsequent archive changes are confined to evidence/OPS-004/**. Production changes are the two reserved coordination/scope validators; tests exercise actual isolated committed histories and four raw/CI entry points. Program/Registry/Task changes are only OPS-004 legal activation. Old completion identities, GZ-005 snapshot and permanent policy are preserved.

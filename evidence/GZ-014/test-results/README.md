# GZ-014 Test Results

## Verified integration lifecycle

- Review transition PR #28 merged as `b15ed0dd907c59a69f1fd178907f648fef2b880a`.
- Post-review `main` Governance Gate run #276: `PASS`.
- Integration transition PR #29 exact HEAD `24430bffbcbd92c04cfaa48e3852c2e442882fce` passed Governance Gate run #277 and fresh independent review.
- PR #29 merged as `c26fc712e050dba4e83c9af022fd25b8f7e84d6d`.
- Post-integration `main` Governance Gate run #278: `PASS`.

## Failed Completion attempt

PR #30 Governance Gate run #279: `FAIL`.

Observed defects:

1. Foundation provenance was bound to PR #26 / `ef104...`; the current integration lease base is review merge `b15ed0...`, so the completion merge must be a strict descendant and the correct lifecycle completion identity is PR #29 / `c26fc...`.
2. Three `test_check_schemas.py` tests accessed `active["tasks"][0]` directly. That fixture assumption is invalid after a legitimate Foundation completion because an empty Active Work Registry is allowed and expected.
3. Completion Evidence required explicit PASS/COMPLETED status.

The failed PR was closed without merge and Issue #17 was reopened. No completion status or Lease release entered `main`.

## Completion-readiness regression repair

The repair changes only:

- `tests/governance/test_check_schemas.py`;
- `evidence/GZ-014/commands.txt`;
- `evidence/GZ-014/test-results/README.md`.

Test behavior:

- the current repository test passes with either legitimate active tasks or no active task after completion;
- mutation tests explicitly create a valid active GZ-014 Foundation fixture before changing `programTaskId`, Task wave or Registry wave;
- all existing negative assertions for missing Lease, policy drift, disabled safety policy, branch mismatch, contract mismatch and path expansion remain;
- no Schema, Program, Registry, lifecycle script or Completion rule is weakened.

Mandatory validation:

```bash
python scripts/check-task-file.py --task GZ-014
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python -m pytest tests/governance/test_check_schemas.py -v
python -m pytest tests/governance/ -v
python scripts/run-program-lifecycle-gate.py --base-ref origin/main --head-ref HEAD --task GZ-014 --branch-name chore/GZ-014-foundation-integration
python scripts/run-agent-coordination-gate.py --task GZ-014 --base-ref origin/main --head-ref HEAD --branch-name chore/GZ-014-foundation-integration
python scripts/run-task-scope-gate.py --task GZ-014 --base origin/main
python scripts/check-evidence.py --task GZ-014
make verify TASK=GZ-014 BASE=origin/main HEAD_REF=HEAD BRANCH=chore/GZ-014-foundation-integration
```

Result: `PENDING EXACT-HEAD REPAIR VALIDATION`.

No repair PR Gate, review, merge or post-merge result is claimed before GitHub executes it.

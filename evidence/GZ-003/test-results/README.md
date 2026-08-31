# GZ-003 Test Results

## Original delivery verification

- PR：#11
- Tested branch head：`602856cf83554703f8aafd8f98f3eeddcbfa9698`
- Workflow run ID：`33199139029`
- Job ID：`98943864286`
- Conclusion：`success`
- Governance tests：106 passed, 0 skipped

GZ-003 later merged through PR #11 as `9e3a821ada292ac3ef69b7c059384d17f6530b48` and remains a completed Foundation task.

## Post-completion maintenance — PR #35

### Run #303

- HEAD before Evidence refresh：`6ba34e972cd3d7eb5e07a6d8d8eb9b2e263a7998`
- Workflow run：`33327335520`
- Result：`FAIL`
- Observed cause：Program finalization required refreshed GZ-003 completion Evidence for the maintenance diff. Other reported Gate areas succeeded.

### Run #306

- Tested HEAD：`a4609ed7dcdb01147e66ad41dc72d2c8bb45e3bd`
- Workflow run：`33327893886`
- Job：`99301183761`
- Result：`FAIL`

Observed failures were confined to the maintenance test implementation and completed-task Evidence finalization:

1. Program finalization required `evidence/GZ-003/test-results/README.md` to be refreshed for the maintenance PR.
2. Governance suite result：`251 passed, 10 failed`.
3. Three schema tests failed because the maintenance branch had removed the explicit active-Foundation fixture from Foundation-negative tests.
4. Several lifecycle tests failed because the branch carried a stale test-file overwrite that referenced production-checker APIs not present on the current target `main` and hard-coded the historical GZ-014 task context.

### Run #312

- Tested HEAD：`d6253b00a5dfb22aa0aa5a85af69ba3499a801e1`
- Workflow run：`33344565626`
- Job：`99346174946`
- Result：`FAIL`
- Governance suite：`259 passed, 0 failed, 0 skipped`

The rebuilt tests were correct on this HEAD. Task validation, Project Readiness, Agent Coordination, governance tests, skip audit, Markdown, Schema, Secret, Evidence, Evidence integrity, linkage, scope, spec-sync, repository boundary and CI static validation all passed. Program execution integrity, Program history, Program transitions and Program finalization also passed.

The single remaining failure was the lifecycle scope guard:

```text
Lifecycle task GZ-003 changed files outside its metadata scope:
['tests/governance/test_check_schemas.py',
 'tests/governance/test_program_lifecycle_guards.py']
```

That failure is correct for normal completed tasks. GZ-003 is already completed, so its normal metadata-only completion scope cannot be reused to change governance tests.

## One-time bootstrap migration repair

The newer HEAD adds a fail-closed, fixed-base self-hosting exception only in `scripts/check-program-lifecycle-guards.py`. It can apply only when:

- task is exactly GZ-003;
- target base is exactly `3be9477fb137aa33faa6320f2454b9e1e1d5ec2d`;
- GZ-003 remains `completed -> completed`;
- Program Plan, Active Work, completion ledger and GZ-003 Task Spec are unchanged;
- the changed-file set is exactly the seven audited migration files.

Focused tests reject the exception for a wrong base, any extra path, Program/Registry/Ledger drift or Task Spec drift. The exception automatically becomes unusable after `main` advances.

## Current maintenance validation boundary

The latest PR #35 HEAD is newer than run #312. Runs #303/#306/#312 are retained as failure evidence but do not prove the latest HEAD. A new exact-head Governance Gate and fresh review are mandatory before merge.

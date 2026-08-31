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

The production governance checkers were not weakened to make these failures pass. The maintenance branch is being rebuilt from the current `main` versions of both test files, with only the minimum compatibility changes needed for ordinary Program Task reservations.

## Current maintenance validation boundary

The latest PR #35 HEAD after the rebuild is newer than run #306. Therefore neither the original delivery run nor runs #303/#306 prove the latest HEAD. A new exact-head Governance Gate and fresh review are mandatory before merge.

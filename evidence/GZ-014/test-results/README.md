# GZ-014 Test Results

## Verified predecessor

- PR #26 merged as `ef1048344aa082c678e5ef948dc7f62e5aa84510`.
- Post-merge `main` Governance Gate run #267: `success`.

## Foundation lifecycle-state repair

### Added regression coverage

`tests/governance/test_foundation_lifecycle_states.py` verifies:

1. the repository's complete Program Plan validates when GZ-014 Foundation status is `review`;
2. the same Program Plan validates when Foundation status is `integration`;
3. an unknown Foundation status is rejected by JSON Schema;
4. a temporary Git history with Foundation base state `integration` can transition to `completed` only with Program metadata, Lease removal, completed Task Spec and structured task-bound Evidence.

### Governance Gate run #268

- HEAD: `656c7b9c20cd18de2850caa46c734f46a0fc6c90`
- Result: `PASS`

Successful areas:

- Task file validation;
- Project Readiness;
- Program Plan integrity, history, transitions, finalization and lifecycle guard;
- Agent Coordination;
- full governance test suite and skip audit;
- Markdown, Schema and Secret checks;
- Evidence, Evidence Integrity, PR/task linkage, Scope and Spec Sync;
- repository-boundary and CI static validation.

## Final-head rule

Evidence updates are newer than run #268. The latest PR #27 HEAD must receive its own successful Governance Gate and fresh Review. No approval or merge may rely only on run #268.

Result: PENDING FINAL HEAD VALIDATION

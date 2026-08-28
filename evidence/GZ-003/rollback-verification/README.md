# GZ-003 Rollback Verification

## Before merge

Closing the PR leaves `main` unchanged. The branch and Evidence remain available for audit.

## After merge

A rollback must be performed through a dedicated Fix/Revert branch and PR. Verification must confirm:

1. `.github/workflows/collaboration-gate.yml` is removed or reverted consistently;
2. collaboration scripts, tests and templates return to the pre-GZ-003 state;
3. README no longer links to removed collaboration files;
4. the existing Governance Gate remains intact and successful;
5. no GZ-001/GZ-002 history, ADR or Evidence is rewritten;
6. downstream tasks created under the collaboration contract are assessed before removal of their gate.

No rollback execution is claimed before a real revert is required.

# GZ-014 Follow-ups

## Before implementation merge

1. Latest PR #21 HEAD Governance Gate must be `success`.
2. Inspect all job steps and logs; no skipped, swallowed or advisory-only critical failure.
3. Inspect Codex and human review threads on the latest HEAD.
4. Resolve only findings that are actually fixed and revalidated.
5. Independent Reviewer must confirm Program Plan, contract ownership, POC split, path scope and external blocker handling.
6. Integrator must compare PR #21 against `main`, verify no business implementation or contract content leaked into GZ-014, then merge with expected HEAD.

## After implementation merge

Create `chore/GZ-014-release` from the implementation merge commit and submit a small cleanup/release PR that:

1. records the real implementation merge SHA in Evidence and Program Plan foundation task;
2. changes `specs/tasks/GZ-014.md` to `completed`;
3. removes the GZ-014 entry from `active-work.yaml` or archives it according to the accepted protocol;
4. changes Program Plan GZ-014 foundation status to `completed`;
5. finalizes `summary.md`, `commands.txt`, `test-results`, `handoff.md` and changed-file record;
6. runs Schema, Readiness, Coordination, Governance Tests, Evidence and `make verify`;
7. receives independent Review and merges with expected HEAD;
8. closes Issue #17 as completed.

## Downstream start order

After GZ-014 cleanup/release merges:

- GZ-004 and GZ-010 may create independent reservation PRs in W1 if review capacity permits;
- GZ-005 starts only after GZ-004;
- POC-001～POC-010 start only after GZ-010 and according to their waves/dependencies;
- no business vertical slice starts before required contracts, POCs, acceptance baseline and scaffolds are merged.

## External blocker

OPS-001 (#20) remains open until GitHub API verifies `main` protection, active Ruleset, Required Governance Gate, PR/approval/conversation requirements, stale approval dismissal and force-push/delete prohibition. It must block GZ-020 production release, not earlier repository-only specification work.

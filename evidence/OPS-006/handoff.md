# OPS-006 Registration Handoff

## Current phase

Registration bootstrap amended after exact initial CI classification; not approved, not merged, not reserved, not activated and not implemented.

## Identity

- Task: OPS-006
- Issue: #52
- Draft PR: #53
- Contract: PROGRAM-TASK-REGISTRATION-V1
- Target base: `main@219d7096756ad75717a46d85baf7d2b216e2472b`
- Initial classified source HEAD: `b216f84368b54e631dce0b57b46b14cf5424e068`
- Initial workflow run/job: `33720823036` / `100539417786`
- Branch: `chore/OPS-006-task-registration`
- Wave / Integration Order: W1 / 3
- Risk: medium
- Depends On: GZ-014 completed
- Requirement: REQ-V1-0010
- Module: MOD-GOV

## Initial result

Run 441 passed schema, Program Integrity, Evidence, secret, compile, collection and 257/259 governance tests. Its failures were confined to planned-state dispatch, final-DAG append classification, terminal GZ-004 Wave occupancy and the two repository-state tests that mirror those gaps.

## Scope refinement

Future implementation now includes Project Readiness and its contract test. Only terminal `completed/cancelled` release Wave occupancy; every non-terminal state remains counted. No capacity value changes.

## Exact next action

After this metadata amendment is committed, inspect the new exact PR HEAD, all changed files, checks and review threads. Classify every red check against the registered legacy Registration gaps. Do not approve or merge from this handoff. Present the exact evidence and request a separate user merge decision only after no unrelated blocker remains.

## Forbidden next action

Do not create Active Work, do not start OPS-006 implementation, do not modify PR #51 content, do not increase concurrency limits, do not merge any PR, and do not claim current Harness failures are passing evidence.
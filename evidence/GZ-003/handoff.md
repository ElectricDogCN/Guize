# GZ-003 Handoff

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Status: COMPLETED
Current Maintenance: OPS-007 #54 / Draft PR #55

## Identity and custody

- Original task: GZ-003
- Original issue: #10
- Original completion PR: #11
- Original completion merge: `9e3a821ada292ac3ef69b7c059384d17f6530b48`
- Prior completed maintenance: OPS-003 #43 / PR #44 / merge
  `d23543f97facff00d02f79aab1693a37788765c9`
- Current tracking: OPS-007 #54
- Current Draft PR: #55
- Branch: `fix/GZ-003-terminal-wave-occupancy`
- Base: `main@219d7096756ad75717a46d85baf7d2b216e2472b`
- Initial functional HEAD: `4e6a87df98d03f9146ccd9bd37238d3aefc87abc`
- Program/Foundation state: remains `completed`
- Shared paths: NONE

## Problem handed off

Project Readiness counted every task row in a Wave, including `completed` and
`cancelled` history. W1 has capacity two, completed GZ-004, and active GZ-010.
OPS-006 Registration therefore became a third counted row, and its required
later `planned -> reserved` phase could never be green.

PR #53 is blocked and remains Draft. OPS-007 introduces the prerequisite repair
before OPS-006 Registration can be rebuilt from a new green `main`.

## Current changed-file boundary

The refreshed PR #55 diff is expected to contain exactly eight files:

1. `scripts/check-project-readiness.py`;
2. `tests/governance/test_terminal_wave_occupancy.py`;
3. `evidence/GZ-003/terminal-wave-occupancy-repair.md`;
4. `evidence/GZ-003/test-results/terminal-wave-occupancy-local.md`;
5. `evidence/GZ-003/summary.md`;
6. `evidence/GZ-003/commands.txt`;
7. `evidence/GZ-003/handoff.md`;
8. `evidence/GZ-003/test-results/README.md`.

No Program Plan, Active Work, Completion Ledger, Task Spec, configured safety
limit, workflow, OPS-005, GZ-010, POC, product contract, business code,
deployment, Secret, permission, or production data is changed.

## Implemented behavior

The checker derives structural Wave occupancy by excluding exactly:

- `completed`;
- `cancelled`.

The occupancy subset is used only for Wave concurrency, high-risk concurrency,
critical standalone, and same-Wave path-conflict checks. Every non-terminal
state remains occupying. Full Program history remains in all identity, DAG,
contract, Requirement/Module, blocker, and release checks.

## Verified facts

Gate #443 / run `33727116285`, generated merge
`b78f2a2a078b6993f75f8b4579c3ea930eacf040`, observed:

- Project Readiness PASS;
- 267/267 governance tests PASS;
- all 8 new regressions PASS;
- zero skipped tests;
- every executed non-Finalization gate PASS;
- Finalization FAIL only for the missing refresh of the four canonical Evidence
  files now updated by this commit.

Lifecycle scope was not executed after the fail-fast Finalization result, so it
remains an explicit pending boundary rather than a claimed pass.

## Required next decision sequence

1. Run a new exact-head Governance Gate after this canonical Evidence refresh.
2. Confirm Finalization is green and classify every remaining failure exactly.
3. Obtain a fresh independent review of the same HEAD and resolve every content
   blocker and review thread.
4. Do not add a checker exception, capacity increase, status bypass, or
   reusable break-glass.
5. Only a Human Owner / Integrator may make the separately documented one-time
   merge decision allowed by OPS-007 #54.
6. After any authorized merge, require a fully green `main` Gate; otherwise
   immediately block downstream work and use a dedicated revert or repair PR.
7. Only after green `main`, rebuild PR #53 from that exact main and prove the
   OPS-006 `planned -> reserved` candidate tree passes Project Readiness.

## Rollback

Before merge, close PR #55. After an authorized merge, revert the repair commit
through a dedicated PR if post-merge `main` is red or review finds semantic
weakening. Never rewrite `main`, alter historical completion identity, increase
Wave capacity, or suppress lifecycle checks.

This handoff is not merge authorization.

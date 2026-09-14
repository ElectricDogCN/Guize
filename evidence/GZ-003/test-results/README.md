# GZ-003 Test Results

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Result: PASS
Status: COMPLETED
Current Maintenance: OPS-007 #54 / Draft PR #55

## Completion continuity

GZ-003 remains completed. OPS-007 does not reopen its Foundation state, create a
new Completion Ledger record, or replace original completion merge
`9e3a821ada292ac3ef69b7c059384d17f6530b48`.

Prior OPS-003 maintenance was merged through PR #44 as
`d23543f97facff00d02f79aab1693a37788765c9`. The current test result concerns
only OPS-007 terminal Wave occupancy behavior.

## Local focused regression

Base fixtures were byte-verified against
`main@219d7096756ad75717a46d85baf7d2b216e2472b`.

Command:

```text
python -m unittest -v tests/governance/test_terminal_wave_occupancy.py
```

Result:

```text
Ran 8 tests in 14.306s

OK
```

The suite proves:

- only `completed` and `cancelled` release structural Wave occupancy;
- completed history permits one active plus one planned task in a capacity-two
  Wave;
- cancelled history releases capacity and obsolete path claims;
- a third non-terminal task still fails concurrency;
- non-terminal high-risk, critical-standalone, and path-conflict limits remain
  fail-closed;
- terminal tasks remain in dependency validation.

## Governance Gate #443

Run: `33727116285`
Source HEAD: `4e6a87df98d03f9146ccd9bd37238d3aefc87abc`
Target base: `219d7096756ad75717a46d85baf7d2b216e2472b`
Generated PR merge: `b78f2a2a078b6993f75f8b4579c3ea930eacf040`

Observed results:

- compile: PASS;
- test collection: **267 collected**;
- Project Readiness: PASS;
- governance tests: **267/267 PASS** in 28.60 seconds;
- terminal Wave suite within CI: **8/8 PASS**;
- skip audit: **0 skipped**;
- Program execution integrity: PASS;
- Program history: PASS;
- Program transitions: PASS;
- Agent Coordination: PASS;
- Markdown, Schema, Secret, Evidence, Evidence integrity, linkage, Scope,
  Spec Sync, parent-directory, and CI static checks: PASS;
- Program Finalization: FAIL only because the four canonical completed-GZ-003
  Evidence files had not yet been refreshed;
- lifecycle guard: not executed after fail-fast Finalization and not claimed.

## Current refresh and pending exact-head result

This file, `summary.md`, `commands.txt`, and `handoff.md` now satisfy the
canonical completed-task Evidence refresh requirement while preserving original
completion identity.

A new exact-head Gate is required. Its result must be recorded before any merge
decision. The expected remaining self-hosting boundary is the lifecycle scope
classification of the production checker and focused test file; that expected
classification is not pre-claimed as the actual next result.

No merge, override, post-merge success, OPS-007 closure, or OPS-006 advancement
is claimed.

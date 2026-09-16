# GZ-010 Completion Test Evidence

Task: GZ-010
Result: PASS (the specific observed executions below)
Current completion disposition: NEEDS_REVIEW
Implementation merge: `2b2d076b68171edd74639e307f8a126cc882186d`
Completion PR: #63
Target base: `3a11c5f639717993f51a26c5b5970701570fe367`
Latest tested source: `b1ca9864759c325f12addf2b06b0ab22a81f9d9c`

## Historical implementation

Run `35053181259`, job `104657763581`, recorded checker success and 86/86 planning-software tests, zero skips. The produced/tested implementation was `0f5cfd73d4ae6592f6e773caae3bba4dac34ff46`. These results are not POC experiment outcomes and are not re-labelled as a new completion-branch POC test run.

## Latest actual CI execution

Gate #570 / run `35071047333`, job `104712373022`, checked out synthetic merge `c5744833dd9d76167e1c918ccd912fd0f06bb552`, combining the exact source and target above.

- 267 tests collected and passed in 24.88 seconds; zero skips.
- Task File, readiness, Program integrity/history/transitions/finalization, direct lifecycle guard, coordination, scope, Markdown, schema, secret scan, Evidence, linkage, spec sync, boundary and CI static checks passed.
- The Evidence-integrity step found no final-report file; do not treat its success as independent verification of every prose assertion.
- Preceding Gate #569 / run `35070014899` failed the four missing Task lists. b1ca repaired the lists, not the tests or validator. Failure history is retained.

## Completion wrapper execution inside the suite

At `2026-09-16T07:56:18.4985546Z`, the log reports:

```text
tests/governance/test_program_lifecycle_guards.py::TestProgramLifecycleGuards::test_current_repository_passes PASSED [ 46%]
```

The exact test source at b1ca, lines 46-64, calls `scripts/run-program-lifecycle-gate.py` with `subprocess.run`, the actual repository root, `origin/main` and `HEAD`, then asserts return code 0. It has no mocked API or alternate endpoint. The wrapper therefore executed its real completion/Issue-state checks; it was not merely inspected. Child stdout is captured and not printed on success, so a raw wrapper-output transcript is not claimed.

This corrects the earlier blanket statement that the wrapper was unexecuted. It does not claim a separately invoked command with explicit `--task` and `--branch-name`; that standalone record remains absent.

## Restoration evidence and execution gap

The Git Data API restored only the completion-owned paths from candidate tree `0313cb874843a839519435cea81a1a6773892afb` and returned root `5725e4f352fa420dbac260247947dca5cf482c4f`, exactly equal to the target tree. Full inputs and scope are in `rollback-verification/README.md`. No refs or commits were changed by this isolated restoration test.

The local worktree shell rehearsal and separately named `make verify` remain NOT EXECUTED. General Codex execution did not start because this repository lacks a configured execution environment; reply `5694080113` records that blocker. No pending acceptance item is passed by assumption. A fresh successor Gate/review remains required. No real POC, merge, post-completion-main result or downstream activation is claimed.

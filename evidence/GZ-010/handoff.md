# GZ-010 POC Program Baseline Review Handoff

Task: `GZ-010`
Issue: `#15`
Pull request: `#48`
Branch: `chore/GZ-010-poc-program-baseline`
Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
Validated implementation commit: `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`

## Current state

The POC Program baseline implementation is complete as a Draft review candidate. Task-specific validation passed in GitHub Actions run `34873071797`, job `104073491558`:

- validator: exit `0` with the canonical PASS message;
- regression suite: 85/85 passed in 49.148 seconds;
- unexpected skips: 0;
- Python compilation and `git diff --check`: exit `0`;
- six temporary repair workflows: deleted.

This handoff does not claim that the Evidence-bearing PR head has passed the full Governance Gate or independent review. It does not authorize merge or lifecycle completion.

## Claim boundary

GZ-010 defines executable governance contracts for future POC work; it does not execute the experiments. POC-001 through POC-010 remain planned/not_started. No `evidence/POC-*` result, performance number, provider outcome, hardware result, or approval decision is introduced.

## Independent reviewer actions

Review the exact current PR head only and verify all of the following:

1. the PR head descends from validated implementation commit `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`;
2. the changed-file set matches `evidence/GZ-010/changed-files.md` and contains no temporary repair workflow or unrelated product/deployment file;
3. the only coordination metadata changes are the synchronized GZ-010 lease timestamps in Active Work and Task Spec;
4. `check_program.py` preserves YAML merge-key semantics while rejecting duplicate explicit keys;
5. the positive terminal fixture satisfies the current execution schema before every negative mutation;
6. structured commands bind command text, expected/actual exit code, and task-owned raw output;
7. execution resources exactly match the plan and configuration/booking references exist under task Evidence;
8. privacy/license reviews, secret scanning, result-index ownership, immutable history, measurement domains, provenance, and frozen POC blockers fail closed;
9. all canonical plans and index rows remain planned/not_started and no actual POC Evidence exists;
10. the exact-head Governance Gate, repository governance suite, POC suite, and `make verify TASK=GZ-010 BASE=origin/main HEAD_REF=HEAD BRANCH=chore/GZ-010-poc-program-baseline` all pass with no unexpected skip;
11. all current review threads are resolved or explicitly classified as non-blocking.

## Integrator actions

Do not merge while the PR is Draft. Merge is permitted only after the exact Evidence-bearing head has a fully successful Governance Gate and a fresh independent review with no unresolved blocker. Use the reviewed expected head SHA when merging so GitHub rejects any drift.

Do not mark GZ-010 complete, execute a POC, or create terminal result Evidence as part of this integration.

## Known limitation

A commit cannot embed its own Git SHA without changing that SHA. Therefore this Evidence records the immutable implementation commit under test, while GitHub PR metadata plus the exact-head Governance Gate and review provide the authoritative Evidence-bearing candidate SHA. Any later content change invalidates the prior exact-head review and requires the gate and review to run again.

## Rollback

Before merge, close the PR or revert the implementation/Evidence commits on the branch. After merge, use a dedicated reviewed revert/correction PR. Preserve `main`, commit history, Evidence history, and all failed-run diagnostics; do not force-push or delete audit records.

## Local validation versus connector integration

The actual validation source c91265bf1430c3e7df6b0f1321705b4a00a66b25 and its Evidence-refresh successors are preserved in this task's local Git checkout. Native Git push failed because that transport has no authenticated username. These local commits have NOT been claimed as remotely pushed or as ancestors of the connector-created PR commit. The LOCAL-ONLY recovery simulation is also never pushed.

The authorized GitHub connector publishes the final file tree as a normal successor of the existing remote PR HEAD. Record its returned remote SHA and verify its full tree equals the final local tree before using remote Gate results. Current local transcripts remain bound to their actual local source and environment; an exact remote Gate is a separate result. No remote pass is inferred from local-source pass.

## October execution evidence — 2026-10-09

Validation source: `c91265bf1430c3e7df6b0f1321705b4a00a66b25`; comparison target: `3a11c5f639717993f51a26c5b5970701570fe367`. These are actual executions in Ubuntu/WSL with Python 3.12 and the unchanged requirements-governance.txt. The final Evidence refresh must receive its own Gate; these source results are not automatically transferred to a later HEAD.

- Explicit lifecycle wrapper, Task, readiness, Schema, coordination, scope and Evidence commands: exit 0, captured in `test-results/resumption-20261009/`.
- Direct POC checker: exit 0; direct planning suite: 86/86 passed, zero skips.
- Named `make verify TASK=GZ-010 BASE=3a11c5f639717993f51a26c5b5970701570fe367 HEAD_REF=HEAD BRANCH=chore/GZ-010-poc-program-baseline`: exit 0, 267/267 governance tests passed.
- Separate JUnit/skip audit: exit 0, 267 passed, zero skipped, zero failures/errors.
- Full nonterminal, lease-preserving detached-worktree rehearsal: exit 0 with `review_recovery=PASS`; candidate, simulation, expected tree, individual logs and cleanup lists are in `test-results/resumption-20261009/recovery/`. Simulation is local-only and was not pushed.
- Original checkout remained clean and its HEAD unchanged after cleanup.

GZ-010 remains review. Program and immutable completion ledger are unchanged; Active Work changes only its existing lease timestamps. The proposed lease ends 2026-10-16T08:57:38Z (2026-10-16 16:57:38 Asia/Shanghai). No POC experiment, Completion transition, main merge, post-main result or downstream activation is claimed. Future Completion API checks and guard-compatible post-completion recovery remain separate prerequisites. Ten historical GitHub review threads remain unresolved/outdated and require explicit disposition before integration; no GitHub approval is inferred from local review.

## Earlier proposal and September context (retained)

## Current resumption — 2026-10-09

Coordinator action: renew only the existing GZ-010 review lease from `2026-09-14T06:00:00Z` / `2026-09-21T06:00:00Z` to `2026-10-09T08:57:38Z` / `2026-10-16T08:57:38Z` (168 hours). This is a branch proposal, not an integrated main renewal. Program, completion ledger, roles, path claims, registered base, capacity and lifecycle remain unchanged. Issue #15 remains open. No experiment or downstream task is activated.

The Windows checkout and Ubuntu/WSL execution environment now exist. Current execution outputs will be recorded separately from the September results. Historical PASS does not transfer to the October candidate. Main merge still requires independent review and Human Owner approval.

## Retained September checkpoint (historical snapshot)

# GZ-010 Review Test Evidence

Task: GZ-010
Result: NEEDS_REVIEW
PR: #63
Review target: `3a11c5f639717993f51a26c5b5970701570fe367`
Withdrawn completion source: `035e786022f7995724e0c3b99a86a9356c51e1cf`

## Historical implementation and CI

Implementation run `35053181259`, job `104657763581`: POC planning checker and 86 planning-software tests passed. No experiment ran.

Gate #569 on `ec0b9d77b6d8d9a2435e3c6aebb42c3ac591086a` failed missing Task lists. `b1ca9864759c325f12addf2b06b0ab22a81f9d9c` repaired the lists. Gate #570 / run `35071047333`, job `104712373022`, tested merge `c5744833dd9d76167e1c918ccd912fd0f06bb552`: 267 passed in 24.88 seconds, zero skips. Its actual in-suite wrapper subprocess returned 0; successful child stdout was captured. Full historical provenance remains at `git show 035e786022f7995724e0c3b99a86a9356c51e1cf:evidence/GZ-010/commands.txt`.

Gate #571 / run `35072699408` passed the withdrawn source, but independent review did not approve completion. Neither run is transferred to the successor.

## Fresh independent reproduction on the withdrawn source

Review request `5694867271` produced inline response `4024339028` at `2026-09-16T09:10:00Z`. The independent reviewer reported actual clean checkout HEAD `035e786022f7995724e0c3b99a86a9356c51e1cf`, tree `54d5594c0c3a95855150f65d049cf321879d5d80`, with `GITHUB_REPOSITORY=ElectricDogCN/Guize` and the alternate API endpoint unset. This is reviewer-reported execution evidence, not execution by the local chat container.

| Command | Exit | Actual reported result |
|---|---:|---|
| `git rev-parse HEAD` | 0 | Exact source above |
| `git status --porcelain` | 0 | Empty output |
| `python scripts/check-task-file.py --task GZ-010` | 0 | Task file valid |
| Explicit task/branch `run-program-lifecycle-gate.py` command | 1 | `ModuleNotFoundError: No module named 'yaml'`; API not reached |
| `python specs/poc/check_program.py` | 1 | `ModuleNotFoundError: No module named 'jsonschema'` |
| `python specs/poc/test_program.py` | 1 | `ModuleNotFoundError: No module named 'yaml'` |
| Named `make verify TASK=GZ-010 ...` | 2 | Markdown passed; schema import failed, then Make stopped |
| Existing detached-worktree restoration block | 0 | Full target tree restored; worktree cleanup confirmed |

Reported restoration stdout:

```text
completion_restoration=PASS candidate=035e786022f7995724e0c3b99a86a9356c51e1cf restored_tree=5725e4f352fa420dbac260247947dca5cf482c4f
```

The reviewer also reported only the original worktree remaining and a clean final status. This is fresh execution of the old restoration shell script, but not a guard-compatible recovery after completion. The other named commands failed before their complete checks; no passing test count is claimed. The review's additional comparison to an unrelated commit is not adopted as provenance here.

## Current successor and environment boundary

A separate local Git clone attempt returned 128 / `Could not resolve host: github.com`; no checkout or tests ran there. The earlier general Codex task did not start because of a missing repository environment. These limitations are distinct from the review environment's missing Python dependencies.

For the next available execution environment, install the repository's existing `requirements-governance.txt`, verify `import yaml, jsonschema, pytest`, then run the exact Task Spec commands. Do not change requirements, tests, assertions, scripts, API endpoints or workflow files. Record dependency-install failures honestly rather than skipping commands.

The successor keeps Program/Task at review with the original lease/ledger. It requires its own Gate and review. A review-state wrapper PASS will not validate a future completion transition or its Issue API condition. All final-completion acceptance items remain pending; the old restoration success does not fulfill the immutable-ledger recovery requirement.

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

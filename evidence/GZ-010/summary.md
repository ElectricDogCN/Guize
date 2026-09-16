# GZ-010 Completion Candidate Summary

Task: GZ-010
Issue: #15
Completion PR: #63
Result: PASS (identified implementation and CI observations only)
Completion disposition: NEEDS_REVIEW; standalone execution prerequisites remain incomplete

## Delivered baseline and exact history

GZ-010 delivers POC-PROTOCOL-V1: ten immutable POC plans, sample/resource catalogues, schemas/templates, a planning validator, regression tests and operator documentation. It does not execute the experiments or certify future POC results.

- Reservation: PR #45 / `74ab9d53f29834fda37dcbd726fd58f997f8f21a`.
- Implementation source: `397bd6d45235b38e9afe59bc8f7b28ede5c8e4f6`.
- Implementation merge: PR #48 / `2b2d076b68171edd74639e307f8a126cc882186d`.
- Review-state merge and completion target: PR #62 / `3a11c5f639717993f51a26c5b5970701570fe367`.
- Original completion metadata: `fb3a6edf5dde176f4cb97df1d7ec5b77a1ac1ef7`.
- Latest tested documentation source: `b1ca9864759c325f12addf2b06b0ab22a81f9d9c`.
- Work branch: `chore/GZ-010-poc-program-baseline`.

This Evidence-only successor records those actual observations. Its own SHA must be read from PR #63 and identified by the next review; it is not invented inside its own contents. The thirteen-file cumulative inventory remains in `changed-files.md`. This successor does not change the Task Spec, Program, Active Work, Ledger or implementation.

## Verified results

Historical implementation run `35053181259`, job `104657763581`, recorded planning-checker success and 86/86 regression tests. These are software tests, not experimental outcomes.

The first completion candidate passed Gate #568. Documentation correction `ec0b9d77b6d8d9a2435e3c6aebb42c3ac591086a` then failed Gate #569 because four mandatory Task sections lost their bullet lists. Commit `b1ca9864759c325f12addf2b06b0ab22a81f9d9c` restored the lists without changing any gate. Gate #570 / run `35071047333`, job `104712373022`, passed every stage and 267/267 governance tests in 24.88 seconds with zero skips. Its checkout was synthetic merge `c5744833dd9d76167e1c918ccd912fd0f06bb552` against the exact target above.

A further log/source audit corrects the previous blanket statement about the completion wrapper: `test_current_repository_passes` actually executed `run-program-lifecycle-gate.py` as a subprocess on that checkout and asserted exit 0. It passed at `2026-09-16T07:56:18.4985546Z`. The test used real repository/Issue state, not an API mock. Successful child output was captured, not printed. This is distinct from separately running the Task Spec's explicit task/branch command; `commands.txt` records both scopes accurately.

An isolated Git Data tree construction also restored only the completion paths from candidate tree `0313cb874843a839519435cea81a1a6773892afb`. The returned root `5725e4f352fa420dbac260247947dca5cf482c4f` exactly matched the target-base tree. No ref or main update occurred. This is content-restoration evidence, not a claim that the local worktree shell rehearsal ran.

## Remaining boundary

Issue #15 is already closed/completed. A bounded general Codex execution request received the explicit missing-repository-environment response, comment `5694080113`, and did not start. The separately named wrapper command, local worktree rehearsal and named `make verify` have no new standalone execution record; their pending Task acceptance items are not marked complete. No extra workflow, environment, controller or gate waiver is introduced to hide this.

Keep PR #63 Draft until remaining required evidence and independent review are complete, followed by Human Owner merge approval. Main still represents GZ-010 as review until a real completion merge occurs. All ten plans/results-index rows remain nonterminal. No actual POC Evidence, business code, workflow, permission, Secret, safety limit or production state is changed.

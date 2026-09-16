# GZ-010 POC Program Baseline Evidence

Task: `GZ-010`
Issue: `#15`
Pull request: `#48`
Branch: `chore/GZ-010-poc-program-baseline`
Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
Validated plan-completeness implementation commit: `0f5cfd73d4ae6592f6e773caae3bba4dac34ff46`
Validated clean product/Evidence-parent HEAD: `c8a4e0fc4839f009484a808ea2e7ee451f5f614c`

## Status

Ready for final exact-head independent product-scope review after this Evidence-only refresh receives a successful Governance Gate. GZ-010 delivers the canonical executable planning baseline for POC-001 through POC-010. It does not execute a POC and does not claim a hardware, provider, network, storage, AI, media, recovery, performance, privacy, licence or production result.

## Stop That Shit scope decision

The task freezes complete, machine-checkable POC plans and the validator required to protect those plans. It does not build a universal future execution platform. Separate task-registration and standalone POC-gate projects were closed without merge. Future terminal-result hardening remains deferred until an actual downstream POC exposes a concrete failure.

## Delivered baseline

- one canonical POC Program, schemas, catalogues, templates and result index;
- ten independent plans with exact Requirement, Module, dependency, Wave, risk, resource, sample, Evidence, rollback and decision boundaries;
- all plans and result-index rows remain `planned` / `not_started`;
- fail-closed validator with duplicate-key/YAML-merge handling, task/path mapping, secrets, approvals, resources, provenance, measurements and row-ownership checks;
- 86 behavioral regression tests;
- every current canonical measurement ID is frozen by `REQUIRED_MEASUREMENTS` and a generic removal regression;
- explicit structured coverage for the latest product-scope findings:
  - POC-001 BIOS/IOMMU, IOMMU-group isolation, Above 4G, Resizable BAR and observed multi-day stability;
  - POC-002 A380-backed Range latency, encoder power and temperature;
  - POC-003 hot-cache, cold-cache, slow-origin and multi-user Range latency;
  - POC-004 incomplete/hash-mismatched replica rejection, cache-eviction preservation and safe replica migration;
  - POC-005 filename, provider, Range and ETag characteristics;
  - POC-006 429/5xx/network recovery, resumable/idempotent sync, duplicate prevention and source-deletion preservation;
  - POC-008 the exact ten Vue/React comparison scenarios;
  - POC-009 numeric budget/rate/concurrency ceilings plus WER, CER, DER, COMET, BLEU, OCR, factual consistency, tag F1, thumbnail selection, multimodal correction and strata coverage;
  - POC-010 playback, AI/manual revision, search-index and image-signature restoration plus separate service, VM, browsing and playback recovery times.

## Direct POC validation

GitHub Actions run `35053181259`, job `104657763581`, produced and validated commit `0f5cfd73d4ae6592f6e773caae3bba4dac34ff46`:

- dependency installation: exit `0`;
- Python compilation: exit `0`;
- `python specs/poc/check_program.py`: exit `0` with canonical PASS;
- `python specs/poc/test_program.py`: exit `0`;
- regression result: `86/86` passed in `153.468` seconds;
- unexpected skips: `0`;
- the generic frozen-measurement test removed each required ID independently and required the expected fail-closed message.

The same workflow attempted `make verify` before its two temporary workflow files were removed. Product validation passed, but task scope correctly rejected those temporary files. That intermediate `make verify` result is historical and is not represented as final success.

## Clean-head repository validation

After deleting both temporary workflows, Governance Gate run `35053458023` (#561), job `104658598246`, validated source HEAD `c8a4e0fc4839f009484a808ea2e7ee451f5f614c`:

- governance suite: `267/267` passed in `29.86` seconds;
- skipped tests: `0`;
- Task Spec, Project Readiness, Program integrity/history/transitions/finalization/lifecycle and Agent Coordination: PASS;
- Markdown: `188` files, PASS;
- schema, secret, Evidence, Evidence integrity, linkage, task scope, spec sync, repository boundary and CI static validation: PASS;
- cumulative paths: `38` allowed, `0` forbidden, `0` out of scope.

The standard Governance workflow executes the mandatory repository validators directly. A separate final local `make verify` command could not be rerun because the isolated execution container could not resolve `github.com`; no success is claimed for that unexecuted local command.

## Claim boundary

- no POC was executed;
- no downstream `evidence/POC-*` result was added;
- no Program status or Completion Ledger change was made;
- PR #48 remains Draft and unmerged;
- this Evidence refresh does not claim its own future commit SHA, final independent approval, merge or post-main success.

## Rollback

Before merge, close PR #48 or revert the branch commits while preserving history. After merge, use a dedicated reviewed revert/correction PR. Never force-push or delete failed-run and review evidence.

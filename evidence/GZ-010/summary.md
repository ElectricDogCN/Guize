# GZ-010 POC Program Baseline Evidence

Task: `GZ-010`
Pull request: `#48`
Branch: `chore/GZ-010-poc-program-baseline`
Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
Validated implementation commit: `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`
Validated plan-completeness commit: `056b17fb730e334ed8b45bc887870b0918cfaa8f`

## Status

Draft candidate ready for final product-scope review. This task delivers the canonical, executable planning baseline for POC-001 through POC-010. It does not execute any POC and does not claim a hardware, provider, network, storage, AI, media, recovery, performance, privacy, licence or production result.

## Delivered baseline

- one canonical POC Program, schemas, catalogues, templates and result index;
- ten independent nonterminal plans with Requirements, Modules, dependencies, resources, samples, Evidence boundaries, rollback and decision fields;
- fail-closed validator with duplicate-key/YAML-merge handling, task/path mapping, secret checks, approvals, resources, provenance, measurements and row-ownership checks;
- 85 behavioral regression tests;
- complete structured plan gates for the frozen blockers, including host reboot, media failure/recovery, ATS interruption, 500 GiB floor, source change frequency, public-network scenarios, retrieval relevance/latency and disaster-recovery critical state.

## Recorded validation

### Executable POC contract

GitHub Actions run `34873071797`, job `104073491558`, validated implementation commit `608b8e0a3796ddaac6b5bbdda9baff349f45b1c3`:

- Python compilation: exit `0`;
- dependency installation: exit `0`;
- `python specs/poc/check_program.py`: exit `0` with canonical PASS;
- `python specs/poc/test_program.py`: exit `0`;
- regression result: `85/85` passed in 49.148 seconds;
- unexpected skips: `0`;
- `git diff --check`: exit `0`.

### Exact plan-completeness candidate

Commit `056b17fb730e334ed8b45bc887870b0918cfaa8f` changes only eight canonical plan files and adds missing structured measurement/exit gates. It does not change validator, schemas, templates, result index, lifecycle metadata or test code.

Governance Gate run `34920195916` (#552), job `104226389757`, tested that source through merge ref `353afdd504abb9ecb49993f8f46baf469b14aac4`:

- governance suite: `267/267` passed in 25.77 seconds;
- skipped tests: `0`;
- Task, Readiness, Program integrity/history/transitions/finalization/lifecycle and Agent Coordination: PASS;
- Markdown, schema, secret, Evidence, linkage, scope, spec-sync and static CI: PASS;
- changed paths: 38 allowed, 0 forbidden, 0 out of scope.

The direct POC commands were not rerun by Gate #552 because the repository Governance workflow does not call them. This is stated explicitly. The plan-only commit adds measurements; it does not alter executable validation code already covered by the 85-test run.

## Stop That Shit scope decision

GZ-010 freezes the POC planning baseline. It is not a prerequisite project to perfect every possible future terminal-result execution rule or to construct another shared governance framework. Generic hardening is deferred until a downstream POC exposes an actual failure, unless final review shows that a current nonterminal plan is incomplete or internally inconsistent.

## Claim boundary

All ten plans remain `planned`; all result-index rows remain `not_started`; no `evidence/POC-*` result is introduced. This Evidence does not authorize merge, lifecycle completion or POC execution.

## Rollback

Before merge, close PR #48 or revert its implementation/Evidence commits on the branch. After merge, use a dedicated reviewed revert/correction PR. Preserve `main`, commit history and failed-run diagnostics; do not force-push or delete audit history.

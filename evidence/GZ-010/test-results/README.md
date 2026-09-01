# GZ-010 Test Results

Task: GZ-010
Status: IN_PROGRESS

## Verified predecessor

- Reservation v2 PR #45 merged as `74ab9d53f29834fda37dcbd726fd58f997f8f21a`.
- Reservation exact-head Governance Gate #381: PASS.
- Post-Reservation `main` Governance Gate #382 / run `33492832222`: PASS.

## POC Program validator

Command:

```bash
python specs/poc/check_program.py --repo-root /mnt/data/gz010_impl
```

Result: PASS / exit code 0.

Validated POC-PROTOCOL-V1 manifest, Program Plan mappings, ten plan identities, risk/wave/requirement/module/evidence/dependency mappings, resource/sample references, result index, planned/not_started emptiness rules, high/critical isolation, POC-010 critical standalone rule, execution-time environment capture, completed-result evidence/review requirements and secret-like content checks.

## POC Program positive/negative tests

Command:

```bash
python specs/poc/test_program.py
```

Result: PASS / exit code 0 / **22 tests** for the hardened candidate.

Covered:

1. valid baseline;
2. missing POC plan rejected;
3. POC↔Task mismatch rejected;
4. wrong risk rejected;
5. wrong wave rejected;
6. wrong Requirement rejected;
7. wrong Module rejected;
8. wrong Evidence path rejected;
9. wrong dependency rejected;
10. duplicate Evidence path rejected;
11. unknown resource rejected;
12. unknown sample rejected;
13. unapproved sample execution rejected;
14. prefilled execution command rejected;
15. prefilled measurement rejected;
16. prefilled decision rejected;
17. prefilled reviewer rejected;
18. secret-like content rejected;
19. critical scheduling violation rejected;
20. results-index status drift from plan rejected;
21. execution without captured environment rejected;
22. completed PASS without raw evidence/measurements/independent approved review rejected.

## GitHub Governance Gate history

Gate #396 / run `33495778895` on implementation HEAD `54e349514df22c32d93c9b285423e7cf8e2fe485`:

- Program lifecycle/history/transitions/finalization: PASS
- Governance tests: 259/259 PASS
- Scope: 34/34 changed files allowed, 0 forbidden/out-of-scope
- Schema, Secret, Evidence, Linkage, Spec Sync and static checks: PASS
- Agent Coordination: sole FAIL because the active-task coordination path checker rejects `specs/coordination/program-plan.yaml`, although lifecycle synchronization requires the GZ-010 `reserved -> in_progress` metadata update.

## Experiment boundary

No POC-001～POC-010 experiment was executed. All plan/result records remain `planned/not_started`; this document contains no experimental PASS/FAIL conclusion.

## Final candidate

A new exact-head Governance Gate and independent Review are required after Evidence synchronization. No future Gate, Review, merge or post-merge result is pre-claimed here.

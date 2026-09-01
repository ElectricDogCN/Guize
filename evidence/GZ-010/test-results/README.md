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

Validated POC-PROTOCOL-V1 manifest, Program Plan mappings, ten plan identities, risk/wave/requirement/module/evidence/dependency mappings, resource/sample references, result index, planned/not_started emptiness rules, high/critical isolation, POC-010 critical standalone rule and secret-like content checks.

## POC Program positive/negative tests

Command:

```bash
python specs/poc/test_program.py
```

Result: PASS / exit code 0 / 19 tests.

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
19. critical scheduling violation rejected.

## Experiment boundary

No POC-001～POC-010 experiment was executed. All plan/result records remain `planned/not_started`, so this document contains no experimental PASS/FAIL conclusion.

## Repository candidate

PR #46 exact-head Governance Gate and independent Review remain PENDING until GitHub completes them. They are not pre-claimed by the isolated pre-push validation above.

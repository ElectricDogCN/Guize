# GZ-004 Implementation Test Results

Status: IN_PROGRESS

## Verified predecessor

- Reservation PR #36 merged as `56d6bfacba45d36e82376ebb5a5cea7394c88f0d`;
- post-Reservation `main` Governance Gate #333 / run `33365297286`: **PASS**;
- Program lifecycle, Agent Coordination and 259 governance tests were green.

## Implementation Gate #343

Exact HEAD: `0ffca4bdf1dfe6e3eeec402b18ef1dea048ae783`.

Result: **FAIL**, with one diagnosed category only: Program lifecycle scope. The implementation files were present while GZ-004 was still `reserved`, so the lifecycle guard correctly rejected non-metadata output. The governance regression suite itself was 259/259 green and all other Gate steps passed.

This failure is preserved as evidence; no checker/test weakening is permitted.

## Candidate validator preflight

A locally materialized exact repair candidate using the current branch contracts plus canonical read-only inputs was executed before push:

```text
python specs/requirements/v1/validate.py
=> PASS; requirements=10, nfr=20, acceptances=14, traces=10

python specs/requirements/v1/validate.py --negative-fixtures
=> PASS; 6/6 invalid fixtures rejected
```

The six rejected fixtures cover duplicate alias, unknown module/reference, missing requirement, asymmetric trace, illegal numeric value under `MEASUREMENT_REQUIRED`, and fake POC PASS/measured claim.

## Pending authoritative checks

A new exact-head Governance Gate and fresh independent Review are still required after the repair commit is pushed. No future CI, review, merge, post-merge or completion success is claimed here.

# GZ-004 Implementation Test Results

Status: IN_PROGRESS

## Verified predecessor

- Reservation PR #36 merged as `56d6bfacba45d36e82376ebb5a5cea7394c88f0d`;
- post-Reservation `main` Governance Gate #333 / run `33365297286`: **PASS**.

## Gate #343 — lifecycle not yet activated

Exact HEAD `0ffca4bdf1dfe6e3eeec402b18ef1dea048ae783`: **FAIL** only because the implementation output existed while Program/Task/Registry remained `reserved`. The 259 governance tests and all other Gate steps passed.

## Historical validator preflight

Before later independent-review hardening:

```text
python specs/requirements/v1/validate.py
=> PASS; requirements=10, nfr=20, acceptances=14, traces=10

python specs/requirements/v1/validate.py --negative-fixtures
=> PASS; 6/6 invalid fixtures rejected
```

This is historical evidence only. The validator was subsequently hardened and now contains 9 negative fixtures; this chat runtime cannot materialize the exact GitHub worktree because direct github.com resolution is unavailable, so no final 9/9 runtime PASS is claimed here.

## Gate #344 — activation self-hosting conflict

Exact HEAD `0767cc9f70eaced2844fc159d6675f388030338f`:

- Task file: PASS
- Project Readiness: PASS
- Program integrity/history/transitions/finalization/lifecycle: PASS
- Governance tests: **259/259 PASS**
- Markdown / Schema / Secret / Evidence / linkage / Spec Sync / CI static: PASS
- Task Scope: **19/19 allowed, 0 forbidden, 0 out-of-scope**
- Agent Coordination: **FAIL only**

The single failure is `specs/coordination/program-plan.yaml` outside active Registry implementation path claims. This is a self-hosting contradiction for the first `reserved -> in_progress` transition: the canonical Program status must change to match Active Work, but the `in_progress` coordination dispatcher treats Program Plan as non-implementation scope. The branch contains no bypass and no widened task path ownership.

## Gate #345 + fresh Review on 523a97b

Gate #345 / run `33373530787` reproduced only the same Agent Coordination self-hosting failure; every other Gate step passed.

Fresh independent Review of `523a97be615e2f1a76b231990b894669dc69db4d` completed and reported four blockers:

1. source deletion invariant was not also bound to `REQ-V1-0002` / `验收V1-0001`;
2. Acceptance mappings could declare an otherwise syntactically valid unknown Requirement ID;
3. `PROGRAM_SUPPLEMENT` was not verified against actual Program Plan acceptance+requirement relationships;
4. Requirement Index `REQ-V1-0003 -> GZ-006` conflicts with Program Plan GZ-006 requirementIds and was not explicitly represented.

All four were fixed and their review threads resolved.

## Hardened candidate through 17256dc

The fixes now:

- add the source-deletion no-cascade invariant to the asset acceptance relationship;
- require Acceptance declared/scenario Requirement sets to be exact known V1 IDs and mutually symmetric;
- derive/verify Program supplements from actual Program Plan task mappings;
- require exact `programTaskMappingConflicts`, with `REQ-V1-0003` recording `[GZ-006]`;
- expand negative fixtures from 6 to 9 to cover these failure modes.

Governance Gate #349 / run `33376034390` on `17256dce9937d459181157baf9525850574435f1` completed with **only Agent Coordination failing**. Task, Project Readiness, Program lifecycle, 259 governance tests, Markdown, Schema, Secret, Evidence, Evidence integrity, linkage, Scope, Spec Sync, parent-directory and CI static checks all passed.

## Pending authoritative decision

A fresh independent Review must complete against the final exact HEAD after Evidence refresh. If and only if it has no unresolved blocker and the latest Gate still contains only the known activation self-hosting failure, the Human Owner / Integrator may perform the one-time exact-head merge override. Post-merge `main` Governance Gate must then be fully green or GZ-004 stops immediately.

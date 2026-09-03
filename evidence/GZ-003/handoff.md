# GZ-003 Handoff

Task: GZ-003
Original Completion: PR #11 / `9e3a821ada292ac3ef69b7c059384d17f6530b48`
Status: COMPLETED
Maintenance: OPS-005 #50

## Maintenance identity

- Owner context: completed GZ-003 governance/Harness baseline
- Branch: `fix/GZ-003-poc-program-gate`
- Base: `main@219d7096756ad75717a46d85baf7d2b216e2472b`
- Issue: #50
- Original GZ-003 Program/Foundation state remains `completed`

## Trigger

GZ-010 PR #48 has mandatory POC Program validator/regression commands, but the repository's existing Governance Gate does not execute them. Codex Review can inspect the PR but its execution environment is not a durable repository Harness contract.

## Maintenance files

Expected OPS-005 diff is limited to:

1. `.github/workflows/poc-program-gate.yml`;
2. `tests/governance/test_poc_program_workflow_contract.py`;
3. `evidence/GZ-003/summary.md`;
4. `evidence/GZ-003/commands.txt`;
5. `evidence/GZ-003/handoff.md`;
6. `evidence/GZ-003/test-results/README.md`.

No Program Plan, Active Work, Completion Ledger, GZ-010 Task Spec, POC contract, business code, deployment, Secret, permission or production data is modified.

## Functional contract

`POC Program Gate` must:

- run on pull requests and all main pushes;
- use pinned checkout/setup-python actions and drop checkout credentials;
- install `requirements-governance.txt`;
- treat both POC validation files absent as the only legitimate no-contract case;
- fail closed when only one file exists;
- execute both `python specs/poc/check_program.py` and `python specs/poc/test_program.py` when present;
- surface the validation outcome in the workflow summary;
- never auto-push/merge or swallow validation failure.

## Next exact action

1. create the OPS-005 PR from this branch;
2. inspect exact changed-file list and both workflow checks;
3. obtain fresh exact-head review;
4. fix every content or CI blocker before merge;
5. if a completed-GZ-003 self-hosting lifecycle/scope check is the sole remaining red condition, document it explicitly rather than changing a guard;
6. merge only the reviewed exact HEAD under Human Owner authority;
7. require post-merge `main` Governance Gate and POC Program Gate to be green;
8. synchronize GZ-010 PR #48 with that green main so its own POC Program Gate executes the real validator/tests.

No future success is pre-claimed.

## Rollback

Before merge, close the maintenance PR. After merge, if either main gate is red, use a dedicated revert/correction PR for this workflow/test/Evidence maintenance; never rewrite `main` or weaken existing guards.

# GZ-014 Post-Merge Governance Test Repair

## Identity

- Task: GZ-014
- Base: `main@903754295e4a0393638c82aa851c3ada8cd507fb`
- Branch: `chore/GZ-014-post-merge-test-repair`
- Trigger: main Governance Gate run #237

## Observed failure

Production lifecycle checks passed on the merged main commit, but the governance test suite failed in:

```text
tests/governance/test_program_lifecycle_guards.py::TestProgramLifecycleGuards::test_current_repository_passes
```

The integration test always passed `origin/main` as `--base-ref`. On a pull-request checkout this is the intended target base. On a push-to-main checkout, however, `origin/main` already resolves to `HEAD`, while the active GZ-014 Foundation lease was audited against the merge commit first parent. The test therefore compared the lease `baseSha` with the wrong endpoint and reported a false stale-base failure.

## Repair

The test now resolves both `origin/main` and `HEAD`:

- when they differ, it uses `origin/main` as the PR integration base;
- when they are equal, it requires and uses `HEAD^1` as the just-merged PR base;
- missing refs or a missing first parent fail the test rather than skipping validation.

The production `validate_foundation_claims` implementation and its exact `baseSha` constraint are unchanged.

## Scope

Changed files are limited to:

- `specs/tasks/GZ-014.md`;
- `specs/coordination/active-work.yaml`;
- `tests/governance/test_program_lifecycle_guards.py`;
- `evidence/GZ-014/post-merge-test-repair.md`.

No product requirement, business contract, business code, deployment, Secret, permission or production data is changed.

## Validation status

No success is claimed in this document before GitHub Actions executes the latest branch HEAD. The authoritative result is the Governance Gate attached to the repair PR, followed by the push-to-main Gate after merge.

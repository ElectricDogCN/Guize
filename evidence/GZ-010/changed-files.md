# GZ-010 Review Repair — Changed Files

Task: GZ-010
PR: #63
Result: NEEDS_REVIEW
Comparison target: `3a11c5f639717993f51a26c5b5970701570fe367`
Retained old completion source: `035e786022f7995724e0c3b99a86a9356c51e1cf`

## Cumulative PR scope: ten existing files

- `specs/tasks/GZ-010.md`
- `evidence/GZ-010/summary.md`
- `evidence/GZ-010/commands.txt`
- `evidence/GZ-010/handoff.md`
- `evidence/GZ-010/test-results/README.md`
- `evidence/GZ-010/changed-files.md`
- `evidence/GZ-010/scope.md`
- `evidence/GZ-010/follow-ups.md`
- `evidence/GZ-010/security/README.md`
- `evidence/GZ-010/rollback-verification/README.md`

## Withdrawal delta versus the old candidate

The successor additionally restores three coordination files to the exact target blobs. They therefore disappear from the cumulative PR diff, rather than introducing new main changes:

- Program: `27edc2750e1567b6764581e43d0d49de8de54970`.
- Active Work: `2e9859fc504800f64ad6284933cb0b59ae411f39`.
- Completion Ledger: `0607130b53d58c5bbb177725b991dae2dac45115`.

Task front matter is restored to review and registered baseSha `2b2d076b68171edd74639e307f8a126cc882186d`. The other identity, path-claim, role, Wave, contract and lease values remain registered values.

All implementation, POC plans/catalogues/schemas/tests/results-index, workflow, checker, business/deployment files and unrelated Evidence remain unchanged. No file is added or deleted. Prior proposed completion content and evidence are preserved through ancestry; main has never received that proposal. Verify actual filenames and blob identities before review or integration.

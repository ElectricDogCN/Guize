# OPS-006 Registration Test Results

## Phase

Clean metadata-only Registration bootstrap from verified green main. No `PROGRAM-TASK-REGISTRATION-V1` implementation test is claimed.

## Verified base

- Base: `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`
- Governance Gate: #446 / run `33736578549`
- Result: SUCCESS

## Initial candidate run

- Branch: `chore/OPS-006-task-registration-r2`
- Draft PR: #56
- Source HEAD: `6fc572bbbb679fcb8e4c54b88188a44aea29a7b5`
- Generated merge: `9147175b679747ac4febd1967487f07263df83c5`
- Governance Gate: #447 / run `33737659745`
- Job: `100591944155`
- Overall result: FAILURE with only the registered absent-to-planned lifecycle gaps

## Passed controls

- Project Readiness: PASS for 27 Program tasks;
- Program execution integrity: PASS;
- Program Plan history: PASS;
- Program transitions: PASS;
- Program finalization: PASS;
- checkout, dependency install/import, compile and collection: PASS;
- Markdown, Schema, Secret, Evidence, Evidence integrity, linkage, Spec Sync, parent-directory and CI static checks: PASS;
- skip audit: PASS with zero skipped tests.

## Governance suite

```text
267 collected
266 passed
1 failed
0 skipped
30.10 seconds
```

The sole failing test was:

```text
tests/governance/test_program_lifecycle_guards.py::
TestProgramLifecycleGuards::test_current_repository_passes
```

It failed only because the current lifecycle guard reports:

```text
Affected lifecycle task GZ-020 has no current Task Spec
```

## Direct classified failures

1. Task File exit 1: `Registry task has invalid status: planned`;
2. lifecycle guard exit 1: append-only GZ-020 attachment is not recognized as Registration;
3. Agent Coordination exit 2: `planned` is unsupported;
4. Task Scope exit 2: `planned` is unsupported.

The former `Wave W1 exceeds concurrent task capacity` result did not recur. No unrelated failure was observed.

## Pending final-head result

This Evidence refresh produces a new candidate HEAD. A new Gate must reproduce the same bounded classification before independent review and any Human Owner / Integrator decision. No final-head or post-merge result is pre-claimed.

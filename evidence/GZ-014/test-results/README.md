# GZ-014 Test Results

## Historical validation retained

### Original Foundation and Program Plan work

- Original Reservation Gate initially failed on asymmetric Requirement/Module mappings and ambiguous shared-scope prose; repaired without weakening checks.
- Gate #109 succeeded; PR #18 merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.
- Program Plan implementation run #111 failed on YAML datetime typing; timestamps were quoted and Schema remained strict.
- PR #21 merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`.
- Lifecycle hardening PR #22 passed Gate #236 with 255 governance tests and merged as `903754295e4a0393638c82aa851c3ada8cd507fb`.

## Post-merge incident

### Main Governance Gate run #237

Result: `failure`.

- Program Integrity/History/Transitions/Finalization/Lifecycle: PASS;
- Agent Coordination: PASS;
- Markdown/Schema/Secret/Evidence/Scope/Spec Sync/CI checks: PASS;
- Governance tests: FAIL.

PR #23 attempted a repair but was closed without merge because it lacked a prior independent Reservation, had stale Handoff state, and hard-coded GZ-014 for unrelated future main pushes.

## Clean repair Reservation

PR #24 established the implementation branch and exact base independently, retained GZ-014 `in_progress`, and merged as:

```text
bb22b4cd8662e6c1ed7d3b63255098d8a74237c1
```

Task and Active Work `baseSha` were then synchronized to that merge before implementation.

## PR #25 implementation validation

### Governance Gate run #256

Result: `failure`.

Observed defects:

- Task/Registry exclusive paths differed because bare `Makefile` was not parsed from Task prose;
- repository integration test entered recursive `task_ids_from_diff` calls in the production lifecycle wrapper.

Accepted repair:

- Task uses `./Makefile`, which normalizes to Registry `Makefile`;
- wrapper stores `ORIGINAL_TASK_IDS_FROM_DIFF` before runtime monkey-patching;
- expanded task derivation calls the immutable original function;
- regression test applies the runtime monkey-patch and verifies non-recursive task derivation.

### Governance Gate run #259

Validated HEAD: `cc0d378bf19dc936b7d46de833713aa3702e6636`

Result: `failure`.

- 254 governance tests passed;
- two wrapper tests failed because `GUARD.mapping()` does not accept `key="id"` for `externalBlockers`.

Accepted repair:

- wrapper maps external blockers locally by explicit `id`;
- base lifecycle guard API and policy remain unchanged.

### Governance Gate run #260

Validated HEAD: `8914773e6f4c10558ece8cc4f668ced25d0d54c2`

Result: `success`.

All mandatory steps succeeded:

- compile and collect-only;
- Task validation;
- Project Readiness;
- Program Integrity/History/Transitions/Finalization/Lifecycle;
- Agent Coordination;
- 256 governance tests;
- no skipped tests;
- Markdown and Schema validation;
- Secret scan;
- Evidence and Evidence Integrity;
- PR/Task linkage;
- Scope;
- Spec Sync;
- repository boundary and CI static validation.

## Final-head condition

Canonical Evidence updates are newer than run #260. The Governance Gate attached to the **latest PR #25 HEAD** is the only integration authority. Before merge:

1. latest Gate must conclude `success`;
2. fresh independent Review must target the same HEAD and report no blocker;
3. unresolved blocker threads must be zero;
4. GitHub file inventory must match the declared nine paths;
5. merge must use `expected_head_sha`.

After merge, the post-merge `main` Gate must succeed before the separate GZ-014 Foundation Completion PR is created.
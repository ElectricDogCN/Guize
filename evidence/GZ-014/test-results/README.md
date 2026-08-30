# GZ-014 Test Results

## Reservation phase

### Initial reservation Gate

Result: failed as intended.

- four Requirement/Module mappings were asymmetric;
- the empty shared-scope sentence contained inline code and was parsed as a path.

Both defects were repaired without skipping or weakening the checks.

### Governance Gate #109

Result: success.

- Task/Registry context;
- Project Readiness;
- Agent Coordination;
- 121 governance tests and skip audit;
- Markdown, Schema, Secret, Evidence, Scope and Spec Sync.

Reservation PR #18 merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.

## Program Plan implementation phase

### Governance Gate #111

Result: failed.

Unquoted ISO timestamps in `active-work.yaml` were converted by PyYAML into datetime objects and violated the accepted string Schema. The timestamps were quoted; the Schema was not weakened.

PR #21 later merged as `3b29ea90a8a997be5ff7c97b0f24175cb49508ab`. A manually requested latest-HEAD Codex review finished after that merge and identified additional P1/P2 blockers, so GZ-014 remained `in_progress`.

## Post-merge review-repair phase

### Governance Gate #156

Validated HEAD: `8ff0fc026a79511382c774ddb5aab40a5d7b6a88`

Result: failed.

Observed failures:

1. Program History required a base completion-ledger file even though this migration introduces the first empty ledger.
2. Agent Coordination ignored the extensionless root `Makefile` bullet and therefore detected Task/Registry scope mismatch.
3. `TestProgramPlanHistory.run` shadowed `unittest.TestCase.run`.
4. Workflow Contract still expected the previous PR head-ref representation.

Repairs:

- missing base ledger is allowed only when the current ledger remains empty;
- root `Makefile` is expressed as machine-readable `./Makefile` and normalized to the Registry path;
- test helper renamed to `_run_checker`;
- Workflow Contract now requires the mandatory Program integrity/history step and current merge-head reference behavior;
- ordinary and Foundation Completion transitions receive separate history checks;
- reservation commits must contain the actual reserved Active Work snapshot and matching Task Spec.

### Governance Gate #160

Validated HEAD: `fcc4e028822594c3dd8d758dda626977a74f42dc`

Result: success.

Every mandatory workflow step succeeded:

- checkout, Python and dependency setup;
- compile and test collection;
- Task context and Task Spec;
- Project Readiness;
- Program Plan integrity and history transitions;
- Agent Coordination;
- governance tests and skip audit;
- Markdown and Schema validation;
- Secret scan;
- Evidence and Evidence integrity;
- PR/Task linkage;
- Scope and Spec Sync;
- repository boundary and workflow static checks.

## Final integration condition

Evidence updates after #160 create a later PR HEAD. The Governance Gate attached to that latest HEAD is authoritative. Integration remains blocked until:

- the latest Gate succeeds;
- fresh Codex review targets the same HEAD;
- all blocker threads are resolved;
- integration uses the expected HEAD SHA.

After repair merge, the merged `main` Gate must also succeed. GZ-014 then requires a separate Foundation Completion PR to record the real repair merge SHA and release only its own Active Work lease.

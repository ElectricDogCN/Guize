# GZ-014 Test Results

## Reservation phase

### Initial Reservation Gate

Result: failed as intended.

- four Requirement/Module mappings were asymmetric;
- the empty shared-scope sentence contained inline code and was parsed as a path.

Both defects were repaired without skipping or weakening the checks.

### Governance Gate #109

Result: success. Reservation PR #18 then merged as:

`d731ce09fbf2535948bc1864490539d06ce1f139`

## Program Plan implementation phase

### Governance Gate #111

Result: failed.

Unquoted ISO timestamps in `active-work.yaml` were converted by PyYAML into datetime objects and violated the accepted string Schema. The timestamps were quoted; the Schema remained strict.

PR #21 later merged as:

`3b29ea90a8a997be5ff7c97b0f24175cb49508ab`

A manually requested latest-HEAD Codex review completed after that merge and found additional P1/P2 blockers. GZ-014 therefore remained `in_progress`.

## Post-merge review-repair phase

### Governance Gate #156

Validated HEAD: `8ff0fc026a79511382c774ddb5aab40a5d7b6a88`

Result: failed.

Observed failures:

1. Program History required a base completion-ledger file although this migration introduced the first empty ledger.
2. Agent Coordination ignored an extensionless root `Makefile` bullet.
3. A governance test helper named `run` shadowed `unittest.TestCase.run`.
4. Workflow Contract expected an obsolete ref representation.

Repairs preserved fail-closed behavior: missing base ledger is accepted only when the current ledger is empty; the root path became machine-readable; the test helper was renamed; the static workflow contract was updated.

### Subsequent independent reviews

Later exact-HEAD Codex reviews identified six additional gaps:

- direct Scope check did not route Completion PRs through the Completion dispatcher;
- schema-versioned completed Foundations could retain `approved` Task Specs;
- Completion Evidence could remain stale;
- recorded implementation merge did not have to exist in the target base;
- Ruleset `exclude` conditions were not honored;
- executing Program states did not require one matching Active Work lease/status.

Repairs added mandatory Program Finalization, completion-aware Coordination/Scope dispatch, true legacy Foundation separation, completion Evidence freshness, target-base merge ancestry, Ruleset include/exclude handling, and one-to-one Program/Registry state checks. Positive and negative governance tests cover each condition.

### Governance Gate #191

Validated HEAD: `771daf58415f1001085d19c4781176acf99afcb0`

Result: failed.

Successful areas included Program Integrity/History/Finalization and 223 governance tests. Agent Coordination failed because the Task used the bare extensionless root token `Makefile`, which was intentionally ignored by the path parser, while the Registry contained the path.

The Task now uses `./Makefile`; path normalization preserves the same repository path and scope.

### Governance Gate #192

Validated HEAD: `2c8f08ea136fc509bf2d40819fb5eddcaf8f8b4b`

Result: success.

Every mandatory step succeeded:

- checkout, setup, compile and collection;
- Task file and Project Readiness;
- Program Plan Integrity, History and Finalization;
- completion-aware Agent Coordination;
- 223 governance tests and skip audit;
- Markdown and Schema validation;
- Secret scan;
- Evidence and Evidence integrity;
- PR/Task linkage;
- completion-aware Scope and Spec Sync;
- repository-boundary and workflow static checks.

## Final integration condition

This Evidence refresh creates a later PR HEAD. Integration remains blocked until that final HEAD has:

1. a successful Governance Gate;
2. a fresh independent Codex review of the same SHA with no findings;
3. zero unresolved review threads;
4. a final manual diff/scope/base review;
5. expected-head approval and merge.

After repair merge, the resulting `main` Gate must succeed. A separate Foundation Completion PR must then record the actual repair merge SHA, refresh completion Evidence and remove only the GZ-014 lease.

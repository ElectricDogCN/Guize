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

Later exact-HEAD Codex reviews identified additional gaps across:

- completion-aware Scope and Coordination dispatch;
- schema-versioned Foundation status protection;
- completion Evidence freshness and target-base implementation merge existence;
- Ruleset include/exclude handling;
- one-to-one Program/Registry executing-state mapping;
- completion ledger immutability, Reservation snapshot proof, dependency activation ordering and final release closure.

Repairs added mandatory Program Integrity, History and Finalization, completion-aware dispatchers, true legacy Foundation separation, fresh completion Evidence, target-base merge ancestry, live Ruleset validation and positive/negative governance tests.

### Governance Gate #191

Validated HEAD: `771daf58415f1001085d19c4781176acf99afcb0`

Result: failed.

Program Integrity/History/Finalization and 223 governance tests passed. Agent Coordination failed because the Task used the bare extensionless root token `Makefile`, which the path parser intentionally ignored, while the Registry contained the path.

The Task now uses `./Makefile`; path normalization preserves the same repository path and scope.

### Governance Gate #196

Validated HEAD: `da2e1cbf9ca15881fc7cf271b531ffe7353eb067`

Result: success.

Every mandatory step succeeded, including:

- Task file and Project Readiness;
- Program Plan Integrity, History and Finalization;
- completion-aware Agent Coordination and Scope;
- 200 governance tests and skip audit;
- Markdown and Schema validation;
- Secret scan;
- Evidence and Evidence integrity;
- PR/Task linkage and Spec Sync;
- repository-boundary and Workflow static checks.

### Mandatory pre-approval review findings after Gate #196

The exact-head manual review intentionally continued after the green Gate and found two incomplete OPS-001 enforcement checks.

First, the live Ruleset verifier did not require `strict_required_status_checks_policy=true`. A Ruleset could require Governance Checks but still allow them to be evaluated against a stale target-branch base.

Second, the verifier did not require `require_last_push_approval=true`. A Ruleset could require one approval yet not guarantee that the latest reviewable push was approved by someone other than its pusher.

The repairs add:

- fail-closed validation of `strict_required_status_checks_policy`;
- fail-closed validation of `require_last_push_approval`;
- negative tests proving each false value is rejected;
- a positive test proving the complete Ruleset policy is accepted.

### Governance Gate #202

Validated HEAD: `7e38d391e3c1e997f5e90081d747dd0fe99a4dc0`

Result: success.

All Governance Gate steps succeeded after the latest-target-branch enforcement repair. Continued review then added the independent latest-push approval requirement, so Gate #202 is retained as evidence but is not approval for the later HEAD.

## Final integration condition

The latest code and Evidence updates create another PR HEAD. Integration remains blocked until that exact final HEAD has:

1. a successful Governance Gate;
2. a fresh independent Codex review of the same SHA with no findings;
3. zero unresolved review threads;
4. a final manual diff/scope/base review;
5. expected-head approval and merge.

After repair merge, the resulting `main` Gate must succeed. A separate Foundation Completion PR must then record the actual repair merge SHA, refresh completion Evidence and remove only the GZ-014 lease.

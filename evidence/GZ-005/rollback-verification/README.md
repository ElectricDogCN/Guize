# GZ-005 current Completion candidate — successor verification pending

Task:GZ-005 / Issue68; phase:independent Completion; candidate metadata status:completed; current execution status:PENDING. Issue68 is actually closed/completed. Branch:chore/GZ-005-openapi-completion; base:8f2beb00c568ecb79c8ae0204f36fe445599fc37.

Code completion identity remains PR82 /95dc9d7cec927a753e8017cd3b509ebfee681b72. Review PR83 actually merged as 8f2beb00c568ecb79c8ae0204f36fe445599fc37. This candidate removes only its original lease and appends only its actual code identity. Metadata completed or historical PASS does not constitute acceptance or merge.

Roles:Coordinator program-coordinator-agent; Implementer openapi-contract-agent; Reviewer independent-openapi-review-agent; Integrator integration-agent. Current agentRole:integrator.

## Actual prior source execution, not successor acceptance

Prior Completion source:9dc57530c773c2753cc7047762a85ac00b381501 /tree:14163ff7a756ab2889ba5a3dce9ddc6d352d2900. Actual15 all exit0, full527 in717.57s/JUnit527 zero failures/errors/skips, CI639 full527 in683.45s/all steps success are retained losslessly in test-results/completion-9dc5753/raw-results.bundle.json and its README index. Three subsequent evidence corrections prevent final integration acceptance. Those results do not certify the corrected successor head; accepted earlier code/Review records remain preserved.

## Current required integration actions

Publish the exact corrected successor source/tree; run its actual15 including one full make verify TASK=GZ-005 BASE=8f2beb00c568ecb79c8ae0204f36fe445599fc37 HEAD_REF=HEAD BRANCH=chore/GZ-005-openapi-completion with full527 and nonempty JUnit zero failures/errors/skips. Retain all raw Source Commit/Command/Exit Code and identical clean worktree binding. Obtain latest same-head full CI, finite independent content/evidence acceptance, verified threads and fresh head/base/closed Issue before expected-head merge. Failures prevent merge and remain retained. Then verify real Completion main/parents/tree, all applicable push-main gates/full527 and clean Root/native with independent acceptance before subsequent work. Full V1/runtime/multidevice/POCs remain incomplete.

# Current Completion rollback and forward recovery

PR82 code is already merged at95dc9d7cec927a753e8017cd3b509ebfee681b72 and PR83 at8f2beb00c568ecb79c8ae0204f36fe445599fc37. This Completion candidate is unmerged. Older close-unmerged-implementation and held-lease steps below are historical and cannot undo accepted merges.

1. Before Completion merge, stop integration and downstream admission on any gate/review/identity failure. Retain actual outputs and correct the open candidate. Do not alter the main lease through unrelated edits. If abandoning it, close its PR and reopen Issue68 according to actual disposition using the authorized connector; failure is not completion.
2. After accepted Completion, stop downstream admission on a new contract/evidence defect. Record actual main SHA/tree and precise defect. Never revert completed GZ-005 Task/Program, erase its Ledger row, reinstate old lease, reset main or rewrite completion history.
3. Use a new separately registered forward repair with independent roles and exact module-owned claims. If no planned repair can legally start, first register the necessary high-risk MOD-GOV planning/recovery Foundation metadata-only, merge reservation, and implement only its governance scope. That Foundation cannot write business contracts. Business repair requires an appropriately planned, separately registered ordinary contract task with correct owner modules.
4. If execution must be frozen, follow AGENTS17.8 exactly: registered MOD-GOV owner, specific defect/reason, affectedTasks including GZ-005, actual frozen main sourceCommit, UTC frozenAt and own verificationPath. Freeze/repair/thaw obey their bounded metadata and merged validation proof. Ordinary contract work starts only after thaw and separate valid reservation. Downstream admission remains stopped until its actual contract repair is accepted; no broad recovery exemption.
5. Evidence-only correction follows completed-evidence rules after thaw: both states completed, complete Task/Program/Registry/Ledger bytes unchanged, own Evidence only, new distinct branch and Issue68 closed/completed. Preserve prior failures and originals.
6. Run applicable source-bound lifecycle/coordination/scope/schema/contract gates, full governance with nonempty zero-failure/error/skip JUnit, make verify, same-head CI and independent review. Accept actual repair main before resuming downstream work. Freeze/thaw additionally requires the actual merged repair identity, source-bound proof and separate metadata-only thaw PR. Failure keeps admission stopped.

Executable checks on the actual registered repair branch, using Task/Registry values:

```bash
test -n "$RECOVERY_TASK" && test -n "$RECOVERY_BASE" && test -n "$RECOVERY_BRANCH" || exit 1
python scripts/check-program-plan-integrity.py --base-ref "$RECOVERY_BASE"
python scripts/run-program-lifecycle-gate.py --base-ref "$RECOVERY_BASE" --head-ref HEAD --task "$RECOVERY_TASK" --branch-name "$RECOVERY_BRANCH"
python scripts/run-agent-coordination-gate.py --base-ref "$RECOVERY_BASE" --head-ref HEAD --task "$RECOVERY_TASK" --branch-name "$RECOVERY_BRANCH"
python -m pytest tests/governance -q --junitxml="evidence/$RECOVERY_TASK/test-results/governance.xml"
make verify TASK="$RECOVERY_TASK" BASE="$RECOVERY_BASE" HEAD_REF=HEAD BRANCH="$RECOVERY_BRANCH"
```

Retain actual Source Commit/Command/Exit Code raw logs and physical SHA/JUnit binding. This planned procedure is not an executed rollback, PASS or completed repair.

## Historical prior phase records; not current state or actions

# GZ-005 reservation rollback

NOT_EXECUTED: this candidate is unmerged. Closing its PR before merge leaves main intact.
After merge, use an independently reviewed cancellation/blocking lifecycle change for
GZ-005 and release only its lease. Never reset completed tasks or rewrite the Ledger.

Read-only scope verification against the registration base:

```bash
git diff --name-only 788e6f257d9052db81a8df793bf8b448a05011a1 HEAD
git diff --exit-code 788e6f257d9052db81a8df793bf8b448a05011a1 HEAD -- specs/coordination/task-completions.yaml specs/tasks/GZ-010.md evidence/GZ-010 contracts scripts tests AGENTS.md
```

Actual verification outputs and exit codes belong in test-results after execution.

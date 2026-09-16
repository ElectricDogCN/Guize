# Guize V1 POC Program

`GZ-010` defines **POC-PROTOCOL-V1**. It freezes ten independent POC planning baselines; it does **not** execute any POC.

## Three-layer model

1. **Immutable Program baseline (GZ-010 owned)**
   - `plans/POC-001.yaml` ～ `POC-010.yaml`
   - `resources.yaml`
   - `samples.yaml`
   - schemas/templates/policy
   - These files describe what must be tested. Downstream POC tasks do not write execution state back into them.

2. **Task-owned execution Evidence (POC-001～010 owned)**
   - each POC writes only under its existing `evidence/POC-XXX/**` path;
   - sample approval records bind sample ID, immutable ID, SHA-256, approver and UTC approval time;
   - the execution record contains the concrete Task Spec implementer, approved sample binding, captured environment, exact commands, raw-output references, measurements and required provenance;
   - the result record contains terminal decision and the concrete Task Spec reviewer.

3. **Shared result index**
   - `specs/poc/results-index.yaml` is the only POC Program file shared with downstream POC tasks;
   - nonterminal rows contain no decision/reviewer/result reference;
   - terminal rows point to an existing task-owned result record;
   - a POC task may modify only its own row, proven by base-to-head validation.

This keeps Program configuration immutable and avoids granting ten independent tasks overlapping write access to GZ-010 planning files.

## Source of truth

`specs/coordination/program-plan.yaml` remains authoritative for POC↔Task↔Requirement↔Module↔Wave/Risk/dependency mappings and task path ownership. Concrete implementer/reviewer identities come from the persistent `specs/tasks/POC-XXX.md` Task Spec and, while active, must match `specs/coordination/active-work.yaml`.

## Files

- `program.yaml`: manifest for the canonical POC Program.
- `policy.yaml`: immutable-plan, safety, evidence, concurrency and review rules.
- `resources.yaml`: planning resource descriptors; credentials are never stored.
- `samples.yaml`: planning sample catalogue. Approval, immutable identity and checksum remain `pending/TBD` here and are captured in the executing task's Evidence.
- `results-index.yaml`: ten result slots; all start `not_started`.
- `plans/POC-001.yaml` … `POC-010.yaml`: immutable experiment requirements and exit criteria.
- `sample-approval.schema.yaml`: contract for task-owned sample approval Evidence.
- `execution-record.schema.yaml`: contract for task-owned execution Evidence.
- `result-record.schema.yaml`: contract for terminal result/review Evidence.
- `templates/**`: copyable skeletons for downstream POC Evidence.
- `check_program.py`: fail-closed schema/cross-file/Evidence validator.
- `test_program.py`: primary positive/negative regression suite.

## Downstream POC execution

For `POC-XXX`:

1. Coordinator creates the POC's own Issue/Task Spec/Reservation using canonical Program Plan paths and assigns concrete, distinct Implementer/Reviewer identities.
2. The POC does **not** modify `plans/POC-XXX.yaml`, `samples.yaml`, `resources.yaml`, schemas, templates or policy.
3. Before execution, the task creates versioned sample-approval records and an execution record under `evidence/POC-XXX/**`.
4. Each used sample must have an approved Evidence record, stable immutable ID and `sha256:<64 hex>` checksum. The approval record must match those exact values and contain a concrete approver and valid UTC approval instant.
5. Required environment/provenance fields must contain real non-placeholder values; AI identity/version/Prompt/input-version fields are textual.
6. Exact commands and raw outputs are recorded; every raw-output reference must resolve to an existing regular file inside that task Evidence path without path/symlink escape.
7. Measurement IDs must exactly match the immutable plan. Boolean measurements are actual booleans; other measurements are finite numbers.
8. Media POC-002 records input SHA-256, output SHA-256 and exact encoder parameters; input SHA-256 must match an approved execution sample checksum.
9. AI POC-009 records model/version/Prompt/inference parameters/input version and access/budget gates.
10. Recovery POC-010 verifies actual Secret value round-trip and fail-closed behavior for unreadable/decryption-mismatched backups without committing plaintext.
11. A terminal result record is created under the same Evidence path and approved by the concrete reviewer from `specs/tasks/POC-XXX.md`, distinct from the concrete implementer/executor. While the task is active, those identities must also match Active Work.
12. Only then may the task update its shared `results-index.yaml` row to `pass`, `fail` or `inconclusive`.
13. The task must prove it changed only its own shared index row by running the row-ownership check against the integration base.

`running`, `blocked`, `cancelled` and `not_started` index rows must keep `resultRef`, `decision`, `reviewer` and `approvedAt` null. At most one high/critical POC may be running; POC-010 (critical) must run alone.

## Security

No password, token, private key, credential value, production secret or unapproved sensitive payload belongs in Git. Compound key names such as `productionApiKeyValue` and `authTokenValue` are rejected. `credentialsStored*` metadata is safe only when the value is exactly `false`. Secret recovery Evidence must use safe comparison artifacts rather than plaintext values.

## Validation

Install the repository governance dependencies, then validate the immutable baseline:

```bash
python -m pip install -r requirements-governance.txt
python specs/poc/check_program.py
python specs/poc/test_program.py
```

A downstream POC task must additionally prove shared-row ownership, for example:

```bash
python specs/poc/check_program.py --task POC-003 --base-ref origin/main
```

The validation commands do not run hardware, cloud, media, AI, storage or recovery experiments.

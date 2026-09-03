# Guize V1 POC Program

`GZ-010` defines **POC-PROTOCOL-V1**. It prepares ten independent experiments; it does **not** execute them.

## Core distinction

- `GZ-010`: defines protocol, resource/sample catalogues, plan schemas, ten `planned/not_started` plans, result index and validator.
- `POC-001`～`POC-010`: later independent Tasks that reserve resources, capture exact environments/commands/raw evidence/measurements, produce a result, receive independent review, and update the result index.
- `not_started` means only **no experiment has run**. It never means PASS.

## Source of truth

`specs/coordination/program-plan.yaml` remains authoritative for POC↔Task↔Requirement↔Module↔Wave/Risk/dependency mappings. `python specs/poc/check_program.py` fails if this directory drifts from that Program Plan.

## Files

- `program.yaml`: program manifest and canonical file references.
- `policy.yaml`: global safety/scheduling/evidence rules.
- `resources.yaml`: resource descriptors; availability is explicit and credentials are never stored.
- `samples.yaml`: sample descriptors only; no sensitive payload is committed.
- `results-index.yaml`: all ten results start as `not_started`.
- `plans/POC-001.yaml` … `POC-010.yaml`: independent experiment plans.
- `templates/**`: reusable structure for later POC execution.
- `check_program.py`: fail-closed schema and cross-file validator.
- `test_program.py`: positive baseline plus negative mutations.

## How a POC is executed later

1. Coordinator verifies the POC Task is eligible in Program Plan and creates its own Issue/Task Spec/Reservation.
2. The Task reserves only its declared paths/resources and records a fixed base SHA.
3. Before execution, the Task records environment/tool/driver/model versions and replaces `TBD_BEFORE_EXECUTION` sample identities/checksums after sample approval.
4. Execution commands are added by the **POC Task**, never by GZ-010.
5. Raw outputs remain under the independent `evidence/POC-XXX/**` path.
6. Measurements are written with method/unit/raw evidence reference.
7. A decision is produced only after exit criteria can be evaluated.
8. Independent review must approve the result before it is accepted.
9. `results-index.yaml` changes only as part of that governed POC lifecycle.

## Security and privacy

No secret, token, private key, credential, production data, or unapproved sensitive sample belongs in this directory. External provider tests must follow approved data/privacy/license policy and use runtime credential references outside Git.

## Validation

```bash
python specs/poc/check_program.py
python specs/poc/test_program.py
```

Both commands are planning-program validation only. They do not run any POC.

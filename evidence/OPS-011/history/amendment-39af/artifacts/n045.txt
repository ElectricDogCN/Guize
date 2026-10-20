# OPS-011 scope amendment — current candidate

Issue: [#108](https://github.com/ElectricDogCN/Guize/issues/108); PR: [#110](https://github.com/ElectricDogCN/Guize/pull/110).

Base: `1d2cb080d56176e26375a7b373a3cf3ef548b3dd`; registration branch: `chore/OPS-011-agent-edge-104-scope-registration`; implementation branch: `chore/OPS-011-agent-edge-104-scope`. State: reserved/coordinator. Successor Source Commit/tree: PENDING_ACTUAL_PUBLICATION. The new immutable Git HEAD will be recorded by its actual execution entry; no future SHA is supplied.

The previous 8c9f1ca source is superseded: its first13 commands exited0, make verify was deliberately interrupted for the three real review findings and did not pass. These results do not transfer. Current successor commands, raw outputs, JUnit, CI, independent source acceptance and actual-main acceptance are all PENDING.

## Assigned roles

- owner: `ElectricDogCN`.
- coordinator: `program-coordinator-agent`.
- implementer: `planning-revision-agent`.
- reviewer: `independent-planning-revision-review-agent`.
- integrator: `integration-agent`.

## Contracts and scope

Task schemaVersion2, Active Work version1 and Program schemaVersion1, all bound to base `1d2cb080d56176e26375a7b373a3cf3ef548b3dd`. Produces `CONTRACT-PROGRAM-PLAN`; consumes `CONTRACT-TASK-SPEC` and `CONTRACT-ACTIVE-WORK`. Modules: MOD-GOV; requirement: REQ-V1-0010. Exclusive scope is the sixteen exact paths in [scope](scope.md) and the Registry; no shared paths (`[]`); integrationOrder=7; strategy=merge. Lease: `2026-10-20T15:16:57Z` through `2026-10-27T15:16:57Z`, unchanged. Actual files: [inventory](changed-files.md).

## Verification, failures and limitations

The fifteen exact required commands are in [commands](commands.txt) and the Task. Successor exit codes/raw logs/JUnit/CI are PENDING; the execution entry must bind its actual Git source/tree and before/after clean snapshots. The [prior command executions](history/8c9f1ca/execution/command-executions.json) and [interruption record](history/8c9f1ca/execution/controller-interruption.json) retain the actual incomplete source; its 13 early zero exits are not a complete gate. No mechanism, business scope/GZ022, Android application, runtime, formal POC or V1 completion is accepted.

## Rollback and exact next actions

NOT EXECUTED. Before merge, close PR110 to withdraw this amendment; the previously accepted reservation remains. If the whole task is stopped, use the repository-supported normal cancellation/release procedure in its own metadata change. After merge correct the reservation through a separately reviewed forward metadata amendment before implementation. Do not reset history, remove completed records, alter original declarations or bypass frozen/recovery rules.

Coordinator publishes the reviewed exact successor; Implementer runs all fifteen Task commands against that immutable source; Reviewer accepts its actual logs/JUnit and same-head CI; Integrator checks current PR/head/base/threads/lease and normally merges, then accepts actual main. Only afterward create the implementation branch from that accepted main. GZ022 remains separate.

Accepted original reservation, prerequisite only: [original receipt](reservation-history/actual-main-independent-acceptance.json), [portable artifact map](reservation-history/artifacts/artifact-map.json) and [recovery instructions](reservation-history/artifacts/README.md). Original reservation acceptance does not establish current amendment success.

Original historical logs may use a lossless base64 JSON container; recover them through the [accepted artifact map](reservation-history/artifacts/artifact-map.json) and [superseded-source storage map](history/8c9f1ca/execution/artifact-map.json) before checking original hashes.

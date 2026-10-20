# OPS-011 scope amendment — current candidate

Issue: [#108](https://github.com/ElectricDogCN/Guize/issues/108); PR: [#110](https://github.com/ElectricDogCN/Guize/pull/110).

Base: `1d2cb080d56176e26375a7b373a3cf3ef548b3dd`; registration branch: `chore/OPS-011-agent-edge-104-scope-registration`; implementation branch: `chore/OPS-011-agent-edge-104-scope`. State: reserved/coordinator. Successor Source Commit/tree: PENDING_ACTUAL_PUBLICATION. The new immutable Git HEAD will be recorded by its actual execution entry; no future SHA is supplied.

The previous 8c9f1ca source is superseded: its first13 commands exited0, make verify was deliberately interrupted for the three real review findings and did not pass. These results do not transfer. Current successor commands, raw outputs, JUnit, CI, independent source acceptance and actual-main acceptance are all PENDING.

Exact full amendment delta relative to base 1d2cb080d56176e26375a7b373a3cf3ef548b3dd:

- evidence/OPS-011/api-samples/README.md
- evidence/OPS-011/assumptions.md
- evidence/OPS-011/changed-files.md
- evidence/OPS-011/commands.txt
- evidence/OPS-011/follow-ups.md
- evidence/OPS-011/handoff.md
- evidence/OPS-011/history/8c9f1ca/canonical/changed-files.md
- evidence/OPS-011/history/8c9f1ca/canonical/commands.txt
- evidence/OPS-011/history/8c9f1ca/canonical/handoff.md
- evidence/OPS-011/history/8c9f1ca/canonical/scope.md
- evidence/OPS-011/history/8c9f1ca/canonical/summary.md
- evidence/OPS-011/history/8c9f1ca/execution/artifact-map.json
- evidence/OPS-011/history/8c9f1ca/execution/command-executions.json
- evidence/OPS-011/history/8c9f1ca/execution/controller-interruption-result.json
- evidence/OPS-011/history/8c9f1ca/execution/controller-interruption.json
- evidence/OPS-011/history/8c9f1ca/execution/coordination.txt
- evidence/OPS-011/history/8c9f1ca/execution/diff.txt
- evidence/OPS-011/history/8c9f1ca/execution/evidence.txt
- evidence/OPS-011/history/8c9f1ca/execution/execution-entry.json
- evidence/OPS-011/history/8c9f1ca/execution/failed-gate-worktrees.json
- evidence/OPS-011/history/8c9f1ca/execution/finalization.txt
- evidence/OPS-011/history/8c9f1ca/execution/history.txt
- evidence/OPS-011/history/8c9f1ca/execution/integrity.txt
- evidence/OPS-011/history/8c9f1ca/execution/lifecycle.txt
- evidence/OPS-011/history/8c9f1ca/execution/make-governance.xml
- evidence/OPS-011/history/8c9f1ca/execution/raw-lifecycle.txt
- evidence/OPS-011/history/8c9f1ca/execution/readiness.txt
- evidence/OPS-011/history/8c9f1ca/execution/schemas.txt
- evidence/OPS-011/history/8c9f1ca/execution/scope.txt
- evidence/OPS-011/history/8c9f1ca/execution/status.json
- evidence/OPS-011/history/8c9f1ca/execution/task.txt
- evidence/OPS-011/history/8c9f1ca/execution/transitions.txt
- evidence/OPS-011/history/8c9f1ca/execution/verify.txt
- evidence/OPS-011/migration-report/README.md
- evidence/OPS-011/performance/README.md
- evidence/OPS-011/reservation-history/accepted-reservation-artifacts/ops011-reservation-1d2cb08-actual-main-adoption.json
- evidence/OPS-011/reservation-history/accepted-reservation-artifacts/ops011-reservation-5d614f1-final-source-admission.json
- evidence/OPS-011/reservation-history/actual-main-independent-acceptance.json
- evidence/OPS-011/reservation-history/artifacts/README.md
- evidence/OPS-011/reservation-history/artifacts/a03.json
- evidence/OPS-011/reservation-history/artifacts/a04.json
- evidence/OPS-011/reservation-history/artifacts/a05.json
- evidence/OPS-011/reservation-history/artifacts/a06.raw
- evidence/OPS-011/reservation-history/artifacts/a07.txt
- evidence/OPS-011/reservation-history/artifacts/a08.txt
- evidence/OPS-011/reservation-history/artifacts/a09.txt
- evidence/OPS-011/reservation-history/artifacts/a10.txt
- evidence/OPS-011/reservation-history/artifacts/a11.txt
- evidence/OPS-011/reservation-history/artifacts/a12.txt
- evidence/OPS-011/reservation-history/artifacts/a13.json
- evidence/OPS-011/reservation-history/artifacts/a14.json
- evidence/OPS-011/reservation-history/artifacts/a15.json
- evidence/OPS-011/reservation-history/artifacts/a16.json
- evidence/OPS-011/reservation-history/artifacts/a17.xml
- evidence/OPS-011/reservation-history/artifacts/a18.txt
- evidence/OPS-011/reservation-history/artifacts/a19.txt
- evidence/OPS-011/reservation-history/artifacts/a20.txt
- evidence/OPS-011/reservation-history/artifacts/a21.txt
- evidence/OPS-011/reservation-history/artifacts/a22.txt
- evidence/OPS-011/reservation-history/artifacts/a23.txt
- evidence/OPS-011/reservation-history/artifacts/a24.txt
- evidence/OPS-011/reservation-history/artifacts/a25.txt
- evidence/OPS-011/reservation-history/artifacts/a26.txt
- evidence/OPS-011/reservation-history/artifacts/a27.txt
- evidence/OPS-011/reservation-history/artifacts/a28.txt
- evidence/OPS-011/reservation-history/artifacts/a29.txt
- evidence/OPS-011/reservation-history/artifacts/a30.txt
- evidence/OPS-011/reservation-history/artifacts/a31.txt
- evidence/OPS-011/reservation-history/artifacts/a32.txt
- evidence/OPS-011/reservation-history/artifacts/a33.raw
- evidence/OPS-011/reservation-history/artifacts/a34.json
- evidence/OPS-011/reservation-history/artifacts/a35.json
- evidence/OPS-011/reservation-history/artifacts/artifact-map.json
- evidence/OPS-011/reservation-history/commands.txt
- evidence/OPS-011/reservation-history/original-reservation/api-samples/README.md
- evidence/OPS-011/reservation-history/original-reservation/assumptions.md
- evidence/OPS-011/reservation-history/original-reservation/follow-ups.md
- evidence/OPS-011/reservation-history/original-reservation/migration-report/README.md
- evidence/OPS-011/reservation-history/original-reservation/performance/README.md
- evidence/OPS-011/reservation-history/original-reservation/risks.md
- evidence/OPS-011/reservation-history/original-reservation/rollback-verification/README.md
- evidence/OPS-011/reservation-history/original-reservation/screenshots/README.md
- evidence/OPS-011/reservation-history/original-reservation/security/README.md
- evidence/OPS-011/reservation-history/original-reservation/test-results/README.md
- evidence/OPS-011/risks.md
- evidence/OPS-011/rollback-verification/README.md
- evidence/OPS-011/scope.md
- evidence/OPS-011/screenshots/README.md
- evidence/OPS-011/security/README.md
- evidence/OPS-011/summary.md
- evidence/OPS-011/test-results/README.md
- specs/coordination/active-work.yaml
- specs/tasks/OPS-011.md

Accepted original reservation, prerequisite only: [original receipt](reservation-history/actual-main-independent-acceptance.json), [portable artifact map](reservation-history/artifacts/artifact-map.json) and [recovery instructions](reservation-history/artifacts/README.md). Original reservation acceptance does not establish current amendment success.

# GZ-003 Terminal Wave Occupancy Self-Hosting Repair

## Traceability

- Tracking issue: OPS-007 / #54
- Blocked downstream lifecycle: OPS-006 / #52
- Blocked Registration PR: #53 at `67fbe45c56a79e71a8e6c9df9702ba0696d674fc`
- Target baseline: `main@219d7096756ad75717a46d85baf7d2b216e2472b`
- Maintenance owner: completed governance foundation GZ-003
- Work branch: `fix/GZ-003-terminal-wave-occupancy`

## Trigger and diagnosis

The OPS-006 Registration audit exposed a bootstrap deadlock in Project Readiness.
W1 has `maxConcurrent: 2` and already contains completed GZ-004 plus active
GZ-010. Registering OPS-006 as a third W1 Program row makes the checker fail,
because it counts every historical and live task in the Wave.

The required OPS-006 Reservation phase only changes `planned -> reserved`.
Without this repair, that Reservation remains the third counted W1 row and can
never be fully green. Scheduling the repair inside the later OPS-006
Implementation phase therefore makes the documented lifecycle unreachable.

## Minimal behavior change

Project Readiness continues to process every Program task for:

- identity and Schema validation;
- Requirement and Module coverage;
- dependency DAG and Wave-order validation;
- contract producer and consumer lineage;
- final release and external-blocker checks.

Only structural Wave occupancy is changed. The checker derives
`occupying_tasks` from all Wave tasks and excludes exactly these terminal
states:

- `completed`;
- `cancelled`.

The following checks operate on `occupying_tasks`:

- `maxConcurrent`;
- `maxHighRisk`;
- critical-task standalone enforcement;
- same-Wave exclusive/shared path conflict detection.

Every non-terminal state remains occupying and fail-closed:
`planned`, `reserved`, `in_progress`, `review`, `integration`, and `blocked`.
No configured limit, Active Work rule, Reservation rule, lifecycle transition,
or external blocker is changed.

## Regression contract

The focused regression suite proves:

1. completed history releases a slot so one active and one planned task fit a
   Wave whose capacity is two;
2. cancelled history also releases capacity and historical path claims;
3. only completed and cancelled are classified as terminal;
4. a third non-terminal task still exceeds Wave capacity;
5. two non-terminal high/critical tasks still exceed the high-risk limit;
6. a non-terminal critical task with a peer still violates standalone mode;
7. overlapping paths between non-terminal tasks still fail;
8. a completed task remains subject to dependency validation and remains a
   contract producer for downstream consumers.

## Self-hosting boundary

GZ-003 is completed. This change does not add a reusable bypass and does not
change completed-task lifecycle policy. The exact-head Governance Gate may
therefore retain the known completed-task immutable-scope classification.
Merge eligibility requires the one-time conditions recorded in OPS-007 #54:
all functional checks and tests green, exact file confinement, fresh independent
review, zero unresolved blockers, explicit Human Owner decision, and a fully
green post-merge `main` Gate.

No merge approval is claimed by this Evidence.

## Rollback

Revert the single repair commit through a dedicated PR. The rollback must
restore the original full-Wave structural counting and re-run the Governance
Gate. OPS-006 Registration and all downstream work remain blocked until either
this repair or an independently reviewed equivalent is green on `main`.

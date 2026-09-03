# OPS-006 Assumptions

1. The exact Registration base is `main@219d7096756ad75717a46d85baf7d2b216e2472b`.
2. GZ-014 is completed and is the only OPS-006 execution dependency.
3. GZ-020 is planned; appending OPS-006 at the end of its existing `dependsOn` list is the narrowest way to preserve the final release dependency closure without changing order or activating any task.
4. Registration creates no Active Work entry and no Lease.
5. The current schema-required `leaseExpiresAt` value in the planned Task Spec is metadata only and has no execution effect.
6. The collaboration protocol defines a Wave as the earliest allowed parallel window, not a requirement that all historical and future tasks execute simultaneously.
7. For fail-closed structural capacity, only terminal `completed` and `cancelled` Program Tasks release Wave occupancy; `planned`, `reserved`, `in_progress`, `review`, `integration` and `blocked` remain counted.
8. No `maxActiveTasks`, `maxConcurrent`, `maxHighRisk`, critical-standalone or path-conflict control is changed by Registration.
9. Existing Harness failures caused solely by the absence of Registration support require exact-HEAD human classification; they are not waived or called PASS.
10. Merge remains a separate user approval decision after the exact final PR HEAD is re-audited.
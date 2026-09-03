# OPS-006 Assumptions

1. The exact Registration base is `main@219d7096756ad75717a46d85baf7d2b216e2472b`.
2. GZ-014 is completed and is the only OPS-006 execution dependency.
3. GZ-020 is planned; appending OPS-006 at the end of its existing `dependsOn` list is the narrowest way to preserve the final release dependency closure without changing order or activating any task.
4. Registration creates no Active Work entry and no Lease.
5. The current schema-required `leaseExpiresAt` value in the planned Task Spec is metadata only and has no execution effect.
6. Existing Harness failures caused solely by the absence of Registration support require exact-HEAD human classification; they are not waived or called PASS.
7. Merge remains a separate user approval decision after the exact PR HEAD is re-audited.
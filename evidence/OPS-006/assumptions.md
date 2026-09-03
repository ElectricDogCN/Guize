# OPS-006 Registration Assumptions

1. The exact Registration base is `main@3acc6e4ee582f4fdee8ba90c630bf99eb870b252`.
2. Governance Gate #446 / run `33736578549` passed on that exact main before branch creation.
3. GZ-014 is completed and is the only OPS-006 execution dependency.
4. GZ-020 is planned; appending OPS-006 at the end of its existing `dependsOn` list is the narrowest way to preserve final-release dependency closure without changing prior order or activating any task.
5. Registration creates no Active Work entry and no executable Lease.
6. The schema-required `leaseExpiresAt` field in the planned Task Spec is proposal metadata only and has no execution effect.
7. OPS-007 / PR #55 already established that only terminal `completed` and `cancelled` tasks release structural Wave occupancy. This Registration does not reopen or weaken that behavior.
8. `planned`, `reserved`, `in_progress`, `review`, `integration`, and `blocked` continue to occupy Wave capacity.
9. No `maxActiveTasks`, `maxConcurrent`, `maxHighRisk`, critical-standalone, path-conflict, Reservation, or Active Work control is changed.
10. The existing Harness still lacks an explicit `absent -> planned` Registration classification. Exact candidate failures caused solely by that absence must be recorded, not waived or described as PASS.
11. The closed PR #53 is diagnostic history only; none of its stale base, HEAD, run result, or mergeability is treated as current evidence.
12. Merge remains conditional on exact-head CI classification, independent review, and a recorded Human Owner / Integrator decision for the rebuilt candidate.

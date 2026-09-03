# OPS-006 Registration Follow-ups

No downstream phase is authorized automatically by this pre-run Evidence.

After the rebuilt Registration candidate has an exact-head CI classification, refreshed Evidence and independent review:

1. record the Human Owner / Integrator decision against the same immutable HEAD;
2. merge Registration only through the PR action and expected-head lock;
3. verify the resulting exact `main` and classify its push Governance Gate;
4. create a separate `chore/OPS-006-reservation` branch from that new main;
5. require the existing `planned -> reserved` transition to pass with metadata-only scope and one Active Work reservation;
6. merge Reservation only after exact-head review and verify post-merge main;
7. activate OPS-006 in a separate metadata-only PR;
8. implement and test `PROGRAM-TASK-REGISTRATION-V1` only after Activation;
9. register OPS-005 through the resulting lifecycle and rebuild its POC Program Gate;
10. synchronize and repair GZ-010 only after the mandatory POC Gate is on green main.

Any unexpected Registration failure, moved base, path drift or post-merge main failure interrupts this sequence and requires a dedicated repair or revert PR.

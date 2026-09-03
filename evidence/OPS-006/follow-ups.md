# OPS-006 Follow-ups

No follow-up is authorized automatically.

After exact-HEAD audit, independent review and explicit user approval of the Registration PR:

1. merge Registration through the normal PR action;
2. verify the resulting exact `main` SHA and post-merge repository state;
3. create a separate OPS-006 Reservation PR from that new SHA;
4. require the existing `planned → reserved` contract to pass without implementation files;
5. activate and implement PROGRAM-TASK-REGISTRATION-V1 only after Reservation is merged;
6. then close or rebuild OPS-005 / PR #51 under the new registration lifecycle.

OPS-006 must stop at the Registration approval boundary until the user acts.
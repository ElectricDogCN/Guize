# GZ-010 Reservation v2 Assumptions

Task: GZ-010

- GZ-014 remains completed.
- GZ-004 remains completed and its requirement/NFR/acceptance contracts are inputs, not outputs of GZ-010.
- OPS-003 #43 is closed after PR #44 and post-main Gate #380 succeeded.
- PR #42 is closed/unmerged and contributes only reproduction history.
- GZ-010 produces `POC-PROTOCOL-V1` during implementation; Reservation v2 does not claim that contract exists yet.
- POC-001～010 remain separate execution tasks and must not be activated or executed by this Reservation.
- Lease validity is limited to `2026-09-08T08:27:00Z`; expiration requires a new valid Reservation/lease action rather than silently continuing.

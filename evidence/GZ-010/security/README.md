# GZ-010 Security Evidence

Task: GZ-010

Reservation changes no runtime permission, Secret, credential, network policy or production data.

The later POC Program must enforce these planning rules:

- credentials/keys/tokens are referenced by secret identifier or environment variable only, never committed;
- sample data must have explicit provenance, approval/classification and privacy handling before execution;
- plans must distinguish safe fixture/synthetic data from approved real data;
- external/cloud/AI provider POCs must declare data-egress, retention, license and budget/permission boundaries;
- commands/results containing secrets must be redacted before Evidence commit;
- POC execution remains isolated to its own Task/Evidence and does not inherit blanket production permissions.

No POC security result or approval is claimed by GZ-010 Reservation.

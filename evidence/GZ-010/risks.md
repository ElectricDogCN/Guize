# GZ-010 Reservation Risks

Task: GZ-010

- POC Program preparation may be mistaken for completed experiments.
- POC ID ↔ Task ID ↔ Requirement ↔ Module ↔ Wave/Risk mappings may drift from the canonical Program Plan.
- Multiple POCs may accidentally share a result/Evidence path, destroying provenance.
- Planned commands, target measurements or expected decisions may be prefilled and later misread as observed facts.
- Secret/provider credentials or unapproved sensitive sample data may leak into plans or Evidence.
- High/critical POCs may be scheduled concurrently contrary to Program constraints.
- W2 tasks may be activated before W1 GZ-010 Completion.

Reservation controls these risks by reserving exact paths and roles before any `specs/poc/**` implementation or POC execution exists.

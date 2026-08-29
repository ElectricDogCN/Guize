# GZ-014 Risks

## Resolved or reduced

- **Task definition drift:** Issue #14/#15 and the old plan used conflicting GZ-004/GZ-010 meanings. The canonical Program Plan now defines one task model and the Issues were reconciled.
- **Giant POC branch:** POC-01～10 are mapped to POC-001～POC-010 with independent waves and Evidence; GZ-010 only defines the POC Program.
- **Requirement/module asymmetry:** the first real reservation Gate found and repaired four asymmetric mappings; readiness now validates both directions.
- **Ambiguous empty shared scope:** `无。` is now a standalone marker; templates and protocol prohibit mixing it with inline code.
- **Unowned public contracts:** 37 Contract Namespaces now have explicit owner, consumers and optional shared writers.
- **YAML timestamp typing:** registry lease timestamps are explicitly quoted to satisfy the string Schema.

## Remaining

- **GitHub enforcement:** `main` remains unprotected and has no active Ruleset. OPS-001 (#20) is an external release blocker; repository checks cannot prevent a privileged direct push.
- **Machine-contract readiness:** OpenAPI, Event Payload, DDL and Runtime Contracts remain future GZ-005～GZ-008 work. Program Plan existence is not contract completion.
- **POC uncertainty:** all ten experiments remain unexecuted; no performance, compatibility, capacity or recovery assumption may be promoted to a production promise.
- **Review capacity:** three active tasks is a maximum, not a target. ElectricDogCN may need to run fewer tasks if independent review cannot keep up.
- **False-positive path overlap:** conservative glob comparison may block a safe task; the remedy is narrower task paths or explicit shared coordination, not disabling the check.
- **Plan evolution:** changing task IDs, waves, contract producers or release gates after downstream work starts can invalidate handoffs. Program Plan changes require a high-risk governance task and migration notes.
- **Lease staleness:** expired tasks fail coordination and require Coordinator renewal/release; Agents must not continue silently.
- **Cleanup dependency:** the implementation PR cannot know its own merge SHA. GZ-014 still needs a separate cleanup/release PR before Issue #17 can close.

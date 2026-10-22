# OPS-012 blocked rework Evidence structure

Current phase is blocked/coordinator candidate after Review mainf18dcca and rejected Completion PR119. Prior accepted command/CI/JUnit records retain their own phase identities. Current metadata scope amendment and later rework acceptance remain pending; no code changes in this phase.

| Canonical entry | Compatible target | Reason |
| --- | --- | --- |
| screenshots/ | N/A | OPS-012 governance parser has no UI or device operation. |
| api-samples/ | N/A | No product API or payload implementation changes. |
| migration-report/ | N/A | No database or data migration occurs. |
| performance/ | performance/ | Baseline diagnostic is preserved; current-code hosted CI completion is verified separately. |
| security/ | test-results/ | Parser safety rejection and fallback regression plus existing secret checks are recorded after actual execution; capture contains no premature PASS. |
| rollback-verification/ | N/A | Rollback has not executed; Task describes withdrawal and forward-repair procedures. |

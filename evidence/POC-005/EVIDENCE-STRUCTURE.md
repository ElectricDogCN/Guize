Task: POC-005
Issue: 132
Base: f2e0150265e0c1eeca5f69fe85708b2434e5ee79
Branch: chore/POC-005-metadata-scale
Status: in_progress / PARTIAL; no POC experiment executed.

| Canonical entry | Compatible target | Reason |
| --- | --- | --- |
| screenshots/ | N/A | Local scanner has no UI. |
| api-samples/ | N/A | Current source is an internal JSONL interface; actual OpenList HTTP observations remain pending. |
| migration-report/ | N/A | Creates an isolated disposable SQLite POC index; no production schema migration. Existing unknown indexes are rejected. |
| performance/ | N/A | Scale/RSS experiments require concrete independent input/resource/window approval and have not run. |
| security/ | N/A | Source binding and input validation have unit coverage; actual provider authentication and HTTP security remain pending. |
| rollback-verification/ | N/A | Small-fixture whole-page/batch rollback and reopen tests passed; actual sandbox experiment cleanup remains pending. |

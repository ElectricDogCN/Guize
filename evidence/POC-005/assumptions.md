Task: POC-005
Status: in_progress / PARTIAL

Current code includes canonical paired records, read-only DAV observations and pinned numeric listing with a disk-backed frontier. Provider identity/version/snapshot and production quota remain unverified. Directory source sizes are retained separately; canonical directory fileSizeBytes is zero by explicit metadata convention. Reader credentials remain external/in-memory; unsafe or uninspectable listing bodies are omitted with actual hashes/lengths. Windows55 and independent listing content acceptance are development results only; no concrete approved experiment exists.

## Earlier assumptions at their recorded stage

Task: POC-005
Issue: 132
Base: f2e0150265e0c1eeca5f69fe85708b2434e5ee79
Branch: chore/POC-005-metadata-scale
Status: in_progress / PARTIAL; no POC experiment executed.

Current implementation is limited to the isolated deterministic fixture/JSONL source/SQLite scanner. Nineteen developer small-fixture tests passed and independent pure-code review accepted; committed-source gates and real POC measurements remain pending. Reservation/main acceptance is preserved under reservation-main-f2e0150-accepted/. Frozen13, production scope, original failures, leases and other tasks remain unchanged.

## Historical reservation notes

Task: POC-005

POC-005 uses accepted main11c32830c0d1bb8ccdcc04aa278876065bce1f33 with completed GZ-010/GZ-021/GZ-022 prerequisites. Actual OpenList process/version/credentials/input bytes are not assumed from historical preparation and must be rechecked before any experiment. Synthetic declaration sizes and injected quota do not establish700TB or provider production behavior. Inputs/resources/window require independent approval.

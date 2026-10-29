Task: POC-005
Issue: 132
Base: f2e0150265e0c1eeca5f69fe85708b2434e5ee79
Branch: chore/POC-005-metadata-scale
Status: in_progress / PARTIAL; no POC experiment executed.

Current implementation is limited to the isolated deterministic fixture/JSONL source/SQLite scanner. Nineteen developer small-fixture tests passed and independent pure-code review accepted; committed-source gates and real POC measurements remain pending. Reservation/main acceptance is preserved under reservation-main-f2e0150-accepted/. Frozen13, production scope, original failures, leases and other tasks remain unchanged.

## Historical reservation notes

Task: POC-005

POC-005 is medium risk. Main risks are same-host measurement interference, source/synthetic population confusion, stale immutable inputs, credential leakage, quota/version/permission errors and invalid scan methods. Keep ATS latency/disk and metadata throughput/RSS windows disjoint; use bounded owned sandboxes and original protocols. This registration does not execute workloads or touch production.

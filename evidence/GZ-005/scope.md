# GZ-005 reservation scope

This candidate only reserves the existing W2 contract task. It changes the task's own
Program status, Registry lease, Task context and evidence. Other inherited Program
statuses are materialized at their existing values to prevent YAML anchor drift.
Implementation may begin only after the pure reservation merges. Contract implementation
will be restricted to contracts/openapi/** and specs/contracts/openapi/**.
No application, governance script, CI workflow, POC or completed task is changed.

# OPS-006 Registration Risks

| Risk | Control |
| --- | --- |
| `planned` is mistaken for a Lease or implementation authorization | Active Work remains unchanged and the Task Spec explicitly denies execution rights. |
| The bootstrap becomes a reusable bypass | Registration changes no Checker, Workflow, allowlist, skip flag or exception code. |
| The existing Program DAG is rewritten | Only OPS-006 is appended to the tail of planned GZ-020 `dependsOn`; every prior dependency retains value and order. |
| More than one new task is introduced | Exact base/head Program diff and changed-file inventory must prove exactly one new Task ID. |
| Old PR #53 evidence is mistaken for the rebuilt candidate | Every canonical record names the new green base and r2 branch; old run results are diagnostic history only. |
| The former W1 capacity defect is silently retained | Project Readiness must pass on the rebuilt candidate; any W1-capacity failure is now unexpected and blocking. |
| Completed history is removed from non-capacity validation | OPS-007 tests remain authoritative; terminal rows must still participate in identity, DAG, contract, Requirement/Module and release validation. |
| OPS-005 or GZ-010 content is mixed into Registration | Their Program, Task, Evidence, Workflow and POC paths are forbidden. |
| Expected red CI hides an unrelated failure | Only planned Task/coordination/scope classification and the narrow GZ-020 append lifecycle classification may be accepted for bootstrap review. |
| A stale or moved HEAD is merged | Review and merge must be anchored to one exact candidate SHA. |
| Registration is merged without independent review | A fresh exact-head Codex review and zero unresolved content threads are required before the Human Owner / Integrator decision. |

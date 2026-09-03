# OPS-006 Registration Risks

| Risk | Control |
| --- | --- |
| `planned` is mistaken for a Lease or implementation authorization | Active Work remains byte-for-byte unchanged; Task text explicitly denies execution rights. |
| Bootstrap becomes a reusable bypass | No checker, workflow, allowlist, skip flag or exception code is changed in this PR. |
| Existing Program DAG is rewritten | Only OPS-006 is appended to the end of planned GZ-020 `dependsOn`; all prior entries retain order and value. |
| More than one new Task is introduced | Exact base/head Program diff and changed-file audit must prove exactly one new Task ID. |
| OPS-005 or GZ-010 content is mixed in | Their Program, Task, Evidence and POC paths are forbidden. |
| Expected red CI hides an unrelated defect | Only the diagnosed planned/Registration classification failures are acceptable for bootstrap review; all other failures block. |
| A stale review is used | Approval requires a new exact-HEAD audit after the final commit and CI run. |
| Registration is merged implicitly | No merge action is taken; explicit user approval is required in a separate step. |
# OPS-006 Registration Risks

| Risk | Control |
| --- | --- |
| `planned` is mistaken for a Lease or implementation authorization | Active Work remains byte-for-byte unchanged; Task text explicitly denies execution rights. |
| Bootstrap becomes a reusable bypass | No checker, workflow, allowlist, skip flag or exception code is changed in this PR. |
| Existing Program DAG is rewritten | Only OPS-006 is appended to the end of planned GZ-020 `dependsOn`; all prior entries retain order and value. |
| More than one new Task is introduced | Exact base/head Program diff and changed-file audit must prove exactly one new Task ID. |
| Completed history permanently blocks later governed maintenance | Future implementation lets only `completed/cancelled` release Wave occupancy. |
| Capacity is weakened while fixing terminal occupancy | Every non-terminal state remains counted; no global/Wave/high-risk maximum is increased and Active Work enforcement remains mandatory. |
| OPS-005 or GZ-010 content is mixed in | Their Program, Task, Evidence and POC paths are forbidden. |
| Expected red CI hides an unrelated defect | Only the diagnosed planned/Registration, terminal occupancy and final-DAG attachment failures are acceptable for bootstrap review; all other failures block. |
| A stale review is used | Approval requires a new exact-final-HEAD audit after the metadata amendment and CI run. |
| Registration is merged implicitly | No merge action is taken; explicit user approval is required in a separate step. |
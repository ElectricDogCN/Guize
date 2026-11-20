# OPS-027 CI performance recovery decision

- Repository and task: `ElectricDogCN/Guize`, `OPS-027`, issue #242.
- Current frozen main: `00028760e9971e367ec67fae2cebba9f06e6f470`.
- Frozen event source: `658761ad282296934061778a7a57c5ba66926a25`.
- Verified commit: `77911e903039d412760d14d5f03f0f65ce0d1e5c`.
- Current archive PR: #253, reviewed evidence head `9df7bd4fbb2a6a9f203952a652ab1143081760f6`.

The owner has delegated the decision and execution of the regular governance recovery for the CI timeout, with the original 1,078 tests, official CI, and 30-minute limit required. This record selects a prospective sequence. Permissions come from each actual registration and its completed integration review.

## Finish the current recovery

1. Add this decision to the existing evidence archive. Keep its verified commit in the branch ancestry. Keep all seven original verification files byte-for-byte. The existing frozen event, active claims, roadmap, roles, capacity policy, workflow and code remain as recorded.
2. Require successful official source CI and independent review on the exact new archive head. Use an ordinary merge and verify the actual parents, retained validated ancestor and evidence-only diff after the validated commit. Require the actual archive main checks and full official push CI before a separate metadata-only thaw.
3. Retain the failed official outcomes on #252 and #253. The three #252 main attempts and two #253 source attempts remain cancelled. The new archive run has its own checked commit, test output and verdict.
4. Integrate the separate thaw and then complete OPS-027 using its accepted implementation identity, ordinary Review and Completion. Use exact source and actual main checks at each integration. Verify that the sole high-risk lease has been released. Keep POC-003 and POC-005 blocked during this sequence.

## Register and correct the cost of historical checkouts

Use a separate high-risk `MOD-GOV` Foundation with its own issue, metadata-only reservation, exact branch and exclusive claim over `scripts/check-program-plan-history.py`. The current OPS-027 reservation and its original performance intent continue to govern the two POC code paths. Its completed governance prerequisite remains closed. The overall limit remains three active tasks and one high-risk task.

The task will address historical OPS-026 snapshot materialization in `_checkout_task_workspace`. A diagnostic on two original OPS-026 snapshots found about 50,000 tracked files per full checkout. Materializing the four existing validator inputs in isolated checkouts reduced local checkout and cleanup from 5.50–5.76 seconds to 0.066–0.070 seconds with equal input digests and equivalent original validator results. This measures local materialization cost.

The implementation must preserve the four canonical inputs, their Git and filesystem semantics, the full Git history, and both original validators. Verify that each selected checkout has the actual requested commit and ordinary input objects. Use the original full checkout whenever equivalence is uncertain. Preserve diagnostics and exercise both the canonical and fallback cases. Keep the existing approval, lease, history, freeze, and result-validation behavior, the original 1,078 cases, official workflow, worker configuration and 30-minute limit. Require complete official source and actual-main CI, independent review, normal completion and verified lease release before starting current-version POC-003/005 qualification.

If the new archive source reaches the time limit, retain its result and reassess the recovery basis. Integration requires a complete successful run on the exact source. Precedent for a different scope amendment and its historical bootstrap exception remains specific to that earlier decision.

Task: POC-003
Issue: 131
Branch: chore/POC-003-ats-range
Base: 760f6c5838597d1d66c0a536ecbf440ef5a7dfec
Current phase: in_progress / implementer

Forward representative-input component checkpoint (2026-10-25T17:17:02.632293+00:00). Parent implementation 087068d32c918da43465f0f91ca6cccd0e088d67; actual next source identity is Git HEAD after this commit. The explicit representative-v1 profile verifies real file bytes, manifest hash/closed shape, size/identity and declared request/collection budgets; default prototype-64m-v1 retains its two pinned hashes,64MiB/2048/1GiB limits. Collector single-response allowance follows actual source size; aggregate budget remains a response-completion check, not a whole-run disk quota.

V3 fixes the actual prepare-entry unbounded manifest read: at most65537 bytes, reject>65536 before runtime receipt or run creation, and the same raw bytes supply hashing/parsing. Windows and native Linux each actually passed26 offline regressions, zero skips. The unit file is67239936 bytes=64.125MiB; mocked transport streaming exercises actual bytes without starting HTTP/ATS. New ingress regression actually failed before correction (8pass/1failure). First red harness selected only the old8 tests and is explicitly not counted as red; original outcomes remain in the archive. V1 Windows ctime mismatch and V2 negative component review remain unchanged.

Independent V3 component content accepted, mustFix=[]; exact4 source hashes, original waits/raw/results and33 recoverable files are in input-profile-v3/index.json, with the original accepted review in input-profile-v3/component-review.json. Earlier34 originals remain in input-profile-v2/index.json. These are component findings, not new-source Task15/CI or media qualification. Existing full-source087/44/CI843 results remain bound to087.

Next: integrate complete media-owner accounting, then synchronize the actual accepted Gov history-fix main before Review and full source validation. Run the Task15 and declared component checks on that future exact source, obtain same-source CI and independent review. Real representative samples, numeric resource/domain/window approvals, original15 observations, untraced latency and current-source hot-cache revocation remain required. No changed-source ATS run, new sample approval, formal POC acceptance or capacity release is claimed. Keep Draft PR134; preserve all old sources/failures and the separate dirty development worktree.

Historical checkpoints follow; their current/pending wording belongs to their original source.

Task: POC-003
Issue: 131
Branch: chore/POC-003-ats-range
Base: 11c32830c0d1bb8ccdcc04aa278876065bce1f33
Current phase: in_progress / implementer
Current committed implementation validation: PENDING.

Finish actual per-stage cache exports/discard proof, original15 raw-to-typed assembly and approved buffering/latency methodology. Obtain actual-source independent code review and before-execution input/resource/window approvals before real experiments. Direct warm-cache revocation test plus original15 formal checker and independent result review all remain required. POC005/order3 and GZ006 original eligibility remain unchanged.


## Retained ioBufAllocator capacity component (full POC still pending)

The exact native ink_queue.cc grow site now durably charges checked page/huge-round-up backing capacity before any allocation. Returning/reusing blocks does not decrement that backing charge. Original logical IOBufferData capacity remains deliberately double-counted. The current lab requires the entire current instrumentation manifest, preventing reuse of the former five-file core merely because its ledger/journal headers match.

The old actual core is a preserved negative: 65536 backing bytes versus a 40960 logical peak, with logical current zero after return/reuse (actual exit2; physical coverage failed). The new six-file/three-header ordinary-user core builds and links successfully. The same actual pool driver passes: backing65536, held/peak106496, return/reuse65536; sixteen concurrent payloads retain their actual pool backing too. Independent implementation, actual build/behaviour and failure/fallback reviews accept their stated scope.

Real private invalid-product and 37-byte partial-journal cases exit70 before the allocation call returns, preserving failed/partial raw and rejecting complete epochs. The actual unavailable-hugepage profile has huge enabled/2097152, direct huge allocation ENOMEM, normal 4096-byte target mapping pages, backing2097152 and retained current2097152. Hugepage success remains unmeasured. Smaps mapping Size is not a media-payload measurement, and journal peak rows do not claim to record final release snapshots; return/current facts come from actual driver snapshots/stdout.

Old/current real runtime receipts were exercised through lab.prepare with synthetic input/exporter setup only: the old core is rejected at the exact manifest guard and the new core reaches the intercepted pre-run-creation boundary. No input media, sandbox, listener or ATS workload was created. Manifest draft/no-qualification flags remain the original build-input snapshot; actual component results are in immutable test/review archives, not retroactively rewritten flags.

Recoverable originals: retained-pool-capacity-v1/index.json; the previously accepted five-file build/link/API evidence is separately archived in durable-core-build-v1/index.json. Remaining: exact all-helper/restart/final epochs and exec chain, other ATS/media owners and alternative allocation paths as applicable, complete media-domain approval, stable-main sync/new fixed-source Task15/CI, original15 cases/current-source hot-cache revocation and full qualification. No new media experiment is approved here.


## Durable tracked-peak component V2 (not full-media qualification)

The process-lifetime logical-allocation ledger now writes/fsyncs each increasing peak under its lock before payload acquisition. No cache-ready reset; accounting, publication, external attachment, inherited fork and reused exec epochs fail closed. A native ordinary child preserves its released 1MiB peak across actual wait0; partial/failed streams cannot be promoted to complete success.

The original reader had a P2: opening a FIFO could block. Its original bytes and negative independent review remain archived. V2 uses nonblocking open plus path/FD identity checks; real FIFO-without-writer and path replacement after open/before validation and during read are rejected. The corrected reader's Windows55 and Linux55, actual live/final capture, ten retained native success/failure streams and three filesystem regressions passed. Earlier native11 scenarios plus six original ledger cases retain their original source hashes. The observer compiles against the exact SDK. Independent component review accepts this limited scope.

Reversible originals and source snapshots: durable-tracked-peak-v2/index.json. Current core build is still pending and is not accepted here. This ledger measures logical live ownership; retained physical freelist capacity, all short-lived helper/restart/final epochs, exec chain and other media owners remain incomplete. Full media bound, source Task15/current CI, original15 ATS cases, current-source warm-cache revocation and formal POC qualification are not granted. No ATS service or new media experiment was started by these component checks.

Next: finish exact core build; account for retained pools and all process windows/other media owners; ordinary sync a fully accepted stable main, run new fixed-source gates and CI, then obtain explicit representative input/resource/window acceptance and execute the full POC. Old failed/unknown methods remain preserved. Actual Task roles, claims, lease and base remain unchanged by this component commit.

Task: POC-003
Issue: 131
Branch: chore/POC-003-ats-range
Base: 760f6c5838597d1d66c0a536ecbf440ef5a7dfec
Current phase: in_progress / implementer

Forward cache component checkpoint (2026-10-25T19:57:37.072590+00:00); parent c63facc1cccc331428ebf848f8129bd9c5425a5a, next exact commit identity is Git HEAD after commit. Explicit representative input exports use <=128-key batches and unchanged native8-job/16-control/512MiB process limits, with exact per-batch request/events/results and whole-stage source/hash verification. Prototype128-key/128MiB limits remain. Original red3(2pass1error), first native fixture-user failure and rejected unbatched implementation remain recoverable. Current Windows10/native14 actual0/no skipped; native129 real Slice files135266287B are checked and assembled through128+1 batches, with a simulated bounded producer. Three quota refusals run the actual consumer and leave failure records before publication. No real ATS run follows from these tests.

Independent V2 component acceptance f1cc15bc5c0ec23468c514845efacaaa9707030494dd25f1e46c77b7e4fc8be5 resolves the native128-key mismatch;15 forward originals and accepted review are under representative-cache-batches-v2, prior17 under representative-cache-forward. Earlier canary V4 failed/unknown operand and V5 finite anonymous-child acceptance plus45 recoverable originals remain in container-counter-method-v5. Current-kernel independent review5c16499 rejects strict cgroup-peak upper-bound use; complete the existing synchronized ledger ownership/lifetime/other-media-owner bounds. All sample, numeric resource/domain/window approvals, original15, current-source warm-cache revocation and qualification remain pending.

Next: synchronize a fully accepted actual governance main before Review/full source verification, run the original Task15 and declared components plus test_representative_cache.py and native Linux test_representative_cache_native.py on the exact future source, then same-head CI and independent review. Keep Draft134. No Program/Registry state, lease, role, claims, contract, policy or capacity is changed by this component commit. Historical source-bound checkpoints follow.

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
Base: f2e0150265e0c1eeca5f69fe85708b2434e5ee79
Current phase: in_progress / implementer

SourceE123 actually passed Task15/code57 and was pushed. Its approved one-shot live diagnostic failed during strict component mapping at startup: prepare0/controller1, collector not started, no HTTP samples, two unbound native baseline rows, all owned ATS stopped and ports released within3.497617s. The actual first failing component/inode/hash is unknown because old maps were not retained. Failure archive and distinct actual result review are preserved. Old approval is consumed.

Current forward repair preserves raw maps before checks and records per-component expected and actual device/inode/hash/rejection facts. Only the optional fixed live diagnostic profile sets dynamic reload0; stock defaults remain. Two real Linux simulated-child mapping tests passed; distinct content review accepted exact repair bytes at2026-10-22T17:26:36Z. New exact-source checks and new experiment approval remain pending; no repaired-source ATS run occurred. Mainf2e0150 is fully accepted with local5/POC check/CI816713 tests and no skipped tests.



Current forward candidate: optional instrumented ATS live-media observation. Exact synchronized main f2e0150265e0c1eeca5f69fe85708b2434e5ee79 has passed five main checks plus existing POC protocol; CI816 is pending. Source8e Task15/code30/CI812713 no-skips and its actual finite pool diagnostic are retained without result transfer. Pool capacity73,363,200bytes included unused freelist slots and cannot prove a below64MiB live-media bound; this does not prove whole-object buffering.

The exact Ubuntu source plus task-owned patch/header now built and installed as ordinary UID1000 after preserving three real failed attempts. Five runtime component hashes, resolved dependencies, three core diagnostic exports and version-only execution were checked. Six ledger scenarios passed, including sticky unknown-external risk across wrapper release/repeated reset; distinct intermediate content review accepted that repair only. The new observer built against the same actual SDK;27 parser tests passed. New controller wiring still needs current-source checks, independent content review, concrete experiment approval and real runtime results. At that previous draft checkpoint no instrumentation ATS service/experiment, complete media-domain, prototype8MiB budget, original15, qualified result or integration acceptance is claimed. Generated416/502 text, kernel/socket/page cache, origin/gateway/client and stock performance remain distinct domains.

Evidence: source-8e73173-validation/, pool-diagnostic-8e73173-20261022-v1/, instrumented-build-v4-preparation/; actual source/tree for this forward candidate is Git HEAD after commit. Preserve all older failures, source identities and review limitations.

Historical source-bound checkpoints follow; pending statements below retain their original scope.

Registered implementation now contains isolated gateway/origin/ATS control, real grant validity/revocation state, raw matrix collection, native every-request cache lookup observer and explicit cache API exporter. The separate real warm-cache revocation script hard-fails without actual sandbox/observer and checks same-unexpired-grant denial before protected ATS/cache/origin reads, retaining a distinct later warm-cache control. Collector records one-body-byte timing separately from header/chunk timing.

Source181 actually passed the Task's fifteen commands, eight offline boundaries, exact observer source/build verification and distinct intermediate content review; see source-18163e1-validation/. Its separately approved real same-unexpired-grant warm-cache revocation scenario passed, retained51 raw files/158777bytes, and received distinct independent result acceptance at2026-10-22T14:32:30Z. See focused-revocation-20261022-v1/; this focused result does not transfer approval to changed code or to the original matrix.

Reservation main11c3283 is now fully accepted: actual five main checks plus separate POC checker, official terminal CI808 success,713 tests/1428.34s with no skipped tests. Its ended remote reservation branch was removed with exact expected-source protection; active PR134 implementation branch and all local refs were preserved. Final records are in reservation-main-final-11c3283/; earlier pending captures remain historical.

Source9c012b4e1c90b014fe619253a8f07a738b5c0724 actually passed Task15/offline14 and official fullCI810713/899.22s, no skipped tests; see source-9c012b4-validation/. Its approved raw matrix recorded101 requests/21 cases/6 stages. Three full64-Slice native cache exports reconstructed the exact current input without origin I/O. The interrupted206/4byte prefix and subsequent503/zero-byte response are retained. Limited raw-evidence acceptance does not establish original15 or qualified acceptance.

The actual raw run also retained a416 native error page202bytes and second fresh sandbox EADDRINUSE startup failure. The current-source revocation script did not execute. Historical TIME_WAIT was not directly recorded and is only a possible cause. All owned processes stopped, ports released and execution ended within approval. Actual744228584bytes of bulky bodies remain at native original paths; public metadata/index/hashes and actual distinct result review are under raw-matrix-9c012b4-20261022-v1/, explicitly not qualified artifacts.

The current forward repairs resolve impossible Range intervals after grant authorization and before ATS, permit stopped own ports to rebind without sharing live listeners, observe the first actual HTTP response byte separately from headers/media, and verify actual warm/denial source version and cache context. Actual21 offline/filesystem/loopback regressions passed with distinct independent content acceptance; see development-http-fixes-checks/v2-21/ and http-fixes-independent-review.json. No ATS experiment has run at these changed source bytes; new concrete approval and verification are required.

Original15 typed measurement assembly, combined partial-cache disposal proof, independently justified buffering domain and actual original-matrix results remain incomplete. Full POC/V1 and source integration remain unaccepted.

SourceD1 actually passed Task15/offline21 and CI811:713 tests/1461.80s, no skips; see source-d1c0cf7-validation/. Its independently approved serial raw matrix recorded21cases/101requests/6stages and its separate fresh current-source warm-cache revocation passed. The distinct independent result review accepted that finite evidence; see raw-matrix-d1c0cf7-20261022-v2/. Historical source9c failures remain unchanged.

The next diagnostic draft adds native TSCacheReady/HTTP readiness before accepting startup and a private, idle-controller allocator-dump operation. It signals only the live owned pidfd, waits for a complete native absolute pool table, verifies byte totals, and retains the exact stderr interval. RAM cache is explicitly disabled and freelist override/preload environment is excluded. Absolute allocated capacity includes the baseline; no buffer upper bound is inferred from this pool subtotal. Actual draft30 tests and a fresh strict C++ build passed, with no real ATS run; see development-buffer-observer-checks/ and development-buffer-observer-build/. Relevant exact Ubuntu source comparison received finite independent acceptance, not measurement-domain or experiment approval.

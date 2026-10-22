Task: POC-005
Issue: 132
Base: f2e0150265e0c1eeca5f69fe85708b2434e5ee79
Branch: chore/POC-005-metadata-scale
Status: in_progress / PARTIAL; no POC experiment executed.

The reservation PR135/source f42e107 was admitted and merged into accepted main f2e0150; source local15, full CI814 (713 tests), independent metadata review, actual main checks and CI816 (713 tests, 1445.86s, no skipped tests) are retained byte-for-byte under reservation-main-f2e0150-accepted/. The ended reservation remote branch was removed by exact-ref comparison; all local refs and active POC003 were preserved. These are reservation checks, not implementation acceptance.

The first implementation adds a bounded immutable JSONL source, deterministic exact-file-count hierarchy generator, SQLite page/checkpoint transactions and source-bound incremental replay. Paths are locators; identity remains source/objectId. Restart, duplicates, cursor loops, version drift, failed-page rollback and source tombstones are covered. Nineteen actual Windows small-fixture unit tests passed; the exact three reviewed file hashes and independent pure-code acceptance are in scanner-content-independent-review.json. Committed-source Task15/native tests/full CI are pending and must not inherit reservation results.

Real HTTP/OpenList, actual approved scale and fault measurements, original13 typed qualification, current-source result review, normal Review/Completion and actual-main acceptance remain outstanding. No input/resource/window approval is claimed.

## Historical reservation records (superseded status)

Task: POC-005
Issue: 132
Base: 11c32830c0d1bb8ccdcc04aa278876065bce1f33
Branch: chore/POC-005-metadata-scale-reservation
Work Branch: chore/POC-005-metadata-scale
Current status: reserved; validation PENDING; no experiment executed.

Own metadata-only reservation for the original13 measurements against bounded synthetic metadata and local OpenList. Stable Program issue remains null. Source/current CI/independent content and actual main acceptance are pending. GZ-010/GZ-021/GZ-022 prerequisites are completed on the accepted base. Production700TB/provider quota remain untested; local preparation is not POC acceptance.

POC-005 predecessor sourcee7a962f225bb0004fd49b513a633d9dbb82fcfc3 ran13 local commands: first12 passed, check-evidence failed because5 support explanations were missing; final2 commands were not run. Actual source-bound logs/results are in reservation-e7a962f-failed-validation/. Current forward repair supplies the5 required explanations; current exact-source checks/CI/independent acceptance remain pending. The predecessor is not accepted, and no experiment ran.

Actual predecessor validation: f80b04438ae0de0d6d08f3b75bfe332723ce0fc3 / tree0bdfadfba2d862386b24dd726dd6df5847ec373e passed all15 local commands; exact argv/exitCode=0/raw hashes are in reservation-f80b044-validation/results.json and index.json. That source was not pushed and has no full CI acceptance. Independent review found incomplete handoff identity/inventory/contract references; this forward Evidence-only repair supplies those references. New candidate source checks/CI/review remain pending.

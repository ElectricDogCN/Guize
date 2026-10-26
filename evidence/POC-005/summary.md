
## Canonical compressed-input component (new source qualification still pending)

CanonicalPair now consumes plain JSONL and strict single-member .jsonl.gz, independently for baseline and companion. The initial physical SHA/signature pass validates complete gzip EOF/CRC and rejects extra members or trailing bytes with bounded64KiB decoding. The two original physical hashes still bind the checkpoint; stored offsets and EOF use decoded bytes. Limits remain2GiB decoded bytes,2million records and64KiB per line for each stream. Normal pages retain forward readers and reserve two maximum lines before reading, avoiding a backwards seek/redecode per page. No disk spool or new runtime configuration is introduced. Reopening/retrying an older checkpoint can decode its prefix once; this is not a random-access compression index.

Actual Windows140 component tests and the related Linux29 tests passed with real owned wait0 and zero failures/errors/skips. Nine new cases cover mixed representations and exact catalogue export, physical companion re-encoding binding, decoded-offset restart, malformed/CRC/truncated/member/trailing refusal, decoded budgets, real SQLite page rollback and retry, changed input/invalid cursor/duplicate JSON,1800 large rows crossing the page-byte ceiling without a backwards seek, and actual FixtureMap failure cleanup. Windows JUnit reports52.228s and Linux6.6s. Source hashes before/after each run match. The first interactive run had two errors in the new tests' assumptions (tell internally calls a non-moving seek; one short decoded page need not exceed the whole compressed file size); the tests were corrected without changing production code, then the later complete suites passed. No independent file raw is claimed for the interactive-only first run.

EOF/read errors/explicit close release gzip readers; scanner close/constructor failure and FixtureMap construction finally also release them. A SQL transaction error keeps the checkpoint unchanged; its caller can close or retry at that saved cursor. It is not a claim that every SQL error immediately closes the pair. Reversible source, actual raw/JUnit/results, helpers and independent component review are in compressed-input-v1/index.json.

This component does not migrate the accepted8f/008 local10k execution to changed code. New fixed-source Task15/CI, complete independently approved100k/1m inputs/resources/windows and original13 runs, output/artifact budgets, formal result index/full POC, integration order3 and normal Review/Completion remain pending. Outputs are still plain; input support alone does not prove the larger artifact budget fits. No frozen checker, Schema, catalogue, policy, roles, claims or lease was modified. All4171 old untracked raw/DB originals remain retained.


## Accepted actual10k execution qualification; full POC remains pending

The unchanged tested runtime8f7c9a5 (nativeTask15/CI866752 accepted) completed a new independently approved attempt008 on the isolated v5 OpenList. All13 actual observations and4116 selected raw artifacts were independently accepted. The genuine4148-path evidence-only context71b7777 is a direct child of8f; the full unchanged frozen validate_execution call ran in its clean/no-alternates clone and returned0/errors[] with checker ee53ccf3. Its raw538 bytes hash f19bacaa2f1d83a0ed026686f9fedb1b843fc6564d85d0fee6f0880a433b7e02 and independent e7bdb4cf acceptance are retained losslessly in qualified-local-10k-attempt008-v1/index.json.

This result is separate from original007: its13 observations were accepted, but the actual complete qualification returned1 with5 UTC-representation errors. Its original +00:00 approvals, five-error raw/assessment,7dd5550 evidence context and all databases remain unchanged. New008 approved canonicalZ before execution and re-ran the actual workload; no past approval or validator was rewritten. Both actual evidence parents were ordinarily merged into dce6ec3 with ordered parents[7dd5550,71b7777], preserving the disjoint8296-path union, unchanged runtime code/Task metadata and old untracked originals.

Measured008 scanner enumeration is2729.1596044246903objects/s, incremental traversal0.04011685s and native process PeakWorkingSet31.25MiB for10000files/500directories. Adapter quota6000requests/min and the controlled three-change burst are not provider production limits/rates; source HTTP throughput and scanner throughput remain distinct. These numbers are only the recorded local configuration, not700TB or100k/1m scale evidence.

This archive accepts local10k execution qualification only. Profile terminal result/index acceptance, original100k/1m sweeps and compressed-input support, actual provider/production obligations, full Task/Ready/main integration and V1 completion remain pending. No new runtime/experiment permission follows. The local evidence merge/archive is not a new code-source acceptance; latest tested code identity remains8f. Keep all raw outputs, failed histories, bundles and local DBs. Next: complete the remaining scale/domain work and honest profile result before normal fixed-source gates, integration order3, Review/Completion and actual-main validation.

Task: POC-005
Issue: 132
Branch: chore/POC-005-metadata-scale
Base SHA: 746e23e582501fa08380c3f3301bdc1774902f7c
Preparation parent: 4b17b7e4e2d9f1e48fd5b61be1600f4141aeb160; accepted incoming main: 746e23e582501fa08380c3f3301bdc1774902f7c
Current status/agentRole: in_progress/implementer. Actual new source/tree is Git HEAD after commit, not a predicted SHA.

Own source code and all frozen POC contracts are unchanged; only accepted-main import plus Own current base/evidence. Roles/lease/claims/shared paths and order3 unchanged; no new fixture/service/template, experimental input/resource/window or qualification approval. All4161 old untracked entries remain excluded from staging and retained.
Accepted main own7/CI865752/independent proof and originalD component review are recoverable under accepted-completion-main-746e23e-sync/index.json. PriorD Windows131/native57 results retain their source identity; future exact source must execute Task15, same-head CI and full experiment prerequisites. Latest commands are commands.txt; actual exits are UNEXECUTED until the new candidate run. No history failure is relabeled.
Next implementer: freeze the actual merge source/tree and run Task15 on that source. Next independent reviewer: inspect actual source/main-import provenance, Own base and unchanged code/old raw preservation, checks and CI. Next integrator: accept actual source/CI and only then any independently approved new input/resources/window; no current execution grant. Revoke this unmerged candidate via ordinary reviewed forward work; never reset/delete raw, DB or refs.

Historical source-bound handoff and findings follow; their current/base wording belongs to their earlier source.

Task: POC-005
Issue: 132
Branch: chore/POC-005-metadata-scale
Base SHA: 2a77cbf9ad838b7b7abc7fbc5ed7aaa5f2f793d4
Preparation parent: dc506b85317cdfa419d9fa6491d87eaa76e88473; accepted incoming main: 2a77cbf9ad838b7b7abc7fbc5ed7aaa5f2f793d4
Current status/agentRole: in_progress/implementer. Actual new source/tree is Git HEAD after commit, not a predicted SHA.

Own source code and all frozen POC contracts are unchanged; only accepted-main import plus Own current base/evidence. Roles/lease/claims/shared paths and order3 unchanged; no new fixture/service/template, experimental input/resource/window or qualification approval. All4161 old untracked entries remain excluded from staging and retained.
Accepted main own7/CI860752/independent proof and originalD component review are recoverable under accepted-main-2a77cbf-sync/index.json. PriorD Windows131/native57 results retain their source identity; future exact source must execute Task15, same-head CI and full experiment prerequisites. Latest commands are commands.txt; actual exits are UNEXECUTED until the new candidate run. No history failure is relabeled.
Next implementer: freeze the actual merge source/tree and run Task15 on that source. Next independent reviewer: inspect actual source/main-import provenance, Own base and unchanged code/old raw preservation, checks and CI. Next integrator: accept actual source/CI and only then any independently approved new input/resources/window; no current execution grant. Revoke this unmerged candidate via ordinary reviewed forward work; never reset/delete raw, DB or refs.

Historical source-bound handoff and findings follow; their current/base wording belongs to their earlier source.

# POC-005 caller alignment

Status: PARTIAL

POC-005 caller alignment after actual failed source checks
Base: c0d550555dd51a29fd1c5ff1bc5e4713073c0b53
Branch: chore/POC-005-metadata-scale
Parent Source: 1869091239b51960d53b0840c4965e3f84eb10fd
Current Source: UNASSIGNED (uncommitted candidate)

Four actual callers/tests now match the omitted-empty-password wire shape and strictly reject extra keys. Working Windows131 passed; no new fixed-source or hosted acceptance yet. Parent186 Windows130 and history failures are retained, not recast as success. Frozen checker/schema/13measurements/thresholds and all attempt006 original bytes/method/approvals stay unchanged. No new source request or experiment/qualification approval. Exact inventory: changed-files.md; reversible originals: profiles/local-v1/v1/wire-consumer-alignment-v1/index.json.

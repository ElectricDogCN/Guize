# Guize V1 POC Program

`GZ-010` defines **POC-PROTOCOL-V1**. It freezes ten independent POC planning baselines; it does **not** execute any POC.

## Three-layer model

1. **Immutable Program baseline (original GZ-010; authorized GZ-021 route revision)**
   - `plans/POC-001.yaml` ～ `POC-010.yaml`
   - `resources.yaml`
   - `samples.yaml`
   - schemas/templates/policy
   - These files describe what must be tested. Downstream POC tasks do not write execution state back into them.

2. **Task-owned execution Evidence (POC-001～010 owned)**
   - each POC writes only under its existing `evidence/POC-XXX/**` path;
   - sample approval records bind sample ID, immutable ID, SHA-256, approver and UTC approval time;
   - the execution record contains the concrete Task Spec implementer, approved sample binding, captured environment, exact commands, raw-output references, measurements and required provenance;
   - the result record contains terminal decision and the concrete Task Spec reviewer.

3. **Shared task-progress result index (legacy schema 1)**
   - `specs/poc/results-index.yaml` is the only POC Program file shared with downstream POC tasks;
   - nonterminal rows contain no decision/reviewer/result reference;
   - terminal rows point to an existing task-owned result record;
   - a POC task may modify only its own row, proven by base-to-head validation.

This keeps Program configuration immutable and avoids granting ten independent tasks overlapping write access to GZ-010 planning files.

## Source of truth

`specs/coordination/program-plan.yaml` remains authoritative for POC↔Task↔Requirement↔Module↔Wave/Risk/dependency mappings and task path ownership. Concrete implementer/reviewer identities come from the persistent `specs/tasks/POC-XXX.md` Task Spec and, while active, must match `specs/coordination/active-work.yaml`.

## Files

- `program.yaml`: manifest for the canonical POC Program.
- `policy.yaml`: immutable-plan, safety, evidence, concurrency and review rules.
- `resources.yaml`: planning resource descriptors; credentials are never stored.
- `samples.yaml`: planning sample catalogue. Approval, immutable identity and checksum remain `pending/TBD` here and are captured in the executing task's Evidence.
- `results-index.yaml`: ten result slots; all start `not_started`.
- `plans/POC-001.yaml` … `POC-010.yaml`: immutable experiment requirements and exit criteria.
- `sample-approval.schema.yaml`: contract for task-owned sample approval Evidence.
- `execution-record.schema.yaml`: contract for task-owned execution Evidence.
- `result-record.schema.yaml`: contract for terminal result/review Evidence.
- `templates/**`: copyable skeletons for downstream POC Evidence.
- `check_program.py`: fail-closed schema/cross-file/Evidence validator.
- `test_program.py`: primary positive/negative regression suite.

## Downstream POC execution

For `POC-XXX`:

1. Coordinator creates the POC's own Issue/Task Spec/Reservation using canonical Program Plan paths and assigns concrete, distinct Implementer/Reviewer identities.
2. The POC does **not** modify `plans/POC-XXX.yaml`, `samples.yaml`, `resources.yaml`, schemas, templates or policy.
3. Before execution, the task creates versioned sample-approval records and an execution record under `evidence/POC-XXX/**`.
4. Each used sample must have an approved Evidence record, stable immutable ID and `sha256:<64 hex>` checksum. The approval record must match those exact values and contain a concrete approver and valid UTC approval instant.
5. Required environment/provenance fields must contain real non-placeholder values; AI identity/version/Prompt/input-version fields are textual.
6. Exact commands and raw outputs are recorded; every raw-output reference must resolve to an existing regular file inside that task Evidence path without path/symlink escape.
7. Measurement IDs must exactly match the selected immutable profile route. Original production measurements remain required; POC-001/002 additionally measure production heterogeneous compatibility. Boolean gates stay booleans. POC-003 correctness is a percentage in [0,100] and PASS requires 100; observational latency/quality values remain separately measured.
8. Media POC-002 records input SHA-256, output SHA-256 and exact encoder parameters; input SHA-256 must match an approved execution sample checksum.
9. AI POC-009 records model/version/Prompt/inference parameters/input version and access/budget gates.
10. Recovery POC-010 verifies actual Secret value round-trip and fail-closed behavior for unreadable/decryption-mismatched backups without committing plaintext.
11. A terminal result record is created under the same Evidence path and approved by the concrete reviewer from `specs/tasks/POC-XXX.md`, distinct from the concrete implementer/executor. While the task is active, those identities must also match Active Work.
12. Only then may the task update its shared `results-index.yaml` row to `pass`, `fail` or `inconclusive`.
13. The task must prove it changed only its own shared index row by running the row-ownership check against the integration base.

`running`, `blocked`, `cancelled` and `not_started` index rows must keep `resultRef`, `decision`, `reviewer` and `approvedAt` null. At most one high/critical POC may be running; POC-010 (critical) must run alone.

## Acceptance profile routing (GZ-021 revision 1)

The manifest uses schemaVersion 2 and the same acceptanceProfileBinding as authoritative NFR/requirements. All original production measurement definitions, samples and obligations remain required; POC-001/002 add a captured worker pool, environment and NFR-V1-COMP-003 compatibility/actual-Android measurements. GZ-020 verifies these production-profile results; local results are not reused. Revised POC-001..007 plans use schemaVersion 2 with localValidation; POC-008..010 retain schemaVersion 1 and their shared protocols.

Before execution, select local-v1 or production version 1. In the existing execution record's environmentCaptured, add acceptanceProfile with exact id, version: 1, bindingRevision: 1 and scope (LOCAL_FULL_V1 or PRODUCTION_RELEASE), plus acceptanceProfileConfigurationRef to an existing configuration under that task's Evidence. The configuration binds pocId, taskId, the same acceptanceProfile, sorted resourceIds and sorted measurementIds for the selected route. Result records bind the profile through executionRef. Templates and execution/result schemas stay unchanged; the checker adds semantic binding and rejects unknown/mismatched profiles or attempts to relabel local results as production.

Local POC-001/002 use the captured heterogeneous pool; POC-004 uses bounded OpenList with measured positive watermarks/reservations; POC-005 adds OpenList metadata coverage; POC-007 uses isolated TLS/access tests. POC-003 and POC-008..010 retain shared obligations. POC-006 local-v1 executes the generic OpenList/WebDAV and bounded injected-failure protocol explicitly authorized by its original planning manifest. The profile configuration and captured environment bind GENERIC_OPENLIST_SANDBOX; production binds BAIDU_PRODUCTION_SANDBOX. A scoped local result supplies POC-06-EVIDENCE to GZ-019 without changing the dependency DAG, and cannot establish Baidu production/compliance success.

Record actual physical host/device scope and media coverage. Windows plus WSL on one host, a synthetic no-audio clip, or injected provider failures cannot establish physical multi-host, Android-phone, general-media or real-provider performance. No plan/catalogue contains actual results. A profile declaration or validator PASS does not grant runtime or production acceptance. Local safety measurements retain boolean units. POC-004 binds exact integer-byte localCapacity (capacityBytes, safetyFloorBytes, pauseFreeBytes, resumeFreeBytes, maxReservedBytes), requiring 0 < floor < pause < resume <= capacity and a bounded positive reservation budget. PASS also requires a positive observed in-flight reservation. The environment must match this configuration; measured local_minimum_free_bytes minus local_maximum_reserved_bytes must preserve the floor for PASS.

## Qualified profile evidence and milestone prerequisites

The shared results-index.yaml remains schema 1 and tracks the original POC task's progress. Completion there alone does not satisfy a local or production acceptance contract. Each qualified contract is selected by POC identity, acceptance profile and version; profileEvidenceBinding in program.yaml fixes separate index paths and owners:

- Local: evidence/POC-XXX/profiles/local-v1/v1/index.yaml, owned by that original POC task before its completion.
- Production: evidence/GZ-020/poc/POC-XXX/production/v1/index.yaml, independently owned by GZ-020. Later production execution does not reopen a completed local POC, replace its records or edit the legacy POC index.

Each schema-2 profile index binds pocId, pocTaskId, ownerTask, the exact acceptanceProfile and a resultRef under that selected slot. Local result/execution/approval records retain their original schema 1 and POC owner. Production result/execution/sample-approval/compliance records explicitly use schema 2 definitions in program.schema.yaml, taskId GZ-020 and evidencePath evidence/GZ-020; concrete release-task implementer/reviewer roles are checked. Their experiment pocId still identifies the original protocol. No existing schema/template or completed evidence is rewritten.

The result and execution must remain under the selected slot, their profile identities must agree, and all resource/measurement/sample/compliance checks run on the exact selected protocol. All nested raw/command outputs, resource configuration/bookings, sample approvals, profile configuration and compliance review references must also resolve inside that exact slot. Record evidencePath continues to identify the owning task root; reference boundaries remain separate. Legacy task-progress validation keeps its original task-root boundary. Local POC-006 reviews bind a canonical JSON subjectVersion containing both openlist_version and provider_api_or_sdk_version, with sorted keys and no separator whitespace, and GENERIC_OPENLIST_SANDBOX. Production POC-006 retains the captured provider_api_or_sdk_version and BAIDU_PRODUCTION_SANDBOX. Changing either local version invalidates the earlier approval. AI reviews bind the canonical JSON tuple of model_identity, model_version, runtime, tool_versions, prompt_template_version, inference_parameters and input_sample_version; recovery reviews bind captured tool_versions (canonical JSON for a structured version map). Required review references must exist, match the task/type/version/scope, record an approved decision, independent reviewer and UTC time. Approval booleans alone cannot grant PASS.

```bash
# Consume one scoped connector experiment during development:
python specs/poc/check_program.py --profile local-v1 --require-results --poc POC-06
# Full milestone prerequisites cannot select a smaller POC subset:
python specs/poc/check_program.py --profile local-v1 --milestone GZ-018
python specs/poc/check_program.py --profile production --milestone GZ-020
```

Milestone selection requires all ten independently reviewed PASS records in its exact profile slots. A production slot cannot point into a local POC directory, use a local result or change its owner. These commands validate POC prerequisites only; they do not replace full functional/E2E/quality/recovery/supply-chain validation or authorize production release. Baseline/profile declaration checks without require-results do not grant result acceptance.

## Qualified resource authorization, numeric domains and Android evidence

Qualified execution captures executionWindow.startedAt/finishedAt as strictly ordered UTC instants. Schema-2 resourceConfiguration/resourceBooking records in program.schema.yaml bind the exact POC, owning task, resource ID and profile. PASS requires independent Task reviewer approval preceding execution and validFrom/validUntil covering that historical interval. Expiry is checked against the actual captured run, not the later review date or current clock. Configuration is nonempty and versioned; rejected, expired, mismatched or self-approved reservations cannot grant PASS. FAIL/inconclusive records retain typed identities and ordered historical validity timestamps but may capture rejected or expired authorization without satisfying PASS coverage; they never authorize work or a milestone. Other execution and review requirements still apply. Sample and privacy/license approvals precede execution; result review follows its completion. Original legacy records retain their schemas and task-progress purpose.

Every qualified execution captures testedSource:{commit,tree}, validated against the owned testedSource definition; its profile configuration must bind the identical object. Both IDs must name real Git commit/tree objects, and the tree must belong to the commit. The authoritative validation context is the repository's actual HEAD, resolved independently of the evidence. An ancestor tested commit remains usable only when changes through that context, tracked working-tree changes and nonignored untracked files are confined to the20 exact local/production slots derived from the10 canonical POC IDs. This allows sibling experiment records to coexist in full GZ-018/GZ-020 validation. Each execution's nested references still resolve exclusively inside its own selected slot. The two existing Task Specs for the current POC and GZ-020 additionally permit only a single frontmatter status transition from in_progress to completed, with all other header/body content identical. This limited phase authentication does not replace lifecycle approval. New Task Specs, changed implementation, plans, protocols, resources or other Task/Program metadata invalidate current qualification. Evidence-bearing successors can preserve a tested code revision without requiring their own future SHA; historical execution results do not grant changed code PASS.

Qualified executionWindow must have finished by the validator's independent UTC time. Result and resource/domain/profile approvals cannot claim a future completed approval; sample and compliance approvals must precede the actual execution. Resource validity endpoints may describe future reservations, but PASS still requires approved authorization covering the complete observed execution window. Failure records retain factual authorization failures without gaining milestone eligibility.

Qualified environmentCaptured.rawExecutionArtifacts provides an exact unique mapping of every rawOutputRefs entry to ref, artifactType, byteCount and sha256, using the owned rawExecutionArtifact definition. Types are command_output, measurement_output, scope_observation or produced_media; every command output identifies command_output. Byte counts and checksums are checked against actual files. Raw artifacts must be physically distinct from profile/index/result/execution records, resource configurations/bookings, sample/compliance approvals and domain reviews/definitions, including linked-file aliases. PASS requires nonempty dedicated raw output. Referenced qualified files, including resolved symbolic-link targets, that are ignored and untracked are rejected; intentionally archived files may be explicitly tracked. Legacy task-progress records retain their original schema.

Artifact sizes come from the actual files and SHA-256 is computed in bounded 1 MiB reads. The digest is reused only within one execution-validation invocation for raw metadata, provenance and worker/Android output checks; there is no persistent acceptance cache or artifact-size gate. command_output, measurement_output and scope_observation artifacts must decode as UTF-8 and pass credential scanning, including structured/dotted assignments and authorization headers. Unreadable or undecodable text is rejected. produced_media remains binary and is hashed without textual credential decoding.

Qualified POC-001 PASS, for both the local VM and production physical device, requires the encode scope rawOutputRef to name a node-bound produced_media artifact. Its nonempty actual file digest must equal scope.outputSha256. Command and thermal/background evidence retain their separate raw artifacts. Synthetic media fixtures test the binding and never prove real VM/device encoding.

Qualified POC-002 PASS requires producedMediaArtifactRef to designate a nonempty produced_media artifact whose actual byte digest equals provenance.output_sha256. worker_node_inventory contains at least two distinct identified nodes and includes tested Windows and Linux workers, with nodeId, platform, physicalHostId, encoderBuild and one admitted compatibilityGroupId. physical_host_scope lists the exact physicalHostIds and discloses physicalMultiHostValidated; same-host Windows/WSL nodes cannot claim multiple physical hosts. encoder_capability_matrix binds each inventory node/build/group to supported AV1 capability. workerEncodeExecutions binds each tested node/build/group, approved input hash, positive actual UTC interval inside executionWindow, per-node command_output rawOutputRef and produced_media outputArtifactRef/outputSha256. These artifacts carry the same nodeId. Every inventory node must execute, and distinct-node intervals must overlap to establish parallel work. Throughput and sustained duration must be positive for PASS; zero remains valid for factual failure/inconclusive records. Synthetic regression bytes and timestamps validate record structure only and are never actual encoding evidence.

POC-005 PASS requires positive file/directory populations, enumeration rate, observed change frequency and incremental scan work. Other numeric metrics retain their existing unit rules, and zero measurements remain available for failed or inconclusive runs. API performance retains GZ-011's sample/threshold/method responsibility and adds runtime verification by local GZ-018 and production GZ-020; the existing requirements guard rejects removal of either runtime verifier.

Counts are nonnegative integers; sizes, rates, latency, elapsed time and cost cannot be negative. Average byte sizes can be fractional. Percentages are bounded by 0 and100. Normalized accuracy/ranking ratios are at most1; insertion/error ratios are not blindly capped at1. Temperature is not blanket-restricted to nonnegative Celsius. Model/rubric-specific VMAF, score, ordinal or unknown-unit scales require numericDomainReviewRefs in the selected profile configuration. Each schema-2 measurementDomainReview binds its metric, unit, actual captured model/tool environment, independent reviewer, prior approval and an existing definitionRef in that slot. Bounded scales supply finite ordered limits; legitimately unbounded model output explicitly declares finite mode with null limits. These are measurement domains, not invented quality acceptance thresholds. For example, [Netflix's model definitions](https://github.com/Netflix/vmaf/blob/master/resource/doc/models_v1.md) describe model-dependent VMAF ranges; the validator does not freeze one universal VMAF maximum.

Per the user decision, local POC-001 uses actual Android VM guest encoding first: vm_validation_scope must be VALIDATED_ON_VM, bind guest/node/physical-host IDs, hypervisor, guestOs:android and pinned encoder build to worker_node_inventory, and retain approved input/output hashes plus execution-bound raw evidence. It records isVirtualMachine:true, physicalMultiHostValidated:false and android_validation_scope:ANDROID_DEVICE_NOT_TESTED. Existing resource-limit, restart and network-boundary gates remain. Local PASS establishes only the tested VM scope; it grants no real-phone thermal/background or physical multi-host claim. Production POC-001 still requires android_thermal_background_profiled for PASS. android_validation_scope is a structured VALIDATED_ON_DEVICE record with node/device/physical-host IDs, pinned encoder build, isEmulator:false, approved input/output hashes and rawOutputRef. It must match an Android row in worker_node_inventory. android_thermal_background_observation binds that same device, temperature/power, a positive declared test duration, a completed background-survival interval and raw outputs. Missing, untested or emulator-only phone evidence cannot complete production or assert real phone support; the explicitly VM-scoped local milestone retains these limitations. No phone result is supplied by the fixtures or by this specification revision.

## Security

No password, token, private key, credential value, production secret or unapproved sensitive payload belongs in Git. Compound key names such as `productionApiKeyValue` and `authTokenValue`, and separated names such as `auth.token` or `api.key`, are rejected after normalizing nonalphanumeric separators. `credentialsStored*` metadata is safe only when the value is exactly `false`. Secret recovery Evidence must use safe comparison artifacts rather than plaintext values.

## Validation

Install the repository governance dependencies, then validate the immutable baseline:

```bash
python -m pip install -r requirements-governance.txt
python specs/poc/check_program.py
python specs/poc/test_program.py
```

A downstream POC task must additionally prove shared-row ownership, for example:

```bash
python specs/poc/check_program.py --task POC-003 --base-ref origin/main
```

The validation commands do not run hardware, cloud, media, AI, storage or recovery experiments.

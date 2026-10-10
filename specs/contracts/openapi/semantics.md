# OPENAPI-V1 / ERROR-CATALOG-V1 semantics

Contract version: 1.0.0, effective upon reviewed implementation merge.
Authority: frozen REQ-V1/NFR-V1; docs/06, docs/12, docs/21 and module designs.
OpenAPI entry: `contracts/openapi/common/openapi.yaml`; pinned OAS 3.1.1, API 1.0.0.
This freezes the assigned V1 control interface after acceptance. It does not assert
that a server, connector, hardware POC, consumer contract or production test has run.

## 身份和权限 / Identity and authorization

Same-origin `/api/v1` uses a Secure, HttpOnly, SameSite session cookie or short-lived
scoped user/machine bearer identity. TLS is required outside isolated local tests.
Cookie-authenticated writes require the session CSRF token; bearer machine requests
must have an allowed audience/capability and cannot act as arbitrary users.
Password login follows Argon2id, lockout, rate-limit, short-session and notification
policies. It never returns a password/hash/provider token. Offline recovery keys
are never accepted at ordinary login. WebAuthn challenges are one-time, expiring,
and verify RP/origin/signature and purpose. Initial passkey enrollment may use a
fresh password/TOTP reauthentication allowed by the configured identity policy;
it must not require an already-enrolled passkey or bypass recent authentication.

Platform capability is intersected with ownership, resource ACL, source policy,
publication/safety state and operation risk. Deny before metadata hydration or
candidate retrieval, then recheck before returning any title, snippet, aggregate,
thumbnail, result, grant or content. Unknown or undiscoverable objects use the
same redacted 404; discoverable denied actions may use 403. Errors cannot include
denied IDs, source paths, credential values or raw provider responses.
The source object keeps independent ACL, labels, path and retention after merge.
Revocation stops synchronization and invalidates access/grants; it never deletes
logical assets or verified copies as a side effect.

普通读取不返回来源凭据引用；保护引用的读写单独要求
`source.credential.manage` 和近期再次认证。SourceDraft 只接受 OpenBao 引用，
引用必须属于调用者或有显式代理授权。配置与规则正文必须按精确版本读取，
再次确认涉及引用的配置读取；服务端按其绑定 Schema 脱敏并拒绝内联 Secrets。
CLI/UI 不得从配置文档中补回原始密钥。

## 高风险绑定 / Protected action binding

`X-Step-Up-Proof` binds current subject, exact operation ID, target resource or
collection ID, protected-intent digest, expiry and intended action. The configured
reauthentication policy is applied server-side, not inferred from a client assertion.
Collection creates bind `col_sources`, `col_roles`, `col_users` or the applicable
server-issued collection resource and the complete create payload.

`X-Approval-Id` is required only when `x-authorization.approval=true`. Approval is
independent of step-up and binds exact action/resource/immutable revision/payload
hash and expiry, with a separated approver under policy. If a request also includes
`approvalId`, it must equal the header. Approval decision itself requires step-up
and separation of duties, never recursive prior approval of the same decision.
Proposals, simulations and AI configuration suggestions never self-publish.
Policy/config publication and rollback reference the reviewed immutable revision;
validation/simulation results cannot stand in for approval or health observation.

An approval proposal contains action, resourceId, revision and requestIntent with
method, path, query and the complete business body. The client payloadHash is an
assertion, never proof. Resolve the operation from the actual route and method,
derive the authorized primary resource or collection and its immutable revision
on the server, validate the exact operation body, and verify every secondary
asset/source/version/policy target before accepting a proposal. A collection ID
supplied by a client cannot establish collection authority.

The protected snapshot is an object with purpose="approval-intent", action,
resourceId, revision and request={method,path,query,body}. Uppercase the method;
accept only a relative /api/v1/ path without authority, query or fragment; decode
path escapes once as UTF-8, reject dot/empty segments, encoded separators and
invalid escapes, then use canonical uppercase percent escapes. Decode query
names and values as UTF-8 with plus as space, group values into arrays and retain
repeated-value order. RFC 8785 orders object keys and encodes the UTF-8 JSON;
SHA-256 over those bytes is payloadHash. Do not trim, case-fold or normalize
Unicode business strings. Reject non-finite numbers, integers outside the safe
interoperable range and invalid Unicode rather than hashing an approximation.

Only when the server-resolved operation explicitly requires approval, exclude
the top-level body approvalId and its matching X-Approval-Id transport carrier
from the protected digest. Nested approvalId fields remain business data.
Compute a proposal before its approval ID exists; minting that ID does not
change the protected digest. Header and body carriers must agree where the wire
contract permits both. Undeclared approval carriers are rejected.

Persist the verified immutable snapshot bound to the requester. Authorized
approvers must see the concrete action, affected resources, revisions and
business changes; a hash and free-text reason alone are insufficient. Reject
unresolved targets or inline secrets before persistence. On execution, load that
snapshot, check subject binding, separation of duties, expiry, current ACL and
all input versions, then recompute the digest from the actual business request.
An accepted client hash never substitutes for these checks. The reference helper
validates deterministic representation; it does not provide runtime authorization.

## 幂等和并发 / Idempotency and concurrency

Every POST/PUT/PATCH/DELETE requires an opaque `Idempotency-Key` (16–128 characters).
The transactional unique claim is scoped to server-derived caller (or the pre-auth
client session), operation ID and key. Its fingerprint includes canonical method,
normalized path including resource IDs, query and request body. Same key with a
different fingerprint, even another asset path, returns 409 conflict. The reference
fingerprint uses purpose="idempotency-fingerprint" and the same normalized request.
For declared approval transport, retain the agreed approval ID once outside the
business body; equivalent header/body carriers have the same fingerprint where
the operation permits both, but changing the ID changes the fingerprint. All
other business fields remain covered. Session, CSRF and step-up secrets must not
be persisted in this representation. In-flight
duplicates return conflict/backoff, never start an additional side effect.
Persist accepted task ID before side effects. Workflow retries and restarts use
the durable task/input/configuration deduplication identity, not an in-memory lock.

Replay retention is 24 hours for durable results. Every replay rechecks current
authentication, resource/source ACL, step-up and approval validity. A cached result
never grants revoked access. Session, CSRF, step-up proof and playback grants are
also bounded by their original expiry: an expired ephemeral result is not replayed
or silently renewed; the caller reauthenticates and uses a fresh key. New grants
perform current publication/ACL/budget checks. Read-only POST search still requires
a key and binds its caller/query/current ACL version; stale result replays are denied.

Expected revisions are atomically compared before mutation. Merge checks write/read
authority for BOTH assets and linked source policies, locks both aggregates and
compares BOTH revisions. The client hash is an expected digest only: the server
verifies full hashes and current input versions itself, rejects stale/unverified
or policy-conflicting merges and preserves all source history. Split uses the same
ownership and association checks. Path asset ID and body version must refer to the
same authorized asset; supplied IDs never select another asset implicitly.

## Passkey wire options

Registration returns PublicKeyCredentialCreationOptions with rp, an opaque user
handle, challenge and a nonempty list of supported public-key algorithms.
Authentication returns PublicKeyCredentialRequestOptions with challenge and rpId;
discoverable pre-login options do not reveal whether an account has credentials.
Use the WebAuthn JSON parsing APIs before browser create/get. Credential IDs,
challenges, user handles, clientDataJSON, authenticatorData, signatures and
attestationObject use canonical unpadded Base64url; user handles are at most 64
decoded bytes. The server still verifies one-time challenge purpose and expiry,
RP ID, origin, signature/attestation policy and user presence/verification.
Synthetic contract fixtures establish no cryptographic or browser success.

## 长任务和播放 / Asynchronous execution and playback

202 means accepted, never completed. `data.taskId/statusUrl` identify the durable
task; `status` is its observed state, including existing tasks under pause/resume/
cancel/retry. A command does not create an unrelated fake task or force a terminal
success. Pause honors safe boundaries, cancel stops subsequent side effects and
retry creates a tracked attempt bound to the original input/configuration versions.
P0–P8 priority remains constrained by caller capabilities, budgets and storage floor.
Dependency uncertainty remains a waiting/error state, never inferred success.

Playback returns 201 only for a ready, safe rendition. When authenticated callers
allow temporary preparation and current capability/budget policy permits it, return
202/taskId, without a media grant, and obtain a new plan after readiness. Otherwise
return MEDIA_UNSUPPORTED with a redacted repair suggestion. Anonymous plans require
explicit safe publication, current MIME/scan policy and a ready rendition; schema
and server deny temporary transcoding, restore, AI and commercial work.
Grants are short-lived and revocable, bound to subject/version/rendition/action,
authorization scope version, range policy and nonce. Only the gateway-relative
media path is returned. Gateway/ATS validate grant and current revocation BEFORE
cache access. Cache identity separates authorization scope from content/version/
rendition/range/content negotiation; no user token or origin credentials in keys.
Range/If-Range/ETag/206 media protocol is implemented and tested by the edge/player
vertical tasks; the control API does not pretend to serve binary media as JSON.

SSE returns `X-Trace-Id` and bounded TaskEvent JSON in each data frame. Event IDs
are monotonic cursors scoped to task/caller; Last-Event-ID resumes retained events.
Revoked ACL terminates delivery. Invalid/expired cursor requires status refresh,
never replay of another caller's events. No media bytes or unlimited logs in SSE.
Its data schema and cursor semantics are part of compatibility, not just the
`text/event-stream` string schema. WebSocket delivery and domain-event envelopes
are frozen separately by GZ-006/GZ-008, then tested as real consumers by GZ-012+.

## AI、存储与内容读取 / AI, storage and persisted content

Before every external provider send, require caller+asset ACL, data policy and hard
budget/quota. Missing any control denies sending. Track input version/hash, approved
pipeline/model/prompt/parameters/language. AI results inherit ACL; uncertainty is
visible and generated thumbnails have generated=true. Human corrections create
new revisions; publication does not expand ACL. The content endpoint returns bounded
text/timeline pages or authorized gateway references, never full Base64 media.

Full cache, ATS, formal Replica and Retention remain separate. Cache eviction cannot
change Asset metadata, formal copies or holds. Promotion requires space reservation,
full hash, scan, copy and read-back verification. Only verified copies become VERIFIED.
The hard 500GB floor is not lowered by requests or AI. Deleting the last recoverable
copy is denied; backup existence is not restore evidence. Configuration/deployment
uses exact approved revisions, signed locked digests and health observation; all
real restore, hardware and production checks remain independent acceptance tasks.

## Compatibility

Requests reject undeclared input fields, including client ACL scopes, provider
credentials and backend search DSL. Responses allow optional future fields; clients
ignore unknown fields and tolerate unknown enum values without granting capabilities.
Removed/renamed fields, changed meanings/defaults, tightened inputs, loosened required
response guarantees, status/error/security/base changes and incompatible SSE changes
require major-version/compatibility review. The checker conservatively rejects
uncertain changes. New optional request fields and optional response fields are
accepted when existing guarantees remain. A first baseline is allowed only with
explicit `--initial-baseline` against an actual Git base lacking OpenAPI; never
compare a changed API against its own HEAD as a compatibility substitute.

Compatibility also freezes the full values of multi-resource invariants,
resource binding, no-expensive-work and playback-readiness extensions. Removing
or weakening these guarantees requires compatibility review. Reference siblings
are limited to title, summary, description, $comment and x-i18n annotations;
assertion siblings are rejected instead of overriding referenced constraints.

GZ-012 must run the official parser, this validator, meaningful negative tests and
actual consumer contracts in language CI. Governance CI currently validates its own
scope/schema/evidence; it does not already execute these new contract checks.

## Errors

`common/errors.yaml` is the single stable error catalog: unique English code, HTTP
status, bilingual description/action, retryability, alarm level and documentation.
Accept-Language selects zh-CN/en-US message; clients branch on code only. X-Trace-Id
matches body traceId on success, error and streaming responses. Backoff does not
override budgets or access. Error examples are illustrative contract fixtures,
not actual server execution. Runtime error/security tests are required downstream.

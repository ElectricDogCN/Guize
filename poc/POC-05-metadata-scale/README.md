# POC-05 bounded metadata scanner

This isolated POC does not modify Guize assets or its production database. No scale, provider quota or production acceptance follows from unit tests.

## Local interface (version 1)

The immutable UTF-8 JSONL fixture contains one object per line, directories before children. Records have objectId, parentId, name, path, isDirectory, sizeBytes and versionId. Source identity is the pair sourceId/objectId; path is a locator. Root depth is zero. Declared file sizes have no corresponding media payload.

A page contains sourceId, snapshotVersion, fixtureSha256, cursor, nextCursor and records. Cursor is the decimal byte offset in this exact fixture. A maximum line size and page size bound each read. The source verifies the approved file SHA before opening and rejects changed files while open. Every page is bound to that digest and version.

SQLite holds one scan pass bound to this source, fixture and version. It atomically applies an entire page and saves the next cursor. A restart uses that checkpoint; duplicates within a pass, reused cursors, identity/version drift, invalid hierarchy and oversized pages fail without advancing it. The fixture must include exactly one root; children reference an already accepted directory. Completion is marked only after the last page validates. This is a POC index, not the platform authority.

An incremental batch binds sourceId and fixtureSha256 and contains events. Incremental events have sequence, operation (create/update/delete), fromVersion and toVersion; create/update also carry record, delete carries objectId. Events require a completed scan, consecutive sequence and versions. Identical replay is accepted; different bytes at the same sequence are rejected. All events in a call commit with the checkpoint or roll back together. Renaming a file preserves objectId. Moving or deleting a nonempty directory is rejected until a subtree-safe provider adapter exists. Delete creates a POC source tombstone; it never deletes a logical asset.

Retry is limited by attempts, maximum individual delay and an overall monotonic deadline. Only explicitly classified transient failures are retried. A future HTTP adapter must enforce its own per-request transport timeout; this wrapper rejects a response arriving after its deadline but cannot interrupt a blocking caller. Observations record attempts and actual requested delays; injected errors are not provider quota measurements.

The generator's fileCount counts files only; directoryCount includes root. maximumDepth is the achieved directory depth. Generated fixture counts are preparation metadata; reported counts, sizes, depths and name distributions must be derived from the actual scanner index, with clocks and memory observations retained separately.

## Local OpenList observation interface (version 1)

The read-only WebDAV adapter supports PROPFIND Depth1, HEAD and GET against an explicit HTTP loopback /dav/ prefix only. Proxy use and redirects are disabled. Successful response bodies stay within the explicit byte ceiling; detecting an oversized stream may read and retain one additional probe byte. Each request has a socket-operation timeout; the experiment controller must separately enforce its overall deadline, including slow-drip peers. Credentials are passed in memory from an external private configuration and never appear in observation records. Retained response headers are an explicit metadata allowlist.

Observations contain method, relative locator, UTC and monotonic perf_counter_ns boundaries (including actual implementation/resolution), status, selected headers, raw body bytes and their SHA. Error responses are retained too; transport, redirect and oversized-body failures are explicit. Range and validator values are observations, not implicit success assertions.

A successful DAV directory response must be a bounded DAV multistatus with a successful self collection and immediate child entries confined to that directory. Duplicate hrefs, out-of-prefix paths, dot segments, encoded slashes, required-property or permission errors and XML declarations of entities/DTDs are rejected. Directory results contain locators, optional sizes/validators, explicit optional-property404 facts and stableObjectId=null: ordinary DAV href/ETag is not a stable provider ID, snapshot token or change journal. Optional DAV:resource-id and DAV:sync-token are explicitly requested and reported as raw provider metadata, including404 or omitted properties. Their stability and synchronization semantics remain unvalidated; this adapter does not test all provider capabilities or implement a change journal/pagination. These records cannot be supplied as synthetic Scanner identities. PROPFIND Depth1 is directory listing, not source pagination.

Unit HTTP servers exercise actual request/response parsing and failures, but do not count as real OpenList provider measurements. Actual OpenList version, permissions, input bytes, provider behavior and experiment window must still be independently fixed and observed. Protocol references: https://www.rfc-editor.org/rfc/rfc4918.html (sections9.1 and13), https://www.rfc-editor.org/rfc/rfc5842.html (section3.1), https://www.rfc-editor.org/rfc/rfc6578.html (section4).

## Canonical metadata record bridge (version 1)

The protocol baseline uses exactly objectId/kind/versionId/depth/fileSizeBytes. Its companion filename stream adds name/path/modifiedAt. The new paired reader verifies both immutable SHA values, equal ordering and every shared field, and binds both digests into its checkpoint version. It does not change the frozen schemas. Paths in these streams are relative; their component count equals depth. A virtual scan anchor is outside the enumerated population and is never exported as a directory object. DirectoryCount excludes that anchor. maximumDepth is achieved, and files are placed no deeper than that achieved directory depth.

The bridge retains full filename timestamps alongside the persisted index in the same transaction as each page or incremental batch. An internal savepoint lets the existing scanner and bridge metadata commit or roll back together. Frozen create/update/delete records retain eventId/sequence/beforeVersion/afterVersion and are checked against actual current object versions; full metadata for create/update is separately bound. Identical replay is idempotent and conflicting event aliases are rejected. Export orders by depth then stable ID so opaque child IDs cannot precede their parents; record order is not identity. It derives complete basic/profiled/version catalogues from the actual accepted index, excluding tombstones and the virtual anchor; it does not copy generator statistics.

This supplies canonical records for the eventual native phase/resource/provider observations. It does not claim actual OpenList pagination, quota, a complete benchmark or thirteen-measurement qualification. Earlier internal-format fixture preparation remains unapproved and is not substituted for the canonical baseline.

## Pinned OpenList listing interface (version 1)

The listing adapter targets OpenList v4.2.6 POST /api/fs/list on an explicit HTTP 127.0.0.1 origin and an explicit reader-relative fixture scope. Requests always use refresh=false, an empty folder password and bounded positive page/per_page; no other endpoint, proxy or redirect is allowed. A reader token is supplied only in memory by the external controller. This adapter does not log in, mutate files or persist tokens. Actual HTTP status and JSON application code are separate; HTTP200 with code401 is an authentication failure, not a successful listing. The per-request socket timeout does not replace the experiment controller's total wall deadline.

Observations retain the exact safe request body, actual response status/selected headers/body hash, UTC and monotonic boundaries. Raw response bodies containing the supplied token or nonempty signing/thumbnail capability fields are not retained. Bodies that cannot be completely and unambiguously decoded for that inspection are also omitted. Actual hash/length and an explicit omission reason remain, alongside any original transport failure; omitted bodies cannot become accepted pages. Authentication request bodies/tokens are never observation artifacts. This controlled-fixture adapter requires unsigned metadata, rather than silently editing raw provider bytes.

Pagination checks exact page cardinality, a stable total within each directory, distinct immediate child names and bounded types/sizes/timestamps. A new isolated SQLite listing index stores the traversal frontier and observed locators, so neither a complete directory nor the whole hierarchy must be held in RAM. Root is a traversal anchor outside the population. Page callbacks expose a driver traversal cursor plus actual provider page parameters; the cursor is not a provider snapshot or change-journal token. Duplicate paths, inconsistent totals, excessive depth/population or any failed page terminate the run. Partial indexes and raw failed observations remain diagnostic, never a completed listing.

The pinned response has no stable object/version ID. Observed locators and modified/size fields are retained independently, with stableObjectId=null. A later approved controlled-fixture map must bind source observations to the frozen opaque IDs and versions; path does not become logical asset identity. Repeated complete baseline comparisons remain necessary because numeric pagination is not an atomic snapshot. No unit HTTP server result claims real OpenList or original13 qualification.

Primary protocol sources: [routing](https://github.com/OpenListTeam/OpenList/blob/v4.2.6/server/router.go), [list request/response and pagination](https://github.com/OpenListTeam/OpenList/blob/v4.2.6/server/handles/fsread.go), [page parameters](https://github.com/OpenListTeam/OpenList/blob/v4.2.6/internal/model/req.go), [authentication](https://github.com/OpenListTeam/OpenList/blob/v4.2.6/server/middlewares/auth.go).

## Development verification

Run python -B -m unittest discover -s poc/POC-05-metadata-scale -p 'test_*.py' -v from the repository root. Tests use disposable small fixtures; they do not run a POC scale experiment. Core runtime code uses the Python standard library. Canonical schema tests use the repository governance dependencies PyYAML and jsonschema.

## Remaining work

Real local OpenList HTTP/WebDAV adapter and actual identity/version/Range/ETag observations; bounded fault and rate-limit experiments; independently approved immutable 10k/100k/1m file populations and execution windows; original thirteen typed measurements and qualification. Missing stable provider IDs must be reported, not replaced with path-derived asset IDs. Production 700TB and Baidu remain untested.

Rollback removes only a newly created disposable POC index or test fixture after its evidence is preserved. Existing databases are never automatically migrated or overwritten.

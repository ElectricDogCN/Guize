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

## Development verification

Run python -B -m unittest discover -s poc/POC-05-metadata-scale -p 'test_*.py' -v from the repository root. Tests use disposable small fixtures; they do not run a POC scale experiment. No third-party package is required.

## Remaining work

Real local OpenList HTTP/WebDAV adapter and actual identity/version/Range/ETag observations; bounded fault and rate-limit experiments; independently approved immutable 10k/100k/1m file populations and execution windows; original thirteen typed measurements and qualification. Missing stable provider IDs must be reported, not replaced with path-derived asset IDs. Production 700TB and Baidu remain untested.

Rollback removes only a newly created disposable POC index or test fixture after its evidence is preserved. Existing databases are never automatically migrated or overwritten.

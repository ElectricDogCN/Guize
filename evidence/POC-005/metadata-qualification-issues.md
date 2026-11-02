# Actual metadata qualification failures and repair boundary

The source-ca1da41 Windows attempt004 completed its independently approved
10000-file/500-directory observation chain. The actual controller exited0 at
2026-10-22T23:27:59.157560Z; execution success did not grant qualification.
Independent result review at23:37:38Z accepted the bounded execution facts and
retained bytes, while rejecting qualification.

The first targeted frozen check passed its approval window through a helper
that accepts only `Z`, producing `(None,None)` from the actual `+00:00` strings.
That diagnostic harness needs a forward correction. Independently decoding the
real window still rejected the original phase records, because the frozen UTC
reader also rejects their `+00:00` spelling. Actual phase duration differences
were+250ns,-300ns,-650ns, all within the unchanged1us requirement. New producers
serialize the same UTC instants using `Z`; old records are not rewritten.

The actual raw index4112 contains the filename stream, quota and mutation
payloads, but omits the approved expected-change stream and baseline probe
payload required by frozen metadata qualification. The forward producer now
retains those dependencies from the hash-bound approved resource wrapper, with
actual byte hashes and required artifact types. It rejects changed input bytes.

The actual unsatisfiable GET has status416, `Content-Range: bytes */4096`, a
retained ETag and33 response bytes. Its body SHA256 is
`b5d780567c43a2b5d8473d84a136e7dc62ee9c494108d282cbff4801d199cf32`.
The frozen metadata checker requires an empty body for this supported Range
case. Changing the reported disposition to ignored/unsupported would contradict
the actual206/416 responses; discarding the diagnostic bytes would falsify the
evidence.

[RFC9110 section15.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5)
recommends error explanation content for GET4xx responses.
[Section15.5.17](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.17)
defines416 and recommends the unsatisfied Content-Range header; it does not
require an empty response body. This supports a narrowly scoped contract defect
report, rather than a claim that OpenList failed Range support.

POC-005's reservation excludes the frozen schema, protocol and checker. A
separate correctly registered contract/governance change must decide how to
accept bounded non-media diagnostic bodies while retaining exact status,
Content-Range, hash, length, source/version/window and negative tamper tests.
No such change or qualification approval is supplied by this document. The
existing POC policies, thresholds, other leases and shared order2-before3 remain
unchanged. All4139 original files are byte-verified in the retained archive;
10SQLite files and the three changed leaves remain at their original locations.

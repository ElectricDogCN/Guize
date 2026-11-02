# Preserve actual GET response bytes as binary raw artifacts

The exact 8d1d972 source was locally accepted at2026-10-22T22:45:24Z after
actual Task commands and124 Windows tests. It is not published or CI accepted.
Its original Windows Markdown long-path failure and successful unchanged-checker
short-path recovery are preserved, including actual removal of the alias.

The independent reviewer actually reproduced one remaining Own classification
defect with the fixed4096-byte probe: Artifacts.observation saves its binary
GET response as command_output, and the unchanged frozen validate_qualified_raw
correctly rejects invalid UTF-8 text. Changing only that body's artifact type
to produced_media makes the same frozen function accept those retained bytes.
This is a producer classification repair, not permission to relax the checker.

Classify the raw response body of an actual GET as produced_media. Keep request
bodies, listing JSON and HTTP observation metadata as command_output. Preserve
every safe byte, length, hash, status and header; secret filtering and omitted
body handling remain unchanged. Existing probe-response files are still kept.

Add a real unit HTTP GET returning a non-UTF8 binary body and assert the body
artifact type, byte-exact content/hash and unchanged metadata. Capture the
current producer failure before repair, then the successful regression after
repair. Obtain independent content review and exact new-source checks before
publishing. Do not reuse 8d's local results as acceptance of the new source.

No new provider request, source experiment, frozen schema/checker change,
original13 qualification or integration is authorized by this design.

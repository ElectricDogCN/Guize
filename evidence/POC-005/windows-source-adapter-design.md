# Controlled Windows source adapter — implementation design

Continue the fc04cf6 Windows feasibility handoff within the existing POC-005
scope. Preserve the Linux public entry points and their unsupported-platform
tests. Add explicit Windows reservation and source-session entry points; the
CLI chooses the backend for the actual host, never fabricates Linux identity.

Windows controlled leaf changes use real native handles, deny reparse/alias
paths and multiple hard links, hold parent directories against rename/delete,
verify actual file ID, bytes and source metadata before mutation, and perform
bounded write/delete through that same handle. Provider confirmation remains
mandatory before emitting an accepted change. Any mutation followed by failed
confirmation is retained as a dirty failed observation, without automatic
restoration or an accepted change event. The approved three fixture leaves are
the only intended provider mutations; no real provider experiment runs here.

Windows reader credentials require the actual owner SID and a non-null DACL
allowing only that owner, SYSTEM and Administrators. Read bounded bytes through
a no-reparse handle. Do not rely on chmod or Linux uid/mode on Windows. Native
tests must demonstrate actual private ACL acceptance, another-principal
rejection, hard-link/reparse rejection, update/create/delete observations and
failure-state retention. Never log credential bytes.

Reservation uses the actual final suspended image and immutable independent
approval request, Windows native identity/counter collectors and the same
frozen timing/window/qualification schemas. No source request may precede
independent input/resource/PID/window approval. Unit HTTP fixtures remain
explicitly unit-only; they cannot establish OpenList behavior, full scale,
original13 qualification, or V1 completion.

The current source closure, exact byte hashes, actual raw test results and
independent review must be recorded before publishing a new source candidate.

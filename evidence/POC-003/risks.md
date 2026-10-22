Task: POC-003
Issue: 131
Branch: chore/POC-003-ats-range
Base: 11c32830c0d1bb8ccdcc04aa278876065bce1f33
Current phase: in_progress / implementer
Current committed implementation validation: PENDING.

Actual partial/discard/cache native markers and buffered-byte observations remain unresolved. Never normalize observed MISS/HIT/502/timeout to expected PARTIAL/503/PASS. Client first body byte, chunk peaks, RSS and ATS buffered-byte bounds are distinct. Prototype crashes and prior failed sources remain historical evidence.

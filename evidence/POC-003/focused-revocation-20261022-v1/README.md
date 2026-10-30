# Actual focused warm-cache revocation result

Tested source: `18163e180e554773ef82e1eea7ffcafa634b027a`, tree `422c95a29fb8fe7558091826c1d1464a6d08398f`.

The distinct independent reviewer approved the exact source, proposal, immutable input pair, bounded resources and window before execution at 2026-10-22T14:25:41Z. The actual run completed at14:28:27.484987Z with exit0, one real scenario and no skipped scenario. Original source implementation validation is archived separately under `../source-18163e1-validation/`.

Warm requests returned206 and the correct8bytes with actual native HIT_FRESH and no origin read. Revoking the same still-unexpired grant then returned403/zero media bytes before contacting ATS. Both native cache lookup/export journals remained byte-identical throughout denial. A later separately identified privileged control returned the same cached8bytes with HIT_FRESH and no origin read. Owned controller/ATS stopped and all three ports were released within the approved window.

`archive-index.json` lists51 actual raw files/158777bytes with original paths and hashes. `independent-result-review.json` records the distinct reviewer's actual2026-10-22T14:32:30Z acceptance and verification against native originals. Public approval/proposal/config and runtime facts are retained; runtime private keys/settings are excluded.

This is only a focused functional result at the exact tested source. Original15, qualified profile, performance/buffering and overall integration remain unaccepted. New code requires its own validation and applicable concrete approval before execution.

# OPS-013 implementation verification

- Reservation sourcecae Task15/713 andCI831713 passed; accepted actualmain3eb
  CI832713/1419.98s with no test skips. Raw main proof and independent acceptance
  are in reservation-3eb9bb6-ci832/ and reservation-3eb9bb6-actual-main/.
- Developmentv1:15cases/1failure/3errors, retained in admission-development-v1-failed/.
- Developmentv2:17cases/3failures/3errors, retained in admission-development-v2-failed/.
  These failures exposed fixture construction errors; existing assertions stayed.
- Developmentv3:17cases/56.841s/exit0; original source/log retained in v3-passed/.
  Independent P2 subsequently rejected its immediate import on old fixtures.
- Forward developmentv4:22cases/65.598s/exit0/no skips plus actual unchanged
  old-planner three-checker regression3/9.53s/exit0. Original91-file manifest,
  six core source snapshots and complete logs are in admission-development-v4-passed/.
- Missing-helper independent probe: ordinary/legacy import works, new repair
  gets no permission and contract changes keep a rejection; see P2/content receipts.
- Windows same-manifest22 cases passed/1072.393s/exit0, zero skips; raw originals are in admission-development-v4-windows/.
- Exact committed source Task15/full735/JUnit/latestCI/final review are PENDING.

The positive Foundation and successor histories are isolated Git test fixtures,
not actual completed OPS013 or an OPS014 production registration. The candidate
does not modify specs/poc, quality/timing thresholds or original response bytes.

OPS-009 metadata-only reservation
Status: RESERVED
Verification: PENDING_ACTUAL_SOURCE
Issue: #85
Base: bf0e5cbf51c1f8991986f503e22d1312ac9b5836
Actual reservation branch: chore/OPS-009-planning-revision-reservation
Implementation branch claim: chore/OPS-009-planning-revision-admission
Lease: 2026-10-10T15:29:31Z to 2026-10-17T15:29:31Z

NOT EXECUTED. Before merge close this reservation PR. After merge, if still reserved, stop further activation and retain Registry, Lease and capacity; do not directly become blocked or release the Lease. Only from in_progress/review/integration may a separate own metadata-only blocked PR retain Registry, valid Lease and capacity. Lawful later repair and independent Review/actual Completion remove the Lease. All Lease changes remain subject to existing time limits and gates. No Foundation cancelled path is claimed; preserve original registration/failure evidence and never remove history or completed identities. Any implementation defect later requires stop admission and independently register forward repair under the correct scope; AGENTS17.8 frozen/thaw separation remains mandatory.

# OPS-021 bounded metadata materialization

# OPS-021 prospective implementation notes

Status: prospective implementation design. Registration actual main 0b973f13cd0e26158348b4f052139a25f2967725 is fully accepted by the separately pinned final receipt; this preparation has not written performance code or run tests. No POC experiment or qualification is supplied.

## Bounded change

- Retain the existing OPS-019 metadata path. Consider only audited OPS-020 and own OPS-021 snapshots for the same two metadata-only consumers.
- The read-only inventory covers 16 actual canonical regular-file input shapes. It does not prove arbitrary future inputs. Unknown IDs and unproven shapes retain the existing dense checkout.
- Check the canonical Task/evidence/handoff binding and actual metadata file modes before choosing the added sparse path. Symlink or alternative bindings must not silently lose their targets. Failed or unsupported shape inspection takes the existing path, never a new permission result.
- Preserve all current sparse metadata directories/root inputs, selecting the corresponding own Evidence directory. Keep complete Git objects/history and exact detached HEAD. Do not alter merge/freeze/recovery snapshot reconstruction.
- Preserve current check-task-file execution, Registry linkage, handoff checks, validation cache keys and failure behavior. Set skip-smudge only in the temporary metadata subprocess environment. Source/main real LFS fetch and materialized probe remain separate mandatory checks.

## Meaningful regression coverage

- Use small real Git histories and actual current checkers. Do not clone the full current media/evidence tree per new case.
- Compare cold dense and bounded snapshots for both metadata consumers, including original reserved and later lifecycle states. Assert exact commit/history and absence of unrelated payload materialization only on the bounded path.
- Independently cold cases cover malformed Task metadata, missing/ambiguous Task, invalid Program data, missing own Evidence/handoff and mismatched Registry fields. Assert real refusal and equivalence to the original behavior.
- Do not accidentally compare through a warmed successful VALIDATED_TASK_SNAPSHOTS entry: use fresh module/cache context for each dense/optimized comparison.
- After a success, a different commit or entry must still validate and reject bad data. Failed snapshots must not populate the success cache.
- Cover unchanged OPS-019 behavior, unknown task and unproven-shape dense fallback, failed checkout propagation, caller environment/root refs/status preservation, and the independent hydrated LFS probe.

For the small full `foundation_reservation` fixture, prefer ordinary OPS-021. OPS-020 has its own immutable recovery-intent admission and should not be represented by a fake ordinary reservation. OPS-020 can still have direct historical Task/Registry snapshot comparisons; real OPS-020 authority is independently exercised by retained original91/933 and the fixed historical context comparison. Copy the actual Registry schema and module ownership into a small real-Git fixture, keep its lease historically valid, and preserve real admission checks rather than stubbing them.

## Performance evidence and acceptance

The baseline child profile is instrumented cost only: 74.107 seconds total, with 46.427 seconds in eight checkout calls (inclusive costs are not additive). Preserve its original record. A successor comparison should keep the exact old repository context67bd and its refs/status untouched, run the checker from the separately identified new implementation source, pin the unchanged surrounding checker bytes, and explicitly distinguish checker-source identity from the historical repository being checked. Do not edit the old context or relabel its source as the new implementation. Match instrumentation/environment for any direct timing comparison; local benefit does not prove hosted budget success.

Implementation starts only after normal registration actual-main7/full official CI/final acceptance. Then retain original933 and old91 byte/assertion inventory, add necessary regressions, execute literal gates and require complete official source/main CI. Normal Code/Review/Completion and released capacity precede consuming the optimization in POC recovery. CI970's two cancelled attempts remain cancelled, with no third identical-source retry.

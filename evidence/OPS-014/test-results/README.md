# OPS-014 actual source verification

See ../recovery-validation/source-results.json for all18 real commands, ../recovery-proof.json for the five mandatory bound checks and JUnit, and ../recovery-validation/windows-focused-results.json.base64 for seven Windows regressions. POC selftests are separate from governance collection. Earlier failures remain in prior-attempts; none are relabelled. Archive head/hostedCI/actual-main/thaw acceptance remain pending.

Supporting Windows JSON originals use reversible base64; decode according to ../recovery-validation/archive-index.json. Mandatory proof logs remain raw and byte-identical. Decode the Windows raw log according to the archive index to recover its exact original bytes.

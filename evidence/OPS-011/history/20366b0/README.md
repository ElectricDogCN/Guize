# OPS-011 source 20366b0 failed execution archive

This archive retains the actual stopped fifteen-command execution for source `20366b0546c09a2ec776ab801f8efa2aea45713f`, tree `8bd15dcbdece22744be62e20996f1f53daf41a54`, sole parent `af290fd5b69ff09aff31ca086cbac2ca5c998d71`, audited base `39afaf007d800bab43d7703ac082df2bbc7e8e87`, branch `chore/OPS-011-agent-edge-104-scope`.

The first thirteen commands exited 0. Command 14, `make verify`, naturally exited 2 after the governance suite reported 674 test cases: 667 passed, 7 failed, 0 errors and 0 skipped. Command 15, `docs`, was not started. This execution failed; it supplies no source acceptance, complete-gate acceptance or transferred verdict for a successor source.

| Order | Executed command | Exit code | Original output |
| --- | --- | --- | --- |
| 1 | diff | 0 | [original output](artifacts/n001.txt) |
| 2 | task | 0 | [original output](artifacts/n002.txt) |
| 3 | readiness | 0 | [original output](artifacts/n003.txt) |
| 4 | schemas | 0 | [original output](artifacts/n004.txt) |
| 5 | integrity | 0 | [original output](artifacts/n005.txt) |
| 6 | history | 0 | [original output](artifacts/n006.txt) |
| 7 | transitions | 0 | [original output](artifacts/n007.txt) |
| 8 | finalization | 0 | [original output](artifacts/n008.txt) |
| 9 | raw-lifecycle | 0 | [original output](artifacts/n009.txt) |
| 10 | lifecycle | 0 | [original output](artifacts/n010.txt) |
| 11 | coordination | 0 | [original output](artifacts/n011.txt) |
| 12 | scope | 0 | [original output](artifacts/n012.txt) |
| 13 | evidence | 0 | [original output](artifacts/n013.txt) |
| 14 | verify | 2 | [original output](artifacts/n014.base64.json) |

The original [JUnit](artifacts/n019.base64.json) records these seven failures:

- `tests.governance.test_program_plan_history.TestProgramPlanHistory::test_foundation_accepts_working_nonconflicting_claim`
- `tests.governance.test_program_plan_history.TestProgramPlanHistory::test_foundation_own_renewal_with_main_foreign_registry_conflict`
- `tests.governance.test_program_plan_history.TestProgramPlanHistory::test_foundation_post_disjoint_peer_old_own_lease`
- `tests.governance.test_program_plan_history.TestProgramPlanHistory::test_foundation_postclaim_foreign_disjoint`
- `tests.governance.test_program_plan_history.TestProgramPlanHistory::test_foundation_postclaim_foreign_disjoint_side`
- `tests.governance.test_program_planning_revision::test_manifest_mutation_restoration_cannot_disappear[check-program-plan-transitions.py]`
- `tests.governance.test_program_planning_revision::test_manifest_mutation_restoration_cannot_disappear[check-program-lifecycle-guards.py]`

Five Foundation history positive cases report `Program tasks must belong to exactly their fixed scope`. The two manifest-mutation/restoration endpoint cases report `Original registered planning manifest changed in intermediate history`. Their complete original assertion messages, tracebacks, suite timing and outcomes remain in the JUnit and verify output. This archive records the observed failures and does not claim their repair.

The [entry](artifacts/n015.json) binds actual source/tree/base/argv/process/script and before-execution worktrees. The [command execution records](artifacts/n016.json) retain the fourteen actual commands, process identities, completed waits, timing, raw hashes and sizes. The [status](artifacts/n017.json) contains only those fourteen commands. The [failed-gate snapshots](artifacts/n018.json) record identical before/after source, tree, branch, status and pinned physical files for both the authoring and native verification worktrees, with `unchanged=true` and `requiredCurrentGatesPassed=false`.

The [exact executed entry script](artifacts/n020.py) retains SHA-256 `deb197fc3484fea97495c83989ca5c7fa96fe3bc8eb9b52c12388e8a473439ee`. The external result directory and entry script remain unchanged. No docs output, later success, CI verdict or acceptance record is synthesized.

[artifact-map.json](artifact-map.json) maps each original absolute path/basename to its repository-relative stored artifact, recording original/stored SHA-256, byte count and encoding. Raw storage preserves original bytes. Where trailing whitespace requires lossless storage, `storageEncoding=base64-json` identifies a container whose `dataBase64` decodes to the exact original bytes; both forms have independent pins. Original controller filenames resolve through this map. The boundary is exactly the nineteen direct result files plus this execution's entry script; JSON references and older archives are not traversed or copied.

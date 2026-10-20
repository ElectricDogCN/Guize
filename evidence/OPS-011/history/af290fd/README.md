# OPS-011 source af290fd failed execution archive

This bounded archive preserves the actual stopped execution for source `af290fd5b69ff09aff31ca086cbac2ca5c998d71`, tree `7bbb281010234732e0616d2dd3f2ea1802ae0287`, sole parent and audited base `39afaf007d800bab43d7703ac082df2bbc7e8e87`, branch `chore/OPS-011-agent-edge-104-scope`.

The first eleven commands exited 0. Command 12, the task scope gate, naturally exited 1: its raw output reports 67 OwnEvidence files outside the Task's allow list. This is a failed source execution, with no source acceptance. The later `evidence`, `make verify`, and `docs` commands were not started; no governance suite or JUnit was produced in this execution. Earlier results do not transfer to a successor source.

| Order | Executed command | Exit code | Original output |
| --- | --- | --- | --- |
| 1 | diff | 0 | [raw](artifacts/n001.txt) |
| 2 | task | 0 | [raw](artifacts/n002.txt) |
| 3 | readiness | 0 | [raw](artifacts/n003.txt) |
| 4 | schemas | 0 | [raw](artifacts/n004.txt) |
| 5 | integrity | 0 | [raw](artifacts/n005.txt) |
| 6 | history | 0 | [raw](artifacts/n006.txt) |
| 7 | transitions | 0 | [raw](artifacts/n007.txt) |
| 8 | finalization | 0 | [raw](artifacts/n008.txt) |
| 9 | raw-lifecycle | 0 | [raw](artifacts/n009.txt) |
| 10 | lifecycle | 0 | [raw](artifacts/n010.txt) |
| 11 | coordination | 0 | [raw](artifacts/n011.txt) |
| 12 | scope | 1 | [raw](artifacts/n012.txt) |

The [entry record](artifacts/n013.json) binds the actual source, tree, base, argv, process, script hash, and before-execution worktrees. The [command execution records](artifacts/n014.json) retain each actual command, process, completed wait, timing, raw hash and byte count. The [terminal status](artifacts/n015.json) contains only the twelve commands that actually ran. The [failed-gate worktree record](artifacts/n016.json) records identical before/after source, tree, branch, status and pinned physical files for the authoring and native verification worktrees; `unchanged=true` and `requiredCurrentGatesPassed=false`.

The [exact executed entry script](artifacts/n017.py) retains SHA-256 `2c828b6a39ba1a9355940cab56d2ce732a7cc7cb4df4d2becb3f9d899d875fe2`; the external original script and result directory remain unchanged. No missing logs, JUnit, later command outcomes or acceptance records are synthesized.

[artifact-map.json](artifact-map.json) maps every original absolute path and basename to a repository-relative stored artifact, with original/stored SHA-256 and byte count. Raw artifacts retain their bytes. If original trailing whitespace requires lossless storage, `storageEncoding=base64-json` identifies a JSON container whose `dataBase64` decodes to the original bytes; hashes and sizes bind both forms. Original command records keep their original raw-log names, resolved through this map. Exactly 17 original files are retained; existing archives and their referenced materials are not copied recursively.

# POC-005 caller alignment

Status: PARTIAL

POC-005 caller alignment after actual failed source checks
Base: c0d550555dd51a29fd1c5ff1bc5e4713073c0b53
Branch: chore/POC-005-metadata-scale
Parent Source: 1869091239b51960d53b0840c4965e3f84eb10fd
Current Source: UNASSIGNED (uncommitted candidate)

Four actual callers/tests now match the omitted-empty-password wire shape and strictly reject extra keys. Working Windows131 passed; no new fixed-source or hosted acceptance yet. Parent186 Windows130 and history failures are retained, not recast as success. Frozen checker/schema/13measurements/thresholds and all attempt006 original bytes/method/approvals stay unchanged. No new source request or experiment/qualification approval. Exact inventory: changed-files.md; reversible originals: profiles/local-v1/v1/wire-consumer-alignment-v1/index.json.

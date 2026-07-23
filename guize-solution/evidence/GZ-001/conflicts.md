# Conflicts

## 冲突 1：Evidence 目录结构

- **AGENTS.md 要求**：`evidence/<task-id>/` 应包含 `summary.md`, `commands.txt`, `test-results/` 等
- **本任务要求**：`evidence/GZ-001/` 应包含 `README.md`, `scope.md`, `changed-files.md`, `commands.md`, `test-results.md`, `assumptions.md`, `risks.md`, `rollback.md`, `follow-ups.md`
- **判断**：AGENTS.md 为长期权威规则，但 GZ-001 作为治理初始化任务，其证据结构更细化。`commands.md` 可视为 `commands.txt` 的扩展。
- **处理**：GZ-001 按本任务要求创建证据文件，同时保留 AGENTS.md 的通用指导。未来可通过 ADR 统一两种结构。
- **状态**：已记录，未阻塞

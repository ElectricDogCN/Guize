# Evidence Structure — GZ-001

本目录定义 GZ-001 任务执行期间的证据文件结构。

## 权威结构

根据 ADR-0012 和 AGENTS.md 的协调，本任务的证据结构为：

```
evidence/GZ-001/
├── README.md           # 证据摘要（对应 AGENTS.md 的 summary.md）
├── scope.md            # 任务范围
├── changed-files.md    # 变更文件清单
├── commands.md         # 执行命令记录（对应 AGENTS.md 的 commands.txt）
├── test-results.md     # 测试结果
├── assumptions.md      # 假设和依赖
├── conflicts.md        # 冲突记录
├── repository-boundary.md  # 仓库边界分析
├── risks.md            # 风险识别
├── rollback.md         # 回滚步骤
└── follow-ups.md       # 后续任务
```

## 与 AGENTS.md 的兼容性

| AGENTS.md 要求 | GZ-001 实现 | 说明 |
|----------------|-------------|------|
| `summary.md` | `README.md` | README.md 包含摘要内容 |
| `commands.txt` | `commands.md` | Markdown 格式表格，更结构化 |
| `test-results/` | `test-results.md` | 表格形式记录测试结果 |
| `rollback-verification/` | `rollback.md` | 回滚步骤 |

## 权威来源

- **唯一权威**：`specs/tasks/GZ-001-repository-baseline.md`
- **工具适配**：`.trae/specs/GZ-001-repository-baseline/` 是 Trae 工具的生成物，不作为权威来源

## 历史修订

- GZ-001 (2026-07-23): 初始创建
- GZ-001-R1 (2026-07-23): 修复仓库边界，增加 repository-boundary.md
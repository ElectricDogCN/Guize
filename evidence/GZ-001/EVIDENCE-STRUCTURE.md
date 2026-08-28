# Evidence Structure — GZ-001

本目录定义 GZ-001 任务执行期间的证据文件结构，并显式声明与 `AGENTS.md` 规范 Evidence Contract 的兼容关系。

## 权威结构

GZ-001 创建时间早于当前 `AGENTS.md` 的规范目录命名，因此保留历史文件名，不复制或伪造不存在的执行产物。规范要求通过本文件进行显式映射；后续新任务优先直接使用规范路径。

```text
evidence/GZ-001/
├── README.md                    # 证据摘要
├── scope.md                     # 任务范围
├── changed-files.md             # 变更文件清单
├── commands.md                  # 执行命令记录
├── test-results.md              # 测试与门禁结果
├── assumptions.md               # 假设和依赖
├── conflicts.md                 # 冲突记录
├── repository-boundary.md       # 仓库边界分析
├── repository-root-migration.md # 仓库根迁移记录
├── risks.md                     # 风险识别
├── rollback.md                  # 回滚与验证步骤
└── follow-ups.md                # 后续任务
```

## 与 AGENTS.md 的兼容性

| AGENTS.md 规范路径 | GZ-001 兼容引用 | 说明 |
|---|---|---|
| `summary.md` | `README.md` | GZ-001 摘要入口；历史命名保留。 |
| `commands.txt` | `commands.md` | Markdown 结构化记录真实命令和退出码。 |
| `test-results/` | `test-results.md` | GZ-001 为治理任务，以单文件记录测试、静态检查和门禁结果。 |
| `screenshots/` | N/A | GZ-001 无 UI/视觉验收，不产生截图证据。 |
| `api-samples/` | N/A | GZ-001 不实现业务 API，不产生 API 请求/响应样例。 |
| `migration-report/` | `repository-root-migration.md` | 本任务迁移对象是仓库根目录而非数据库，迁移过程单独记录。 |
| `performance/` | N/A | GZ-001 为治理与文档基线任务，无性能验收范围。 |
| `security/` | `test-results.md` | Secret scan 与安全相关治理检查记录在测试结果中。 |
| `rollback-verification/` | `rollback.md` | 包含可执行回滚路径和验证说明；未伪造未执行的破坏性回滚。 |

`N/A` 不是跳过证据的通配符，只允许用于任务明确不适用的证据类别，并必须在本表说明原因。

## 校验规则

`check-evidence.py` 必须：

1. 优先检查 `AGENTS.md` 规范路径；
2. 规范路径不存在时，只接受本文件显式声明的兼容引用；
3. 兼容引用指向文件/目录时，目标必须真实存在且非空；
4. `N/A` 必须提供原因；
5. 不得因历史命名差异静默放宽 Evidence Contract。

## 权威来源

- **任务权威**：`specs/tasks/GZ-001-repository-baseline.md`
- **工程治理权威**：`AGENTS.md`、`rules/never-rules.md`
- **工具适配**：`.trae/specs/GZ-001-repository-baseline/` 是 Trae 工具生成/适配内容，不作为任务权威来源。

## 历史修订

- GZ-001 (2026-07-23)：初始创建。
- GZ-001-R1 (2026-07-23)：修复仓库边界，增加 `repository-boundary.md`。
- GZ-001 clean recovery (2026-08-29)：补齐 `AGENTS.md` 规范 Evidence Contract 的全部兼容映射，并由 checker 强制验证。

# Test Results — GZ-001

| 检查项 | 命令 | 退出码 | 结果 | 备注 |
|--------|------|--------|------|------|
| 任务文件校验 | python scripts/check-task-file.py --task GZ-001 | 0 | 通过 | 包含所有必需字段 |
| 修改范围校验 | python scripts/check-task-scope.py --task GZ-001 --base main | 0 | 通过 | 无越界文件 |
| Evidence 校验 | python scripts/check-evidence.py --task GZ-001 | 0 | 通过 | 初始为空文件已修复 |
| PR-任务关联 | python scripts/check-pr-task-link.py --branch chore/GZ-001-repository-baseline | 0 | 通过 | 分支与任务一致 |
| 规范同步检查 | python scripts/check-spec-sync.py --base main | 0 | 通过 | 无同步问题 |
| 治理脚本单元测试 | python -m pytest tests/governance/ -v | 0 | 通过 | 11/11 通过 |
| Prompt 生成 | make agent-prompt TASK=GZ-001 | 0 | 通过 | 生成 .agent/GZ-001-prompt.md |
| 任务综合校验 | make task-verify TASK=GZ-001 | 0 | 通过 | 全部子检查通过 |
| 全面基线校验 | make verify | 0 | 通过 | docs-check, schema-check, secret-scan, governance-test, task-verify 均通过 |
| Markdown 链接检查 | (docs-check 子步骤) | 0 | 通过 | 无断链 |
| Schema 检查 | (schema-check 子步骤) | 0 | 通过 | contracts/ 下 JSON/YAML 有效 |
| Secret 扫描 | (secret-scan 子步骤) | 0 | 通过 | 未发现常见 Secret 模式 |

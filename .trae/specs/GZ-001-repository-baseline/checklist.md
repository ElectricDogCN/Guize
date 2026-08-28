# GZ-001-R2 Checklist

## 原始 GZ-001 验收项

- [x] 已建立正式 GZ-001 任务规范
- [x] 已建立通用动态 Prompt 模板
- [x] 已建立 `render-agent-prompt.py`
- [x] 已建立任务文件检查
- [x] 已建立修改范围检查
- [x] 已建立 Evidence 检查
- [x] 已建立 PR 与任务关联检查
- [x] 已建立规范同步检查
- [x] 已建立治理脚本测试
- [x] 已建立统一 Makefile 命令
- [x] `make agent-prompt TASK=GZ-001` 能生成 Prompt
- [x] `make task-verify TASK=GZ-001` 可执行
- [x] `make verify` 可执行
- [x] GitHub Issue 模板完整
- [x] PR 模板完整
- [x] 治理 CI 文件语法有效
- [x] 没有真实 Secret
- [x] 没有业务功能越界实现
- [x] Evidence 内容完整且来自真实执行
- [x] 新增长期决策已通过 ADR 记录
- [x] 未验证内容被明确标记
- [x] 回滚步骤明确
- [x] 没有自动推送、合并或部署

## GZ-001-R1 新增验收项

- [x] 仓库边界分析文档已创建
- [x] 测试正确位于 guize-solution/tests/governance/
- [x] fixtures.py 路径正确
- [x] CI 工作流使用 working-directory: guize-solution
- [x] Makefile 测试路径为 tests/governance/
- [x] 新增 11 个仓库边界回归测试
- [x] 测试总数从 11 增加到 22
- [x] Evidence 结构说明文档已创建
- [x] 回滚策略已更新为分级安全方案
- [x] 修订报告已创建（final-report-r1.md）

## GZ-001-R2 新增验收项

- [x] Git 状态和仓库边界已重新确认
- [x] 所有 GZ-001 文件都处于当前 Git 仓库
- [x] PyYAML 等关键治理依赖被明确安装（requirements-governance.txt）
- [x] YAML 校验不再因缺少依赖而跳过
- [x] GitHub Actions 路径和工作目录正确
- [x] GitHub Actions 不依赖仓库外文件
- [x] GitHub Actions 没有吞掉关键失败
- [x] 新增 CI 工作流静态回归测试（12 项）
- [x] 治理测试全部通过（33/33）
- [x] `make task-verify TASK=GZ-001` 通过
- [x] `make verify` 通过
- [x] 干净检出模拟通过（临时目录中 make verify 通过）
- [x] 提交结构可审查（3 个提交）
- [x] PR 草稿内容完整
- [x] 已生成远程人工操作命令
- [x] 未实际 Push、创建 PR、合并或部署
- [x] GitHub Actions 被明确标记为待真实 PR 验证
- [x] Evidence 和 R2 报告完整
- [x] 未开始下一任务

# GZ-001 Project Bootstrap — 归档

> **状态**：已归档，仅作历史参考  
> **任务 ID**：GZ-001  
> **原始任务**：`specs/tasks/GZ-001-repository-baseline.md`

---

本文件标记 GZ-001 的初始工程化任务。GZ-001 的目标是将归泽・Guize 方案文档仓库转化为具备以下能力的正式工程仓库：

- 可机器读取的任务规范格式
- 动态 Prompt 模板体系与生成器
- 治理检查脚本（任务文件、范围、证据、PR 关联、规范同步）
- 治理脚本单元测试
- 统一 Makefile 治理入口
- 基础仓库配置与 GitHub 模板
- 首个治理 CI 工作流
- 证据框架与 ADR 记录

GZ-001 的原始引导 Prompt 已沉淀为 `prompts/templates/task-execution.md` 及配套模板体系。后续任务应基于模板体系生成执行 Prompt，不再直接引用本归档内容。

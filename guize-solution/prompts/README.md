# Prompts 目录

本目录存放归泽・Guize 项目的动态 Prompt 模板与历史归档。

## 目录结构

```
prompts/
├── README.md              # 本说明
├── archive/               # 历史 Prompt 归档（只读参考）
│   └── GZ-001-project-bootstrap.md
└── templates/             # 可复用的动态模板
    ├── task-execution.md
    ├── task-fix-ci.md
    ├── task-review.md
    ├── poc-execution.md
    └── release-verification.md
```

## 目录说明

### `archive/`

存放已经执行完毕、仅作追溯参考的历史 Prompt。归档内容不应再被脚本直接渲染为执行指令，但可供人工查阅理解任务起源。

归档文件命名规范：`{TASK_ID}-{short-description}.md`

### `templates/`

存放可复用的动态模板。模板使用 `{{VARIABLE}}` 占位符语法，由渲染脚本（如 `scripts/render-agent-prompt.py`）在运行时注入实际值。

模板命名规范：`{purpose}-{context}.md`

## 变量替换约定

所有模板统一使用双大括号占位符：

```text
{{TASK_ID}}
{{TASK_FILE}}
{{ISSUE_REFERENCE}}
{{BRANCH_NAME}}
{{BASE_BRANCH}}
{{EXECUTION_MODE}}
```

- 占位符名使用全大写蛇形命名（`UPPER_SNAKE_CASE`）。
- 渲染脚本负责从任务规范文件（`specs/tasks/{TASK_ID}.md`）中提取元数据并填充变量。
- 若某个变量在模板中存在但在当前上下文中无值，保留占位符原文，不静默替换为空字符串。
- 模板本身**不**复制被引用文档的完整内容，只保留指向权威文件的路径引用，由执行 Agent 自行读取。

## 使用方式

通过 Makefile 或渲染脚本生成最终 Prompt：

```bash
make agent-prompt TASK=GZ-001
# 或
python scripts/render-agent-prompt.py \
  --task GZ-001 \
  --branch chore/GZ-001-repository-baseline \
  --base main \
  --mode implement \
  --issue GZ-001 \
  --output .agent/GZ-001-prompt.md
```

生成的 Prompt 写入 `.agent/` 目录，供 Agent 执行时加载。

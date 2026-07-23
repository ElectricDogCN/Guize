# GZ-001-R1 Repository Boundary Analysis

## 1. Git 仓库边界确认

### 执行命令与结果

```bash
# 从 /workspace 执行
git rev-parse --is-inside-work-tree: true
git rev-parse --show-toplevel: /workspace

# 从 /workspace/guize-solution 执行
git rev-parse --is-inside-work-tree: true
git rev-parse --show-toplevel: /workspace

# Git 追踪的测试文件
git ls-files | grep 'tests/':
  guize-solution/tests/__init__.py
  guize-solution/tests/governance/__init__.py
  guize-solution/tests/governance/fixtures.py
  guize-solution/tests/governance/test_check_evidence.py
  guize-solution/tests/governance/test_check_pr_task_link.py
  guize-solution/tests/governance/test_check_spec_sync.py
  guize-solution/tests/governance/test_check_task_file.py
  guize-solution/tests/governance/test_check_task_scope.py
  guize-solution/tests/governance/test_render_agent_prompt.py
```

## 2. 结论

| 问题 | 答案 |
|------|------|
| `/workspace` 是否为 Git 仓库 | **是**，是唯一的 Git 仓库根目录 |
| `/workspace/guize-solution` 是否为独立 Git 仓库 | **否**，是 `/workspace` 仓库的子目录 |
| 两者是否为嵌套仓库 | **否**，只有一个仓库，`guize-solution/` 只是子目录 |
| `/workspace/tests/governance/` 当前由哪个仓库追踪 | **不存在于 Git 中**，已被清理 |
| GitHub Actions 实际会检出哪个仓库 | 会检出 `/workspace` 仓库，当前仓库名称需要从远程确认 |
| 单独克隆当前治理仓库后，是否能获得治理测试 | **是**，测试文件位于 `guize-solution/tests/governance/`，随仓库克隆 |

## 3. 仓库结构

```
/workspace/                    # Git 仓库根
├── .git/                      # Git 目录
├── README.md
├── guize-solution-v1.zip
└── guize-solution/            # 治理仓库内容（子目录）
    ├── AGENTS.md
    ├── Makefile
    ├── scripts/               # 治理脚本
    ├── tests/governance/      # 治理测试（Git 追踪）
    ├── evidence/GZ-001/       # 证据
    ├── prompts/               # Prompt 模板
    ├── specs/tasks/           # 任务规范
    └── ...
```

## 4. 发现的问题

### 4.1 测试路径历史问题

在 GZ-001 初始执行过程中，测试曾短暂移动到 `/workspace/tests/governance/`，但这是错误的，因为：

1. `/workspace/tests/` 不在 Git 追踪中
2. 治理仓库的测试应该位于治理仓库内部
3. 该路径已恢复，测试现在正确位于 `guize-solution/tests/governance/`

### 4.2 Makefile 和 CI 路径问题

之前的修复引用了 `../tests/governance`，这是错误的：
- 当前 Git 仓库根是 `/workspace`
- 从 `guize-solution/` 目录看，`../tests/governance` 指向 `/workspace/tests/governance`（不存在）
- 正确的路径应该是 `tests/governance`（从仓库根）或 `guize-solution/tests/governance`（从仓库根）

### 4.3 fixtures.py 路径问题

`fixtures.py` 中的 `SCRIPTS_DIR` 使用相对路径：
```python
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
```

当测试位于 `guize-solution/tests/governance/fixtures.py` 时：
- `__file__` → `/workspace/guize-solution/tests/governance/fixtures.py`
- `..` → `/workspace/guize-solution/tests/`
- `..` → `/workspace/guize-solution/`
- `scripts` → `/workspace/guize-solution/scripts/` ✓ 正确

## 5. 修复方案

1. **测试位置**：保持在 `guize-solution/tests/governance/`
2. **Makefile**：使用相对于仓库根的正确路径
3. **CI**：使用相对于检出根的正确路径
4. **fixtures.py**：当前路径计算已正确，无需修改

## 6. 独立仓库验证方案

由于 `/workspace/guize-solution/` 不是独立仓库，GitHub Actions 会检出整个 `/workspace` 仓库。验证方案：

1. 创建临时目录
2. 复制 `/workspace` 内容（排除 `.git`）
3. 在临时目录执行测试
4. 确认测试能正确找到脚本
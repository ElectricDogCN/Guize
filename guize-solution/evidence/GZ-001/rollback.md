# Rollback

## 方法 1：丢弃分支（推荐）

```bash
git checkout main
git branch -D chore/GZ-001-repository-baseline
```

## 方法 2：从基础提交重置

```bash
git checkout chore/GZ-001-repository-baseline
git reset --hard 0860ca2
```

> 注意：`0860ca2` 是当前 `main` 的最新提交。如果 `main` 已更新，请使用对应的基础提交哈希。

## 方法 3：手动删除新增文件

如果已有其他提交在此分支上：

```bash
# 删除新增目录
rm -rf prompts/ scripts/ tests/governance/ .agent/ evidence/GZ-001/

# 删除新增文件
rm -f Makefile .editorconfig .gitattributes .gitignore
rm -f .github/workflows/governance-gate.yml
rm -f .github/pull_request_template.md
rm -f .github/ISSUE_TEMPLATE/agent-task.yml
rm -f .github/ISSUE_TEMPLATE/poc.yml
rm -f .github/ISSUE_TEMPLATE/bug.yml
rm -f .github/ISSUE_TEMPLATE/feature.yml
rm -f .github/ISSUE_TEMPLATE/architecture-decision.yml
rm -f .github/ISSUE_TEMPLATE/security.yml
rm -f adr/0012-adopt-repository-native-agent-task-harness.md
rm -f specs/tasks/GZ-001-repository-baseline.md

# 恢复可能修改的文件
git checkout -- .github/ISSUE_TEMPLATE/feature.md
git checkout -- .github/workflows/README.md
```

以上方法均不会影响用户未提交的修改（前提是这些修改不在被删除的文件中）。

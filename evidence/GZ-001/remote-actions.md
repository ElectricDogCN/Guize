# Remote Actions — GZ-001-R2

## 远程仓库状态

```bash
$ git remote -v
origin  https://github.com/ElectricDogCN/Guize (fetch)
origin  https://github.com/ElectricDogCN/Guize (push)
```

远程仓库已配置。

## 人工推送命令（未执行）

```bash
# 确认当前分支
git branch --show-current
# 预期输出：chore/GZ-001-repository-baseline

# 推送分支到远程（未执行）
git push -u origin chore/GZ-001-repository-baseline
```

## Draft PR 创建命令（未执行）

使用 GitHub CLI：

```bash
gh pr create \
  --draft \
  --base main \
  --head chore/GZ-001-repository-baseline \
  --title "GZ-001: establish repository governance and agent execution harness" \
  --body-file guize-solution/evidence/GZ-001/pull-request-draft.md
```

或使用 GitHub Web UI：

1. 访问 https://github.com/ElectricDogCN/Guize
2. 点击 "Compare & pull request"
3. 选择 base: main, compare: chore/GZ-001-repository-baseline
4. 勾选 "Create draft pull request"
5. 复制 PR 草稿内容

## 未执行声明

本任务 **未执行** 以下任何操作：

- [ ] `git push`
- [ ] `gh pr create`
- [ ] `gh pr merge`
- [ ] 远程分支删除
- [ ] GitHub Settings 修改

以上命令仅作为人工操作参考生成。

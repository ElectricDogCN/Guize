# GZ-001-R4 无效报告记录

## 状态

> **状态：INVALID / RETRACTED**
>
> 本报告中引用的六个提交未存在于任何可访问的本地或远程 Git
> 对象库，相关验证无法复现，因此不得作为验收、合并或发布依据。
> 详见 `r4-evidence-integrity-incident.md`。

## 声称的提交

```text
3276a1e
07ba43d
d792dde
9c1a072
3deb022
a7962df
```

## 无效原因

- 这些提交不存在于任何本地分支
- 不存在于任何远程分支
- 不存在于当前 Git 对象库
- 当前本地 `fix/GZ-001-R4-ci` 实际指向 `cc34293`，与 `origin/main` 相同
- PR #4 远程 Head 仍为 `f13660a`
- R4 修改并未落盘、提交或推送

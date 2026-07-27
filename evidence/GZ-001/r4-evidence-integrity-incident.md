# GZ-001 R4 证据完整性事故报告

## 报告声称的提交

```text
3276a1e
07ba43d
d792dde
9c1a072
3deb022
a7962df
```

## 验证结果

对每个 SHA 执行 `git cat-file -e <sha>^{commit}`：
- 全部返回 "Not a valid object name"
- 本地分支、远程分支、Git 对象库中均不存在

## 实际本地分支

```text
fix/GZ-001-R4-ci -> cc34293 (与 origin/main 相同)
```

## 实际远程 PR Head

```text
f13660ac79e3edff502093e0af0d453838f27cc8
```

## 结论

原 R4 报告属于 INVALID / UNVERIFIED。所有声称的提交均为虚构。

## 根因分析

1. 报告生成时未执行实际的 `git commit`
2. 未验证提交是否存在
3. 用自然语言总结代替了 Git 对象和命令证据

## 影响

- 虚假完成证据可能导致错误的合并决策
- 浪费审查时间
- 损害治理流程可信度

## 恢复措施

1. 标记原报告无效
2. 从真实远程 PR Head 重新开始
3. 实际修改文件、创建提交、验证存在性
4. 生成可信 Evidence

## 预防措施

1. 新增 `scripts/check-evidence-integrity.py` 自动检查
2. 新增 Never Rule 66 禁止报告不存在的提交
3. 最终报告前必须执行验证命令

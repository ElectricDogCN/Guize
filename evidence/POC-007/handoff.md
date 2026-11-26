# POC-007 登记交接

## 登记身份

[Issue #315](https://github.com/ElectricDogCN/Guize/issues/315) 的登记基线为 `4c83731f60449abd1749cb2be1568c195f42f443`，登记分支为 `chore/POC-007-local-range-reservation`，工作分支为 `chore/POC-007-local-range`。集成顺序为 3。

协调人 `program-coordinator-agent`，实现人 `task-owner-agent`，审核人 `independent-review-agent`，集成人 `integration-agent`。登记租约从 `2026-11-26T14:30:06Z` 至 `2026-12-03T14:30:06Z`。

## 输入与范围

- 使用 GZ-010 的 `POC-PROTOCOL-V1` 和 [POC-007 规格](../../specs/poc/plans/POC-007.yaml)。
- 固定 `RES-LOCAL-ACCESS-PATH`、`RES-OPENLIST-LOCAL`、`SAMPLE-RANGE-LARGEFILE` 及证书、工具版本与批准的阈值。
- 本地测试以真实服务和合成数据验证正常播放入口，记录 TLS、Range、授权边界、限流、流式传输及环境清理。生产网络验收沿用原规格。
- 共享 ADR 与结果索引依 `poc-results` 集成顺序更新，当前变更见 [登记清单](changed-files.md)。

## 验证与交接

[登记命令](commands.txt) 的退出状态由提交和 PR 绑定。集成人在完整官方源检查和审核通过后合并并复验实际主线。工作分支从已验主线开始，固定实验环境与样本，保存测量、原始结果与回收记录。

候选合入前可撤回。合入后依据正常生命周期取消自身登记，保留审查与证据记录。

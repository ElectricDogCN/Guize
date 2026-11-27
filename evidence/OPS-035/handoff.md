# OPS-035

## 任务身份

- OPS-035 对应 Issue #352，工作分支 chore/OPS-035-poc-dependency-admission，基线 cb51148e41e8b420a5c58fb928d5bc84bdacb89c。
- ElectricDogCN 负责。协调、实现、集成为 /root，独立审查为 /root/independent_review。
- 租约从 2026-11-27T17:20:00Z 到 2026-12-04T17:20:00Z，集成组 poc-source-dependency-admission，顺序 27，使用普通合并。前置为 OPS-027。
- 固定源 SHA 从引入不可变意图的单一提交读取，使用 `git log -1 --format=%H -- evidence/OPS-035/source-dependency-admission-intent.json`。固定本地受测 SHA 是后继证据提交的可取回祖先。审查和集成另核实际 PR HEAD 与完整官方源 CI，核对后继提交仅记录同一组登记检查。

## 实际范围与验证

- [实际写入路径](changed-files.md)列出 19 项。无共享写入范围。四条后续治理声明和五条已保护合同路径在登记候选逐字节保持。
- 本任务消费 Program Plan v1、Task Spec v2、Active Work v1。登记无消费契约或公共产品接口版本变动。
- 复跑入口见 [命令和退出码](commands.txt)。官方 CI 及独立终验在固定源上执行后由 PR 和实际主线记录。证据集中于本目录。
- 基线已知限制为 POC-003 和 POC-005 的两项源码资格拒绝，#280 保留实际容器诊断。登记阶段不执行专用测量。

## 下一职责与回滚

- Reviewer 核对基线、源、四条声明和两个既有 POC 租约，检查原始意图、准确字节和完整官方源检查。
- Integrator 按同头独审结果普通合入，复验实际主线，再允许实施四条治理范围。后继作独立登记、冻结和修复。
- 未合入候选可撤回。已合入按正常独立审查前向修订。原始批准、原件与同行租约保持可追溯。

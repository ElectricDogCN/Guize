# OPS-036

当前为 OPS-036 登记，Issue #357，分支 `chore/OPS-036-poc-source-qualification`，基线 `f132bb93ac03ba39af9b991e9f147e9075031e05`。使用 `git rev-parse HEAD` 核对固定源。

租约 2026-11-27T20:46:43Z 至 2026-12-04T20:46:43Z。集成组 `poc-source-dependency-admission`，顺序 28。使用 Program Plan v1、Task Spec v2、Active Work v1。/root 负责协调、实现与集成，/root/independent_review 独立审查。

本次只改 [19 条登记路径](changed-files.md)。两条后继范围及五个保护对象在 [登记上下文](reservation-context.json) 中固定，测试入口见 [命令](commands.txt)。

先执行固定源完整官方 1,105 项并独立终审，再普通合入和执行完整实际主线终验。登记实际受验后另行办理正式冻结，实际修订验证和受审解冻各自留证。

共享写入范围为空。预提交任务检查已通过。原校验器在实际旧上下文中仍拒绝两项 POC，登记阶段没有获得修订后的资格。未合入登记可撤回，实际合入后按普通前向修订处理。

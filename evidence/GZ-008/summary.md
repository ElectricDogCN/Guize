# GZ-008 登记

承接已验收的需求、OpenAPI、事件与数据库契约，冻结 Workflow、Policy、Worker 和 Plugin 运行时契约。核心和各插件依据明确版本对接，分别验证与交付。

登记 PR #320 的实际合并主线 `593ad7ee` 完整通过 1,090 项官方测试和六项适用本地控制，独立终验接受。首批实施绑定十个 Workflow 类型与三类 Activity，并提供有限重试、截止时间、心跳、取消的可执行配置校验。合成用例的 Windows 与 WSL 结果一致，实际运行验收继续由后续集成执行。[登记主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45869097662) · [验证结果](test-results/README.md)

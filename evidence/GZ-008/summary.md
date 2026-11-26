# GZ-008 运行时契约

承接已验收的需求、OpenAPI、事件与数据库契约，冻结 Workflow、Policy、Worker 和 Plugin 运行时契约。核心和各插件依据明确版本对接，分别验证与交付。

登记 PR #320 的实际合并主线 `593ad7ee` 完整通过 1,090 项官方测试和六项适用本地控制，独立终验接受。首批实施绑定十个 Workflow 类型与三类 Activity，并提供有限重试、截止时间、心跳、取消的可执行配置校验。合成用例的 Windows 与 WSL 结果一致，实际运行验收继续由后续集成执行。[登记主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45869097662) · [验证结果](test-results/README.md)

本次实施固定规范化重放、确定性策略建议、独立的节点与执行租约、能力包制品锁及版本兼容。TASK 保有状态写入、执行尝试和条件接受权。合成样例覆盖 P0 建议、已锁定 AV1 能力包与指定尝试领取，并验证插件缺席与上报故障时核心仍可启动的契约结论。[验证结果](test-results/README.md)

## 正式审查

实施 PR #321 已普通合入 `904a2f680fa50ad60b113e99af16181ee8844565`。实际主线树与受审预览一致，七项本地检查、完整官方 1,090 项与独立终验通过。本轮办理 GZ-008 正式审查。[实施 PR #321](https://github.com/ElectricDogCN/Guize/pull/321) · [实际主线 CI #1177](https://github.com/ElectricDogCN/Guize/actions/runs/45883231537)

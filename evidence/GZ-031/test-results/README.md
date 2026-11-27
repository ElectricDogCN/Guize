# GZ-031 验证记录

- [实施构建及启动](implementation-cc26ec1e.json)记录固定源码、真实控制面健康检查、子进程失败隔离、SDK 兼容性和摘要失配。
- [瞬时失败和探测预算](plugin-probe-39cbcc07.json)记录固定产品源码、旧实现失败对照、800 毫秒 Windows 回归及 22 秒专用 Linux 容器验证。
- [登记阶段本地验证](reservation-controls-80d6d4ca.json)保留当时的原命令与结果。
- [实施实际主线](../implementation-main-79879e47/acceptance.json)记录官方覆盖和独立结论。[独立验收原件](../implementation-main-79879e47/independent-review.original.json)可逐字节核对。[八项控制命令及摘要](../implementation-main-79879e47/native-controls.json)可复跑。

## 正常结项

正式 Review [PR #350](https://github.com/ElectricDogCN/Guize/pull/350) 已合入实际主线 `8f439a287ac192bca1049f6b826e18f676e202a6`。正式结项保留 [实施 PR #348](https://github.com/ElectricDogCN/Guize/pull/348) 及实际实施合并 `79879e47cda6361bdfcfe6edf40ce9a37c5defbb`。独立实际终验、完整官方 1,101 项及八项本地主线门禁通过。原 1,078 项完整保留。[实际 Review CI](https://github.com/ElectricDogCN/Guize/actions/runs/46031536751) [实际主线命令](../accepted-review-main-8f439a28/native-controls.json)

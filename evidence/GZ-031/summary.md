# GZ-031 控制面与 Worker 启动

任务路径按 [#345](https://github.com/ElectricDogCN/Guize/issues/345) 实现，并使用已验收的 GZ-008 契约。配置为空时，控制面可以独立构建、启动并通过健康检查。使用三个真实合成子进程后，普通媒体插件保留两项能力，退出和迟到的插件处于不可用状态，核心继续就绪。关闭后迟到的就绪事件不会启动探测。

Worker 使用固定 SDK 执行 40 项实际协议向量，拒绝修改后的包。[测试证据](test-results/implementation-cc26ec1e.json)对应固定提交 `cc26ec1e687352f84dcaf2a5854c924008b45dff`。[登记最终验收](https://github.com/ElectricDogCN/Guize/actions/runs/45999354149)

针对启动审查的两项缺陷，固定提交 `39cbcc07bcee541b151f689c16bd3625b2b40d28` 在共享期限内重试瞬时失败，子进程预算覆盖完整探测期限。Windows 800 毫秒回归和专用 Linux 22 秒对照复用了同一 JAR。媒体插件两次收到 503 后恢复声明能力，退出及迟到的插件持续不可用，核心健康为 UP。[缺陷对照及复验](test-results/plugin-probe-39cbcc07.json)

实施 [PR #348](https://github.com/ElectricDogCN/Guize/pull/348) 普通合入实际主线 `79879e47cda6361bdfcfe6edf40ce9a37c5defbb`。实际有序双父和文件树与固定预览一致。官方实际主线完整通过 1,101 项，原 1,078 项均保留。八项 Windows 原生控制和同头独立终验通过。[官方 CI #1219](https://github.com/ElectricDogCN/Guize/actions/runs/46025398065) [实际主线记录](implementation-main-79879e47/acceptance.json)

## 正常完成

Status: PASS

正式 Review [PR #350](https://github.com/ElectricDogCN/Guize/pull/350) 已合入实际主线 `8f439a287ac192bca1049f6b826e18f676e202a6`。正式结项保留 [实施 PR #348](https://github.com/ElectricDogCN/Guize/pull/348) 及实际实施合并 `79879e47cda6361bdfcfe6edf40ce9a37c5defbb`。独立实际终验、完整官方 1,101 项及八项本地主线门禁通过。原 1,078 项完整保留。[实际 Review CI](https://github.com/ElectricDogCN/Guize/actions/runs/46031536751) [独立原件](accepted-review-main-8f439a28/independent-review.original.json)

# GZ-031 控制面与 Worker 启动

任务路径按 [#345](https://github.com/ElectricDogCN/Guize/issues/345) 实现，并使用已验收的 GZ-008 契约。配置为空时，控制面可以独立构建、启动并通过健康检查。使用三个真实合成子进程后，普通媒体插件保留两项能力，退出和迟到的插件处于不可用状态，核心继续就绪。关闭后迟到的就绪事件不会启动探测。

Worker 使用固定 SDK 执行 40 项实际协议向量，拒绝修改后的包。[测试证据](test-results/implementation-cc26ec1e.json)对应固定提交 `cc26ec1e687352f84dcaf2a5854c924008b45dff`。[登记最终验收](https://github.com/ElectricDogCN/Guize/actions/runs/45999354149)

针对启动审查的两项缺陷，固定提交 `39cbcc07bcee541b151f689c16bd3625b2b40d28` 在共享期限内重试瞬时失败，子进程预算覆盖完整探测期限。Windows 800 毫秒回归和专用 Linux 22 秒对照复用了同一 JAR。媒体插件两次收到 503 后恢复声明能力，退出及迟到的插件持续不可用，核心健康为 UP。[缺陷对照及复验](test-results/plugin-probe-39cbcc07.json)

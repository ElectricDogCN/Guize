# GZ-031 正式 Review 交接

当前阶段为 `review`，审查分支为 `chore/GZ-031-bootstrap-v1`，正式 Review 基线为实际主线 `79879e47cda6361bdfcfe6edf40ce9a37c5defbb`。实施 PR #348 的受验源码为 `88e0a92c2b7b3990cf1ede58ef89584c52590696`，合入树为 `ee17e924e80e69d2c37dadf5a52112ad6e5e106b`。协调人、实施人与集成人为 `/root`，独立审查人为 `/root/independent_review`。租约截至 2026-12-04T11:46:01Z，W5 集成顺序为 3，共享路径为空。[任务 #345](https://github.com/ElectricDogCN/Guize/issues/345) · [分支实际变更文件](changed-files.md#正常-review-路径)

实际主线八项原生控制的可复跑命令、退出码 0 和日志摘要已归档。官方 #1219 五个作业通过，1,101 项包含原 1,078 项。独立实际终验原件可直接核对。[原生命令及结果](implementation-main-79879e47/native-controls.json) · [独立验收原件](implementation-main-79879e47/independent-review.original.json) · [实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/46025398065)

审查者接手时读取 PR 的当前头和基线，核对 [正式 Review 命令](../../specs/tasks/GZ-031.md#必须执行的测试)、同头完整官方结果和所有审查意见。集成人核对同头独立结论后普通合入并复验实际主线，取得接受后才办理结项和释放租约。Review 合入前可按任务流程撤回候选，合入后通过正常前向修订处理。生产依赖维护在 #340，22 秒回归的范围为专用容器内的合成回环进程。

## 输入和交付

- 依赖 GZ-008 固定的 `guize.plugin/v1`、`worker-v1` 和 Worker SDK 1.0.0。控制面按 [ADR-0002](../../adr/0002-modular-monolith-control-plane.md) 使用 Java 17 与 Spring Boot 3。
- 产品文件位于 `backend/guize-bootstrap/`、`services/guize-worker-agent/bootstrap/` 和自身 Evidence。[实际变更路径](changed-files.md)
- W5 集成顺序为 3，共享写入范围为空。[实际登记验收](https://github.com/ElectricDogCN/Guize/actions/runs/45999354149)
- 实施分支起于 `421db3f3c6ce34c4f2bea87413cfd5b0e6360999`。激活提交为 `366f87c03d0d2f59e6405c5156cec0785d02027a`，首次受测产品提交为 `cc26ec1e687352f84dcaf2a5854c924008b45dff`。

## 实际运行

[实施验证记录](test-results/implementation-cc26ec1e.json)保存每项执行命令、结果、制品及日志摘要。Maven clean package、JAR 与三个实际合成进程的回环验证、Worker 固定 SDK 启动和篡改回归均退出 0。首轮工具缓存缺少实际测试所需的 Surefire 提供者。补入 Maven 官方依赖后对固定源码的离线构建已经通过。

目前插件探测使用本机回环和可信发布清单。插件进程与制品均为合成夹具。独立审查定位的关闭竞态已修复，关闭后迟到的就绪事件不能启动探测线程，受控并发回归已通过。Worker 源码和消费契约与已实际验证的前一提交逐字节一致，沿用原回执。生产依赖维护决策单独跟踪于 [#340](https://github.com/ElectricDogCN/Guize/issues/340)。

固定产品源码的独立技术复评已关闭关停竞态，回执 SHA-256 `bd5273fbc72c39ed8a9cd79a231ac7f157d10e5877afb85f5cb56c6b62125756`。

实施 PR 的两项后续发现分别涉及启动重试及进程总预算。修复固定在 `39cbcc07bcee541b151f689c16bd3625b2b40d28`。两个旧实现对照均按预期失败。新实现的 Maven 两项检查通过，同一 JAR 通过 Windows 800 毫秒回归和专用 Linux 容器 22 秒对照。后者一次执行并归档结果，覆盖合法探测期限超过旧预算的情况。已验证的 Worker 字节与两条冻结消费契约未变更。[对照记录](test-results/plugin-probe-39cbcc07.json)
